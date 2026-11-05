#!/usr/bin/env python3
"""Figures for the Doc tab and the .docx. One source: inline SVG with CSS variables."""
import math, json
def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def T(x,y,s,size=13,anchor='start',fill='var(--ink)',w=None,mono=False):
    fam=' font-family="var(--mono)"' if mono else ''
    wt=f' font-weight="{w}"' if w else ''
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" fill="{fill}"{fam}{wt}>{esc(s)}</text>'
def L(x1,y1,x2,y2,c='var(--line)',w=1,dash=None):
    d=f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" stroke-width="{w}"{d}/>'
def R(x,y,w,h,f='none',s='none',sw=1,rx=0):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{f}" stroke="{s}" stroke-width="{sw}" rx="{rx}"/>'
def svg(w,h,body,label): return f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{esc(label)}" style="display:block;height:auto">{body}</svg>'
def nice(a,b,n):
    s=(b-a)/n; m=10**math.floor(math.log10(s)); r=s/m
    st=(1 if r<1.5 else 2 if r<3 else 5 if r<7 else 10)*m
    v=math.ceil(a/st)*st; o=[]
    while v<=b+st*1e-6: o.append(round(v,10)); v+=st
    return o
def chart(w,h,series,xl,yl,xr=None,yr=None,logx=False,label='chart',labels=None):
    m=dict(l=64,r=16,t=12,b=46); iw=w-m['l']-m['r']; ih=h-m['t']-m['b']
    xs=[x for s in series for x in s['x']]; ys=[y for s in series for y in s['y']]
    fx=(lambda v:math.log10(v)) if logx else (lambda v:v)
    x0,x1=xr or (min(xs),max(xs)); y0,y1=yr or (min(ys),max(ys))
    X=lambda v:m['l']+(fx(v)-fx(x0))/(fx(x1)-fx(x0))*iw
    Y=lambda v:m['t']+ih-(v-y0)/(y1-y0)*ih
    b=R(m['l'],m['t'],iw,ih,'var(--face)')
    for v in nice(y0,y1,5):
        b+=L(m['l'],Y(v),m['l']+iw,Y(v),'var(--grid)')+T(m['l']-6,Y(v)+4,f'{v:g}',12,'end','var(--axis)',mono=True)
    xt=[v for v in (12.5,25,50,100,200,400,800) if x0<=v<=x1] if logx else nice(x0,x1,7)
    for v in xt:
        b+=L(X(v),m['t'],X(v),m['t']+ih,'var(--grid)')+T(X(v),m['t']+ih+16,f'{v:g}',12,'middle','var(--axis)',mono=True)
    b+=R(m['l'],m['t'],iw,ih,'none','var(--line)')
    for s in series:
        d=''
        pts=[(a,c) for a,c in zip(s['x'],s['y']) if x0<=a<=x1]
        for i,(a,c) in enumerate(pts): d+=('L' if i else 'M')+f'{X(a):.1f} {Y(max(min(c,y1),y0)):.1f}'
        da=f' stroke-dasharray="{s["dash"]}"' if s.get('dash') else ''
        b+=f'<path d="{d}" fill="none" stroke="var(--{s["c"]})" stroke-width="{s.get("w",2.2)}"{da}/>'
        if s.get('pts'):
            for a,c in pts: b+=f'<circle cx="{X(a):.1f}" cy="{Y(c):.1f}" r="3.5" fill="var(--{s["c"]})"/>'
    b+=T(m['l']+iw/2,h-8,xl,13,'middle','var(--axis)')
    b+=f'<text transform="translate(15 {m["t"]+ih/2}) rotate(-90)" text-anchor="middle" font-size="13" fill="var(--axis)">{esc(yl)}</text>'
    for (x,y,t,c) in (labels or []):
        b+=T(X(x),Y(y),t,12,'start',f'var(--{c})',w=600)
    return svg(w,h,b,label)

