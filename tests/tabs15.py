#!/usr/bin/env python3
"""How far is a 15-point cell table from the true volume, and from RASPIPE's table?
True volume: a level water surface over a sloping circular pipe cell, integrated finely."""
import numpy as np, json
def area(y,D):
    y=np.clip(y,0,D); th=2*np.arccos(1-2*y/D); return D*D/8*(th-np.sin(th))
def Vtrue(eta,D,L,S):
    # flat water level eta above the low end of the cell; invert rises from 0 at the low end to S*L
    x=(np.arange(40000)+.5)/40000*L
    return np.array([np.sum(area(e-S*x,D))*L/40000 for e in eta])
def err(e_tab,V_tab,e,Vt):
    Vh=np.interp(e,e_tab,V_tab)
    return Vh-Vt
R=[]
for D,L,S in ((3,100,.001),(3,100,.005),(3,100,.02),(3,100,.05),(1,100,.005),(1,100,.05),(8,100,.005),(3,25,.005),(3,400,.005)):
    z=S*L; lo,hi=0.0,z+D
    # 15 Gauss-Legendre abscissae mapped on to [lo,hi], with the two ends, as piecewise linear volume
    g,_=np.polynomial.legendre.leggauss(15)
    eG=np.concatenate([[lo],lo+(g+1)/2*(hi-lo),[hi]])
    # 15 equally spaced levels, the other reading of the page
    eU=np.linspace(lo,hi,15)
    # RASPIPE: intervals of D/32 over the same range, 32 to 128 of them
    k=int(np.ceil((z+D)/(D/32))); k=max(32,min(128,k)); eR=np.linspace(lo,hi,k+1)
    e=np.linspace(lo,hi,1501); Vt=Vtrue(e,D,L,S); Vf=Vt[-1]
    res={}
    for n,tab in (('gauss15',eG),('even15',eU),('rp',eR)):
        Vtab=Vtrue(tab,D,L,S); d=err(tab,Vtab,e,Vt)
        # storage derivative error, the quantity Newton uses
        dT=np.gradient(np.interp(e,tab,Vtab),e)-np.gradient(Vt,e)
        res[n]=dict(n=len(tab),maxpct=float(100*np.max(np.abs(d))/Vf),rmspct=float(100*np.sqrt(np.mean(d**2))/Vf),maxT=float(np.max(np.abs(dT))/(D*L)))
    R.append(dict(D=D,L=L,S=S,**res))
    print(D,L,S,{k:(v['n'],round(v['maxpct'],4),round(v['rmspct'],4)) for k,v in res.items()})
json.dump(R,open('/root/rp/tests/v/tabs15.json','w'),indent=0)
