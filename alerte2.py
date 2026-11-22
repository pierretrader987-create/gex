# gex_btc_gm_v1 - ALERTE 2 GRANDS MOUVEMENTS : ranges (6 mois, 1 an) + annonces. Deribit public.
import json,sys,time,re,urllib.request,datetime as dt
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md
from matplotlib.patches import Rectangle,FancyBboxPatch
B="https://www.deribit.com/api/v2/public/"
def get(p):
    with urllib.request.urlopen(B+p,timeout=30) as r: return json.load(r)["result"]
ARG=sys.argv[1:]; JOUR=None; TITRE=None
for a in ARG:
    if a.startswith("--jour="): JOUR=dt.datetime.fromisoformat(a.split("=")[1])
    if a.startswith("--titre="): TITRE=a.split("=",1)[1][:110]
end=int(time.time()*1000)
def fetch(res,days):
    J=get(f"get_tradingview_chart_data?instrument_name=BTC-PERPETUAL&resolution={res}&start_timestamp={end-days*86400*1000}&end_timestamp={end}")
    T=[dt.datetime.fromtimestamp(t/1000) for t in J["ticks"]]
    A=[np.array(J[k]) for k in("open","high","low","close")]
    if JOUR is not None:
        m=[t<=JOUR for t in T]; T=[t for t,k in zip(T,m) if k]; A=[a[np.array(m)] for a in A]
    return T,A
S=get("get_index_price?index_name=btc_usd")["index_price"]
TD,(OD,HD,LD,CD)=(lambda r:(r[0],r[1]))(fetch("1D",1100))
TH,(OH,HH,LH,CH)=(lambda r:(r[0],r[1]))(fetch("60",8))
L={"FED":"2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-08-22 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28 2026-12-09","CPI":"2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11 2026-10-14 2026-11-10 2026-12-10","NFP":"2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16 2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05 2026-07-02 2026-08-07 2026-09-04 2026-10-02 2026-11-06"}
L={k:[dt.datetime.fromisoformat(x) for x in v.split()] for k,v in L.items()}
NOM={"FED":"Fed","CPI":"CPI","NFP":"Emploi"}; COL={"FED":"#a371f7","CPI":"#39c5cf","NFP":"#ffa657"}
def ranges(ys,Xw,minlen):
    out=[];i=0;n=len(ys)
    while i<n-1:
        j=i;mx=mn=ys[i]
        while j+1<n and max(mx,ys[j+1])/min(mn,ys[j+1])-1<=Xw:
            j+=1;mx=max(mx,ys[j]);mn=min(mn,ys[j])
        if j-i+1>=minlen and j+1<n: out.append((i,j,mn,mx,"up" if ys[j+1]>mx else "down",j+1));i=j+1
        else: i=i+1 if j==i else j
    return out
def open_range(ys,Xw,minlen):
    n=len(ys);j=n-1;mx=mn=ys[j];i=j
    while i-1>=0 and max(mx,ys[i-1])/min(mn,ys[i-1])-1<=Xw: i-=1;mx=max(mx,ys[i]);mn=min(mn,ys[i])
    return (i,j,mn,mx) if j-i+1>=minlen else None
ECH=[("6 MOIS",190,0.15,14),("1 AN",372,0.25,30)]
def signal(Cc,Xw,ml):
    """etat a la derniere cloture : SORTIE_BAS / SORTIE_HAUT (sortie ce jour), VENDRE / ACHETER (arrivee haut/bas), None"""
    n=len(Cc)
    for a,b,mn,mx,dr,k in ranges(list(Cc),Xw,ml):
        if k==n-1: return ("SORTIE_HAUT" if dr=="up" else "SORTIE_BAS",None)
    r=open_range(Cc,Xw,ml)
    if r:
        a,b,mn,mx=r; pos=(Cc[-1]-mn)/(mx-mn)
        if pos>=0.9: return ("VENDRE",r)
        if pos<=0.1: return ("ACHETER",r)
        return (None,r)
    return (None,None)
