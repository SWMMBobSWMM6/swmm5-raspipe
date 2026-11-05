#!/usr/bin/env python3
"""Independent reference: full Saint-Venant in a 3 ft circular pipe by a shock-capturing
finite volume (HLL) scheme, written from the textbook, sharing no code with SWMM."""
import numpy as np, json, sys
g=32.2; D=3.0; n=0.013; S0=0.001; L=8000.0; PHI=1.486
def build():
    th=np.linspace(1e-4,2*np.pi-1e-4,4001)
    A=D*D/8*(th-np.sin(th)); P=th*D/2; y=D/2*(1-np.cos(th/2)); T=D*np.sin(th/2)
    # I1 = integral of (y-s) T(s) ds = integral of A dy
    dy=np.diff(y); I=np.concatenate([[0],np.cumsum(.5*(A[1:]+A[:-1])*dy)])
    return A,y,T,P,I
At,yt,Tt,Pt,It=build()
def props(A):
    A=np.clip(A,1e-6,At[-1])
    return np.interp(A,At,yt),np.interp(A,At,Tt),np.interp(A,At,Pt),np.interp(A,At,It)
def An(Q):
    # normal area for Q, on the rising part of the conveyance curve
    k=PHI/n*At*(At/Pt)**(2/3)*np.sqrt(S0)
    m=np.argmax(k)
    return np.interp(Q,k[:m+1],At[:m+1])
def inflow(t):
    ts=np.array([0,20,40,60,80,240])*60.; q=np.array([2,2,16,16,2,2.])
    return np.interp(t,ts,q)
def solve(N,cfl=0.45,tend=4*3600):
    dx=L/N
    x=(np.arange(N)+.5)*dx
    A=np.full(N,An(2.0)); Q=np.full(N,2.0)
    t=0; rec=[]; probes=[int(6000/dx),int(4000/dx)]
    nextrec=0
    while t<tend:
        y,T,P,I=props(A)
        u=Q/A; c=np.sqrt(g*A/np.maximum(T,1e-3))
        dt=cfl*dx/np.max(np.abs(u)+c)
        # ghosts
        Al=np.concatenate([[A[0]],A]); Ql=np.concatenate([[inflow(t)],Q])
        Ar=np.concatenate([A,[An(max(Q[-1],.01))]]); Qr=np.concatenate([Q,[Q[-1]]])
        yl,Tl,Pl,Il=props(Al); yr,Tr,Pr,Ir=props(Ar)
        ul=Ql/Al; ur=Qr/Ar; cl=np.sqrt(g*Al/np.maximum(Tl,1e-3)); cr=np.sqrt(g*Ar/np.maximum(Tr,1e-3))
        sl=np.minimum(ul-cl,ur-cr); sr=np.maximum(ul+cl,ur+cr)
        Fl1=Ql; Fl2=Ql*ul+g*Il; Fr1=Qr; Fr2=Qr*ur+g*Ir
        d=np.maximum(sr-sl,1e-9)
        F1=np.where(sl>=0,Fl1,np.where(sr<=0,Fr1,(sr*Fl1-sl*Fr1+sl*sr*(Ar-Al))/d))
        F2=np.where(sl>=0,Fl2,np.where(sr<=0,Fr2,(sr*Fl2-sl*Fr2+sl*sr*(Qr-Ql))/d))
        An1=A-dt/dx*(F1[1:]-F1[:-1])
        # pressure-bed source balanced by bed slope term
        Qn=Q-dt/dx*(F2[1:]-F2[:-1])+dt*g*A*S0
        An1=np.maximum(An1,1e-4)
        yy,TT,PP,II=props(An1)
        R=An1/PP
        cf=g*n*n/(PHI*PHI)/R**(4/3)
        # implicit friction
        Qn=Qn/(1+dt*cf*np.abs(Qn)/An1)
        A,Q=An1,Qn
        t+=dt
        if t>=nextrec:
            rec.append((t/60,Q[probes[0]],Q[probes[1]],props(A[probes[1]:probes[1]+1])[0][0]))
            nextrec+=30
    return np.array(rec)
out={}
for N in (320,640,1280):
    r=solve(N)
    i=np.argmax(r[:,1]); j=np.argmax(r[:,2])
    print(f'N={N} dx={L/N:.2f}: x=6000 peak {r[i,1]:.3f} at {r[i,0]:.1f} min; x=4000 peak {r[j,2]:.3f} at {r[j,0]:.1f} min; depth at 4000 {r[:,3].max():.3f}',flush=True)
    out[N]=r.tolist()
json.dump(out,open('/root/rp/tests/v/refsol.json','w'))
