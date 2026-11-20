#!/usr/bin/env python3
"""SWMM5, SWMM6 and RASPIPE on the same decks. Every deck is a plain .inp, so every engine reads the same thing."""
import os,sys,re,json,math,subprocess,time
sys.path.insert(0,'/root/rp/tests')
import gen, gen2, outread as o
REF='/root/rp/ref/swmm5_ref'; RP='/root/rp/bin/swmm5_rp12'; S6='/root/rp/swmm6/run6.js'
S6N=os.environ.get('S6N','')          # native build of the latest swmm6_rel, when given
W='/root/rp/tests/b/'; TMO=int(os.environ.get('TMO','280'))
TAG=os.environ.get('TAG','sixcmp')
MODES=[('ex5','EPA 5.2.4, EXTRAN'),('sl5','EPA 5.2.4, SLOT'),('s6ex','SWMM6, EXTRAN'),('s6dw','SWMM6, DYNAMIC_SLOT'),('s6fv','SWMM6 FV, defaults'),('s6fv2','SWMM6 FV, matched mesh, 2nd order'),('rpdw','RASPIPE, diffusion wave'),('rpsw','RASPIPE, full equations')]
def setopt(s,k,v):
    r=re.compile(r'^[ \t]*'+k+r'[ \t]+\S.*$',re.M|re.I)
    if r.search(s): return r.sub(f'{k}  {v}',s,1)
    return re.sub(r'^\s*\[OPTIONS\][^\n]*\n',lambda m:m.group(0)+f'{k}  {v}\n',s,count=1,flags=re.M|re.I)
def conv(t,m,cell=100,theta=0.6,extra_rp=''):
    t=re.sub(r'^[ \t]*RASPIPE_[A-Z_]+[ \t].*\r?\n','',t,flags=re.M|re.I)
    t=re.sub(r'^[ \t]*(SURCHARGE_METHOD|NODE_CONTINUITY|ANDERSON_ACCEL)[ \t].*\r?\n','',t,flags=re.M|re.I)
    if m in('ex5','s6ex'): return setopt(t,'FLOW_ROUTING','DYNWAVE')
    if m=='sl5': return setopt(setopt(t,'FLOW_ROUTING','DYNWAVE'),'SURCHARGE_METHOD','SLOT')
    if m=='s6dw':
        t=setopt(t,'FLOW_ROUTING','DYNWAVE')
        for k,v in (('SURCHARGE_METHOD','DYNAMIC_SLOT'),('NODE_CONTINUITY','SEMI_IMPLICIT'),('ANDERSON_ACCEL','YES')): t=setopt(t,k,v)
        return t
    if m=='s6fv': return setopt(t,'FLOW_ROUTING','FV')
    if m=='s6fv2':
        t=setopt(t,'FLOW_ROUTING','FV')
        for k,v in (('FV_CELL_LENGTH',cell),('FV_ORDER',2)): t=setopt(t,k,v)
        return t
    t=setopt(t,'FLOW_ROUTING','RASPIPE')
    t=setopt(t,'RASPIPE_CELL_LENGTH',cell); t=setopt(t,'RASPIPE_MAX_CELLS',800)
    if m=='rpsw':
        t=setopt(setopt(t,'RASPIPE_EQUATIONS','SWE'),'RASPIPE_THETA',theta)
    for l in extra_rp.split('\n'):
        if l.strip(): a,b=l.split(); t=setopt(t,a,b)
    return t
