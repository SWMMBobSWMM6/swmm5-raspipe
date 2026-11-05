#!/usr/bin/env python3
"""External benchmark 2: U-tube mass oscillation between two tanks. The period has a closed form."""
import os,sys,math,subprocess,json,re
sys.path.insert(0,'/root/rp/tests')
import gen, outread as o
RP='/root/rp/bin/swmm5_rp12'; REF='/root/rp/ref/swmm5_ref'
W='/root/rp/tests/b/'
G=32.2; L=1000.0; D=2.0; As=1000.0; Ap=math.pi*D*D/4; Y0=10.0; a0=0.5
Texact=2*math.pi*math.sqrt(L*As/(2*G*Ap))
print('exact period',Texact)
def deck(route,extra,dt):
    return gen.head('utube',route,end='01:00:00',rep=f'00:{max(dt,2):02d}' if dt<60 else '01:00',dt=str(dt),extra=extra+'\nMIN_SURFAREA 1')+f"""
[JUNCTIONS]
J9 5 5 0 0 0
[OUTFALLS]
O9 0 FREE
[STORAGE]
S1 0 30 {Y0+a0} FUNCTIONAL 0 0 {As} 0 0
S2 0 30 {Y0-a0} FUNCTIONAL 0 0 {As} 0 0
[CONDUITS]
C1 S1 S2 {L} 0.001 0 0 0 0
C9 J9 O9 100 0.013 0 0 0 0
[XSECTIONS]
C1 CIRCULAR {D} 0 0 0 1
C9 CIRCULAR 1 0 0 0 1
"""+gen.TAIL
def run(name,exe,route,extra,dt):
    p=W+'ut'
    open(p+'.inp','w').write(deck(route,extra,dt))
    subprocess.run([exe,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
    r=o.read(p+'.out'); tx=open(p+'.rpt',errors='replace').read()
    y1=list(o.node(r,'S1',0)); y2=list(o.node(r,'S2',0))
    z=[.5*(a-b) for a,b in zip(y1,y2)]
    st=max(dt,2); t=[(i+1)*float(st) for i in range(len(z))]
    # upward and downward zero crossings give half periods
    zc=[]
    for i in range(1,len(z)):
        if z[i-1]*z[i]<0: zc.append(t[i-1]+(t[i]-t[i-1])*z[i-1]/(z[i-1]-z[i]))
    T=(zc[2]-zc[0]) if len(zc)>=3 else None
    T2=(zc[-1]-zc[-1-2*((len(zc)-1)//2)])/((len(zc)-1)//2) if len(zc)>=3 else None
    # successive extremes
    ex=[]
    for i in range(1,len(z)-1):
        if abs(z[i])>=abs(z[i-1]) and abs(z[i])>abs(z[i+1]) and (not ex or ex[-1][1]*z[i]<0): ex.append((t[i],z[i]))
    a1=abs(ex[1][1]) if len(ex)>1 else None; a2=a1
    row=dict(name=name,dt=dt,T=T,Tmean=T2,err=100*(T-Texact)/Texact if T else None,a0=a0,a1=a1,a2=a2,dec=(a2/a0 if a2 else None),cont=(re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx) or [None])[-1],crossings=len(zc))
    print(f"{name:40s} dt {dt:5} period {T if T is None else round(T,2)} ({'' if row['err'] is None else round(row['err'],3)}%)  amplitude ratio after one cycle {row['dec'] if row['dec'] is None else round(row['dec'],4)}  crossings {len(zc)} cont {row['cont']}",flush=True)
    k=max(1,10//st); row['z']=[round(x,4) for x in z[::k]]; row['tz']=t[::k]
    return row
R=[]
SWE="RASPIPE_EQUATIONS SWE\nRASPIPE_COURANT 0\nRASPIPE_INITIAL_STAGE NO\nVARIABLE_STEP 0"
for th in (1.0,0.6):
    for dt in (60,30,10,2):
        R.append(run(f'RASPIPE SWE, theta {th}',RP,'RASPIPE',SWE+f'\nRASPIPE_THETA {th}',dt))
R.append(run('RASPIPE SWE, theta 0.5',RP,'RASPIPE',SWE+'\nRASPIPE_THETA 0.5',10))
R.append(run('RASPIPE diffusion wave (no inertia)',RP,'RASPIPE','RASPIPE_COURANT 0\nVARIABLE_STEP 0',10))
R.append(run('EPA 5.2.4 EXTRAN',REF,'DYNWAVE','VARIABLE_STEP 0',2))
R.append(run('EPA 5.2.4 SLOT',REF,'DYNWAVE','VARIABLE_STEP 0\nSURCHARGE_METHOD SLOT',2))
os.environ['SLOTVAR']='4'
R.append(run('EPA 5.2.4 EXTRAN, full pipe adds no surface',"/root/rp/slotx/swmm5_slot",'DYNWAVE','VARIABLE_STEP 0',2))
os.environ['SLOTVAR']='0'
As=4000.; Texact=2*math.pi*math.sqrt(L*As/(2*G*Ap))
w=2*math.sqrt(.96*D*D*.04); print('4000 ft2 tank: exact',Texact,'predicted EPA',Texact*math.sqrt(1+w*L/2/As))
r=run('EPA 5.2.4 EXTRAN, 4,000 ft2 tanks',REF,'DYNWAVE','VARIABLE_STEP 0',2); r['exact']=Texact; R.append(r)
os.environ['SLOTVAR']='4'
r=run('same, full pipe adds no surface',"/root/rp/slotx/swmm5_slot",'DYNWAVE','VARIABLE_STEP 0',2); r['exact']=Texact; R.append(r)
os.environ['SLOTVAR']='0'
r=run('RASPIPE SWE, theta 0.6, 4,000 ft2 tanks',RP,'RASPIPE',SWE+'\nRASPIPE_THETA 0.6',2); r['exact']=Texact; R.append(r)
As=1000.; Texact=2*math.pi*math.sqrt(L*As/(2*G*Ap))
pred=1/(1+(4/3)*a0*As/(L*Ap)); print('one-cycle ratio from a V^2/2g exit loss alone',pred)
json.dump(dict(pred=pred,exact=Texact,L=L,D=D,As=As,Ap=Ap,a0=a0,rows=R),open('/root/rp/tests/v/utube.json','w'))
