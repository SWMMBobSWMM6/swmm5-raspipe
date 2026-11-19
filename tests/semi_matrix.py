#!/usr/bin/env python3
"""NODE_CONTINUITY SEMI_IMPLICIT one deck at a time: as written, with a tight head tolerance, and with the test patch (S6_NEWTON)."""
import re,subprocess,os,json
C='/root/rp/corpus/'; S6='/root/rp/swmm6/b6a/src/cli/openswmm'; W='/tmp/claude-0/s6c/m'; os.makedirs('/tmp/claude-0/s6c',exist_ok=True)
def setopt(s,k,v):
    r=re.compile(r'^[ \t]*'+k+r'[ \t]+\S.*$',re.M|re.I)
    if r.search(s): return r.sub(f'{k}  {v}',s,count=1)
    return re.sub(r'^\s*\[OPTIONS\][^\n]*\n',lambda m:m.group(0)+f'{k}  {v}\n',s,count=1,flags=re.M|re.I)
def run(d,ops,env):
    t=open(C+d,errors='replace').read()
    for k,v in ops: t=setopt(t,k,v)
    dd=os.path.dirname(C+d); f=dd+'/__m.inp'; open(f,'w').write(t); e=dict(os.environ); e.update(env)
    try: subprocess.run([S6,f,W+'.rpt',W+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=dd,timeout=90,env=e)
    except subprocess.TimeoutExpired: os.remove(f); return None
    os.remove(f); tx=open(W+'.rpt',errors='replace').read()
    m=re.search(r'Flow Routing Continuity(.*?)Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx,re.S)
    if not m: return None
    g=lambda l:float(re.search(l+r'[ .]*\s+(-?[\d.]+)',m.group(1)).group(1))
    return dict(cont=float(m.group(2)),ext=g('External Inflow'),out=g('External Outflow'),flood=g('Flooding Loss'),fin=g('Final Stored Volume'))
S=[('NODE_CONTINUITY','SEMI_IMPLICIT')]; T=[('HEAD_TOLERANCE','0.00000001'),('MAX_TRIALS','400')]; N={'S6_NEWTON':'1'}
R={}
for d in ('XPSWMM/Peter.inp','XPSWMM/IMPERIAL.inp','XPSWMM/CALIBR.inp','XPSWMM/mod59.inp','EPA/pump_exam.inp'):
    R[d]=dict(plain=run(d,[],{}),semi=run(d,S,{}),semit=run(d,S+T,{}),patch=run(d,S,N),patcht=run(d,S+T,N))
    print(d,{k:(v or {}).get('cont') for k,v in R[d].items()})
json.dump(R,open('/root/rp/tests/v/semi_matrix.json','w'),indent=0)
