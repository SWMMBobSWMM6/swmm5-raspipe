"""Score RASPIPE (and EPA) against a RAS plan at RAS's output step. Options are passed as KEY=VALUE pairs."""
import sys,re,json,numpy as np
sys.path.insert(0,'/root/rp/hecras/cmp'); sys.path.insert(0,'/root/rp/tests')
import rasread,outread,cmp1,mkdeck_extran as M
def deck(hdf,inp,out,opts,minsurf=12.566,rim=False):
    R=M.build(hdf,inp,out,dict(opts),minsurf=minsurf)
    if rim:
        s=open(out).read()
        for n,d in R['geom_nodes'].items():
            if d['inlet'] and n in R['ws']:
                pk=float(R['ws'][n].max())
                if pk>d['terr']: s=re.sub(rf'^{M.sid(n)} {d["inv"]:.3f} \S+',f'{M.sid(n)} {d["inv"]:.3f} {pk-d["inv"]:.3f}',s,flags=re.M)
        open(out,'w').write(s)
    return R
def score(R,O):
    inv={k:v['inv'] for k,v in R['geom_nodes'].items()}
    outs={k for k,v in R['geom_nodes'].items() if v['type'] in ('Culvert Opening','External')}
    H=[];Q=[];hm=[];qm=[]
    for k in R['ws']:
        if k in outs: continue
        try: y=np.array(outread.node(O,k.replace(' ','_'),0))+inv[k]
        except Exception: continue
        d=np.abs(y-R['ws'][k][1:]); H.append(d<=0.1); hm.append(d.mean())
    for k in R['qmid']:
        try: q=np.array(outread.link(O,k.replace(' ','_'),0))
        except Exception: continue
        r=R['qmid'][k][1:]; e=np.abs(q-r)/max(np.abs(r).max(),.035); Q.append(e<=0.02); qm.append(e.mean())
    H=np.array(H);Q=np.array(Q)
    return dict(h=float(H.mean()),q=float(Q.mean()),he=int((H.mean(1)>=.9).sum()),hn=len(H),qe=int((Q.mean(1)>=.9).sum()),qn=len(Q),hmean=float(np.mean(hm)),qmean=float(np.mean(qm)))
def timing(R,O,nodes,lv):
    inv={k:v['inv'] for k,v in R['geom_nodes'].items()}; t=R['t'][1:]; out={}
    for k in nodes:
        y=np.array(outread.node(O,k,0))+inv[k]; r=R['ws'][k][1:]
        f=lambda z,cond,after=0: next((round(a*60) for a,b in zip(t,z) if a>after and cond(b)),None)
        out[k]=(f(r,lambda v:v>=lv[k]),f(y,lambda v:v>=lv[k]),f(r,lambda v:v<lv[k],3.0),f(y,lambda v:v<lv[k],3.0))
    return out
