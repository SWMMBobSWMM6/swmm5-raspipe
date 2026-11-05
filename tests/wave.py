#!/usr/bin/env python3
"""Hydrograph routed down a long part-full pipe: does the mesh converge, and to what?"""
import sys, re, subprocess, json
sys.path.insert(0,'/root/rp/tests')
import gen, outread as o
D='/root/rp/tests/v/'
import os
RP=os.environ.get('RPBIN','/root/rp/bin/swmm5_rp'); REF='/root/rp/ref/swmm5_ref'
def deck(route,extra,dt):
    return gen.head('wave',route,end='06:00:00',rep='00:30',dt=dt,extra=extra)+"""
[JUNCTIONS]
J1 100 20 0 0 0
J2 96 20 0 0 0
[OUTFALLS]
O1 92 NORMAL
[CONDUITS]
C1 J1 J2 4000 0.013 0 0 0 0
C2 J2 O1 4000 0.013 0 0 0 0
[XSECTIONS]
C1 CIRCULAR 3 0 0 0 1
C2 CIRCULAR 3 0 0 0 1
[TIMESERIES]
H 0:00 2
H 2:20 2
H 2:40 16
H 3:00 16
H 3:20 2
H 6:00 2
[INFLOWS]
J1 FLOW H FLOW 1 1 0
"""+gen.TAIL
def run(txt,exe):
    p=D+'wave'
    open(p+'.inp','w').write(txt)
    subprocess.run([exe,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    r=o.read(p+'.out')
    return r,open(p+'.rpt',errors='replace').read()
res={}
r,t=run(deck('DYNWAVE','VARIABLE_STEP 0.75','1'),REF)
q=o.link(r,'C2',0); qp=max(q); tp=q.index(qp)*.5
print('stock DYNWAVE      peak',round(qp,3),'t',tp,'J2 y',round(max(o.node(r,'J2',0)),3)); res['stock']=dict(q=q[::10],peak=qp,tp=tp)
for dx,dt in [(800,'5'),(400,'5'),(200,'5'),(100,'5'),(50,'5'),(25,'5'),(12.5,'5'),(25,'1'),(25,'30'),(25,'60')]:
    r,t=run(deck('RASPIPE',f'RASPIPE_CELL_LENGTH {dx}',dt),RP)
    q=o.link(r,'C2',0); qp=max(q); tp=q.index(qp)*.5
    tr=re.search(r'Trials per step \.+ ([\d.]+)',t).group(1)
    print(f'dx {dx:7} dt {dt:3}  peak {qp:.3f} t {tp} J2 y {max(o.node(r,"J2",0)):.3f} trials {tr}'); res[f'{dx}_{dt}']=dict(q=q[::10],peak=qp,tp=tp)
for ex in ['RASPIPE_EQUATIONS SWE\nRASPIPE_CELL_LENGTH 25']:
    r,t=run(deck('RASPIPE',ex,'1'),RP)
    q=o.link(r,'C2',0); qp=max(q); tp=q.index(qp)*.5
    print('SWE 25 1 peak',round(qp,3),'t',tp,'J2 y',round(max(o.node(r,'J2',0)),3)); res['swe']=dict(q=q[::10],peak=qp,tp=tp)
json.dump(res,open(D+'wave.json','w'))
