#!/usr/bin/env python3
"""Run stock EPA 5.2.4 and the RASPIPE solver over a list of .inp files.
usage: sweep.py listfile outdir [rasOptionsLine]  -> outdir/results.jsonl"""
import os, re, sys, json, time, subprocess, shutil, tempfile, multiprocessing as mp
sys.path.insert(0, '/root/rp/tests')
import outread
REF='/root/rp/ref/swmm5_ref'; RP=os.environ.get('RPBIN','/root/rp/bin/swmm5_rp')
TMO=int(os.environ.get('TMO','90'))
def parse(rpt):
    t=open(rpt,errors='replace').read()
    d={}
    m=re.search(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(-?[\d.]+)',t,re.S)
    d['cont']=float(m.group(1)) if m else None
    m=re.search(r'Flow Routing Continuity.*?External Outflow \.+\s+([\d.]+)\s',t,re.S)
    d['outflow']=float(m.group(1)) if m else None
    m=re.search(r'Flooding Loss \.+\s+([\d.]+)\s',t)
    d['flood']=float(m.group(1)) if m else None
    m=re.search(r'Quality Routing Continuity.*?Continuity Error \(%\) \.+\s+(-?[\d.]+)',t,re.S)
    d['qcont']=float(m.group(1)) if m else None
    d['err']=' | '.join(sorted(set(re.findall(r'ERROR \d+',t))))[:80] or None
    for k,p in dict(trials=r'Trials per step \.+ ([\d.]+)',fact=r'Factorizations per step \. ([\d.]+)',nested=r'Nested Newton solves \.+ ([\d.]+)',substeps=r'Pipe steps per routing step ([\d.]+)',unconv=r'Unconverged nested solves (\d+)',unsolved=r'Steps left unsolved \.+ (\d+)',maxres=r'Largest volume residual \. ([\d.e+-]+)',ledger=r'= (-?[\d.e+-]+)\n',cells=r'Cells / faces \.+ (\d+)').items():
        m=re.search(p,t); d[k]=float(m.group(1)) if m else None
    m=re.search(r'% of Steps Not Converging\s*:\s*([\d.]+)',t); d['nonconv']=float(m.group(1)) if m else None
    return d
def run(exe,inp,rpt,out):
    t0=time.time()
    try:
        p=subprocess.run([exe,inp,rpt,out],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=TMO)
        rc=p.returncode
    except subprocess.TimeoutExpired:
        rc=-99
    return rc,time.time()-t0
def peaks(o):
    r=outread.read(o)
    nl=r['nl']; L=r['L']; P={}
    for j,n in enumerate(L):
        P[n]=max(abs(x[j*nl]) for x in r['lk']) if r['lk'] else 0
    nn=r['nn']; N={}
    for j,n in enumerate(r['N']):
        N[n]=max(x[j*nn] for x in r['nd']) if r['nd'] else 0
    return P,N
def stats(a,b,floor):
    import statistics as st
    v=[]
    for k in a:
        if k in b and max(a[k],b[k])>floor: v.append(abs(a[k]-b[k])/max(a[k],floor))
    if not v: return None
    v.sort()
    return dict(n=len(v),med=v[len(v)//2],p90=v[int(.9*len(v))],max=v[-1])
def one(args):
    inp,outdir,extra=args
    res=dict(inp=inp)
    tmp=tempfile.mkdtemp(prefix='sw',dir=os.environ.get('SWTMP','/tmp'))
    try:
        s=open(inp,errors='replace').read()
        m=re.search(r'^\s*FLOW_ROUTING\s+(\S+)',s,re.M|re.I)
        route=(m.group(1).upper() if m else 'DYNWAVE')
        res['route']=route
        if route!='DYNWAVE': res['skip']='not DW'; return res
        if not re.search(r'^\s*\[CONDUITS\]',s,re.M|re.I): res['skip']='no conduits'; return res
        res['nlink']=len(re.findall(r'^[^;\[\s]\S*\s+\S+\s+\S+\s+[\d.]',s[re.search(r'^\s*\[CONDUITS\]',s,re.M|re.I).end():].split('[')[0],re.M))
        res['surch']=re.search(r'^\s*SURCHARGE_METHOD\s+(\S+)',s,re.M|re.I).group(1).upper() if re.search(r'^\s*SURCHARGE_METHOD\s+(\S+)',s,re.M|re.I) else 'EXTRAN'
        a=os.path.join(tmp,'a.inp'); b=os.path.join(tmp,'b.inp')
        open(a,'w').write(s)
        s2=re.sub(r'^(\s*FLOW_ROUTING\s+)\S+',lambda g:g.group(1)+'RASPIPE',s,count=1,flags=re.M|re.I)
        if not m: s2=re.sub(r'(\[OPTIONS\]\s*\n)',r'\1FLOW_ROUTING RASPIPE\n',s,count=1,flags=re.I)
        if extra: s2=re.sub(r'(\[OPTIONS\]\s*\n)',lambda g:g.group(1)+extra.replace('|','\n')+'\n',s2,count=1,flags=re.I)
        open(b,'w').write(s2)
        rc,t=run(REF,a,tmp+'/a.rpt',tmp+'/a.out'); res['ref_rc']=rc; res['ref_t']=round(t,3)
        rc2,t2=run(RP,b,tmp+'/b.rpt',tmp+'/b.out'); res['rp_rc']=rc2; res['rp_t']=round(t2,3)
        if os.path.exists(tmp+'/a.rpt'): res['ref']=parse(tmp+'/a.rpt')
        if os.path.exists(tmp+'/b.rpt'): res['rp']=parse(tmp+'/b.rpt')
        try:
            pa,na=peaks(tmp+'/a.out'); pb,nb=peaks(tmp+'/b.out')
            res['qdiff']=stats(pa,pb,0.01); res['ydiff']=stats(na,nb,0.01)
        except Exception as e:
            res['cmp_err']=str(e)[:60]
    except Exception as e:
        res['exc']=repr(e)[:120]
    finally:
        shutil.rmtree(tmp,ignore_errors=True)
    return res
if __name__=='__main__':
    lst=[l.strip() for l in open(sys.argv[1]) if l.strip()]
    outdir=sys.argv[2]; os.makedirs(outdir,exist_ok=True)
    extra=sys.argv[3] if len(sys.argv)>3 else ''
    with mp.Pool(int(os.environ.get('WORKERS','2'))) as pool, open(outdir+'/results.jsonl','w') as f:
        for i,r in enumerate(pool.imap_unordered(one,[(x,outdir,extra) for x in lst])):
            f.write(json.dumps(r)+'\n'); f.flush()
            if i%100==0: print(i,flush=True)
