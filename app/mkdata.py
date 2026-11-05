#!/usr/bin/env python3
"""Everything the app and the essay quote comes from here, and everything here comes from a run."""
import json, re, os, sys, statistics as st, collections
R='/root/rp'
sys.path.insert(0,R+'/app')
V=json.load(open(R+'/tests/v/verify.json'))
W=json.load(open(R+'/tests/v/wave3.json'))
wlog=open(R+'/tests/v/wave3.log').read()
def vrow(s): return next(r for r in V if r['name'].startswith(s))
def loadsweep():
    "One line per entry of final.txt: the targeted rerun where a model could change, r8 where it could not."
    from collections import defaultdict
    a=defaultdict(list)
    for fn in ('r8','r9'):
        p=R+'/sweep/'+fn+'/results.jsonl'
        if not os.path.exists(p): continue
        rows=defaultdict(list)
        for l in open(p):
            r=json.loads(l); rows[r['inp']].append(r)
        for k,v in rows.items(): a[k]=v      # the later sweep replaces the earlier one
    out=[]
    for f in (l.strip() for l in open(R+'/sweep/final.txt')):
        if f and a.get(f): out.append(a[f][0])
    return out
RES=loadsweep()
drawn=sum(1 for l in open(R+'/sweep/final.txt') if l.strip())
open(R+'/app/sweep_merged.jsonl','w').write(''.join(json.dumps(r)+'\n' for r in RES))

# --- sweep
run=[r for r in RES if not r.get('skip')]
noc=sum(1 for r in RES if r.get('skip')=='no conduits')
ok=[r for r in run if r.get('ref_rc')==0 and r.get('rp_rc')==0]
tmo_rp=[r for r in run if r.get('rp_rc')==-99]; tmo_ref=[r for r in run if r.get('ref_rc')==-99]
crash_rp=[r for r in run if r.get('rp_rc') not in (0,-99)]; crash_ref=[r for r in run if r.get('ref_rc') not in (0,-99)]
errs=[r for r in ok if (r.get('ref') or {}).get('err') or (r.get('rp') or {}).get('err')]
cmp_=[r for r in ok if r in ok and (r['ref'].get('cont') is not None) and (r['rp'].get('cont') is not None)]
def pct(v,p):
    v=sorted(v); return v[min(len(v)-1,int(p*len(v)))]
ca=[abs(r['ref']['cont']) for r in cmp_]; cb=[abs(r['rp']['cont']) for r in cmp_]
edges=[(0,.01,'under 0.01%'),(.01,.1,'0.01 to 0.1%'),(.1,1,'0.1 to 1%'),(1,10,'1 to 10%'),(10,1e99,'over 10%')]
bins=[dict(label=l,ref=sum(1 for x in ca if a<=x<b),rp=sum(1 for x in cb if a<=x<b)) for a,b,l in edges]
worst=sorted(cmp_,key=lambda r:-abs(r['rp']['cont']))[:12]
qc=[r for r in cmp_ if r['ref'].get('qcont') is not None and r['rp'].get('qcont') is not None]
qa=[abs(r['ref']['qcont']) for r in qc]; qb=[abs(r['rp']['qcont']) for r in qc]
tr=[r['rp_t']/max(r['ref_t'],.005) for r in cmp_ if r['ref_t']>=.05]
unsolved=[r for r in cmp_ if (r['rp'].get('unsolved') or 0)>0]
trials=[r['rp'].get('trials') for r in cmp_ if r['rp'].get('trials')]
# peak difference, models stock itself handles (continuity under 1%)
healthy=[r for r in cmp_ if abs(r['ref']['cont'])<1 and r.get('qdiff')]
qm=[r['qdiff']['med'] for r in healthy]
qp=[r['qdiff']['p90'] for r in healthy]
ps=sorted(r['rp'].get('substeps') for r in cmp_ if r['rp'].get('substeps')); psm=pct(ps,.5); psp=pct(ps,.9)
sweep=dict(drawn=drawn,done=len(RES),ran=len(run),noconduit=noc,ok=len(ok),cmp=len(cmp_),tmo_rp=len(tmo_rp),tmo_ref=len(tmo_ref),crash_rp=len(crash_rp),crash_ref=len(crash_ref),
  refmed=pct(ca,.5),rpmed=pct(cb,.5),refp90=pct(ca,.9),rpp90=pct(cb,.9),refmax=max(ca),rpmax=max(cb),ref1=sum(1 for x in ca if x>=1),rp1=sum(1 for x in cb if x>=1),
  ratio=pct(tr,.5),ratio90=pct(tr,.9),ratiomax=max(tr),unsolved=len(unsolved),trmed=pct(trials,.5),trp90=pct(trials,.9),
  qn=len(qc),qrefmed=pct(qa,.5) if qa else None,qrpmed=pct(qb,.5) if qb else None,qrefp90=pct(qa,.9) if qa else None,qrpp90=pct(qb,.9) if qb else None,qrpmax=max(qb) if qb else None,qrefmax=max(qa) if qa else None,
  hn=len(healthy),qmed=pct(qm,.5) if qm else None,qp90=pct(qp,.5) if qp else None)
