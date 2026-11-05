#!/usr/bin/env python3
"""External benchmark 3: the 8,000 ft wave, scored several ways against the independent solver, one cause at a time."""
import os,sys,re,json,math,subprocess
sys.path.insert(0,'/root/rp/tests')
import gen, outread as o
RP='/root/rp/bin/swmm5_rp12'; REF='/root/rp/ref/swmm5_ref'; W='/root/rp/tests/b/'
ref=json.load(open('/root/rp/tests/v/refsol.json'))['1280']
tr=[x[0] for x in ref]; qr6=[x[1] for x in ref]; qr4=[x[2] for x in ref]; yr4=[x[3] for x in ref]
def interp(t,xs,ys):
    import bisect
    i=bisect.bisect_left(xs,t)
    if i<=0: return ys[0]
    if i>=len(xs): return ys[-1]
    f=(t-xs[i-1])/(xs[i]-xs[i-1]); return ys[i-1]+f*(ys[i]-ys[i-1])
TAIL=open('/root/rp/tests/wave.py').read()
BODY=TAIL[TAIL.index('[JUNCTIONS]'):TAIL.index('"""+gen.TAIL')]
def deck(route,extra,dt,body=BODY):
    return gen.head('wave',route,end='06:00:00',rep='01:00',dt=str(dt),extra=extra)+body+gen.TAIL
def fine(n,dt):
    dx=8000/n; J=[f'K{i} {100-i*dx/1000:.5f} 20 0 0 0' for i in range(n)]
    C=[f'P{i} K{i} K{i+1} {dx} 0.013 0 0 0 0' for i in range(n-1)]+[f'P{n-1} K{n-1} O1 {dx} 0.013 0 0 0 0']
    X=[f'P{i} CIRCULAR 3 0 0 0 1' for i in range(n)]
    tt=BODY[BODY.index('[TIMESERIES]'):].replace('J1 FLOW','K0 FLOW')
    return '[JUNCTIONS]\n'+'\n'.join(J)+'\n[OUTFALLS]\nO1 92 NORMAL\n[CONDUITS]\n'+'\n'.join(C)+'\n[XSECTIONS]\n'+'\n'.join(X)+'\n'+tt
R=[]
def score(name,group,txt,exe,lq='C2',ny='J2',tag='w3'):
    p=W+tag
    open(p+'.inp','w').write(txt)
    subprocess.run([exe,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=280)
    r=o.read(p+'.out'); tx=open(p+'.rpt',errors='replace').read()
    t0=r['t'][0]; rs=r['rstep']/60.0
    ts=[(x-t0)*1440+rs for x in r['t']]        # minutes from the start, from the file's own clock
    q=list(o.link(r,lq,0)); y=list(o.node(r,ny,0))
    S=[(a-120,b,c) for a,b,c in zip(ts,q,y) if a>=120]
    t=[a for a,b,c in S]; q=[b for a,b,c in S]; y=[c for a,b,c in S]
    qr=[interp(a,tr,qr6) for a in t]; yr=[interp(a,tr,yr4) for a in t]
    n=len(t); rm=sum((a-b)**2 for a,b in zip(q,qr))/n; rmse=math.sqrt(rm)
    mn=sum(qr)/n; nse=1-sum((a-b)**2 for a,b in zip(q,qr))/sum((b-mn)**2 for b in qr)
    ip=max(range(n),key=lambda i:q[i]); jp=max(range(n),key=lambda i:qr[i])
    def rise(v):
        base=v[0]; top=max(v); h=base+.5*(top-base)
        for i in range(1,len(v)):
            if v[i-1]<h<=v[i]: return t[i-1]+(t[i]-t[i-1])*(h-v[i-1])/(v[i]-v[i-1])
    vol=sum((a-2)*60 for a in q); volr=sum((a-2)*60 for a in qr)
    tv=sum(abs(q[i]-q[i-1]) for i in range(1,n)); osc=tv/(2*(q[ip]-min(q)))-1
    row=dict(name=name,group=group,peak=q[ip],peak_err=100*(q[ip]-qr[jp])/qr[jp],tp=t[ip],tp_err=t[ip]-t[jp],rise_err=rise(q)-rise(qr),rmse=rmse,nse=nse,vol_err=100*(vol-volr)/volr,osc=osc,y_err=max(abs(a-b) for a,b in zip(y,yr)),y_rmse=math.sqrt(sum((a-b)**2 for a,b in zip(y,yr))/n),cont=(re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx) or [None])[-1],
      steps=(re.findall(r'Pipe step \(sec\) \.+ (min [\d.]+, mean [\d.]+, max [\d.]+)',tx) or [None])[-1],cr=(re.findall(r'Largest Courant reached \. ([\d.]+)',tx) or [None])[-1],sub=(re.findall(r'Pipe steps per routing step ([\d.]+)',tx) or [None])[-1])
    R.append(row)
    print(f"{group:8s} {name:50s} peak {q[ip]:.3f} ({row['peak_err']:+.2f}%) t {row['tp_err']:+.1f} rise {row['rise_err']:+.2f} RMSE {rmse:.3f} NSE {nse:.4f} vol {row['vol_err']:+.2f}% osc {osc:.3f} y {row['y_err']:.3f} cont {row['cont']} {row['steps'] or ''} Cr {row['cr']}",flush=True)
