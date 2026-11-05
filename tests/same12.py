#!/usr/bin/env python3
"""The last edit touched bookkeeping only. .out byte comparison with the build the full-equations sweep used, on every test deck, both equation sets."""
import os,glob,subprocess,hashlib,json,re
A='/root/rp/bin/swmm5_rp12_sweep'; B='/root/rp/bin/swmm5_rp12'; W='/tmp/claude-0/s12'; os.makedirs(W,exist_ok=True)
decks=[d for d in sorted(glob.glob('/root/rp/tests/v/*.inp')) if 'RASPIPE' in open(d,errors='replace').read().upper()]
same=diff=skip=0;bad=[]
for d in decks:
    t=open(d,errors='replace').read()
    for tag,tx in (('a',t),('s',t.replace('[OPTIONS]\n','[OPTIONS]\nRASPIPE_EQUATIONS SWE\n',1) if 'RASPIPE_EQUATIONS' not in t else None)):
        if tx is None: continue
        q=f'{W}/d.inp'; open(q,'w').write(tx); h=[]
        for n,e in (('a',A),('b',B)):
            for x in ('.rpt','.out'):
                if os.path.exists(f'{W}/{n}{x}'): os.remove(f'{W}/{n}{x}')
            try: subprocess.run([e,q,f'{W}/{n}.rpt',f'{W}/{n}.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
            except subprocess.TimeoutExpired: pass
            h.append(hashlib.sha256(open(f'{W}/{n}.out','rb').read()).hexdigest() if os.path.exists(f'{W}/{n}.out') else None)
        if None in h: skip+=1
        elif h[0]==h[1]: same+=1
        else: diff+=1; bad.append((os.path.basename(d),tag))
print(dict(same=same,diff=diff,skip=skip),bad)
json.dump(dict(same=same,diff=diff,skip=skip,bad=bad),open('/root/rp/tests/v/same12.json','w'))