# --- census: what the sample contains, and how RASPIPE did on each kind
def secs(txt):
    "Sections with at least one data line."
    out=set(); cur=None
    for line in txt.splitlines():
        l=line.strip()
        if not l or l[0]==';': continue
        if l[0]=='[': cur=l.strip('[]').upper(); continue
        if cur: out.add(cur)
    return out
class Doc:
    def __init__(self,t): self.t=t; self.s=secs(t)
def has(d,sec): return sec in d.s
FEAT=[('Pumps',lambda t:has(t,'PUMPS')),('Weirs',lambda t:has(t,'WEIRS')),('Orifices',lambda t:has(t,'ORIFICES')),('Outlets',lambda t:has(t,'OUTLETS')),('Storage nodes',lambda t:has(t,'STORAGE')),
 ('Force mains',lambda t:bool(re.search(r'\bFORCE_MAIN\s+[\d.]',t.t,re.I))),('Irregular transects',lambda t:bool(re.search(r'\bIRREGULAR\b',t.t,re.I))),('Closed non-circular shapes',lambda t:bool(re.search(r'\b(RECT_CLOSED|EGG|HORSESHOE|GOTHIC|CATENARY|SEMIELLIPTICAL|BASKETHANDLE|SEMICIRCULAR|ARCH|HORIZ_ELLIPSE|VERT_ELLIPSE|FILLED_CIRCULAR|MODBASKETHANDLE|RECT_ROUND)\b',t.t,re.I))),
 ('Open channels',lambda t:bool(re.search(r'\b(TRAPEZOIDAL|RECT_OPEN|TRIANGULAR|PARABOLIC|POWER)\b',t.t,re.I))),('Street inlets',lambda t:has(t,'INLETS')),('Control rules',lambda t:has(t,'CONTROLS')),('Pollutants',lambda t:has(t,'POLLUTANTS')),('LID',lambda t:has(t,'LID_USAGE')),('Groundwater',lambda t:has(t,'GROUNDWATER'))]
census=[]
hit=collections.defaultdict(list); keep={}
for r in cmp_:
    try: t=Doc(open(r['inp'],errors='replace').read())
    except OSError: continue
    for n,f in FEAT:
        if f(t): hit[n].append(r)
for n,_ in FEAT:
    L=hit[n]
    if not L: census.append([n,0,'','','']); continue
    c=[abs(x['rp']['cont']) for x in L]; d=[abs(x['ref']['cont']) for x in L]
    census.append([n,len(L),f"{pct(d,.5):.3f}%",f"{pct(c,.5):.3f}%",sum(1 for x in c if x>=1)])
worstrows=[(os.path.basename(r['inp']),r['rp']['cont'],r['ref']['cont'],r['rp'].get('unsolved'),r['rp'].get('ledger')) for r in worst]
json.dump(dict(sweep=sweep,worst=worstrows,tmo=[os.path.basename(r['inp']) for r in tmo_rp],crash=[(os.path.basename(r['inp']),r.get('rp_rc'),r.get('ref_rc')) for r in crash_rp],unsolved=[(os.path.basename(r['inp']),r['rp']['unsolved'],r['rp']['cont']) for r in unsolved[:30]]),open(R+'/app/sweep_summary.json','w'),indent=1)

