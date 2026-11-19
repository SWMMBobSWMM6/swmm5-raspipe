# --- version 1.4: HEC-RAS 7.0.2. Every number here comes from hecras/cmp/app14.py, hecras/cmp/rerun14.py and the
# parity script for engine 1.3 (wasm/parity13.json). Nothing is typed in by hand.
import math
RS=json.load(open(R+'/tests/v/ras14.json')); RR=json.load(open(R+'/tests/v/ras_rerun.json')); P13=json.load(open(R+'/wasm/parity13.json'))
B13=RS['build']; PL={p['plan']:p for p in RS['plans']}; X1=PL['p06']; XR=X1['rows']
hm=lambda m:f"{m//60}:{m%60:02d}"
f3=lambda x:f"{x:.3f}"
# score table, Extran 1
ORDER=[('rp','RASPIPE'),('rp_rim','RASPIPE, rim at 80608 raised to RAS’s ponded head'),('pa','RASPIPE with full-pipe storage'),('pa_rim','RASPIPE with full-pipe storage, rim raised'),('epa','EPA 5.2.4 DYNWAVE'),('epa_rim','EPA 5.2.4, rim raised')]
def srow(r,lab): return [lab,f"{100*r['h']:.0f}%",f"{100*r['q']:.0f}%",f"{r['hmean']:.3f} ft",f"{100*r['qmean']:.2f}%",f"{r['he']} of {r['hn']} / {r['qe']} of {r['qn']}"]
score=dict(head=['Run against HEC-RAS 7.0.2','Heads within 0.1 ft','Flows within 2% of peak','Mean head difference','Mean flow difference','Nodes / pipes passing 90% of instants'],rows=[srow(XR[k],l) for k,l in ORDER])
# held-out plans, all rim matched
ho=dict(head=['HEC-RAS plan','RASPIPE, mean head difference','With full-pipe storage','RASPIPE, mean flow difference','With full-pipe storage','EPA 5.2.4, mean head difference'],
  rows=[[('EXTRAN 1 (storage value set here)' if p['plan']=='p06' else p['name'].replace('Extran','EXTRAN')),f3(p['rows']['rp_rim']['hmean'])+' ft',f3(p['rows']['pa_rim']['hmean'])+' ft',f"{100*p['rows']['rp_rim']['qmean']:.2f}%",f"{100*p['rows']['pa_rim']['qmean']:.2f}%",f3(p['rows']['epa_rim']['hmean'])+' ft'] for p in RS['plans']])
# timing
T=XR['rp_rim']['timing']; TP=XR['pa_rim']['timing']
timing=dict(head=['Node','Level (ft)','RAS reaches it','RASPIPE','With storage','RAS leaves it','RASPIPE','With storage'],
  rows=[[k,f"{X1['lv'][k]:.2f}",hm(T[k][0]),hm(T[k][1]),hm(TP[k][1]),hm(T[k][2]),hm(T[k][3]),hm(TP[k][3])] for k in ('80408','80608','82309')])
fillR=sorted(T[k][0] for k in T); fillP=sorted(T[k][1] for k in T); fillS=sorted(TP[k][1] for k in TP); drR=sorted(T[k][2] for k in T); drP=sorted(T[k][3] for k in T); drS=sorted(TP[k][3] for k in TP)
rng=lambda a:hm(a[0]) if a[0]==a[-1] else hm(a[0])+' to '+hm(a[-1])
early=max(a-b for a,b in zip([T[k][0] for k in T],[T[k][1] for k in T]))
# volume check on RAS's own tables
V6=RS['volume']['p06']; V2=RS['volume']['p02']; at=lambda V,m:next(r for r in V if r['m']==m)
pl6=at(V6,150); pl2=at(V2,150); r6=pl6['gap']/pl6['over']; r2=pl2['gap']/pl2['over']; aft=max(abs(at(V6,m)['gap']) for m in (240,360))
# 81009 at 2:00
t=X1['t']; i2=min(range(len(t)),key=lambda i:abs(t[i]-2.0))
h81r=X1['ras']['81009'][i2]; h81p=X1['series']['rp_rim']['81009'][i2]; h81s=X1['series']['pa_rim']['81009'][i2]
def ynorm(Q,n,D,S):
    A=lambda y:D*D/8*(2*math.acos(1-2*y/D)-math.sin(2*math.acos(1-2*y/D))); P=lambda y:D*math.acos(1-2*y/D)
    lo,hi=1e-6,0.938*D
    for _ in range(200):
        y=(lo+hi)/2; q=1.486/n*A(y)*(A(y)/P(y))**(2/3)*S**.5
        lo,hi=(y,hi) if q<Q else (lo,y)
    return y