RPO='RASPIPE_COURANT 0\nVARIABLE_STEP 0\n'
# numerical error of the full equations
for dx,mc,dt,th in ((12.5,800,1,1.0),(12.5,800,1,0.6),(50,400,5,1.0),(50,400,5,0.6),(100,100,5,1.0),(100,100,5,0.6)):
    score(f'full equations, {dx} ft, {dt} s, theta {th}','swe',deck('RASPIPE',RPO+f'RASPIPE_EQUATIONS SWE\nRASPIPE_CELL_LENGTH {dx}\nRASPIPE_MAX_CELLS {mc}\nRASPIPE_THETA {th}',dt),RP)
# the diffusion wave approximation, same mesh
for dx,mc,dt in ((12.5,800,1),):
    score(f'diffusion wave, {dx} ft, {dt} s','dw',deck('RASPIPE',RPO+f'RASPIPE_CELL_LENGTH {dx}\nRASPIPE_MAX_CELLS {mc}',dt),RP)
# mesh
for dx,mc in ((800,800),(400,800),(200,800),(100,800),(50,800),(25,800)):
    score(f'diffusion wave, {dx} ft, 5 s','mesh',deck('RASPIPE',RPO+f'RASPIPE_CELL_LENGTH {dx}\nRASPIPE_MAX_CELLS {mc}',5),RP)
# time step, Courant control off
for dt in (60,30,15,5,1):
    score(f'diffusion wave, 100 ft, {dt} s, Courant off','time',deck('RASPIPE',RPO+'RASPIPE_MAX_CELLS 800',dt),RP)
# defaults
score('RASPIPE defaults, 100 ft, ROUTING_STEP 30, Courant 0.9','auto',deck('RASPIPE','RASPIPE_MAX_CELLS 800',30),RP)
score('RASPIPE defaults, ROUTING_STEP 5, Courant 0.9','auto',deck('RASPIPE','RASPIPE_MAX_CELLS 800',5),RP)
# stock
score('EPA 5.2.4, the model as built','stock',deck('DYNWAVE','VARIABLE_STEP 0.75',1),REF)
score('EPA 5.2.4, 160 conduits of 50 ft, 0.05 s','stock',deck('DYNWAVE','VARIABLE_STEP 0\nMIN_SURFAREA 0.1',0.05,fine(160,.05)),REF,lq='P120',ny='K80')
json.dump(R,open('/root/rp/tests/v/wavebudget.json','w'),indent=0)
