import json,collections,sys
R=[json.loads(l) for l in open(sys.argv[1])]
print(len(R),collections.Counter(r.get('skip','run') for r in R))
R=[r for r in R if 'rp' in r or 'ref_rc' in r]
print('ran',len(R))
print('rp rc',collections.Counter(r.get('rp_rc') for r in R),'ref rc',collections.Counter(r.get('ref_rc') for r in R))
e=[r for r in R if r.get('ref',{}).get('err')]
print('stock input errors',len(e))
bad=[r for r in R if not r.get('ref',{}).get('err') and (r.get('rp_rc')!=0 or (r.get('rp',{}).get('cont') is None))]
print('bad',len(bad),[ (r['inp'].split('/')[-1],r['rp_rc'],r.get('rp',{}).get('err'),r.get('ref_t'),r.get('rp_t')) for r in bad][:14])
ok=[r for r in R if r.get('rp',{}).get('cont') is not None and r.get('ref',{}).get('cont') is not None]
def st(v):
    v=sorted(v); n=len(v); return f'med {v[n//2]:.3f} p90 {v[int(.9*n)]:.3f} p99 {v[int(.99*n)]:.3f} max {v[-1]:.3f}'
print('n',len(ok),'RP |cont|',st([abs(r['rp']['cont']) for r in ok]))
print('  stock  |cont|',st([abs(r['ref']['cont']) for r in ok]))
print('worse than 1%: RP',sum(abs(r['rp']['cont'])>1 for r in ok),' stock',sum(abs(r['ref']['cont'])>1 for r in ok))
print('RP worst',[(abs(r['rp']['cont']),r['inp'].split('/')[-1],r['rp'].get('unconv'),r['rp'].get('nested'),r['rp'].get('ledger')) for r in sorted(ok,key=lambda r:-abs(r['rp']['cont']))[:10]])
q=[r['qdiff']['med'] for r in ok if r.get('qdiff')]
print('peak Q diff per model: median of medians',sorted(q)[len(q)//2] if q else None, 'p90',sorted(q)[int(.9*len(q))] if q else None)
print('time ratio rp/ref',st([r['rp_t']/max(r['ref_t'],.01) for r in ok]))
print('trials',st([r['rp']['trials'] or 0 for r in ok]),' fact',st([r['rp']['fact'] or 0 for r in ok]))
print('fails',sum(1 for r in ok if (r['rp'].get('unconv') or 0)>0), 'models with nested', sum(1 for r in ok if (r['rp'].get('nested') or 0)>0))