yn=ynorm(50.0,0.015,4.5,(128.2-117.5)/5100.0); h81n=128.2+yn
# plateau at 82309 and pipe 1602
h82r=X1['ras']['82309'][i2]; h82p=X1['series']['rp_rim']['82309'][i2]; q16r=X1['ras']['q1602'][i2]; q16p=X1['series']['rp_rim']['q1602'][i2]
# rerun check
sh=RR['shipped']; worst_head=max(v['head'] for v in sh.values())
ADJ=('Outfall','1600')   # the two conduits that meet at the outfall junction
wf=max(((p,k,e) for p,v in sh.items() for k,e,_ in v['flows'] if k not in ADJ),key=lambda r:r[2])
adjo=max(e for p,v in sh.items() if p!='p06' for k,e,_ in v['flows'] if k in ADJ); fo=dict((k,e) for k,e,_ in sh['p06']['flows'])
iv=RR['interval']; ivh=max(v['head'] for v in iv.values()); ivo=dict((k,(e,tt)) for k,e,tt in iv['p06']['flows'])
pnames={'p01':'Extran 7','p02':'Extran 2','p03':'Extran 4','p04':'Extran 5','p06':'Extran 1'}
rerun=(f"HEC-RAS 7.0.2 reproduces HEC's shipped results. Two runs of the same five plans on Bob's Windows machine match to the last bit in all {RR['ab']['same']:,} result datasets. "
  f"Against the files HEC shipped, made with 7.0 and 7.0.1, heads agree within {worst_head:.3f} ft on every plan, and mid-pipe flows within {100*wf[2]:.1f}% of peak away from the outfall. "
  f"The two conduits that meet at the outfall differ by up to {100*adjo:.1f}% on the other plans, and on EXTRAN 1 by {100*fo['1600']:.1f}% on pipe 1600 and {100*fo['Outfall']:.0f}% on the 50 ft outfall box at 0:40. Changing only the hydrograph output interval to 1 minute moved RAS's results by up to {ivh:.3f} ft, and {100*ivo['Outfall'][0]:.1f}% of peak at one instant on the outfall box.")