def fig_mesh():
    W,H=760,330; x0,x1=70,690; n=6
    z=lambda x:190+(x-x0)/(x1-x0)*44; D=52
    b=''
    # manholes
    for x,top in ((x0,40),(x1,70)):
        b+=R(x-22,top,44,z(x)+22-top,'none','var(--steel)',2)
        b+=T(x,top-8,'manhole cell' ,12,'middle','var(--ink-dim)')
    # pipe
    b+=f'<path d="M{x0+22} {z(x0+22)-D} L{x1-22} {z(x1-22)-D}" stroke="var(--steel)" stroke-width="2.4" fill="none"/>'
    b+=f'<path d="M{x0+22} {z(x0+22)} L{x1-22} {z(x1-22)}" stroke="var(--steel)" stroke-width="2.4" fill="none"/>'
    dx=(x1-x0)/n
    fx=[x0+dx*(i+.5) for i in range(n)]
    lv=[z(x0)-70,z(fx[0]+dx/2)-D-16,z(fx[1]+dx/2)-D+2,z(fx[2]+dx/2)-30,z(fx[3]+dx/2)-26,z(fx[4]+dx/2)-23,z(x1)-20]
    edges=[x0+22]+fx+[x1-22]
    for i in range(n+1):
        a,c=edges[i],edges[i+1]; e=lv[i]
        za,zc=z(a),z(c); ca,cc=za-D,zc-D
        ya=max(e,ca); yc=max(e,cc)
        b+=f'<path d="M{a:.1f} {min(ya,za):.1f} L{c:.1f} {min(yc,zc):.1f} L{c:.1f} {zc:.1f} L{a:.1f} {za:.1f}Z" fill="var(--water)" opacity=".55"/>'
    # manhole water
    b+=R(x0-20,lv[0],40,z(x0)+20-lv[0],'var(--water)',sw=0); b=b.replace('opacity=".55"','opacity=".55"')
    b+=R(x1-20,lv[-1],40,z(x1)+20-lv[-1],'var(--water)',sw=0)
    for x in fx:
        b+=L(x,z(x)-D-14,x,z(x)+14,'var(--s1)',2)
        b+=f'<path d="M{x-11:.1f} {z(x)+24:.1f} h20 m-6 -4 l6 4 l-6 4" stroke="var(--s1)" fill="none" stroke-width="1.6"/>'
    # HGL
    pts=[(x0,lv[0])]+[( (edges[i]+edges[i+1])/2,lv[i]) for i in range(1,n)]+[(x1,lv[-1])]
    b+='<path d="'+''.join(('L' if i else 'M')+f'{x:.1f} {y:.1f}' for i,(x,y) in enumerate(pts))+'" stroke="var(--s3)" stroke-width="2.2" fill="none" stroke-dasharray="7 4"/>'
    b+=T(150,84,'head above the crown: level = crown + P/γ',13,'start','var(--s3)',w=600)
    b+=L(150,90,(edges[1]+edges[2])/2,lv[1]-2,'var(--s3)')
    b+=T(60,316,'piece of the pipe the manhole borrows',12,'start','var(--ink-dim)')
    b+=L(120,304,x0+46,z(x0+46)-6,'var(--ink-dim)')
    b+=T(292,300,'cell: level and volume live here',13,'start','var(--ink)',w=600)
    b+=L(330,288,fx[1]+dx/2,z(fx[1]+dx/2)-8,'var(--ink-dim)')
    b+=T(560,300,'face: flow lives here',13,'start','var(--s1)',w=600)
    b+=L(600,288,fx[4],z(fx[4])+22,'var(--s1)')
    return svg(W,H,b,'Side view of a conduit divided into cells and faces between two manholes, with head above the crown at the upstream end')

def table(D=3.0,L=100.0,S=.005):
    A=lambda y:0 if y<=0 else (math.pi*D*D/4 if y>=D else D*D/8*(2*math.acos(1-2*y/D)-math.sin(2*math.acos(1-2*y/D))))
    n=64; dy=D/n; G=[0.0]
    for i in range(1,n+1): G.append(G[-1]+.5*(A((i-1)*dy)+A(i*dy))*dy)
    def g(y):
        if y<=0: return 0
        if y>=D: return G[n]+A(D)*(y-D)
        i=min(n-1,int(y/dy)); s=y-i*dy; a0,a1=A(i*dy),A((i+1)*dy)
        return G[i]+s*(a0+.5*s*(a1-a0)/dy)
    dz=S*L; zl,zh=-dz/2,dz/2; k=max(32,min(128,math.ceil((dz+D)/(D/32))))
    e=[zl+(dz+D)*m/k for m in range(k+1)]
    v=[(g(x-zl)-g(x-zh))*L/dz for x in e]; v[0]=0
    Ts=[];T1=[];T2=[];up=dn=pr=0
    for i in range(k):
        s=(v[i+1]-v[i])/(e[i+1]-e[i]); d=s-pr
        if d>0: up+=d
        else: dn-=d
        Ts.append(s);T1.append(up);T2.append(dn);pr=s
    return [x-zl for x in e[:-1]],Ts,T1,T2,e,v
