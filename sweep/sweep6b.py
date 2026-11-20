#!/usr/bin/env python3
"""SWMM6 options one at a time over the same corpus sample, native October 29 build, 45 s limit. Mode semiN sets S6_NEWTON, the test patch."""
import os,re,json,subprocess,time,threading,queue
S6='/root/rp/swmm6/b6a/src/cli/openswmm'; W='/tmp/claude-0/s6b'; os.makedirs(W,exist_ok=True)
L=[x.strip() for x in open('/root/rp/sweep/r12_list.txt') if x.strip()]
MODES={'plain':[], 'slot':[('SURCHARGE_METHOD','DYNAMIC_SLOT')], 'semi':[('NODE_CONTINUITY','SEMI_IMPLICIT')], 'accel':[('ANDERSON_ACCEL','YES')],'semiN':[('NODE_CONTINUITY','SEMI_IMPLICIT')],'noSemi':[('SURCHARGE_METHOD','DYNAMIC_SLOT'),('ANDERSON_ACCEL','YES')]}
def setopt(s,k,v):
    r=re.compile(r'^[ \t]*'+k+r'[ \t]+\S.*$',re.M|re.I)
    if r.search(s): return r.sub(f'{k}  {v}',s,count=1)
    return re.sub(r'^\s*\[OPTIONS\][^\n]*\n',lambda m:m.group(0)+f'{k}  {v}\n',s,count=1,flags=re.M|re.I)
R='/root/rp/sweep/r6b_results.jsonl'
done={json.loads(l)['inp'] for l in open(R)} if os.path.exists(R) else set()
q=queue.Queue(); [q.put(x) for x in L if x not in done]
out=open(R,'a'); lock=threading.Lock()
def work(w):
    while True:
        try: inp=q.get_nowait()
        except queue.Empty: return
        try: t=open(inp,errors='replace').read()
        except Exception: continue
        if '[CONDUITS]' not in t.upper(): continue
        rec=dict(inp=inp); d=os.path.dirname(inp)
        for m,ops in MODES.items():
            x=setopt(t,'FLOW_ROUTING','DYNWAVE')
            for k,v in ops: x=setopt(x,k,v)
            f=os.path.join(d,f'__s6b{w}.inp'); open(f,'w').write(x)
            p=f'{W}/{w}'
            for e in('.rpt','.out'):
                if os.path.exists(p+e): os.remove(p+e)
            t0=time.time(); rc=0; env=dict(os.environ)
            if m=='semiN': env['S6_NEWTON']='1'
            try: rc=subprocess.run(['bash','-c',f'ulimit -v 3000000; exec {S6} "{f}" {p}.rpt {p}.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=45,cwd=d,env=env).returncode
            except subprocess.TimeoutExpired: rc=-99
            os.remove(f); sec=time.time()-t0
            tx=open(p+'.rpt',errors='replace').read() if os.path.exists(p+'.rpt') else ''
            c=re.findall(r'Flow Routing Continuity.*?Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx,re.S)
            rec[m]=dict(rc=rc,sec=round(sec,2),cont=float(c[-1]) if c else None,err=(re.findall(r'ERROR[^\n]*',tx) or [None])[0])
        with lock: out.write(json.dumps(rec)+'\n'); out.flush()
ts=[threading.Thread(target=work,args=(i,)) for i in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]; print('done')
