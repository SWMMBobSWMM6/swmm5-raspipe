#!/usr/bin/env python3
"""External benchmark 1: Stoker's wet-bed dam break, compared with the exact Riemann solution.
A test build places a step in the starting water surface inside one long conduit; the shipped engine is otherwise unchanged."""
import os,sys,math,subprocess,json,re
sys.path.insert(0,'/root/rp/tests')
import gen
G=32.2; HL,HR=10.0,2.0; L=4000.0; X0=2000.0; T=60.0
def exact():
    cL,cR=math.sqrt(G*HL),math.sqrt(G*HR)
    f=lambda c:(c*c/G-HR)*math.sqrt(G*(c*c/G+HR)/(2*c*c/G*HR))-2*(cL-c)
    lo,hi=cR,cL
    for _ in range(200):
        m=.5*(lo+hi)
        if f(m)>0: hi=m
        else: lo=m
    cs=.5*(lo+hi); hs=cs*cs/G; us=2*(cL-cs); S=hs*us/(hs-HR)
    return dict(hs=hs,us=us,S=S,cs=cs,cL=cL)
E_=exact(); print(E_)
def hexact(x,t=T):
    z=(x-X0)/t; e=E_
    if z<-e['cL']: return HL
    if z<e['us']-e['cs']: return (2*e['cL']-z)**2/(9*G)
    if z<e['S']: return e['hs']
    return HR
def deck(dx,dt,theta):
    return gen.head('stoker','RASPIPE',end='00:01:10',rep='00:10',dt=str(dt),extra=f"RASPIPE_EQUATIONS SWE\nRASPIPE_CELL_LENGTH {dx}\nRASPIPE_MAX_CELLS 5000\nRASPIPE_COURANT 0\nRASPIPE_INITIAL_STAGE NO\nRASPIPE_THETA {theta}\nVARIABLE_STEP 0\nMIN_SURFAREA 1")+f"""
[JUNCTIONS]
J1 0 40 {HL} 0 0
J2 0 40 {HR} 0 0
[OUTFALLS]
O1 0 FIXED {HR}
[CONDUITS]
C1 J1 J2 {L} 0.0005 0 0 0 0
C2 J2 O1 400 0.0005 0 0 0 0
[XSECTIONS]
C1 RECT_OPEN 30 10 0 0 1
C2 RECT_OPEN 30 10 0 0 1
"""+gen.TAIL
W='/root/rp/tests/b/'
def run(exe,dx,dt,theta=1.0,acon=None,tag='',aface=False):
    p=W+f'st{tag}'
    open(p+'.inp','w').write(deck(dx,dt,theta))
    e=dict(os.environ,RP_STEP=f'{X0} {HL} {HR}',RP_DUMP=f'{T} {p}.dump')
    if acon: e['RP_ACON']=str(acon)
    if aface: e['RP_AFACE']='1'
    if os.path.exists(p+'.dump'): os.remove(p+'.dump')
    subprocess.run([exe,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=e,timeout=280)
    c=[];Tq=None
    for l in open(p+'.dump'):
        if l[0]=='#': Tq=float(l.split()[1])
        elif l[0]=='c':
            a=l.split()
            if a[1]=='0': c.append((float(a[3]),float(a[4])-float(a[5])))
    tx=open(p+'.rpt',errors='replace').read()
    rep=dict(cont=(re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx) or [None])[-1], trials=(re.findall(r'Trials per step \.+ ([\d.]+)',tx) or [None])[-1], un=(re.findall(r'Steps left unsolved \.+ (\d+)',tx) or [None])[-1])
    return c,Tq,rep
def score(c,Tq):
    xs=[a for a,b in c]; hs=[b for a,b in c]
    dx=xs[1]-xs[0]
    l1=sum(abs(h-hexact(x,Tq)) for x,h in c)*dx/L
    # the star plateau: mean over the middle of the exact plateau
    e=E_; a=X0+(e['us']-e['cs'])*Tq; b=X0+e['S']*Tq
    pl=[h for x,h in c if a+.25*(b-a)<x<b-.15*(b-a)]
    star=sum(pl)/len(pl)
    mid=.5*(e['hs']+HR); xsh=None
    for i in range(len(c)-1,0,-1):
        if hs[i]<mid<=hs[i-1]:
            xsh=xs[i-1]+(hs[i-1]-mid)/(hs[i-1]-hs[i])*dx; break
    over=max(hs)-HL
    # overshoot ahead of the shock
    osc=max(h-e['hs'] for x,h in c if a<x<b+200)
    return dict(l1=l1,star=star,star_err=100*(star-e['hs'])/e['hs'],shock=xsh,shock_err=(xsh-(X0+e['S']*Tq)) if xsh else None,speed=(xsh-X0)/Tq if xsh else None,over=osc)
R=[]
def go(name,exe,dx,dt,**k):
    c,Tq,rep=run(exe,dx,dt,**k)
    s=score(c,Tq); s.update(name=name,dx=dx,dt=dt,T=Tq,**rep,**{kk:v for kk,v in k.items() if kk!='tag'}); R.append(s)
    print(f"{name:34s} dx {dx:5} dt {dt:5} L1 {s['l1']:.4f} ft  h* {s['star']:.4f} ({s['star_err']:+.2f}%)  shock x err {s['shock_err']:+.1f} ft speed {s['speed']:.3f}  over {s['over']:+.3f} cont {rep['cont']} tr {rep['trials']} un {rep['un']}",flush=True)
    return c
V12='/root/rp/testbuild/swmm5_v12'; V11='/root/rp/testbuild/swmm5_v11'
print('exact h*',E_['hs'],'u*',E_['us'],'S',E_['S'],'shock at',X0+E_['S']*T)
keep={}
for dx,dt in ((20,0.5),(10,0.25),(5,0.125)):
    keep[f'v12_{dx}']=go('v1.2, theta 1',V12,dx,dt)
    keep[f'v11_{dx}']=go('v1.1 implicit upwind, theta 1',V11,dx,dt)
    keep[f'v12t_{dx}']=go('v1.2, theta 0.6',V12,dx,dt,theta=0.6)
go('v1.2, upstream face area in V*',V12,5,0.125,aface=True)
for dt in (0.05,0.02):
    go('v1.2, theta 1, time refined',V12,10,dt)
    go('v1.1 implicit upwind, time refined',V11,10,dt)
go('v1.2, theta 0.6, time refined',V12,10,0.05,theta=0.6)
for acon in (1.1,1.25,2.0,4.0):
    go(f'v1.2 contraction ratio {acon}',V12,10,0.25,acon=acon)
go('v1.2 long step, Courant near 3',V12,10,1.0)
go('v1.2 long step, Courant near 6',V12,10,2.0)
go('v1.2 long step, Courant near 3, theta 0.6',V12,10,1.0,theta=0.6)
json.dump(dict(exact=E_,HL=HL,HR=HR,L=L,X0=X0,T=T,rows=R,prof={k:[[round(a,2),round(b,4)] for a,b in v][::max(1,len(v)//400)] for k,v in keep.items()}),open('/root/rp/tests/v/stoker.json','w'))