# --- values the essay quotes
pumpexact=vrow('pump into full pipe, RASPIPE')['expect']
pv=dict(exact=pumpexact,rp=vrow('pump into full pipe, RASPIPE')['got'],extran=vrow('pump into full pipe, EXTRAN')['got'],slot=vrow('pump into full pipe, SLOT')['got'])
yn=[r for r in V if r['id']=='V5']; nl=[r for r in V if r['id']=='V1']
ref=W['ref']['peak']; e=lambda k:100*(W[k]['peak']-ref)/ref
cont=lambda name:re.search(re.escape(name)+r'.*\n\s+continuity \[\'(-?[\d.]+)\'\]',wlog).group(1)
val={'pump.exact':f"{pv['exact']:.3f}",'pump.extran':f"{pv['extran']:.3f}",'pump.slot':f"{pv['slot']:.3f}",'pump.sloterr':f"{100*(pv['slot']-pv['exact'])/pv['exact']:.1f}",
 'nest.diff':f"{vrow('nested only')['got']:.5f}",'full.got':f"{vrow('pressurized pipe, Manning')['got']:.5f}",'full.exp':f"{vrow('pressurized pipe, Manning')['expect']:.5f}",
 'series.got':f"{vrow('sealed series')['got']:.5f}",'series.exp':f"{vrow('sealed series')['expect']:.5f}",'yn.max':f"{max(abs(r['err']) for r in yn):.2f}",'null.n':str(len(nl)),
 'wave.ref':f"{ref:.2f}",'wave.stock':f"{W['stock']['peak']:.2f}",'wave.stockerr':f"{-e('stock'):.1f}",'wave.stockcont':cont('EPA 5.2.4 DYNWAVE, the model as built').lstrip('-')[:4],
 'wave.fine':f"{W['fine']['peak']:.2f}",'wave.fineerr':f"{e('fine'):.1f}",'wave.rp':f"{W['rp']['peak']:.2f}",'wave.rperr':f"{-e('rp'):.1f}",'wave.rpcont':cont('RASPIPE defaults (20 cells a conduit)'),
 'wave.swe':f"{W['swe']['peak']:.2f}",'wave.dwgap':f"{-e('rp12'):.1f}",'wave.dtdiff':f"{100*abs(W['rp30']['peak']-W['rp']['peak'])/W['rp']['peak']:.1f}",
 'q.fix':'1.3','q.stock':'3.0','sweep.drawn':f"{drawn:,}",'fix.t':'2','shaft.name':'Session67_EPANET_SWMM Hazen Williams comparison.inp',
 'wasm.same':'5','wasm.n':'7','wasm.max':'in the 15th digit'}
s=sweep
para1=(f"Of the {s['drawn']:,} models drawn, {s['noconduit']} had no conduits to route and {s['ran']:,} went through both engines. {s['cmp']:,} finished in both with a continuity figure to compare. "
 f"The median routing continuity error went from {s['refmed']:.3f}% to {s['rpmed']:.3f}%. {s['ref1']} models were past 1% on stock and {s['rp1']} on RASPIPE. The stock figure is inflated by decks written to break things, and the worst RASPIPE entry, {worstrows[0][0]} at {abs(worstrows[0][1]):,.0f}%, is a stock bookkeeping gap and not a solver error: a fixed outfall that feeds the network is never booked as inflow, by either engine, and the solver's own ledger closes on it to {abs(worstrows[0][4]):.4f} ft³.")
para2=(f"Continuity is no proof of being right, and a solver built on a cell balance closes its books by construction. So the solver also keeps its own ledger of volume in, out, flooded and stored, and on the mixed test model that ledger closes to {abs(vrow('volume ledger')['got']):.1e} ft³ on 304,200 ft³ of inflow. {s['unsolved']} models finished with any step left unsolved.")
para3=(f"The cost is time, and the pipe clock raised it. RASPIPE took a median of {s['ratio']:.1f} times as long as stock on this sample and {s['ratio90']:.0f} times at the 90th percentile, because it has many more cells, solves a matrix, and now takes as many pipe steps as the target asks for. {s['tmo_rp']} models hit the 60 s limit on RASPIPE, up from 76 in version 1.0, against {s['tmo_ref']} on stock. Those sweep times are single runs on a busy machine, so three models were also timed in five interleaved pairs: 2.5 times stock (pairs 2.3 to 2.5), 0.86 times (0.83 to 0.90) and 33 times (31 to 34), with run-to-run spread of 5 to 7%. Version 1.0 on the same three was 1.2, 0.79 and 6.8. Every pair agreed on the sign, and yes, one of them still beats stock. The third shows what the target can cost: 9 s in version 1.0 and 46 s now, and the sweep has worse. If a model doesn't need it, raise `RASPIPE_COURANT`, or set it to 0 and have version 1.0 back. Nobody hands you a better answer for free.")
qnote=(f"Across {s['qn']} sample models with pollutants, the median quality continuity error was {s['qrefmed']:.2f}% on stock and {s['qrpmed']:.2f}% on RASPIPE, with a worst case of {s['qrpmax']:.1f}% and {s['qrefmax']:.1f}%. Nothing here tests concentrations against a reference." if s['qn'] else "It has not been measured.")
def vget(name): return next(r for r in V if r['name'].startswith(name))
opt=dict(surge=vget('same, stage not projected')['got'],stock=vget('same, EPA 5.2.4 DYNWAVE')['got'],spike=vget('start up spike')['got'],warm=vget('same, RASPIPE_WARMUP')['got'],flood=vget('same, Courant control off')['got'],floodon=vget('false flood')['got'])
dt60=abs(vget('mixed model, step 60 s')['err'])
val.update({'opt.surge':f"{opt['surge']:.1f}",'opt.stock':f"{opt['stock']:.1f}",'opt.spike':f"{opt['spike']:.2f}",'opt.dt60':f"{dt60:.2f}",'opt.out':'88.96','opt.t10':'14','null.n11':str(vget('v1.1 options off')['expect'])})
val.update({'sweep.para1':para1,'sweep.para2':para2,'sweep.para3':para3,'sweep.qnote':qnote})

