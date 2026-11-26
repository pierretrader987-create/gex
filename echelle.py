# echelle.py - ECHELLE DU RANGE BTC (zones d'achat / vente), recalculee a chaque lancement. Deribit public.
# Usage : python3 -I echelle.py [--sortie=/chemin/echelle.png]
import json,sys,time,urllib.request,datetime as dt
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,FancyArrowPatch
B="https://www.deribit.com/api/v2/public/"
def get(p):
    with urllib.request.urlopen(B+p,timeout=30) as r: return json.load(r)["result"]
ARG=sys.argv[1:]; SORTIE="/tmp/echelle.png"
for a in ARG:
    if a.startswith("--sortie="): SORTIE=a.split("=",1)[1]
end=int(time.time()*1000)
J=get(f"get_tradingview_chart_data?instrument_name=BTC-PERPETUAL&resolution=1D&start_timestamp={end-1500*86400*1000}&end_timestamp={end}")
T=[dt.datetime.fromtimestamp(t/1000) for t in J["ticks"]]
O,H,L,C=[np.array(J[k])[:-1] for k in("open","high","low","close")]; T=T[:-1]; n=len(C)   # jour en cours exclu
px=float(get("get_index_price?index_name=btc_usd")["index_price"])
fm=lambda v:f"{v:,.0f}".replace(","," ")
# ---- 1) range : on remonte tant que (max/min - 1) <= 50 % (meme logique qu'alerte2)
def open_range(ys,Xw):
    j=len(ys)-1;mx=mn=ys[j];i=j
    while i-1>=0 and max(mx,ys[i-1])/min(mn,ys[i-1])-1<=Xw: i-=1;mx=max(mx,ys[i]);mn=min(mn,ys[i])
    return i,j,mn,mx
i0,_,mnC,mxC=open_range(list(C),0.50)
mnI,mxI=float(L[i0:].min()),float(H[i0:].max())
# ---- 2) pivots (retournement >= 8 % sur les clotures) dans le range
th=.08;P=[];hi=lo=0;dirn=0
for k in range(1,n):
    if C[k]>C[hi]:hi=k
    if C[k]<C[lo]:lo=k
    if dirn>=0 and C[k]<=C[hi]*(1-th):P.append((hi,"H"));dirn=-1;lo=k
    elif dirn<=0 and C[k]>=C[lo]*(1+th):P.append((lo,"B"));dirn=1;hi=k
Hs=[C[p] for p,t in P if t=="H" and p>=i0];Bs=[C[p] for p,t in P if t=="B" and p>=i0]
def bands(v):
    v=np.array(v,float);m=v.mean();return v[v>=m].mean(),m,v[v<=m].mean()
sh,sm,sb=bands(Hs) if len(Hs)>=2 else (mxC,mxC,mxC)
ch,cm,cb=bands(Bs) if len(Bs)>=2 else (mnC,mnC,mnC)
# ---- 3) zones de gravite vivantes (impulsion >= 8 % en 3 j, non cassee a la cloture)
atr=np.array([np.nan]*14+[np.mean([max(H[k]-L[k],abs(H[k]-C[k-1]),abs(L[k]-C[k-1])) for k in range(j-13,j+1)]) for j in range(14,n)])
Z=[];last={"D":-99,"S":-99}
for i in range(20,n-4):
    up=max(C[i+1:i+4])/C[i]-1;dn=1-min(C[i+1:i+4])/C[i]
    if up>=.08 and (max(C[i+1:i+4])-C[i])>=2.5*atr[i] and i-last["D"]>5: Z.append((L[i],max(O[i],C[i]),"D",i));last["D"]=i
    if dn>=.08 and (C[i]-min(C[i+1:i+4]))>=2.5*atr[i] and i-last["S"]>5: Z.append((min(O[i],C[i]),H[i],"S",i));last["S"]=i
def vivante(z):
    lo,hi_,k,i=z
    return not any((k=="D" and C[j]<lo) or (k=="S" and C[j]>hi_) for j in range(i+4,n))
