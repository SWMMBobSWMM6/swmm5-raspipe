#!/usr/bin/env python3
"""Diffusion wave is untouched by the v1.2 advection change: .out byte comparison with frozen v1.1."""
import os,glob,subprocess,hashlib,random,json,re
A='/root/rp/bin/swmm5_rp11_final2'; B='/root/rp/bin/swmm5_rp12'
W='/tmp/claude-0/dws'; os.makedirs(W,exist_ok=True)
decks=sorted(glob.glob('/root/rp/tests/v/*.inp'))
def rp(d):
    t=open(d,errors='replace').read().upper()
    return 'RASPIPE' in t and 'RASPIPE_EQUATIONS' not in t.replace('RASPIPE_EQUATIONS DW','')
decks=[d for d in decks if rp(d)]
random.seed(7); random.shuffle(decks); decks=decks[:48]
same=diff=fail=0; bad=[]
for d in decks:
    r={}
    for n,e in (('a',A),('b',B)):
        p=f'{W}/{n}'
        for x in ('.rpt','.out'):
            if os.path.exists(p+x): os.remove(p+x)
        try: subprocess.run([e,d,p+'.rpt',p+'.out'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=40)
        except subprocess.TimeoutExpired: pass
        r[n]=hashlib.sha256(open(p+'.out','rb').read()).hexdigest() if os.path.exists(p+'.out') else None
    if r['a'] is None or r['b'] is None: fail+=1
    elif r['a']==r['b']: same+=1
    else: diff+=1; bad.append(os.path.basename(d))
print(dict(n=len(decks),same=same,diff=diff,unrun=fail)); print(bad)
json.dump(dict(n=len(decks),same=same,diff=diff,unrun=fail,bad=bad),open('/root/rp/tests/v/dwsame.json','w'))