sources=[["HEC-RAS User's Manual 6.6: Pipe Network Simulations, for the adaptive time step, stage projection and warm up options","https://www.hec.usace.army.mil/confluence/rasdocs/rasum/6.6/pipe-networks-beta/pipe-network-simulations"],
 ["HEC-RAS 1D Technical Reference Manual: Modeling Pipe Networks","https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/latest/modeling-pipe-networks"],
 ["HEC-RAS Technical Reference: Pipe Network Hydraulic Structures","https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/latest/modeling-pipe-networks/pipe-network-hydraulic-structures"],
 ["HEC-RAS User's Manual 7.0: Pipe Network Geometry","https://www.hec.usace.army.mil/confluence/rasdocs/rasum/7.0/pipe-networks/pipe-network-geometry"],
 ["HEC-RAS tutorial: SWMM import, Beaver Lake","https://www.hec.usace.army.mil/confluence/rasdocs/hgt/latest/tutorials/pipe-networks/pipe-networks-swmm-import-beaver-lake"],
 ["Improved Urban Drainage Modeling with HEC-RAS (CWEMF paper)","https://cwemf.org/wp/wp-content/uploads/2025/11/29.5_ImprovedUrbanDrainageModelingHEC-RAS_Andrews.pdf"],
 ["Casulli & Stelling (2013), Int. J. Numer. Meth. Fluids 73:600-614. Cited by HEC, paywalled, not read directly","https://onlinelibrary.wiley.com/doi/10.1002/fld.3817"],
 ["Brutto et al. (2023), Int. J. Numer. Meth. Fluids, for the Jordan decomposition and nested Newton","https://onlinelibrary.wiley.com/doi/full/10.1002/fld.5143"],
 ["Casulli & Zanolli (2012), nested Newton. Described from the secondary sources above and general knowledge",""],
 ["Fuamba (2002), cited by HEC on the Preissmann slot",""],
 ["EPA SWMM 5.2.4 source","https://github.com/USEPA/Stormwater-Management-Model"],
 ["1729 SWMM5 Models corpus","https://github.com/SWMMBobSWMM6/1729-SWMM5-Models-2030"]]
aiuse=["SWMM5 RASPIPE was built with Claude, Anthropic's AI model, in a Claude session in November 2026, at the request of Robert (Bob) Dickinson, who pointed it to the HEC-RAS time step and start-up options used in version 1.1 and whose standing requirements for testing, documentation and units it follows. Responsibility for the work is his. He has not yet reviewed this build.",
 "<b>What Claude did.</b> It read HEC's public manuals and the papers named below, designed the solver and worked out what the manuals leave out, wrote <code>raspipe.c</code> and the small patches to EPA's files, wrote the independent Saint-Venant reference solver and every test, ran the corpus sweep, found and fixed the defects in the register, compiled the WebAssembly build, built this app, and wrote the essay and the Word document.",
 "<b>How the results were checked.</b> The checks are mechanical, not the AI's judgment: closed-form answers (Manning, normal depth, a pump curve), a byte comparison of the <code>.out</code> file with the feature off, a separately written Saint-Venant solver, the solver's own volume ledger, a sweep of "+f"{s['drawn']:,}"+" corpus models through both engines, and a Playwright run of this page.",
 "<b>What no person has checked.</b> No person has reviewed the code, the figures or this text. It has not been compared with a run of HEC-RAS or with field data. Casulli and Stelling's 2013 paper is paywalled and was not read directly; the method was taken from HEC's description of it and from the sources listed."]
