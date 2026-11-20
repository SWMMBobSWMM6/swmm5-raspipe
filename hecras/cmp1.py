import sys,subprocess,json,numpy as np
sys.path.insert(0,'/root/rp/hecras/cmp'); sys.path.insert(0,'/root/rp/tests')
import rasread,outread,mkdeck_extran as M
RP='/root/rp/bin/swmm5_rp12'; EPA='/root/rp/ref/swmm5_ref'
def run(exe,inp):
    b=inp[:-4]; subprocess.run([exe,inp,b+'.rpt',b+'.out'],capture_output=True,timeout=300); return outread.read(b+'.out')
def compare(R,O,inv,label,tcut=None):
    t=R['t'][1:]; n=len(t); rows=[]
    m=np.ones(n,bool) if tcut is None else (t<=tcut+1e-9)
    hd={};fl={}
    for k in R['ws']:
        if k not in inv or k in ('16009',): continue
        try: y=np.array(outread.node(O,k,0))[:n]+inv[k]
        except Exception: continue
        r=R['ws'][k][1:]; e=np.abs(y-r)[m]; hd[k]=(float(e.max()),float(e.mean()),float(y.max()-r.max()))
    for k in R['qds']:
        try: q=np.array(outread.link(O,k,0))[:n]
        except Exception: continue
        for side in ('qmid','qds','qus'):
            r=R[side].get(k)
            if r is None: continue
            r=r[1:]; pk=max(abs(r).max(),0.035); e=(np.abs(q-r)/pk)[m]
            fl.setdefault(k,{})[side]=(float(e.max()),float(e.mean()),float((q.max()-r.max())/pk))
    return hd,fl
if __name__=='__main__':
    hdf=sys.argv[1]; inp=sys.argv[2]; tag=sys.argv[3]; dt=sys.argv[4]
    common=dict(ROUTING_STEP=dt)
    R=M.build(hdf,inp,f'{tag}_epa.inp',dict(common,FLOW_ROUTING='DYNWAVE'))
    M.build(hdf,inp,f'{tag}_rp.inp',dict(common,FLOW_ROUTING='RASPIPE',RASPIPE_EQUATIONS='DW',RASPIPE_CELL_LENGTH=100,RASPIPE_MAX_CELLS=100,RASPIPE_THETA=1.0,RASPIPE_COURANT=0.9,RASPIPE_INITIAL_STAGE='YES',RASPIPE_WARMUP=0))
    inv={k:v['inv'] for k,v in R['geom_nodes'].items()}
    sp=[t for t,q in zip(R['t'],R['inlet'].get('80608',[0]*len(R['t']))) if q<-0.01]
    tsp=sp[0] if sp else None
    print('RAS',R['version'],R['summary'].get('Solution'),'spill at 80608 starts h',tsp)
    for lab,exe,f in (('EPA DYNWAVE',EPA,f'{tag}_epa.inp'),('RASPIPE DW',RP,f'{tag}_rp.inp')):
        O=run(exe,f)
        for cut in (tsp,None):
            hd,fl=compare(R,O,inv,lab,cut)
            print(f'\n== {lab}  window: {"to spill" if cut else "whole run"}')
            print('  head |diff| max/mean ft, peak diff:',{k:tuple(round(x,3) for x in v) for k,v in hd.items()})
            print('  flow vs RAS mid face |diff|/peak max/mean, peak diff:',{k:tuple(round(x,3) for x in v['qmid']) for k,v in fl.items() if 'qmid' in v})