Z=[z for z in Z if vivante(z)]
dem=sorted([z for z in Z if (z[0]+z[1])/2<px],key=lambda z:-(z[0]+z[1])/2)[:2]
off=sorted([z for z in Z if (z[0]+z[1])/2>px],key=lambda z:(z[0]+z[1])/2)[:2]
# ---- 4) centre de gravite de Belkhayate (poly degre 4, 300 bougies) : bande -2 sigma
NC=300;x=np.arange(NC)/NC;y=C[-NC:];f=np.polyval(np.polyfit(x,y,4),x);sg=np.std(y-f);cog2=f[-1]-2*sg
# ---- 5) niveaux de l'echelle
NIV=[]  # (prix, texte, couleur)
RO,VE,BL,GR="#ff8a3d","#3fb950","#2ea8ff","#8b949e"
NIV.append((mxI,f"Haut du range (intraday) {fm(mxI)}",GR))
for z in off[::-1]: NIV.append(((z[0]+z[1])/2,f"Gravité offre {fm(z[0])}–{fm(z[1])} (centre)",RO))
NIV+= [(sm,f"Moyenne des sommets {fm(sm)}",RO),(sb,f"Sommets moyenne basse {fm(sb)}",RO),(ch,f"Creux moyenne haute {fm(ch)}",VE),(cm,f"Moyenne des creux {fm(cm)}",VE),(cb,f"Creux moyenne basse {fm(cb)}",VE),(mnI,f"Bas du range (intraday) {fm(mnI)}",GR)]
NIV.append((cog2,f"COG −2σ (300 j) {fm(cog2)}",BL))
for z in dem: NIV.append(((z[0]+z[1])/2,f"Gravité demande {fm(z[0])}–{fm(z[1])} (centre)",BL))
NIV=sorted(NIV,key=lambda t:-t[0])
# ---- 6) dessin
lo_y=min(v for v,_,_ in NIV)*0.93;hi_y=max(max(v for v,_,_ in NIV),px)*1.06
fig,ax=plt.subplots(figsize=(11,10),dpi=110,facecolor="#14161c");ax.set_facecolor("#14161c");ax.set_xlim(0,10);ax.set_ylim(lo_y,hi_y);ax.axis("off")
ax.add_patch(Rectangle((1.2,sb),3.6,mxI-sb,fc=RO,alpha=.16,ec=RO,lw=1))
ax.add_patch(Rectangle((1.2,mnI),3.6,ch-mnI,fc=VE,alpha=.18,ec=VE,lw=1))
ax.add_patch(Rectangle((1.2,mnI),3.6,mxI-mnI,fc="none",ec=GR,lw=1.2,ls="--"))
ax.text(3,mxI*1.012,"ZONE DE VENTE / PRISE DE PROFIT",color=RO,ha="center",fontsize=10,fontweight="bold")
ax.text(3,mnI*0.985,"ZONE D'ACHAT",color=VE,ha="center",fontsize=10,fontweight="bold",va="top")
# etiquettes sans chevauchement
gap=(hi_y-lo_y)*0.034;ys=[v for v,_,_ in NIV];lab=ys[:]
for k in range(1,len(lab)):
    if lab[k-1]-lab[k]<gap: lab[k]=lab[k-1]-gap
for (v,t,c),yl in zip(NIV,lab):
    ax.plot([4.8,5.05],[v,yl],color=c,lw=1.3);ax.text(5.1,yl,t,color=c,fontsize=9,va="center")
    ax.text(9.95,yl,f"{(v/px-1)*100:+.0f} %",color="#e6edf3",fontsize=9,va="center",ha="right",fontweight="bold")
ax.plot([1.2,4.8],[px,px],color="#fff",lw=2.6);ax.text(1.25,px,f"  PRIX {fm(px)} $",color="#fff",fontsize=11,fontweight="bold",va="bottom")
ax.text(9.95,hi_y*0.995,"écart / prix",color="#8b949e",fontsize=8.5,ha="right",va="top")
hautc=sm if sm>px else mxC;basc=(dem[0][0]+dem[0][1])/2 if dem else mnI
ax.add_patch(FancyArrowPatch((0.6,px),(0.6,hautc),arrowstyle="-|>",mutation_scale=20,color=VE,lw=2));ax.text(0.45,(px+hautc)/2,f"range tient\n{(hautc/px-1)*100:+.0f} %\n(moy. sommets)",color=VE,fontsize=8.5,ha="right",va="center")
ax.add_patch(FancyArrowPatch((0.6,px),(0.6,basc),arrowstyle="-|>",mutation_scale=20,color="#f85149",lw=2));ax.text(0.45,(px+basc)/2,f"cassure\n{(basc/px-1)*100:+.0f} %",color="#f85149",fontsize=8.5,ha="right",va="center")
pos=(px-mnC)/(mxC-mnC)*100
fig.text(.05,.965,"BTC · échelle du range (recalculée à chaque lancement)",color="#e6edf3",fontsize=15,fontweight="bold")
fig.text(.05,.94,f"Range {T[i0].strftime('%d/%m/%Y')} → aujourd'hui : {fm(mnC)} – {fm(mxC)} $ aux clôtures ({(mxC/mnC-1)*100:.0f} % de large) · prix à {pos:.0f} % du range · {len(Hs)} sommets / {len(Bs)} creux",color="#8b949e",fontsize=9)
fig.text(.05,.02,f"Sommets/creux = retournements ≥ 8 % · gravité = zones de déséquilibre non cassées · COG = régression degré 4 · cassure = clôture sous {fm(mnI)} · données Deribit · {dt.datetime.now().strftime('%d/%m %H:%M')}",color="#8b949e",fontsize=8)
fig.savefig(SORTIE,facecolor="#14161c");plt.close(fig)
print(json.dumps(dict(png=SORTIE,prix=round(px),range_cloture=[round(mnC),round(mxC)],range_intraday=[round(mnI),round(mxI)],pos_pct=round(pos),moy_sommets=round(sm),moy_creux=round(cm),cog_m2=round(cog2)),ensure_ascii=False))