def fig_split():
    x,Ts,T1,T2,e,v=table()
    # extend past the crown
    xx=x+[x[-1]+.01,4.0]; 
    t1=T1+[T1[-1]]*2; t2=T2+[T1[-1]]*2; t=Ts+[0,0]
    return chart(760,320,[dict(x=xx,y=t,c='s2',w=3),dict(x=xx,y=t1,c='s3'),dict(x=xx,y=t2,c='s4')],'Water level above the low end of the cell (ft)','Storage derivative dV/dη (ft²)',(0,4),(0,340),label='T, T1 and T2 against level',labels=[(.25,262,'T = T1 − T2','s2'),(1.75,318,'T1, the running sum of the rises','s3'),(1.75,60,'T2, the running sum of the falls','s4')])
def fig_eq():
    W,H=760,250; b=''
    b+=T(380,56,'V(η)   +   Δt θ Σ Q(η)   =   V(old) + Δt q',24,'middle','var(--head)',mono=True)
    b+=L(150,68,120,112,'var(--s2)',1.5)+T(36,130,'table: flat above the crown',13,'start','var(--s2)',w=600)
    b+=L(330,68,330,112,'var(--s1)',1.5)+T(250,130,'all faces, solved at once',13,'start','var(--s1)',w=600)
    b+=L(600,68,610,112,'var(--s3)',1.5)+T(500,130,'what it held, plus inflow',13,'start','var(--s3)',w=600)
    b+=T(380,176,'u (I + Δt c |u|) = F − g Δt/Δx [θ Δη(new) + (1−θ) Δη(old)]',15,'middle','var(--ink)',mono=True)
    b+=T(380,200,'Q = A(upstream) · u',15,'middle','var(--ink)',mono=True)
    b+=T(380,232,'I = 0 and F = 0 is diffusion wave. c is Manning friction per unit velocity.',12,'middle','var(--ink-dim)')
    return svg(W,H,b,'The cell equation with its terms labeled')
def fig_path():
    W,H=760,270
    box=[(14,108,120,62,'SWMM','inflows, controls'),(170,36,130,62,'Faces','area, friction, slope'),(330,36,130,62,'Plain Newton','one sparse factor'),(330,180,130,62,'Nested Newton','symmetric faces'),(490,108,120,62,'Flows, levels','ledger updated'),(636,108,112,62,'SWMM','nodes, links, .out')]
    b=''
    for x,y,w,h,t,s in box:
        b+=R(x,y,w,h,'var(--panel)','var(--panel-line)',1,8)+T(x+w/2,y+25,t,14,'middle','var(--panel-ink)',w=600)+T(x+w/2,y+44,s,11,'middle','var(--ink-dim)')
    def arr(p,c='var(--axis)',dash=None):
        d='M'+' L'.join(f'{x} {y}' for x,y in p)
        (x1,y1),(x2,y2)=p[-2],p[-1]; a=math.atan2(y2-y1,x2-x1)
        h=f'M{x2} {y2} L{x2-9*math.cos(a-.45):.1f} {y2-9*math.sin(a-.45):.1f} M{x2} {y2} L{x2-9*math.cos(a+.45):.1f} {y2-9*math.sin(a+.45):.1f}'
        da=f' stroke-dasharray="{dash}"' if dash else ''
        return f'<path d="{d}" fill="none" stroke="{c}" stroke-width="1.6"{da}/><path d="{h}" fill="none" stroke="{c}" stroke-width="1.6"/>'
    b+=arr([(134,139),(152,139),(152,67),(170,67)])+arr([(300,67),(330,67)])+arr([(395,98),(395,180)],'var(--s4)','5 4')+T(402,144,'if it fails',12,'start','var(--s4)',w=600)
    b+=arr([(460,67),(475,67),(475,139),(490,139)])+arr([(460,211),(475,211),(475,139),(490,139)])+arr([(610,139),(636,139)])
    b+=arr([(550,108),(550,16),(235,16),(235,36)],'var(--s1)')+T(392,11,'next trial, until head and flow settle',12,'middle','var(--s1)',w=600)
    return svg(W,H,b,'Flow of one routing step through the solver')
def fig_pump(p):
    W,H=760,250
    rows=[('Pump curve and pipe, by hand',p['exact'],'s3'),('EPA 5.2.4 EXTRAN',p['extran'],'s5'),('RASPIPE',p['rp'],'s2'),('EPA 5.2.4 SLOT',p['slot'],'s1')]
    b='';mx=6.0;x0=230;w=W-x0-90
    for i,(n,v,c) in enumerate(rows):
        y=20+i*52
        b+=T(x0-10,y+22,n,13,'end','var(--ink)')+R(x0,y,w*v/mx,32,f'var(--{c})',rx=3)+T(x0+w*v/mx+6,y+22,f'{v:.3f}',13,'start','var(--ink)',mono=True)
    b+=L(x0+w*p['exact']/mx,12,x0+w*p['exact']/mx,226,'var(--ink-dim)',1,'5 4')
    b+=T(x0+w/2,244,'Steady flow in the pipe (cfs)',13,'middle','var(--axis)')
    return svg(W,H,b,'Bar chart of steady pump flow from four methods')
