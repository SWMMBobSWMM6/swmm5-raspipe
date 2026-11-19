"""Version 1.4 of the app: every HEC-RAS number it quotes, regenerated from HEC-RAS 7.0.2 results (copy C, 1-minute
hydrograph output) and engine 1.3. Writes tests/v/ras14.json and the EXTRAN 1 sample deck the app runs.
  python3 app14.py            (about two minutes)
Plans: p06 Extran 1, p02 Extran 2, p03 Extran 4 (weir), p04 Extran 5 (orifice). p01 Extran 7 is left out: RAS runs
its pump through a pump station and rules, which this deck builder does not translate."""
import sys,os,re,json,subprocess,numpy as np
H='/root/rp/hecras'; sys.path.insert(0,H+'/cmp'); sys.path.insert(0,'/root/rp/tests')
import rasread,outread,cmp13,mkdeck_extran as M
RP='/root/rp/bin/swmm5_rp13'; EPA='/root/rp/ref/swmm5_ref'; W=H+'/cmp/a14'
SW=H+'/orig/SWMM Extran Datasets/'
PLANS=[('p06','Extran 1','EXTRAN 1 example.inp'),('p02','Extran 2','EXTRAN 2 example.inp'),('p03','Extran 4, weir','EXTRAN 4 example.inp'),('p04','Extran 5, orifice','EXTRAN 5 Example.inp')]
RPO=dict(FLOW_ROUTING='RASPIPE',RASPIPE_EQUATIONS='DW',RASPIPE_CELL_LENGTH=100,RASPIPE_MAX_CELLS=100,RASPIPE_THETA=1.0,RASPIPE_COURANT=0.9,RASPIPE_INITIAL_STAGE='YES',RASPIPE_WARMUP=0)
VAR=[('epa','EPA 5.2.4',EPA,dict(FLOW_ROUTING='DYNWAVE'),False),('epa_rim','EPA 5.2.4, rim matched',EPA,dict(FLOW_ROUTING='DYNWAVE'),True),
     ('rp','RASPIPE',RP,RPO,False),('rp_rim','RASPIPE, rim matched',RP,RPO,True),
     ('pa','RASPIPE, full-pipe storage',RP,dict(RPO,RASPIPE_PRESSURE_AREA=12.566),False),('pa_rim','RASPIPE, full-pipe storage, rim matched',RP,dict(RPO,RASPIPE_PRESSURE_AREA=12.566),True)]
def run(exe,inp):
    b=inp[:-4]
    for x in ('.rpt','.out'):
        if os.path.exists(b+x): os.remove(b+x)
    subprocess.run([exe,inp,b+'.rpt',b+'.out'],capture_output=True,timeout=600); return outread.read(b+'.out'),open(b+'.rpt',errors='replace').read()
def crowns(R):
    "Timing level at each node: 2 ft below RAS's own plateau head (its head at 2:00), so filling and draining are timed on the steep part of the rise."
    t=R['t']; i=int(np.argmin(np.abs(t-2.0)))
    return {k:float(v[i])-2.0 for k,v in R['ws'].items()}
res=dict(plans=[],build=open('/root/rp/build_id13.txt').read().strip())
for p,name,inp in PLANS:
    hdf=f'{H}/runC/ExtranTestImport.{p}.hdf'; R0=rasread.read(hdf); dt=R0['plan'].get('Computation Time Step Base','10SEC')
    rs='0:00:%02d'%int(re.match(r'(\d+)',dt).group(1)); pl=dict(plan=p,name=name,ras=R0['version'],step=rs,rows={})
    for key,lab,exe,o,rim in VAR:
        f=f'{W}/{p}_{key}.inp'; R=cmp13.deck(hdf,SW+inp,f,dict(o,ROUTING_STEP=rs),rim=rim); O,rpt=run(exe,f)
        sc=cmp13.score(R,O); pl['rows'][key]=dict(label=lab,**sc)
        if p=='p06':
            lv=crowns(R); up=['80408','80608','82309']
            pl['rows'][key]['timing']={k:list(v) for k,v in cmp13.timing(R,O,up,lv).items()}
            pl['rows'][key]['ver']=(re.search(r'Version \.+ (.+)',rpt) or [None,'EPA'])[1]
            inv={k:v['inv'] for k,v in R['geom_nodes'].items()}
            pl.setdefault('series',{})[key]={k:[round(float(x),3) for x in (np.array(outread.node(O,k,0))+inv[k])] for k in ('82309','80608','81009')}
            pl['series'][key]['q1602']=[round(float(x),3) for x in outread.link(O,'1602',0)]
    if p=='p06':
        pl['ras']={k:[round(float(x),3) for x in R0['ws'][k][1:]] for k in ('82309','80608','81009')}; pl['ras']['q1602']=[round(float(x),3) for x in R0['qmid']['1602'][1:]]
        pl['t']=[round(float(x),5) for x in R0['t'][1:]]; pl['lv']={k:round(v,3) for k,v in crowns(R0).items() if k in ('80408','80608','82309')}
    res['plans'].append(pl); print(name,{k:(round(v['hmean'],3),round(v['qmean']*100,2),round(v['h']*100,1),round(v['q']*100,1)) for k,v in pl['rows'].items()},flush=True)
# --- the sample deck for the app: Extran 1 as RAS stores it, rim matched, with RAS's own series to plot beside it
hdf=f'{H}/runC/ExtranTestImport.p06.hdf'; f=f'{W}/sample_extran1.inp'
R=cmp13.deck(hdf,SW+'EXTRAN 1 example.inp',f,dict(FLOW_ROUTING='DYNWAVE',ROUTING_STEP='0:00:10'),rim=True)
outs={k for k,v in R['geom_nodes'].items() if v['type'] in ('Culvert Opening','External')}
res['sample']=dict(file=f,inp=open(f).read(),ref=dict(t=[round(float(x),5) for x in R['t'][1:]],
  head={M.sid(k):[round(float(x),3) for x in v[1:]] for k,v in R['ws'].items() if k not in outs},
  inv={M.sid(k):R['geom_nodes'][k]['inv'] for k in R['ws'] if k not in outs},
  flow={M.sid(k):[round(float(x),3) for x in v[1:]] for k,v in R['qmid'].items()}),
  rims={M.sid(n):dict(terr=d['terr'],peak=round(float(R['ws'][n].max()),3)) for n,d in R['geom_nodes'].items() if d['inlet'] and n in R['ws'] and float(R['ws'][n].max())>d['terr']})
# --- volume check on RAS's own cell tables, Extran 1 and Extran 2
vc={}
for p in ('p06','p02'):
    out=subprocess.run(['python3',H+'/cmp/rasvol2.py',f'{H}/runC/ExtranTestImport.{p}.hdf'],capture_output=True,text=True).stdout
    vc[p]=json.load(open('/root/rp/tests/v/ras_slot_volume.json'))
res['volume']=vc
json.dump(vc['p06'],open('/root/rp/tests/v/ras_slot_volume.json','w'))
json.dump(res,open('/root/rp/tests/v/ras14.json','w'))
print('written')
