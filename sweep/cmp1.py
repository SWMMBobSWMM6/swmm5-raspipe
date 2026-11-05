import sys,re,subprocess,shutil
sys.path.insert(0,'/root/rp/tests')
import outread as o
name=sys.argv[1]
P=subprocess.run(f"grep -h '/{name}' /root/rp/sweep/pilot.txt | head -1",shell=True,capture_output=True,text=True).stdout.strip()
print(P)
d='/root/rp/sweep/t/'
s=open(P,errors='replace').read()
open(d+'a.inp','w').write(s)
open(d+'b.inp','w').write(re.sub(r'^(\s*FLOW_ROUTING\s+)\S+',lambda g:g.group(1)+'RASPIPE',s,count=1,flags=re.M|re.I))
subprocess.run(['/root/rp/ref/swmm5_ref',d+'a.inp',d+'a.rpt',d+'a.out'],stdout=subprocess.DEVNULL)
subprocess.run(['/root/rp/bin/swmm5_rp',d+'b.inp',d+'b.rpt',d+'b.out'],stdout=subprocess.DEVNULL,timeout=120)
a=o.read(d+'a.out'); b=o.read(d+'b.out')
for k in ['ROUTING_STEP','VARIABLE_STEP','REPORT_STEP','END_DATE','END_TIME','START_TIME','LINK_OFFSETS','ALLOW_PONDING','SURCHARGE_METHOD','FORCE_MAIN']:
    m=re.search(r'^\s*'+k+r'\S*\s+(\S+)',s,re.M|re.I); print(k,m.group(1) if m else None,end='; ')
print()
rows=[]
for L in a['L']:
    qa=o.link(a,L,0); qb=o.link(b,L,0)
    pa=max(abs(x) for x in qa); pb=max(abs(x) for x in qb)
    rows.append((abs(pb-pa)/max(pa,.01),L,pa,pb,qa.index(max(qa,key=abs)),qb.index(max(qb,key=abs))))
rows.sort(reverse=True)
for r in rows[:10]: print(f"{r[1]:14s} stock {r[2]:9.3f} @{r[4]}  rp {r[3]:9.3f} @{r[5]}")
print('periods',len(a['t']), 'rep',a['rstep'])
g=lambda f,k:re.findall(k,open(f,errors='replace').read())
print(g(d+'a.rpt',r'Continuity Error \(%\) \.+\s+(-?[\d.]+)'),g(d+'b.rpt',r'Continuity Error \(%\) \.+\s+(-?[\d.]+)'))
open(d+'worst.txt','w').write(rows[0][1])
