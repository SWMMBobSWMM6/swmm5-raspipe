"""Build a SWMM deck that describes the HEC-RAS EXTRAN pipe network exactly as RAS stores it.
The open channel and 2D surface below 16009 are replaced by RAS's own computed stage at 16009."""
import sys,re
sys.path.insert(0,'/root/rp/hecras/cmp')
import rasread
def sid(n): return n.replace(' ','_')
def build(hdf,swmm_inp,out,opts,minsurf=12.566,deep_no_inlet=True):
    R=rasread.read(hdf); N=R['geom_nodes']; C=R['geom_conds']
    src=open(swmm_inp).read()
    def sec(name):
        m=re.search(r'^\['+name+r'\][^\n]*\n(.*?)(?=^\[)',src,re.S|re.M); return m.group(1) if m else ''
    ts=sec('TIMESERIES'); inflows=sec('INFLOWS')
    L=['[TITLE]',f'EXTRAN as stored in {hdf.split("/")[-1]}: RAS geometry, RAS stage at 16009','','[OPTIONS]',
       'FLOW_UNITS CFS','INFILTRATION HORTON','LINK_OFFSETS ELEVATION','MIN_SLOPE 0','ALLOW_PONDING NO','SKIP_STEADY_STATE NO',
       'START_DATE 01/01/1988','START_TIME 00:00:00','REPORT_START_DATE 01/01/1988','REPORT_START_TIME 00:00:00',
       'END_DATE 01/01/1988','END_TIME 06:00:00',f'REPORT_STEP 00:{int(round((R["t"][1]-R["t"][0])*60)):02d}:00','WET_STEP 00:05:00','DRY_STEP 01:00:00',
       f"ROUTING_STEP {opts.pop('ROUTING_STEP')}",'INERTIAL_DAMPING NONE','NORMAL_FLOW_LIMITED SLOPE','VARIABLE_STEP 0',
       f'MIN_SURFAREA {minsurf}','LENGTHENING_STEP 0']
    L+= [f'{k} {v}' for k,v in opts.items()]
    out_nodes=[n for n,d in N.items() if d['type'] in ('Culvert Opening','External')]
    L+=['','[JUNCTIONS]']; ST=[]
    for n,d in N.items():
        if n in out_nodes: continue
        depth=d['depth'] if (d['inlet'] or not deep_no_inlet) else 100.0
        if depth<=0: depth=100.0
        if d['base']>0: ST.append(f'{sid(n)} {d["inv"]:.3f} {depth:.3f} 0 FUNCTIONAL 0 0 {d["base"]:.3f} 0 0'); continue
        L.append(f'{sid(n)} {d["inv"]:.3f} {depth:.3f} 0 0 0')
    if ST: L+=['','[STORAGE]']+ST
    L+=['','[OUTFALLS]']+[f'{sid(n)} {N[n]["inv"]:.3f} TIMESERIES RAS_STAGE_{sid(n)} NO' for n in out_nodes]
    L+=['','[CONDUITS]']
    for c,d in C.items(): L.append(f'{sid(c)} {sid(d["us"])} {sid(d["ds"])} {d["L"]:.3f} {d["n"]:.5f} {d["ue"]:.3f} {d["de"]:.3f} 0 0')
    L+=['','[XSECTIONS]']
    for c,d in C.items():
        if d['shape'].lower().startswith('circ'): L.append(f'{sid(c)} CIRCULAR {d["rise"]} 0 0 0 1')
        else: L.append(f'{sid(c)} RECT_CLOSED {d["rise"]} {d["span"]} 0 0 1')
    L+=['','[INFLOWS]',inflows.strip(),'','[TIMESERIES]',ts.strip()]
    for n in out_nodes:
        for i,(t,z) in enumerate(zip(R['t'],R['ws'][n])):
            h=int(round(t*60)); L.append(f'RAS_STAGE_{sid(n)} 01/01/1988 {h//60:02d}:{h%60:02d} {z:.4f}')
    L+=['','[REPORT]','NODES ALL','LINKS ALL','']
    open(out,'w').write('\n'.join(L)+'\n'); return R
if __name__=='__main__':
    pass