def fig_wave(w):
    keep=lambda r:dict(x=[t for t in r['t'] if 30<=t<=140],y=[q for t,q in zip(r['t'],r['q']) if 30<=t<=140])
    return chart(760,330,[dict(keep(w['ref']),c='s3',w=4.5),dict(keep(w['fine']),c='s5',dash='7 4'),dict(keep(w['rp']),c='s2'),dict(keep(w['stock']),c='s1')],'Minutes','Flow (cfs)',(30,140),(0,17),label='Four solutions of a wave in a pipe',labels=[(84,15.75,'cut into 160 conduits','s5'),(32,14.2,'independent solver (wide line)','s3'),(32,13.0,'RASPIPE defaults','s2'),(32,11.8,'stock, two conduits','s1')])
def fig_mesh2(w):
    pts=[(800,'rp5'),(200,'rp200'),(50,'rp50'),(12.5,'rp12')]
    xs=[p[0] for p in pts]; ys=[w[p[1]]['peak'] for p in pts]
    s=[dict(x=xs,y=ys,c='s2',pts=True),dict(x=[12.5,800],y=[w['ref']['peak']]*2,c='s3',dash='7 4'),dict(x=[12.5,800],y=[w['stock']['peak']]*2,c='s1',dash='7 4')]
    return chart(760,300,s,'Cell length (ft), log scale','Peak flow at 6,000 ft (cfs)',(12.5,800),(13.0,15.5),logx=True,label='Peak flow against cell length',labels=[(14,15.1,'independent solver','s3'),(14,13.2,'stock, two conduits','s1'),(100,14.3,'RASPIPE','s2')])
def fig_corpus(s):
    W,H=760,290;b='';bins=s['bins'];bw=(W-80)/len(bins);mx=max(max(x['ref'],x['rp']) for x in bins)
    y=lambda v:236-v/mx*210
    for i,c in enumerate(bins):
        x=64+i*bw
        b+=R(x+bw*.12,y(c['ref']),bw*.36,236-y(c['ref']),'var(--s1)')+R(x+bw*.5,y(c['rp']),bw*.36,236-y(c['rp']),'var(--s2)')
        b+=T(x+bw*.3,y(c['ref'])-4,c['ref'],12,'middle','var(--axis)',mono=True)+T(x+bw*.68,y(c['rp'])-4,c['rp'],12,'middle','var(--axis)',mono=True)+T(x+bw/2,254,c['label'],12,'middle','var(--axis)')
    b+=L(64,236,W-10,236,'var(--line)')+T(W/2,282,'Size of the routing continuity error (amber EPA 5.2.4, blue RASPIPE)',13,'middle','var(--axis)')
    return svg(W,H,b,'Bars of model counts by continuity error band')
def fig_options(o):
    W,H=760,300; b=''; x0=250; w=W-x0-110
    rows=[('Surge from a stage boundary','cfs',o['surge'],0.0,'stage projected'),('Start-up peak, 5 cfs pipe','cfs',o['spike'],o['warm'],'warm up 60'),('False flood, steep deck','ac-ft',o['flood'],o['floodon'],'Courant 0.9')]
    for i,(n,u,a,c,lab) in enumerate(rows):
        y=18+i*92; mx=max(a,c,1e-9)
        b+=T(x0-12,y+22,n,13,'end','var(--ink)',w=600)+T(x0-12,y+40,u,12,'end','var(--axis)')
        b+=R(x0,y,w*a/mx,26,'var(--s1)',rx=3)+T(x0+w*a/mx+6,y+18,f'{a:.2f} off',13,'start','var(--ink)',mono=True)
        b+=R(x0,y+32,max(w*c/mx,2),26,'var(--s2)',rx=3)+T(x0+max(w*c/mx,2)+6,y+50,f'{c:.2f} {lab}',13,'start','var(--ink)',mono=True)
    return svg(W,H,b,'Before and after bars for three options')
def all_figs(pump,wave,sweep,opt):
    return dict(options=fig_options(opt),mesh=fig_mesh(),split=fig_split(),eq=fig_eq(),path=fig_path(),pump=fig_pump(pump),wave=fig_wave(wave),mesh2=fig_mesh2(wave),corpus=fig_corpus(sweep))