ser=dict(t=t,ras=X1['ras']['82309'],rp=X1['series']['rp_rim']['82309'],pa=X1['series']['pa_rim']['82309'],epa=X1['series']['epa_rim']['82309'])
vol=dict(m=[r['m'] for r in V6],gap=[round(r['gap'],1) for r in V6],over=[round(r['over'],2) for r in V6])
rp=lambda k,c:XR[k][c]
notes=[f"Deck: EXTRAN 1 built from the geometry stored in RAS's own results file, with RAS's water surface at 16009 as the outfall stage, since RAS has a 2D area where SWMM has the open channel. Both engines use diffusion wave, Courant 0.9 and 100 ft cells. RASPIPE's mid-pipe flow is compared with RAS's mid-pipe face, at RAS's 1-minute output.",
 f"Flooding at 80608. RAS ponds on its 2D surface and the head reaches {RS['sample']['rims']['80608']['peak']:.2f} ft. SWMM caps it at the {RS['sample']['rims']['80608']['terr']:.1f} ft rim. Raising that one rim to RAS's peak is what rim matched means.",
 f"With the rim raised, the plateau head at 82309 agrees to {abs(h82p-h82r):.2f} ft ({h82p:.3f} against {h82r:.3f}) and pipe 1602 carries {q16p:.2f} cfs against {q16r:.2f}.",
 f"Filling and draining. Without full-pipe storage RASPIPE's three upper nodes rise through a level 2 ft below RAS's plateau at {rng(fillP)}, against {rng(fillR)} for RAS, up to {early} minutes early. With 12.566 ft² per full cell they rise at {rng(fillS)}. They leave it at {rng(drP)} without storage, {rng(drS)} with it, against {rng(drR)}.",
 f"Why. RAS's own cell tables end at the crown, yet while pipes 8040, 8060 and 1602 are full, {pl6['gap']:,.0f} ft³ more water is in them than those tables can hold, {r6:.2f} ft² per pressurized cell per ft of head ({r2:.2f} on EXTRAN 2). After they drain the difference is no more than {aft:.0f} ft³. EPA's default manhole area, MIN_SURFAREA, is 12.566 ft².",
 f"81009 is not explained. At the top of the 4.5 ft pipe carrying 50 cfs, RASPIPE sits at {h81p:.2f} ft, which is Manning's normal depth ({h81n:.2f}). RAS sits at {h81r:.2f}. A part-full steady deck is the next test.",
 f"EXTRAN 4 never runs its pipes full, so the storage changes nothing there. EXTRAN 5's 0.7 ft head errors come from somewhere else, perhaps its 800 ft² storage node or the orifice; not traced. EXTRAN 7 is left out because RAS runs its pump through a pump station and rules.",
 f"The pass band, set before the runs, was 90% of nodes and pipes each within tolerance at 90% of instants. Every plan misses it, with or without the storage."]
data['ras']=dict(rerun=rerun,score=score,ho=ho,timing=timing,ser=ser,vol=vol,notes=notes,r6=round(r6,2),r2=round(r2,2),gap=round(pl6['gap']),
  null=P13['null']['text'],par=P13['parity']['text'])
# presets that put the RAS line on the Run chart
RASO=dict(cell=100,maxc=100,cour=.9,theta=1,warm=0,stg='YES',eqn='DW',dt='',vs='')
data['presets'][:0]=[
 dict(label='HEC-RAS 7.0.2: EXTRAN 1, head at 82309',file='extran1_hecras.inp',elem='82309',vari='head',o=dict(RASO,pa=0),note=f"The dashed line is RAS's stored result. RASPIPE as in 1.2 rises to the plateau up to {early} minutes early, because a full pipe cell holds no more water."),
 dict(label='HEC-RAS 7.0.2: same, full-pipe storage 12.566 ft²',file='extran1_hecras.inp',elem='82309',vari='head',o=dict(RASO,pa=12.566),note='Each full pipe cell now stores 12.566 ft² per ft of head, the value measured from RAS on this deck. The rise moves onto RAS’s line.'),
 dict(label='HEC-RAS 7.0.2: flow in pipe 1602',file='extran1_hecras.inp',elem='1602',vari='flow',o=dict(RASO,pa=12.566),note='RASPIPE’s flow is its mid-pipe face, the same place RAS’s line comes from.')]
for p in data['presets']: p['o'].setdefault('pa',0)
data['defects']+= [
 ["RP-17","A full pipe cell held no water above its crown. HEC-RAS 7.0.2 holds about "+f"{r6:.1f}"+" ft² per cell per ft of head on EXTRAN 1, so RASPIPE's upper nodes rose to the plateau up to "+str(early)+" minutes early. RASPIPE_PRESSURE_AREA added in engine 1.3, off by default.","option","hi"],
 ["RP-18",f"81009 sits {h81p-h81r:.2f} ft above RAS on EXTRAN 1, at Manning's normal depth. Which engine is right is not settled.","open","hi"],
 ["RP-19","EXTRAN 5's mean head difference is 0.7 ft, with or without full-pipe storage. Not traced.","open","hi"]]