def verdict(Cd):   # Cd = clotures journalieres FERMEES
    sg=[signal(Cd,x,m) for _,_,x,m in [(e[0],e[1],e[2],e[3]) for e in ECH]]
    etats=[s[0] for s in sg if s[0]]
    if not etats: return "ATTENDRE",sg
    kinds=set(("ACHETER" if e=="ACHETER" else "GARDER" if e=="SORTIE_HAUT" else "VENDRE") for e in etats)
    if len(kinds)>1: return "ATTENDRE",sg
    k=kinds.pop(); return k,sg
Cf=CD[:-1]                       # derniere cloture journaliere fermee (08:00 UTC)
Tf=TD[:-1]
V,SG=verdict(Cf); Vh,_=verdict(Cf[:-1])
ETATS=[s[0] for s in SG]
detail=[(s[0] or "") for s in SG]
Vh_sig=[signal(Cf[:-1],x,m)[0] for _,_,x,m in ECH]
nouvelle=(V!="ATTENDRE") and (ETATS!=Vh_sig)
if "--force" in ARG: nouvelle=True
# annonces proches
now=Tf[-1]+dt.timedelta(days=1) if JOUR else dt.datetime.now()
proches=[(abs((d-now).days),NOM[k],d) for k,v in L.items() for d in v if abs((d-now).days)<=2]
derniere=max(((d,NOM[k]) for k,v in L.items() for d in v if d<=now),default=None)
prochaine=min(((d,NOM[k]) for k,v in L.items() for d in v if d>now),default=None)
fm=lambda v:f"{v:,.0f}".replace(","," ")
# dessin
if nouvelle:
    texte={"ACHETER":"ACHETER (les 3/4)","VENDRE":"VENDRE (les 3/4)","GARDER":"GARDER · sortie ▲","ATTENDRE":"ATTENDRE"}[V]
    if V=="VENDRE" and "SORTIE_BAS" in ETATS: texte="VENDRE · sortie ▼ (racheter plus bas)"
    couleur={"ACHETER":"#3fb950","VENDRE":"#f85149","GARDER":"#3fb950","ATTENDRE":"#6e7681"}[V]
    fig=plt.figure(figsize=(9,16),dpi=100,facecolor="#14161c")
    fig.text(.06,.965,f"BTC  {fm(S)} $",color="#e6edf3",fontsize=28,fontweight="bold",va="center")
    fig.text(.94,.965,now.strftime("%d/%m %H:%M"),color="#8b949e",fontsize=12,ha="right",va="center")
    ba=fig.add_axes([.05,.895,.9,.05]); ba.axis("off"); ba.set_xlim(0,1); ba.set_ylim(0,1)
    ba.add_patch(FancyBboxPatch((0,0),1,1,boxstyle="round,pad=0,rounding_size=0.3",fc=couleur,ec="none")); ba.text(.5,.5,texte,color="white",fontsize=21,fontweight="bold",ha="center",va="center")
    y=.865
    for (nm,_,x,m),s in zip(ECH,SG):
        r=s[1]; t=(f"{nm} : range {fm(r[2])}-{fm(r[3])} ({(r[3]/r[2]-1)*100:.0f} % de large), prix à {(Cf[-1]-r[2])/(r[3]-r[2])*100:.0f} %" if r else f"{nm} : pas de range en ce moment")
        if s[0] in("SORTIE_BAS","SORTIE_HAUT"): t=f"{nm} : sortie du range {'vers le BAS' if s[0]=='SORTIE_BAS' else 'vers le HAUT'}"
        fig.text(.06,y,t,color="#c9d1d9",fontsize=9.5,va="center"); y-=.0175
    if proches: fig.text(.06,y,"Annonce à ±2 jours : "+", ".join(f"{p[1]} {p[2].strftime('%d/%m')}" for p in proches)+" -> prudence, le prix peut bouger fort",color="#ffa657",fontsize=9.5,va="center")
    # 3 echelles
    P=[("1 SEMAINE · bougies 1 h",TH,(OH,HH,LH,CH),None,"h"),("6 MOIS · bougies 1 jour",Tf[-185:],[a[:-1][-185:] for a in (OD,HD,LD,CD)],ECH[0],"d"),("1 AN · bougies 1 jour",Tf[-366:],[a[:-1][-366:] for a in (OD,HD,LD,CD)],ECH[1],"d")]
    for k,(tt,T,(O,H,Lw,C),ec,u) in enumerate(P):
        ax=fig.add_axes([0.07,0.60-k*0.215,0.88,0.17]); ax.set_facecolor("#1c1f27"); w=0.03 if u=="h" else 0.7
        for t,o,h,l,c in zip(T,O,H,Lw,C):
            col="#3fb950" if c>=o else "#f85149"; x=md.date2num(t); ax.plot([x,x],[l,h],color=col,lw=.7); ax.add_patch(Rectangle((x-w/2,min(o,c)),w,max(abs(c-o),h*.0004),color=col,lw=0))
        if ec:
            for a,b,mn,mx,dr,kk in ranges(list(C),ec[2],ec[3]):
                ax.add_patch(Rectangle((md.date2num(T[a]),mn),md.date2num(T[b])-md.date2num(T[a]),mx-mn,fc=(.82,.6,.13,.14),ec="#d29922",ls="--",lw=1))
                ax.scatter(md.date2num(T[kk]),C[kk]*(1.03 if dr=="up" else .97),marker="^" if dr=="up" else "v",s=70,color="#3fb950" if dr=="up" else "#f85149",ec="white",zorder=5)
            orr=open_range(C,ec[2],ec[3])
            if orr: a,b,mn,mx=orr; ax.add_patch(Rectangle((md.date2num(T[a]),mn),md.date2num(T[b])-md.date2num(T[a]),mx-mn,fc=(.82,.6,.13,.22),ec="#f2cc60",lw=1.6))
            for kk,v in L.items():
                for d in v:
                    if T[0]<=d<=T[-1]:
                        j=int(np.argmin([abs((t-d).total_seconds()) for t in T])); ax.scatter(md.date2num(T[j]),H[j]*1.012,s=34,color=COL[kk],ec="white",lw=.5,zorder=6)
        ax.set_title(tt,color="#e6edf3",fontsize=11,loc="left",pad=3)
        ax.tick_params(colors="#8b949e",labelsize=8); [s_.set_visible(False) for s_ in ax.spines.values()]; ax.grid(axis="y",color="#2a2e38",lw=.5)
        ax.xaxis.set_major_formatter(md.DateFormatter("%d/%m" if u=="h" else "%m/%y")); ax.autoscale_view(); lo,hi=ax.get_ylim(); ax.set_ylim(lo,hi*1.01)
    fig.text(.06,.150,"Macro",color="#8b949e",fontsize=11,va="center"); fig.text(.2,.150,(f"prochaine annonce : {prochaine[1]} le {prochaine[0].strftime('%d/%m/%Y')}" if prochaine else "pas de date connue"),color="#e6edf3",fontsize=12,fontweight="bold",va="center")
    fig.text(.06,.122,"Titre",color="#8b949e",fontsize=11,va="center"); fig.text(.2,.122,(("Derniere annonce : "+TITRE) if TITRE else "non trouve"),color="#e6edf3",fontsize=12,va="center")
    fig.text(.06,.085,"Points = annonces : violet Fed · bleu CPI · orange Emploi   |   boite jaune = range   |   fleches = sortie de range",color="#8b949e",fontsize=8.5,va="center")
    fig.text(.5,.045,"Regle, non validee sur le BTC · donnees Deribit · tu decides",color="#8b949e",fontsize=9,ha="center",va="center")
    png="/tmp/alerte2_gm.png"; fig.savefig(png,facecolor="#14161c"); plt.close(fig)
else: png=None
csv=";".join(str(v) for v in [now.strftime("%Y-%m-%d %H:%M"),round(S),V,"/".join(e or "-" for e in ETATS),"NOUVELLE" if nouvelle else "SUITE",(proches[0][1] if proches else "")])
print(json.dumps(dict(verdict=V,etats=ETATS,nouvelle=nouvelle,png=png,csv=csv,derniere=(f"{derniere[1]} du {derniere[0].strftime('%d/%m/%Y')}" if derniere else None)),ensure_ascii=False))