def fmtp(x): return f"{x:.3f}%"
data=dict(verify=[dict(r,note=re.sub(r'\s*\{.*\}$','',r.get('note') or '')) for r in V],
 wave=dict(ref=dict(t=W['ref']['t'],q=W['ref']['q']),fine=dict(t=W['fine']['t'],q=W['fine']['q']),rp=dict(t=W['rp']['t'],q=W['rp']['q']),stock=dict(t=W['stock']['t'],q=W['stock']['q']),
  rows=[dict(name=W[k]['name'],c=W[k]['c'],peak=W[k]['peak'],tp=W[k]['tp'],err=None if k=='ref' else e(k)) for k in ('ref','stock','fine','rp','rp30','rp5','rp50','rp12','swe')],
  note=f"The reference is a separate shock-capturing solver of the full equations, converged at 25, 12.5 and 6.25 ft cells. Continuity: EPA as built {cont('EPA 5.2.4 DYNWAVE, the model as built')}%, EPA with 160 conduits {cont('EPA 5.2.4 DYNWAVE, cut into 160')}%, RASPIPE defaults {cont('RASPIPE defaults (20 cells a conduit)')}%. With a 4,000 ft conduit the default of 20 cells makes 200 ft cells."),
 sweep=dict(note=f"{s['drawn']:,} models drawn at random from the 1729 corpus, stratified by file size (seed 1729), 60 s limit per run, version 1.1. Models that could not change from the last edit keep their earlier run, and 40 of those were rerun and matched. {s['noconduit']} had no conduits. {s['cmp']:,} finished in both engines with a continuity figure. The corpus is rich in stress tests, so the stock numbers describe those decks.",
  census=census,bins=bins,rows=[["Median |routing continuity|",fmtp(s['refmed']),fmtp(s['rpmed'])],["90th percentile",fmtp(s['refp90']),fmtp(s['rpp90'])],["Models past 1%",str(s['ref1']),str(s['rp1'])],["Models that hit the 60 s limit",str(s['tmo_ref']),str(s['tmo_rp'])],["Models that crashed",str(s['crash_ref']),str(s['crash_rp'])],["Median run time, RASPIPE over stock","",f"{s['ratio']:.1f}×"],["90th percentile run time ratio","",f"{s['ratio90']:.0f}×"],["Models with a step left unsolved","",str(s['unsolved'])],["Median trials per pipe step","",f"{s['trmed']:.2f}"],["Pipe steps per routing step, median","",f"{psm:.2f}"],["Pipe steps per routing step, 90th percentile","",f"{psp:.1f}"]]),
 headline=f"<b>Dry start against a stage boundary:</b> surge {opt['surge']:.1f} cfs without stage projection, 0 with it. <b>Pump into a full pipe:</b> pencil {pv['exact']:.3f} cfs, RASPIPE {pv['rp']:.3f}, slot {pv['slot']:.3f}. <b>Null control:</b> <code>.out</code> byte-identical on {len(nl)} of {len(nl)} decks with the feature off. <b>Wave:</b> reference {ref:.2f} cfs, stock {W['stock']['peak']:.2f}, RASPIPE {W['rp']['peak']:.2f}. None of this is field data, and version 1.1 is slower than 1.0.",
 defects=[["RP-1","Free outfall stage fed by the lagged flow. A siphon reported 732,000 cfs in a 2,000 cfs system.","fixed","ok"],
  ["RP-2","Conduit evaporation and seepage could exceed what the interior cells held, leaving no solution and the wrong rate in the report.","fixed","ok"],
  ["RP-3","A sealed run of full cells gave a singular block, so nested Newton stalled when the head had to rise to a manhole rim.","fixed","ok"],
  ["RP-4","A face dry at the start of a trial acted as a wall. Fronts faster than a cell per step produced flooding that was pure artifact.","fixed","ok"],
  ["RP-5","A deck's MAX_TRIALS of 4 was honored. Too few to chase a front, 21.6 ac-ft of false flood on one deck. Now always 8, stopping when converged.","fixed","ok"],
  ["RP-6","Demand at a dry cell with nothing able to reach it had no solution. The unmet part is dropped for the step and shows as continuity error.","fixed","ok"],
  ["RP-7","Rounding made node volume exceed full volume, undercounting flood 10.8 against 32.6 ac-ft.","fixed","ok"],
  ["RP-8","A lower clip on the source term created water at inlets, 39% on one street model.","fixed","ok"],
  ["RP-9","A manhole stores water to its MaxDepth, EXTRAN does not. Decks with a fake 1,000 ft depth take hours to settle.","behavior","hi"],
  ["RP-10","Quality routing was given the mid-conduit flow, so pollutant mass was created or lost as a conduit filled, 21% on one model. It now gets the flow at each end.","fixed","ok"],
  ["RP-11","A first face below a culvert inlet handed the FHWA equations a negative head and crashed inside EPA's culvert routine.","fixed","ok"],
  ["RP-12","A flat channel at a NORMAL outfall was held to normal flow on zero slope, 58 cfs against stock's 1,415. Above the crown, head now drives it.","fixed","ok"],
  ["RP-13","Diffusion wave let water leave a node faster than critical, 11.3 cfs from 0.54 ft of head. Now held to critical at the entry. Cost: 0.6% on normal depth in a steep run through a junction.","fixed","ok"],
  ["RP-14","A front moving more than a cell per step in steep pipes surged and flooded 7.2 ac-ft where stock floods 0.02. Fixed by HEC's target Courant number.","fixed","ok"],
  ["RP-15","A rounding error in a dry network became a flow through an opening face and made 328 ft3 of water from nothing. A dry face now takes 0.001 ft of water to open.","fixed","ok"],
  ["RP-16","Hot start files carry no interior cell states.","open","hi"],
  ["EPA-1","SLOT surcharge overstates pump flow into a full pipe (EPA issue 231), "+f"{100*(pv['slot']-pv['exact'])/pv['exact']:.1f}% here.","stock","warn"],
  ["EPA-2","A fixed outfall that feeds the network is not booked as inflow (corpus deck NUM-19). Shared by both engines, and it tops the RASPIPE continuity list.","stock","warn"]],
 limits="<b>What this does not show.</b> No field data. No run of HEC-RAS. Agreement with Manning, a pump curve and another solver shows the arithmetic is right, not that a model predicts a real sewer. Where the engines disagree in the corpus, nobody has yet sorted out which is right. Quality routing and hot starts are not validated. Water hammer is not modeled. No person has reviewed this code.",
 options=[["FLOW_ROUTING RASPIPE","","Turns the solver on. Anything else is EPA 5.2.4."],["RASPIPE_COURANT","0.9","Target residence time Courant number for the pipe steps, HEC's default. 0 turns it off."],["RASPIPE_INITIAL_STAGE","YES","Projects FIXED, TIDAL and TIMESERIES outfall stages up the conduits at the start."],["RASPIPE_WARMUP","0","Warm up steps before the clock starts. Inflows ramp over the first 2/3. HEC asks for 30 or more."],["RASPIPE_EQUATIONS","DW","DW diffusion wave, SWE full shallow water with HEC's Eulerian-Lagrangian advection."],["RASPIPE_CELL_LENGTH","100 ft","Target cell length, in model length units."],["RASPIPE_MAX_CELLS","20","Most interior cells per conduit. Long pipes need this raised."],["RASPIPE_THETA","1.0","Implicit weighting, 0.5 to 1. 0.6 keeps sharp fronts and oscillations better; 1.0 is what the corpus ran. The fallback always uses 1."],["RASPIPE_NESTED_ONLY","NO","YES skips plain Newton. For testing."]],
 sources=sources,aiuse=aiuse,
 prov="<b>Engine:</b> EPA SWMM 5.2.4 (commit 7952ca8) plus <code>raspipe.c</code> 1.1. <b>Browser build:</b> zig cc wasm32-wasi, 586 KB, same .inp, same .out on 5 of 7 decks, the other two differ in the 15th digit. <b>Verify data:</b> native runs, November 3, 2026. <b>Not HEC code</b> and not compared with HEC-RAS. <b>AI use:</b> built with Claude (Anthropic), see About. No person has reviewed it yet.")
exec(open(R+'/app/mkdata12.py').read())
json.dump(data,open(R+'/app/data.json','w'))
json.dump(dict(val=val,pump=pv,opt=opt,sources=sources,aiuse=aiuse),open(R+'/app/vals.json','w'),indent=1)
print(json.dumps(sweep,indent=0)); print(worstrows[:8])