data['limits']=data['limits'].replace('No field data. No run of HEC-RAS.',"No field data. HEC-RAS 7.0.2 has been run on four of HEC's own EXTRAN examples, on one Windows machine, and every plan misses the pass band set beforehand. The full-pipe storage value came from one of those plans and is not documented by HEC.")
data['options'].append(['RASPIPE_PRESSURE_AREA','0','Storage above the crown of each full pipe cell, ft² per cell per ft of head (m² in SI models). 0 keeps a full pipe rigid, as in 1.2. 12.566 is what HEC-RAS 7.0.2 held on EXTRAN 1. New in engine 1.3.'])
data['method'].append(['Full pipe storage',"Not stated. A cell's property table ends at the crown, and above it the water surface is the crown plus P/γ.",'Off by default. RASPIPE_PRESSURE_AREA gives each full cell a fixed plan area above its crown, and each junction the same per barrel of the highest pipe it borrows from.',f"Measured from RAS's own results: {r6:.2f} ft² per full cell per ft of head on EXTRAN 1, {r2:.2f} on EXTRAN 2. With 12.566 the mean head difference on EXTRAN 1 falls from {rp('rp_rim','hmean'):.3f} to {rp('pa_rim','hmean'):.3f} ft."])
data['measures'].insert(0,dict(t='Against HEC-RAS 7.0.2',big=f"{rp('pa_rim','hmean'):.3f} ft",sub=f"mean head difference on EXTRAN 1 with full-pipe storage and the flooded rim matched; {rp('rp_rim','hmean'):.3f} ft without the storage, EPA {rp('epa_rim','hmean'):.3f}. Every plan misses the pass band."))
data['headline']=(f"<b>HEC-RAS 7.0.2, EXTRAN 1:</b> mean head difference {rp('rp_rim','hmean'):.3f} ft, {rp('pa_rim','hmean'):.3f} with full-pipe storage, EPA {rp('epa_rim','hmean'):.3f}. "+data['headline']).replace(f'Build <code>{BUILD}</code>.',f'Engine 1.3, build <code>{B13}</code>.')
data['prov']=data['prov'].replace(f"<code>raspipe.c</code> 1.2, build <code>{BUILD}</code>",f"<code>raspipe.c</code> 1.3, build <code>{B13}</code>").replace('<b>Verify data:</b> native runs, November 2026, Linux, one machine.',f"<b>Verify data:</b> native runs, November 2026, Linux, one machine. Engine 1.2 results carried to 1.3 by byte comparison: {P13['null']['text']}. <b>HEC-RAS:</b> 7.0.2, run on Bob's Windows machine, November 2026.")
assert 'raspipe.c</code> 1.3' in data['prov'] and 'Engine 1.3' in data['headline']
aiuse[0]=aiuse[0].replace('asked for SWMM6 FV and the SWMM6 modified dynamic wave to be compared in version 1.3,','asked for SWMM6 FV and the SWMM6 modified dynamic wave to be compared in version 1.3, installed HEC-RAS 7.0.2 and ran it on his own machine for version 1.4,')
aiuse[1]=aiuse[1]+" For version 1.4 it planned the check against HEC-RAS, wrote the batch files Bob ran, read RAS's HDF5 results, built SWMM decks from the geometry RAS stores, scored the engines, measured the storage RAS keeps in full pipes from RAS's own cell tables, added <code>RASPIPE_PRESSURE_AREA</code> to the engine, and rebuilt this page and its documents."
aiuse[3]=aiuse[3].replace('It has not been compared with a run of HEC-RAS or with field data.',"It has not been compared with field data. The HEC-RAS comparison covers four of HEC's EXTRAN examples, and no person has checked the deck translation line by line.")
data['aiuse']=aiuse
srcR=[["HEC-RAS 7.0.2, U.S. Army Corps of Engineers Hydrologic Engineering Center. Run here; not part of this page","https://www.hec.usace.army.mil/software/hec-ras/download.aspx"],
 ["HEC, SWMM EXTRAN example projects for HEC-RAS pipe networks, with HEC's own result files and the SWMM decks they came from",""]]