def fig_slot(p,sl):
    W,H=760,296
    rows=[('Pump curve and pipe, by hand',p['exact'],'s3'),('EPA SLOT as written',sl['EPA 5.2.4 SLOT as written'],'s1'),('Velocity term uses the true area',sl['velocity term uses the true area'],'s4'),('Head term uses the true area',sl['head term uses the true area'],'s4'),('Both terms use the true area',sl['both terms use the true area'],'s5'),('RASPIPE',p['rp'],'s2')]
    b='';mx=6.0;x0=250;w=W-x0-90
    for i,(n,v,c) in enumerate(rows):
        y=12+i*44
        b+=T(x0-10,y+20,n,13,'end','var(--ink)')+R(x0,y,w*v/mx,30,f'var(--{c})',rx=3)+T(x0+w*v/mx+6,y+20,f'{v:.3f}',13,'start','var(--ink)',mono=True)
    b+=L(x0+w*p['exact']/mx,6,x0+w*p['exact']/mx,270,'var(--ink-dim)',1,'5 4')
    b+=T(x0+w/2,288,'Steady flow in the pipe (cfs)',13,'middle','var(--axis)')
    return svg(W,H,b,'Bar chart of steady pump flow with the slot terms changed one at a time')
def fig_stoker(bs):
    s=bs['stoker']
    def ser(k,c,**o):
        v=s[k]; return dict(x=v['x'],y=v['h'],c=c,**o)
    return chart(760,320,[ser('exact','s3',w=4.5),ser('v11','s1'),ser('v12','s5'),ser('v12t','s2')],'Distance along the pipe (ft)','Depth (ft)',(0,4000),(0,11),label='Dam break depth profile against the exact solution',labels=[(2700,9.6,'exact (wide line)','s3'),(2700,8.7,'v1.1 implicit upwind','s1'),(2700,7.8,'v1.2, theta 1','s5'),(2700,6.9,'v1.2, theta 0.6','s2')])
def fig_utube(bs):
    u=bs['utube']
    return chart(760,300,[dict(x=u['exact']['x'],y=u['exact']['z'],c='s3',w=4.5),dict(x=u['epa']['x'],y=u['epa']['z'],c='s1'),dict(x=u['rp']['x'],y=u['rp']['z'],c='s2')],'Seconds','Tank level above the mean (ft)',(0,1800),(-.55,.75),label='U-tube oscillation',labels=[(40,.66,'exact, no losses (wide line)','s3'),(620,.66,'EPA 5.2.4 EXTRAN','s1'),(1160,.66,'RASPIPE full equations','s2')])
def fig_budget(rows):
    W=760; pick=[('Full equations, 12.5 ft, 1 s','full equations, 12.5 ft, 1 s, theta 1.0','s2'),('Diffusion wave, 12.5 ft, 1 s','diffusion wave, 12.5 ft, 1 s','s2'),('Diffusion wave, 50 ft, 5 s','diffusion wave, 50 ft, 5 s','s5'),('Diffusion wave, 100 ft, 5 s','diffusion wave, 100 ft, 5 s','s5'),('Diffusion wave, 400 ft, 5 s','diffusion wave, 400 ft, 5 s','s5'),('Diffusion wave, 800 ft, 5 s','diffusion wave, 800 ft, 5 s','s5'),('100 ft, true 30 s step','diffusion wave, 100 ft, 30 s, Courant off','s4'),('100 ft, true 60 s step','diffusion wave, 100 ft, 60 s, Courant off','s4'),('EPA 5.2.4, 160 conduits','EPA 5.2.4, 160 conduits of 50 ft, 0.05 s','s1'),('EPA 5.2.4, as built','EPA 5.2.4, the model as built','s1')]
    H=20+len(pick)*30+36; x0=250; b=''; mx=14.0; w=W-x0-80
    for i,(n,k,c) in enumerate(pick):
        r=next(q for q in rows if q['name']==k); v=abs(r['peak_err']); y=10+i*30
        b+=T(x0-10,y+16,n,13,'end','var(--ink)')+R(x0,y,max(w*v/mx,2),20,f'var(--{c})',rx=3)+T(x0+max(w*v/mx,2)+6,y+15,f"{r['peak_err']:+.2f}%",12,'start','var(--ink)',mono=True)
    b+=T(x0+w/2,H-8,'Size of the peak flow error against the independent solver',13,'middle','var(--axis)')
    return svg(W,H,b,'Bars of peak error by cause')
def more_figs(pump,slot,bench,rows):
    return dict(slot=fig_slot(pump,slot),stoker=fig_stoker(bench),utube=fig_utube(bench),budget=fig_budget(rows))
