# gex_btc_v9 - alerte d'ARRIVEE sur un mur GEX BTC (Deribit public)
import json, math, re, sys, time, urllib.request, subprocess
from datetime import datetime, timezone, timedelta
B="https://www.deribit.com/api/v2/public/"
def get(p):
    with urllib.request.urlopen(B+p, timeout=30) as r: return json.load(r)["result"]
S=get("get_index_price?index_name=btc_usd")["index_price"]
book=get("get_book_summary_by_currency?currency=BTC&kind=option")
end=int(time.time()*1000)
cd=get(f"get_tradingview_chart_data?instrument_name=BTC-PERPETUAL&resolution=60&start_timestamp={end-8*86400*1000}&end_timestamp={end}")
cl=cd["close"]; tk=cd["ticks"]; ref6=cl[-7]; chg7=(cl[-1]/cl[-169]-1)*100 if len(cl)>=169 else None
ARG=sys.argv[1:]
for a in ARG:
    if a.startswith("--prix="): S=float(a.split("=")[1])
MON={m:i+1 for i,m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
now=datetime.now(timezone.utc)
try:
    from zoneinfo import ZoneInfo; TZ=ZoneInfo("Europe/Paris"); hp=datetime.now(TZ)
except Exception: TZ=timezone(timedelta(hours=1)); hp=now+timedelta(hours=1)
def parse(n):
    _,d,k,t=n.split("-"); m=re.match(r"(\d+)([A-Z]{3})(\d+)",d)
    return datetime(2000+int(m[3]),MON[m[2]],int(m[1]),8,tzinfo=timezone.utc),float(k),t,d
def gamma(S,K,T,iv):
    if T<=0 or iv<=0: return 0.0
    d1=(math.log(S/K)+0.5*iv*iv*T)/(iv*math.sqrt(T)); return math.exp(-d1*d1/2)/math.sqrt(2*math.pi)/(S*iv*math.sqrt(T))
ex={}
for b in book:
    e,K,t,d=parse(b["instrument_name"]); days=(e-now).total_seconds()/86400
    if days<=0: continue
    ex.setdefault(d,dict(days=days,opt=[]))["opt"].append((K,t,b.get("open_interest") or 0,(b.get("mark_iv") or 0)/100))
C={};P={}
for x in ex.values():
    if x["days"]>7: continue
    for K,t,oi,iv in x["opt"]:
        g=gamma(S,K,x["days"]/365,iv)*oi*S*S*0.01/1e6; dd=C if t=="C" else P; dd[K]=dd.get(K,0)+g
CH_tot=0.0; CH_loc=0.0; VAN=0.0; CHK={}
for x in ex.values():
    if x["days"]>7 or x["days"]<0.04: continue
    T=x["days"]/365
    for K,t,oi,iv in x["opt"]:
        if oi<=0 or iv<=0: continue
        sg=1 if t=="C" else -1
        d1=(math.log(S/K)+0.5*iv*iv*T)/(iv*math.sqrt(T)); d2=d1-iv*math.sqrt(T); ph=math.exp(-d1*d1/2)/math.sqrt(2*math.pi)
        flow=-sg*oi*(ph*d2/(2*T)/365)
        CH_tot+=flow; CHK[K]=CHK.get(K,0)+flow
        if abs(K/S-1)<=0.03: CH_loc+=flow
        VAN+=-sg*oi*(-ph*d2/iv)*0.01
MG=max(set(C)|set(P),key=lambda k:C.get(k,0)+P.get(k,0))
tc5=sorted(C,key=lambda k:-C[k])[:5]; tp5=sorted(P,key=lambda k:-P[k])[:5]; tc=tc5[:3]; tp=tp5[:3]; net=sum(C.values())-sum(P.values())
walls=sorted(set(tc)|set(tp),reverse=True)
fm=lambda v:f"{v:,.0f}".replace(","," ")
typ=lambda W:"CALL+PUT" if (W in tc and W in tp) else ("PUT" if W in tp else "CALL")
ico={"PUT":"🟢","CALL":"🔴","CALL+PUT":"🟡"}
ev=[]
for W in walls:
    ec=(S/W-1)*100
    if abs(ec)<=1: ev.append((abs(ec),"ARRIVEE",W,ec))
    elif ref6>W and S<W*0.99: ev.append((abs(ec),"TRAVERSE_BAS",W,ec))
    elif ref6<W and S>W*1.01: ev.append((abs(ec),"TRAVERSE_HAUT",W,ec))
ev.sort(); alerte=bool(ev)
nouvelle=False
if ev:
    _,etat,W,ec=ev[0]
    if etat=="ARRIVEE": nouvelle=all(abs(c/W-1)>0.01 for c in cl[-3:-1])
    elif etat=="TRAVERSE_BAS": nouvelle=cl[-2]>=W*0.99
    else: nouvelle=cl[-2]<=W*1.01
if "--force" in ARG: nouvelle=True
rapport=(hp.hour in (8,20)) or ("--rapport" in ARG)
objW=None
if ev:
    _,etat,W,ec=ev[0]; ty=typ(W)
    if etat=="ARRIVEE":
        head=f"{ico[ty]} ARRIVEE SUR MUR {ty} {fm(W)}"+("  (signal contradictoire)" if ty=="CALL+PUT" else "")
        if ty=="PUT": opp=[c for c in tc5 if c>W*1.01]; obj=(f"mur CALL {fm(min(opp))} = {(min(opp)/S-1)*100:+.1f} %" if opp else "aucun mur CALL au-dessus"); objW=(min(opp) if opp else None)
        elif ty=="CALL": opp=[p for p in tp5 if p<W*0.99]; obj=(f"mur PUT {fm(max(opp))} = {(max(opp)/S-1)*100:+.1f} %" if opp else "aucun mur PUT en dessous"); objW=(max(opp) if opp else None)
        else: obj="mur a la fois CALL et PUT : pas de sens clair"
    else:
        head=f"🟠 MUR {ty} {fm(W)} TRAVERSE "+("vers le BAS" if etat=="TRAVERSE_BAS" else "vers le HAUT"); obj="mur franchi : on ne se bat pas contre"
else:
    head="⚪ RAS : aucun mur a 1 % ou moins"; obj=None; ty=None; etat=None; W=None
conf=None; conf_ok=None
if ev and etat=="ARRIVEE" and ty in ("PUT","CALL"):
    reg_ok=net>0; want=1 if ty=="PUT" else -1; flux_ok=(CH_loc*want>0); conf_ok=bool(reg_ok and flux_ok)
    conf=f"Γ régime {'POSITIF ✓' if reg_ok else 'NÉGATIF ✗'} · Charm {'acheteur' if CH_loc>0 else 'vendeur'} {'✓' if flux_ok else '✗'} → {'CONFIRMÉ' if conf_ok else 'NON CONFIRMÉ'}"
L=[head,f"BTC {fm(S)} $  ·  {hp:%d/%m %H:%M} (Paris)",""]
rows=[(w,f"{ico[typ(w)]} {fm(w)}  mur {typ(w)}") for w in walls]; placed=False
for w,txt in rows:
    if not placed and w<S: L.append(f"➡️ {fm(S)}  ◀ PRIX"); placed=True
    L.append(txt+("   ◀" if ev and ev[0][2]==w else ""))
if not placed: L.append(f"➡️ {fm(S)}  ◀ PRIX")
L.append("")
if obj: L.append("Objectif : "+obj)
tend="↘" if (chg7 is not None and chg7<-3) else ("↗" if (chg7 is not None and chg7>3) else "→")
L.append(f"Marché : {tend} {chg7:+.1f} % sur 7 j  ·  gamma {'NEGATIF (murs freinent peu)' if net<0 else 'POSITIF'}")
if conf: L.append("Confirmation : "+conf.replace('Γ','Gamma'))
L.append("Règle de position, non validée sur le BTC.")
carte="\n".join(L)
suite=None
def netg(Sp,md=7):
    t_=0
    for x in ex.values():
        if x["days"]>md: continue
        for K,t,oi,iv in x["opt"]:
            g=gamma(Sp,K,x["days"]/365,iv)*oi*Sp*Sp*0.01/1e6; t_+= g if t=="C" else -g
    return t_
zg=None; grid=[S*(1+i/100) for i in range(-25,26)]; vals=[(g,netg(g)) for g in grid]
for (a,fa),(b2,fb) in zip(vals,vals[1:]):
    if fa*fb<0: zg=round(a+(b2-a)*(-fa)/(fb-fa)); break
zg0=None; vals0=[(g,netg(g,1)) for g in grid]
for (a,fa),(b2,fb) in zip(vals0,vals0[1:]):
    if fa*fb<0: zg0=round(a+(b2-a)*(-fa)/(fb-fa)); break
D=[]; MPL=[]
for d,x in sorted(ex.items(),key=lambda kv:kv[1]["days"]):
    oc=sum(o[2] for o in x["opt"] if o[1]=="C"); op=sum(o[2] for o in x["opt"] if o[1]=="P")
    if oc<=0 or op<=0: continue
    ks=sorted({o[0] for o in x["opt"]}); pain=lambda X: sum(oi*max(0,X-K) if t=="C" else oi*max(0,K-X) for K,t,oi,iv in x["opt"])
    mp=min(ks,key=pain); atm=min(x["opt"],key=lambda o:abs(o[0]-S)); em=S*atm[3]*math.sqrt(x["days"]/365)
    MPL.append((mp,d))
    D.append(f"{d} : max pain {fm(mp)} · P/C {op/oc:.2f} · mouvement attendu ±{em/S*100:.1f} %")
    if len(D)==3: break
details="\n".join(D)
csv=";".join(str(v) for v in [now.strftime("%Y-%m-%d %H:%M"),round(S),(ev[0][1] if ev else "RAS"),(ev[0][2] if ev else ""),(round(ev[0][3],2) if ev else ""),round(net,1),(round(chg7,1) if chg7 is not None else ""),("NOUVELLE" if nouvelle else "SUITE"),("CONF" if conf_ok else ("NONCONF" if conf is not None else ""))])
png=None
if (alerte and nouvelle) or rapport:
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt, matplotlib.dates as md
        from matplotlib.patches import FancyBboxPatch
        BG="#14161c"; CARD="#1c1f27"; INK="#e6edf3"; MUTED="#8b949e"; GRID="#2a2e38"
        COL={"PUT":"#3fb950","CALL":"#f85149","CALL+PUT":"#d29922","X":"#db6d28","RAS":"#6e7681"}
        if etat=="ARRIVEE": key=ty; titre=f"ARRIVÉE SUR MUR {ty} {fm(W)}"
        elif etat: key="X"; titre=f"MUR {ty} {fm(W)} TRAVERSÉ "+("VERS LE BAS" if etat=="TRAVERSE_BAS" else "VERS LE HAUT")
        else: key="RAS"; titre="RAS · aucun mur à 1 % ou moins"
        sous={"PUT":"Mur PUT atteint","CALL":"Mur CALL atteint",
              "CALL+PUT":"Mur à la fois CALL et PUT : signal contradictoire","X":"Mur franchi : on ne se bat pas contre","RAS":"Prix entre les murs"}[key]
        if rapport and etat is None: sous="Rapport du matin/soir"
        if etat=="ARRIVEE" and conf_ok is not None: sous=("Signal confirmé : à toi de juger" if conf_ok else "Pas de signal confirmé : on ne fait rien")
        if hp.weekday()==3 and hp.hour==20 or hp.weekday()==4 and hp.hour==8: sous="AVANT EXPIRATION (vendredi 9h) · rotation principale de la semaine"
        fig=plt.figure(figsize=(9,13),dpi=100,facecolor=BG)
        fig.text(0.06,0.955,f"BTC  {fm(S)} $",color=INK,fontsize=30,fontweight="bold",va="center")
        fig.text(0.94,0.955,f"{hp:%d/%m %H:%M} (Paris)",color=MUTED,fontsize=13,ha="right",va="center")
        ba=fig.add_axes([0.05,0.855,0.90,0.07]); ba.axis("off"); ba.set_xlim(0,1); ba.set_ylim(0,0.1124)
        ba.add_patch(FancyBboxPatch((0,0),1,0.1124,boxstyle="round,pad=0,rounding_size=0.04",fc=COL[key],ec="none"))
        ba.text(0.5,0.0562,titre,color="white",fontsize=22,fontweight="bold",ha="center",va="center")
        fig.text(0.5,0.835,sous,color=MUTED,fontsize=12,ha="center",va="center")
        ax=fig.add_axes([0.06,0.27,0.74,0.53],facecolor=CARD)
        n=min(len(cl),169); xs=[datetime.fromtimestamp(t/1000,TZ) for t in tk[-n:]]; ys=cl[-n:]
        ww=list(walls)+([objW] if objW else []); lo=min(min(ys),min(ww),S)*0.992; hi=max(max(ys),max(ww),S)*1.008
        ax.set_ylim(lo,hi); ax.set_xlim(xs[0],xs[-1]+timedelta(hours=14))
        ax.grid(axis="y",color=GRID,lw=0.6); ax.set_axisbelow(True)
        for s_ in ax.spines.values(): s_.set_visible(False)
        ax.tick_params(colors=MUTED,labelsize=10,length=0)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,p:fm(v)))
        jours=["lun","mar","mer","jeu","ven","sam","dim"]
        d0=xs[0].replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1); tt=[]
        while d0<=xs[-1]: tt.append(d0); d0+=timedelta(days=1)
        ax.set_xticks(tt); ax.set_xticklabels([f"{jours[t.weekday()]} {t.day}" for t in tt])
        if etat:
            ax.axhspan(W*0.99,W*1.01,color=COL[key],alpha=0.13,lw=0)
        for w in walls:
            k=typ(w); c=COL[k]
            ax.axhline(w,color=c,lw=1.0,alpha=0.6,ls=(0,(6,4)),zorder=1)
            g=(f"call {C.get(w,0):.1f} / put {P.get(w,0):.1f} M$")
            ax.text(xs[-1]+timedelta(hours=3),w,f"MUR {k}  {fm(w)}"+(" ★" if w==MG else ""),color=c,fontsize=10.5,fontweight="bold",va="bottom",ha="left",clip_on=False)
            ax.text(xs[-1]+timedelta(hours=3),w,g,color=MUTED,fontsize=8.5,va="top",ha="left",clip_on=False)
        MAG="#f778ba"
        if MG not in walls and lo<=MG<=hi:
            ax.axhline(MG,color=MAG,lw=1.8,ls=(0,(2,2)))
            ax.text(xs[-1]+timedelta(hours=3),MG,f"MAX GAMMA ★  {fm(MG)}",color=INK,fontsize=10,fontweight="bold",va="bottom",ha="left",clip_on=False)
            ax.text(xs[-1]+timedelta(hours=3),MG,f"call {C.get(MG,0):.1f} / put {P.get(MG,0):.1f} M$",color=MUTED,fontsize=8.5,va="top",ha="left",clip_on=False)
        VIO="#a371f7"; CYA="#39c5cf"
        def dd_(d):
            m=re.match(r"(\d+)([A-Z]{3})",d); return f"{int(m[1])}/{MON[m[2]]:02d}"
        for i,(mp,d) in enumerate(MPL[:3]):
            if lo<=mp<=hi:
                ax.axhline(mp,color=VIO,lw=1.6,ls=(0,(5,3)),alpha=0.9)
                ax.text(xs[0]+timedelta(hours=6),mp,f"MAX PAIN {fm(mp)} · exp. {dd_(d)}",color=INK,fontsize=9.5,va="bottom",ha="left",bbox=dict(boxstyle="round,pad=0.15",fc=CARD,ec="none",alpha=0.85))
        if zg:
            if lo<=zg<=hi:
                ax.axhline(zg,color=CYA,lw=1.6,ls=(0,(1,2,5,2)))
                ax.text(xs[0]+timedelta(hours=6),zg,f"ZERO GAMMA {fm(zg)}",color=INK,fontsize=9.5,va="bottom",ha="left",bbox=dict(boxstyle="round,pad=0.15",fc=CARD,ec="none",alpha=0.85))
            else:
                ax.text(0.985,0.985,f"▲ ZERO GAMMA {fm(zg)} ({(zg/S-1)*100:+.0f} %)",color=CYA,fontsize=10.5,fontweight="bold",va="top",ha="right",transform=ax.transAxes)
        if zg0:
            if lo<=zg0<=hi:
                ax.axhline(zg0,color=CYA,lw=1.2,ls=(0,(1,3)))
                ax.text(xs[0]+timedelta(hours=84),zg0,f"FLIP 0DTE {fm(zg0)}",color=INK,fontsize=9.5,va="bottom",ha="left",bbox=dict(boxstyle="round,pad=0.15",fc=CARD,ec="none",alpha=0.85))
            else:
                ax.text(0.985,0.94,f"{'▲' if zg0>S else '▼'} FLIP 0DTE {fm(zg0)} ({(zg0/S-1)*100:+.0f} %)",color=CYA,fontsize=10,va="top",ha="right",transform=ax.transAxes)
        from matplotlib.lines import Line2D
        leg=[Line2D([0],[0],color=COL["PUT"],lw=3,label="mur PUT"),Line2D([0],[0],color=COL["CALL"],lw=3,label="mur CALL"),
             Line2D([0],[0],color=VIO,lw=2,ls=(0,(5,3)),label="max pain"),Line2D([0],[0],color=CYA,lw=2,ls=(0,(1,2,5,2)),label="zero gamma"),Line2D([0],[0],color=MAG,marker="*",ls="",ms=11,label="max gamma")]
        ax.legend(handles=leg,loc="upper center",bbox_to_anchor=(0.5,-0.075),ncol=5,frameon=False,labelcolor=MUTED,fontsize=10,handlelength=2.4)
        if objW and objW not in walls:
            k2=("PUT" if ty=="CALL" else "CALL"); ax.axhline(objW,color=COL[k2],lw=1.6,ls=(0,(6,3)),alpha=0.95)
            ax.text(xs[-1]+timedelta(hours=3),objW,f"OBJECTIF · MUR {k2} {fm(objW)}",color=INK,fontsize=10,fontweight="bold",va="bottom",ha="left",clip_on=False)
            ax.text(xs[-1]+timedelta(hours=3),objW,f"call {C.get(objW,0):.1f} / put {P.get(objW,0):.1f} M$",color=MUTED,fontsize=8.5,va="top",ha="left",clip_on=False)
        ax.plot(xs,ys,color="#58a6ff",lw=1.8,solid_capstyle="round")
        ax.axhline(S,color=INK,lw=0.9,ls=(0,(1,3)))
        try:
            _cw={"PUT":"#3fb950","CALL":"#f85149","CALL+PUT":"#d29922"}; _hist=[]
            for W_ in walls:
                for i_ in range(6,len(ys)):
                    arr=abs(ys[i_]/W_-1)<=0.01 and all(abs(ys[j_]/W_-1)>0.01 for j_ in (i_-1,i_-2))
                    tb=ys[i_]<W_*0.99 and ys[i_-1]>=W_*0.99 and ys[i_-6]>W_
                    th=ys[i_]>W_*1.01 and ys[i_-1]<=W_*1.01 and ys[i_-6]<W_
                    if arr or tb or th: _hist.append((i_,W_,"A" if arr else "T"))
            _hist.sort()
            _m=[]
            for h_ in _hist:
                if _m and _m[-1][1]==h_[1] and _m[-1][2]==h_[2] and h_[0]-_m[-1][0]<=6: continue
                _m.append(h_)
            _hist=_m
            _JS=["lun","mar","mer","jeu","ven","sam","dim"]
            _HL=[]
            for n_,(i_,W_,k_) in enumerate(_hist,1):
                ax.plot([xs[i_]],[ys[i_]],"o",color=_cw[typ(W_)],ms=13,mec="white",mew=1.3,zorder=8)
                ax.text(xs[i_],ys[i_],str(n_),color="white",fontsize=7.5,fontweight="bold",ha="center",va="center",zorder=9)
                _HL.append((n_,f"{_JS[xs[i_].weekday()]} {xs[i_].day}/{xs[i_].month} {xs[i_]:%Hh} · {'arrivée sur' if k_=='A' else 'traversé'} mur {typ(W_)} {fm(W_)}",_cw[typ(W_)]))
            fig.text(0.5,0.185,f"{len(_hist)} alertes cette semaine (liste numérotée sous le dessin) · recalculé avec les murs d'aujourd'hui",color=MUTED,fontsize=9.5,ha="center",va="center")
        except Exception: pass
        try:
            _E=[]
            _gen={"Fed : décision":("20:00","2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09","#a371f7"),
                  "CPI (inflation US)":("14:30","2026-10-14 2026-11-10 2026-12-10","#39c5cf"),
                  "Emploi US":("14:30","2026-10-02 2026-11-06","#ffa657")}
            for nm_,(hh_,ds_,co_) in _gen.items():
                for d_ in ds_.split(): _E.append((datetime.fromisoformat(d_+"T"+hh_+":00").replace(tzinfo=TZ),nm_,co_))
            for d_,nm_,co_ in (("2026-11-17T14:30","Ventes au détail US (oct.)","#ffa657"),("2026-11-18T20:00","Fed : procès-verbal","#a371f7"),("2026-11-19T14:30","Chômage hebdo US","#ffa657")):
                _E.append((datetime.fromisoformat(d_+":00").replace(tzinfo=TZ),nm_,co_))
            _E=sorted(e for e in _E if xs[0]<=e[0]<=xs[-1]+timedelta(hours=14))
            _yl=ax.get_ylim()
            for d_,nm_,co_ in _E:
                ax.axvline(d_,color=co_,lw=1.4,ls=(0,(5,3)),alpha=0.9,zorder=3)
                ax.text(d_,_yl[0]+(_yl[1]-_yl[0])*0.02,f" {_JS[d_.weekday()]} {d_:%Hh%M} · {nm_}",color=co_,fontsize=7.5,fontweight="bold",rotation=90,va="bottom",ha="right",zorder=11)
            _txt=("Annonces éco : "+"  ·  ".join(f"{_JS[d_.weekday()]} {d_.day}/{d_.month} {d_:%Hh%M} {nm_}" for d_,nm_,co_ in _E)) if _E else "Annonces éco : aucune cette semaine (Fed / CPI / emploi)"
            fig.text(0.5,0.150,_txt[:130],color=INK,fontsize=9.5,fontweight="bold",ha="center",va="center")
        except Exception: pass
        ax.plot([xs[-1]],[ys[-1]],"o",color=INK,ms=8,mec=CARD,mew=2)
        ax.text(xs[0]+timedelta(hours=3),S,f" prix {fm(S)} ",color=BG,fontsize=10.5,fontweight="bold",va="center",bbox=dict(boxstyle="round,pad=0.25",fc=INK,ec="none"))
        y0=0.155
        if obj: fig.text(0.06,y0,"Objectif",color=MUTED,fontsize=12,va="center"); fig.text(0.20,y0,obj,color=INK,fontsize=14,fontweight="bold",va="center")
        fig.text(0.06,y0-0.045,"Marché",color=MUTED,fontsize=12,va="center")
        fig.text(0.20,y0-0.045,f"{tend} {chg7:+.1f} % sur 7 j  ·  gamma {'NÉGATIF (les murs freinent peu)' if net<0 else 'POSITIF'}",color=INK,fontsize=14,fontweight="bold",va="center")
        if conf: fig.text(0.06,y0-0.08,"Confirmation",color=MUTED,fontsize=12,va="center"); fig.text(0.20,y0-0.08,conf,color=INK,fontsize=13,fontweight="bold",va="center")
        fig.text(0.5,0.025,"Règle de position, non validée sur le BTC · signe call/put = convention · données Deribit",color=MUTED,fontsize=10,ha="center",va="center")
        png="/tmp/alerte_btc.png"; fig.savefig(png,facecolor=BG); plt.close(fig)
        try:
            if _HL:
                from PIL import Image
                h2=0.34*((len(_HL)+1)//2)+0.9
                f2=plt.figure(figsize=(9,h2),dpi=100,facecolor=BG)
                f2.text(0.06,1-0.45/h2,f"Alertes de la semaine (recalculées avec les murs d'aujourd'hui)",color=INK,fontsize=13,fontweight="bold",va="center")
                half=(len(_HL)+1)//2
                for idx,(n_,tx,co_) in enumerate(_HL):
                    col=idx//half; row=idx%half
                    x0=0.06+col*0.47; yy=1-(0.95+row*0.34)/h2
                    f2.text(x0,yy,str(n_),color="white",fontsize=9,fontweight="bold",ha="center",va="center",bbox=dict(boxstyle="circle,pad=0.3",fc=co_,ec="none"))
                    f2.text(x0+0.03,yy,tx,color=INK,fontsize=10,va="center")
                f2.savefig("/tmp/_liste.png",facecolor=BG); plt.close(f2)
                A_=Image.open(png).convert("RGB"); B_=Image.open("/tmp/_liste.png").convert("RGB")
                C_=Image.new("RGB",(A_.width,A_.height+B_.height),(21,22,28)); C_.paste(A_,(0,0)); C_.paste(B_,(0,A_.height)); C_.save(png)
        except Exception: pass
    except Exception as e:
        png=None; carte+=f"\n(image indisponible : {type(e).__name__})"
print(json.dumps(dict(heure_paris=hp.hour,jour_paris=hp.weekday(),alerte=alerte,nouvelle=nouvelle,rapport=rapport,png=png,carte=carte,suite=suite,details=details,csv=csv),ensure_ascii=False))