data['sources']=srcR+data['sources']; sources[:]=data['sources']
val.update({'ras.gap':f"{pl6['gap']:,.0f}",'ras.r6':f"{r6:.2f}",'ras.r2':f"{r2:.2f}",'ras.aft':f"{aft:.0f}",'ras.ab':f"{RR['ab']['same']:,}",'ras.shiph':f"{worst_head:.3f}",'ras.shipq':f"{100*wf[2]:.1f}",'ras.ivh':f"{ivh:.3f}",
 'ras.h_rp':f"{rp('rp_rim','hmean'):.3f}",'ras.h_pa':f"{rp('pa_rim','hmean'):.3f}",'ras.h_epa':f"{rp('epa_rim','hmean'):.3f}",'ras.h_rp0':f"{rp('rp','hmean'):.3f}",'ras.h_epa0':f"{rp('epa','hmean'):.3f}",
 'ras.q_rp':f"{100*rp('rp_rim','qmean'):.2f}",'ras.q_pa':f"{100*rp('pa_rim','qmean'):.2f}",'ras.q_epa':f"{100*rp('epa_rim','qmean'):.2f}",
 'ras.hin_rp':f"{100*rp('rp','h'):.0f}",'ras.hin_rim':f"{100*rp('rp_rim','h'):.0f}",'ras.hin_epa':f"{100*rp('epa','h'):.0f}",'ras.qin_rp':f"{100*rp('rp','q'):.0f}",'ras.qin_epa':f"{100*rp('epa','q'):.0f}",
 'ras.fillR':rng(fillR),'ras.fillP':rng(fillP),'ras.fillS':rng(fillS),'ras.drR':rng(drR),'ras.drP':rng(drP),'ras.drS':rng(drS),'ras.early':str(early),
 'ras.h81r':f"{h81r:.2f}",'ras.h81p':f"{h81p:.2f}",'ras.h81n':f"{h81n:.2f}",'ras.h82r':f"{h82r:.3f}",'ras.h82p':f"{h82p:.3f}",'ras.q16r':f"{q16r:.2f}",'ras.q16p':f"{q16p:.2f}",
 'ras.x2_rp':f3(PL['p02']['rows']['rp_rim']['hmean']),'ras.x2_pa':f3(PL['p02']['rows']['pa_rim']['hmean']),'ras.x5_rp':f3(PL['p04']['rows']['rp_rim']['hmean']),'ras.x5_pa':f3(PL['p04']['rows']['pa_rim']['hmean']),'ras.x4':f3(PL['p03']['rows']['rp_rim']['hmean']),
 'ras.peak80608':f"{RS['sample']['rims']['80608']['peak']:.2f}",'ras.null':P13['null']['text'],'ras.par':P13['parity']['text'],'b13':B13})
RASSAMPLE=RS['sample']
# browser build parity, now engine 1.3 (replaces the 1.2 figures the essay quoted)
W13=P13['parity']['worst_flow']
val.update({'wasm.same':str(P13['parity']['same']),'wasm.n':str(P13['parity']['n']),'wasm.max':f"{W13['dq']:.2f} cfs on an {W13['peak']:.0f} cfs link" if round(W13['peak'])==8 else f"{W13['dq']:.2f} cfs on a {W13['peak']:.0f} cfs link"})
# a slot that stores 12.566 ft2 per 100 ft cell is about 0.13 ft wide; in a 4 ft pipe its pressure wave runs at sqrt(gA/T)
A4=math.pi*4*4/4; Tsl=12.566/100.0
val.update({'ras.slotw':f"{Tsl:.2f}",'ras.c4':f"{math.sqrt(32.174*A4/Tsl):.0f}",'ras.n6':str(at(V6,150)['n'])})
# how fast the heads rise at 80608 and 82309: RASPIPE's largest 2-minute rise against RAS's largest 1-minute rise
def rise(a,k): return max(a[i+k]-a[i] for i in range(len(a)-k))
val.update({'ras.jump':f"{max(rise(X1['series']['rp_rim'][n],2) for n in ('80608','82309')):.1f}",'ras.rasrate':f"{max(rise(X1['ras'][n],1) for n in ('80608','82309')):.1f}"})
val['pump.rp']=f"{pv['rp']:.3f}"
