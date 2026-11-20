"""v1.3 checks: (1) null control, rp12 vs rp13 with the new option absent: .out byte for byte;
(2) wasm 1.3 vs native 1.3 on every app sample, DW and SWE, option off and on (12.566)."""
import json,subprocess,os,re,struct,sys,glob
R='/root/rp'; W='/tmp/claude-0/par13'; os.makedirs(W,exist_ok=True)
html=open(R+'/app/dist/SWMM5-RASPIPE.html').read()
m=re.search(r'const SAMPLES=(\[.*?\]);\nconst WASM_B64',html,re.S); S=json.loads(m.group(1).replace('<\\/script','</script').replace('<\\!--','<!--'))
def relerr(a,b):
    n=min(len(a),len(b))//4; x=struct.unpack(f'<{n}f',a[:n*4]); y=struct.unpack(f'<{n}f',b[:n*4]); e=0
    for u,v in zip(x,y):
        if u==u and v==v and abs(u)>1e-3: e=max(e,abs(u-v)/abs(u))
    return e
def clean(d):
    for f in glob.glob(d+'/*.out')+glob.glob(d+'/*.rpt'): os.remove(f)
null=[]; par=[]; same=0; worst=0
for s in S:
    t=s['inp']; t=re.sub(r'(?mi)^\s*FLOW_ROUTING\s+\S+','FLOW_ROUTING RASPIPE',t)
    for tag,extra in (('dw',''),('swe','RASPIPE_EQUATIONS SWE\n'),('dw_pa','RASPIPE_PRESSURE_AREA 12.566\n'),('swe_pa','RASPIPE_EQUATIONS SWE\nRASPIPE_PRESSURE_AREA 12.566\n')):
        d=W+'/'+s['file'].replace('.inp','')+'_'+tag; os.makedirs(d,exist_ok=True); clean(d)
        open(d+'/m.inp','w').write(t.replace('[OPTIONS]\n','[OPTIONS]\n'+extra,1))
        subprocess.run([R+'/bin/swmm5_rp13',d+'/m.inp',d+'/n.rpt',d+'/n.out'],stdout=subprocess.DEVNULL,timeout=300)
        if '_pa' not in tag:
            subprocess.run([R+'/bin/swmm5_rp12',d+'/m.inp',d+'/o.rpt',d+'/o.out'],stdout=subprocess.DEVNULL,timeout=300)
            a=open(d+'/o.out','rb').read(); b=open(d+'/n.out','rb').read()
            null.append((s['file'],tag,'identical' if a==b else relerr(a,b)))
        subprocess.run(['node','--no-warnings',R+'/wasm/runwasi.mjs',R+'/wasm/swmm5_rp13.wasm',d,'/m.inp','/m.rpt','/m.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
        a=open(d+'/n.out','rb').read(); b=open(d+'/m.out','rb').read()
        if a==b: same+=1; par.append((s['file'],tag,'identical'))
        else:
            e=relerr(a,b); worst=max(worst,e); par.append((s['file'],tag,e))
nsame=sum(1 for r in null if r[2]=='identical')
out=dict(null=dict(same=nsame,n=len(null),rows=null),parity=dict(same=same,n=len(par),worst=worst,rows=par))
json.dump(out,open(R+'/wasm/parity13.json','w'),indent=0)
print('null',nsame,len(null)); print('parity',same,len(par),worst)
for r in par:
    if r[2]!='identical': print(r)
for r in null:
    if r[2]!='identical': print('NULL',r)
