#!/usr/bin/env python3
"""Final wave table: every solution of the same 8,000 ft pipe, read at x = 6,000 ft."""
import sys, re, subprocess, json
sys.path.insert(0,'/root/rp/tests')
import gen, outread as o
src=open('/root/rp/tests/wave.py').read().split("res={}")[0]; exec(src)
src2=open('/root/rp/tests/wave2.py').read().split("for n,dt,ms in")[0].replace("def deck(","def deck2("); exec(src2)
R={}
def add(k,name,t,q,c=None,shift=120.0):
    # SWMM decks hold 2 cfs for two hours first, so the pipe starts wet and steady like the reference
    if shift: q=[b for a,b in zip(t,q) if a>=shift]; t=[a-shift for a in t if a>=shift]
    i=max(range(len(q)),key=lambda j:q[j]); R[k]=dict(name=name,t=t,q=q,peak=q[i],tp=t[i],c=c); print(f'{name:58s} peak {q[i]:.3f} at {t[i]:.1f}, start {q[0]:.3f}')
r,tx=run(deck('DYNWAVE','VARIABLE_STEP 0.75','1'),REF)
add('stock','EPA 5.2.4 DYNWAVE, the model as built: two 4,000 ft conduits',[(i+1)*.5 for i in range(len(r['t']))],list(o.link(r,'C2',0)),'s1')
print('  continuity',re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx)[-1:])
p=D+'wave2'
open(p+'.inp','w').write(deck2(160,'0.05').replace('MIN_SURFAREA 12.566','MIN_SURFAREA 0.1'))
subprocess.run([REF,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
r=o.read(p+'.out'); add('fine','EPA 5.2.4 DYNWAVE, cut into 160 conduits of 50 ft, step 0.05 s',[(i+1)*.5 for i in range(len(r['t']))],list(o.link(r,'K120',0)),'s5')
print('  continuity',re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',open(p+'.rpt',errors='replace').read())[-1:])
for dx,mc,dt,nm,key in [(100,20,'5','RASPIPE defaults (20 cells a conduit), step 5 s','rp'),(100,20,'30','RASPIPE defaults, step 30 s','rp30'),(800,20,'5','RASPIPE, 5 cells a conduit','rp5'),(200,400,'5','RASPIPE, 200 ft cells','rp200'),(50,400,'5','RASPIPE, 50 ft cells','rp50'),(12.5,800,'5','RASPIPE, 12.5 ft cells','rp12')]:
    r,tx=run(deck('RASPIPE',f'RASPIPE_CELL_LENGTH {dx}\nRASPIPE_MAX_CELLS {mc}\nVARIABLE_STEP 0',dt),RP)
    add(key,nm,[(i+1)*.5 for i in range(len(r['t']))],list(o.link(r,'C2',0)),'s2')
    print('  continuity',re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx)[-1:],re.findall(r'Trials per step \.+ ([\d.]+)',tx),re.findall(r'Cells / faces \.+ (\d+ / \d+)',tx))
r,tx=run(deck('RASPIPE','RASPIPE_CELL_LENGTH 12.5\nRASPIPE_MAX_CELLS 800\nRASPIPE_EQUATIONS SWE','1'),RP)
add('swe','RASPIPE full shallow water, 12.5 ft cells, step 1 s',[(i+1)*.5 for i in range(len(r['t']))],list(o.link(r,'C2',0)),'s2')
ref=json.load(open(D+'refsol.json'))['1280']
add('ref','Independent Saint-Venant solver, 6.25 ft cells',[x[0] for x in ref],[x[1] for x in ref],'s3',0)
json.dump(R,open(D+'wave3.json','w'))