def go(txt,m,name):
    p=W+'x_'+name
    open(p+'.inp','w').write(txt)
    for x in('.rpt','.out'):
        if os.path.exists(p+x): os.remove(p+x)
    t0=time.time(); info={}
    try:
        if m.startswith('s6'):
            if S6N: subprocess.run([S6N,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=TMO)
            else:
                q=subprocess.run(['node','--no-warnings',S6,p+'.inp',p+'.rpt',p+'.out'],capture_output=True,text=True,timeout=TMO); info=json.loads(q.stdout.strip().split('\n')[-1])
        else: subprocess.run([REF if m in('ex5','sl5') else RP,p+'.inp',p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=TMO)
    except subprocess.TimeoutExpired: return None,dict(fail='time limit',sec=TMO)
    sec=time.time()-t0
    tx=open(p+'.rpt',errors='replace').read() if os.path.exists(p+'.rpt') else ''
    c=re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)',tx)
    cont=float(c[-1]) if c else (info.get('cont') if info else None)
    try: r=o.read(p+'.out')
    except Exception as e: return None,dict(fail=(info.get('msg') or (re.findall(r'ERROR[^\n]*',tx) or ['no results'])[0])[:120],sec=sec)
    if info.get('err'): return None,dict(fail=(info.get('msg') or 'engine error')[:120],sec=sec)
    return r,dict(cont=cont,sec=sec)
R={}
def rec(test,m,**k):
    R.setdefault(test,{})[m]=k
    print(f"{test:12s} {m:6s} "+' '.join(f"{a}={b:.5g}" if isinstance(b,float) else f"{a}={b}" for a,b in k.items() if a not in('z','t','prof','q','hours')),flush=True)
def peakq(r,l): return max(abs(float(x)) for x in o.link(r,l,0))
# --- closed forms
fulltxt=gen.fullpipe()
Q0=3.56280
for m,_ in MODES:
    r,i=go(conv(fulltxt,m),m,'full')
    rec('pipe',m,**(dict(got=float(o.link(r,r['L'][0],0)[-1]),exp=Q0,**i) if r else i))
txt=open('/root/rp/tests/v/series.inp').read()
for m,_ in MODES:
    r,i=go(conv(txt,m),m,'series')
    rec('series',m,**(dict(got=float(o.link(r,r['L'][-1],0)[-1]),exp=Q0,**i) if r else i))
txt=open('/root/rp/tests/v/lake.inp').read()
for m,_ in MODES:
    r,i=go(conv(txt,m),m,'lake')
    rec('lake',m,**(dict(got=max(peakq(r,l) for l in r['L']),exp=0.0,**i) if r else i))
txt=open('/root/rp/tests/v/pump_RASPIPE.inp').read()
PE=4.59923
for m,_ in MODES:
    r,i=go(conv(txt,m,cell=100),m,'pump')
    rec('pump',m,**(dict(got=float(o.link(r,'C1',0)[-1]),exp=PE,**i) if r else i))
# --- U-tube
s=open('/root/rp/tests/bench2.py').read(); ns={}; exec(s[:s.index('def run(')],ns)
T0=ns['Texact']
for m,_ in MODES:
    extra='RASPIPE_COURANT 0\nRASPIPE_INITIAL_STAGE NO\n'
    txt=ns['deck']('DYNWAVE','VARIABLE_STEP 0',2)
    r,i=go(conv(txt,m,extra_rp=extra),m,'ut')
    if not r: rec('utube',m,**i); continue
    y1=[float(x) for x in o.node(r,'S1',0)]; y2=[float(x) for x in o.node(r,'S2',0)]
    z=[.5*(a-b) for a,b in zip(y1,y2)]; t=[(i_+1)*2.0 for i_ in range(len(z))]; zc=[]
    for k in range(1,len(z)):
        if z[k-1]*z[k]<0: zc.append(t[k-1]+(t[k]-t[k-1])*z[k-1]/(z[k-1]-z[k]))
    T=(zc[2]-zc[0]) if len(zc)>=3 else None
    ex=[]
    for k in range(1,len(z)-1):
        if abs(z[k])>=abs(z[k-1]) and abs(z[k])>abs(z[k+1]) and (not ex or ex[-1]*z[k]<0): ex.append(z[k])
    rec('utube',m,T=T,exp=T0,err=(100*(T-T0)/T0 if T else None),dec=(abs(ex[1])/ns['a0'] if len(ex)>1 else None),t=t[::5],z=[round(x,4) for x in z[::5]],**i)
# --- dam break as a plain deck: 200 conduits of 20 ft, step across one of them
s=open('/root/rp/tests/bench1.py').read(); nb={}; exec(s[:s.index('def deck(')],nb)
E_=nb['E_']; hx=nb['hexact']; HL,HR,X0,TT=nb['HL'],nb['HR'],nb['X0'],nb['T']
def chain():
    n=200; dx=20.0
    J='\n'.join(f'K{i} 0 40 {HL if i<=100 else HR} 0 0' for i in range(n+1))
    C='\n'.join(f'P{i} K{i} K{i+1} {dx} 0.0005 0 0 0 0' for i in range(n))+f'\nPZ K{n} O1 400 0.0005 0 0 0 0'
    X='\n'.join(f'P{i} RECT_OPEN 30 10 0 0 1' for i in range(n))+'\nPZ RECT_OPEN 30 10 0 0 1'
    return gen.head('stoker','DYNWAVE',end='00:01:00',rep='00:01',dt='0.25',extra='VARIABLE_STEP 0\nMIN_SURFAREA 1').replace('REPORT_STEP 00:00:01','REPORT_STEP 00:01:00')+f"\n[JUNCTIONS]\n{J}\n[OUTFALLS]\nO1 0 FIXED {HR}\n[CONDUITS]\n{C}\n[XSECTIONS]\n{X}\n"+gen.TAIL
ctxt=chain()
open('/root/rp/tests/v/chain.inp','w').write(ctxt)
for m,_ in MODES:
    r,i=go(conv(ctxt,m,cell=25,theta=0.6,extra_rp='RASPIPE_COURANT 0\nRASPIPE_INITIAL_STAGE NO\n'),m,'chain')
    if not r: rec('dambreak',m,**i); continue
    xs=[i_*20.0 for i_ in range(201)]; ys=[float(o.node(r,f'K{i_}',0)[-1]) for i_ in range(201)]
    l1=sum(abs(a-hx(x,60.0)) for x,a in zip(xs,ys))/len(xs)
    e=E_; a=X0+(e['us']-e['cs'])*60; b=X0+e['S']*60
    pl=[h for x,h in zip(xs,ys) if a+.25*(b-a)<x<b-.15*(b-a)]; star=sum(pl)/len(pl) if pl else None
    mid=.5*(e['hs']+HR); xsh=None
    for k in range(200,0,-1):
        if ys[k]<mid<=ys[k-1]: xsh=xs[k-1]+(ys[k-1]-mid)/(ys[k-1]-ys[k])*20; break
    rec('dambreak',m,l1=l1,star=star,speed=((xsh-X0)/60 if xsh else None),exp=e['S'],speed_err=(100*((xsh-X0)/60-e['S'])/e['S'] if xsh else None),prof=[[x,round(h,3)] for x,h in zip(xs,ys)],**i)
# --- the wave against the independent solver
s=open('/root/rp/tests/bench3.py').read(); nw={}; exec(s[:s.index('R=[]')],nw)
for m,_ in MODES:
    r,i=go(conv(nw['deck']('DYNWAVE','',5),m,extra_rp=''),m,'wave')
    if not r: rec('wave',m,**i); continue
    t0=r['t'][0]; rs=r['rstep']/60.0; ts=[(x-t0)*1440+rs for x in r['t']]
    q=[float(x) for x in o.link(r,'C2',0)]; y=[float(x) for x in o.node(r,'J2',0)]
    S=[(a-120,b,c) for a,b,c in zip(ts,q,y) if a>=120]; t=[a for a,b,c in S]; q=[b for a,b,c in S]; y=[c for a,b,c in S]
    qr=[nw['interp'](a,nw['tr'],nw['qr6']) for a in t]; yr=[nw['interp'](a,nw['tr'],nw['yr4']) for a in t]
    n=len(t); rmse=math.sqrt(sum((a-b)**2 for a,b in zip(q,qr))/n); mn=sum(qr)/n; nse=1-sum((a-b)**2 for a,b in zip(q,qr))/sum((b-mn)**2 for b in qr)
    ip=max(range(n),key=lambda k:q[k]); jp=max(range(n),key=lambda k:qr[k])
    rec('wave',m,peak=q[ip],peak_err=100*(q[ip]-qr[jp])/qr[jp],tp_err=t[ip]-t[jp],rmse=rmse,nse=nse,y_err=max(abs(a-b) for a,b in zip(y,yr)),**i)
json.dump(dict(modes=MODES,tests=R,S=E_['S'],hs=E_['hs'],T0=T0),open(f'/root/rp/tests/v/{TAG}.json','w'))
print('done')
