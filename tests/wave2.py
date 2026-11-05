#!/usr/bin/env python3
"""Same wave, stock DYNWAVE with the two 4,000 ft conduits cut into many short ones."""
import sys, re, subprocess, json
sys.path.insert(0,'/root/rp/tests')
import gen, outread as o
D='/root/rp/tests/v/'
REF='/root/rp/ref/swmm5_ref'
def deck(n, dt, extra=''):
    L=8000.0/n; S=0.001
    J=[];C=[];X=[]
    for i in range(n):
        J.append(f"N{i} {100-S*i*L:.6f} 20 0 0 0")
        to=f"N{i+1}" if i<n-1 else 'O1'
        C.append(f"K{i} N{i} {to} {L} 0.013 0 0 0 0")
        X.append(f"K{i} CIRCULAR 3 0 0 0 1")
    return gen.head('wave',"DYNWAVE",end='06:00:00',rep='00:30',dt=dt,extra=extra)+"\n[JUNCTIONS]\n"+"\n".join(J)+"\n[OUTFALLS]\nO1 92 NORMAL\n[CONDUITS]\n"+"\n".join(C)+"\n[XSECTIONS]\n"+"\n".join(X)+"""
[TIMESERIES]
H 0:00 2
H 2:20 2
H 2:40 16
H 3:00 16
H 3:20 2
H 6:00 2
[INFLOWS]
N0 FLOW H FLOW 1 1 0
"""+gen.TAIL
for n,dt,ms in [(8,'1',''),(16,'0.5',''),(32,'0.25',''),(80,'0.1',''),(160,'0.05','MIN_SURFAREA 0.1')]:
    p=D+'wave2'
    txt=deck(n,dt).replace('MIN_SURFAREA 12.566', ms or 'MIN_SURFAREA 12.566')
    open(p+'.inp','w').write(txt)
    subprocess.run([REF,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=280)
    r=o.read(p+'.out')
    k=f'K{3*n//4}' # x = 6000 ft: where RASPIPE reports C2
    q=o.link(r,k,0); nd=f'N{n//2}'
    t=open(p+'.rpt',errors='replace').read()
    c=re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',t)[-1:]
    print(f'{n:4d} conduits of {8000/n:6.0f} ft dt {dt}: flow at x=6000 ft peak {max(q):.3f} at {q.index(max(q))*.5} min; depth {max(o.node(r,nd,0)):.3f}; continuity {c}')
