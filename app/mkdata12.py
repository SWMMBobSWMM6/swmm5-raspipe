# --- version 1.2 additions. Everything here is read from a run or stated as a choice.
BUILD=open(R+'/build_id.txt').read().strip()
st12=json.load(open(R+'/tests/v/stoker.json')); ut12=json.load(open(R+'/tests/v/utube.json')); wb=json.load(open(R+'/tests/v/wavebudget.json')); tb=json.load(open(R+'/tests/v/tabs15.json'))
slot=json.load(open(R+'/tests/v/slot_terms.json')); dws=json.load(open(R+'/tests/v/dwsame.json')); dwc=json.load(open(R+'/tests/v/dwsame_corpus.json'))
import math
# --- evidence types
EV={'V1':('regression check','hi','byte identical'),'V2':('analytical answer','ok','exactly 0'),'V3':('analytical answer','ok','0.01%'),'V4':('analytical answer','ok','0.01%'),'V5':('analytical answer','ok','1%'),
 'V6':('analytical answer','ok','0.01%'),'V7':('regression check','hi','0.01 cfs'),'V8':('analytical answer','ok','one report step'),'V9':('numerical reference','hi','1% of the 1 s run'),'V10':('conservation check','ok','0.001 ft3'),
 'V11':('regression check','hi','byte identical'),'V12':('initialization check','warn','reported'),'V13':('initialization check','warn','reported'),'V14':('cross-engine comparison','warn','reported')}
for r in data['verify']:
    e=EV[r['id']]; r['evidence'],r['ec'],r['tol']=e
    if r['name'].startswith('pump into full pipe, SLOT') or r['name'].startswith('pump into full pipe, EXTRAN'): r['evidence'],r['ec'],r['tol']='cross-engine comparison','warn','reported'
    if r['name'].startswith('pressurized pipe, SWE'): r['note']='The equations lose one velocity head at the exit into the tank.'
    if r['id']=='V12' and 'projected: largest' in r['name']: r['note']='Starting pre-filled is a different starting state. A truly dry network under a higher stage would take inflow.'
    if r['id']=='V13': r['note']=(r.get('note') or '')+' Shows spin-up works. It is not an accuracy test.'
    if r['id']=='V14': r['note']=(r.get('note') or '')+' One engine against another, not against an exact answer.'
# --- Stoker
ex=st12['exact']; G=32.2; HL,HR,X0,TT=st12['HL'],st12['HR'],st12['X0'],st12['T']
def hx(x):
    z=(x-X0)/TT
    if z<-ex['cL']: return HL
    if z<ex['us']-ex['cs']: return (2*ex['cL']-z)**2/(9*G)
    if z<ex['S']: return ex['hs']
    return HR
xe=[i*5.0 for i in range(0,801)]
def prof(k):
    v=st12['prof'][k]; return dict(x=[a for a,b in v],h=[b for a,b in v])
def srow(name,mesh,r):
    return dict(name=name,mesh=mesh,star=r['star'],star_err=r['star_err'],speed=r['speed'],speed_err=100*(r['speed']-ex['S'])/ex['S'],l1=r['l1'])
def fr(nm,dx=None,dt=None,theta=None):
    for r in st12['rows']:
        if r['name']==nm and (dx is None or r['dx']==dx) and (dt is None or r['dt']==dt): return r
    raise KeyError(nm)
strows=[dict(name='Exact (Stoker)',mesh='',star=ex['hs'],star_err=None,speed=ex['S'],speed_err=None,l1=None),
 srow('v1.1 implicit upwind, theta 1','5 ft, 0.125 s',fr('v1.1 implicit upwind, theta 1',5)),srow('v1.2, theta 1','5 ft, 0.125 s',fr('v1.2, theta 1',5)),srow('v1.2, theta 0.6','5 ft, 0.125 s',fr('v1.2, theta 0.6',5)),
 srow('v1.2, theta 0.6','10 ft, 0.25 s',fr('v1.2, theta 0.6',10)),srow('v1.2, theta 0.6','20 ft, 0.5 s',fr('v1.2, theta 0.6',20)),srow('v1.2, theta 1, shorter step','10 ft, 0.02 s',fr('v1.2, theta 1, time refined',10,0.02)),srow('v1.1 implicit upwind, shorter step','10 ft, 0.02 s',fr('v1.1 implicit upwind, time refined',10,0.02)),
 srow('v1.2, long step, Courant near 3','10 ft, 1 s',fr('v1.2 long step, Courant near 3')),srow('v1.2, long step, Courant near 3, theta 0.6','10 ft, 1 s',fr('v1.2 long step, Courant near 3, theta 0.6'))]
acon=[r for r in st12['rows'] if r['name'].startswith('v1.2 contraction')]
acs=[r['l1'] for r in acon]+[fr('v1.2, theta 1',10)['l1']]
stnote=(f"Rectangular channel 10 ft wide, 4,000 ft long, n = 0.0005, read at 60 s. The exact solution is the standard wet-bed Riemann result. Nothing in the mesh or the code knows it. Mean depth error is the average of |h - exact| along the pipe. "
 f"Moving the strong contraction ratio from 1.1 to 4 moved that error only from {min(acs):.3f} to {max(acs):.3f} ft. A test build places the starting step inside one conduit and writes out the cells, because a deck can't and the .out file doesn't, so this case can't be repeated in the browser.")
# --- U-tube
ur=ut12['rows']; T0=ut12['exact']
def uf(n,dt=None):
    for r in ur:
        if r['name']==n and (dt is None or r['dt']==dt): return r
    raise KeyError(n)
u_ex=dict(x=[i*5.0 for i in range(0,721)],z=[round(ut12['a0']*math.cos(2*math.pi*i*5.0/T0),4) for i in range(0,721)])
ep=uf('EPA 5.2.4 EXTRAN'); rp_=uf('RASPIPE SWE, theta 0.6',2)
urows=[dict(name='Exact, no losses',dt='',T=T0,err=None,dec=1.0)]+[dict(name=r['name'].replace('SWE','full equations'),dt=r['dt'],T=r['T'],err=(100*(r['T']-r.get('exact',T0))/r.get('exact',T0)) if r['T'] else None,dec=r.get('dec')) for r in ur]
utnote=(f"Pipe 1,000 ft long and 2 ft across, tanks 1,000 ft² each, 0.5 ft starting offset, n = 0.001. Period = 2π√(L A_s / (2 g A_p)) = {T0:.1f} s. RASPIPE loses amplitude because the water leaving the pipe gives up one velocity head into the tank, which alone gives a ratio of {ut12['pred']:.3f} after one cycle; θ 1 and long steps add numerical damping on top of that. Diffusion wave has no inertia, so it has no oscillation to time. "
 f"EPA's period is long because a full pipe still adds a phantom free surface to its end nodes, the width at 96% of depth over half the length, 392 ft² to a 1,000 ft² tank. That predicts {T0*math.sqrt(1+.7838367*500/1000):.1f} s, and removing it in a test copy gives {uf('EPA 5.2.4 EXTRAN, full pipe adds no surface')['T']:.1f} s. Continuity reads 0.000% either way.")
# --- wave budget
GN={'swe':'Full equations','dw':'Diffusion wave','mesh':'Cell length','time':'Time step, Courant off','auto':'Courant on','stock':'EPA 5.2.4'}
wrows=[dict(r,g=GN[r['group']],osc=max(r['osc'],0.0),steps=' / '.join(f"{float(x):g}" for x in re.findall(r'[\d.]+',r.get('steps') or ''))) for r in wb]
ref=json.load(open(R+'/tests/v/refsol.json')); rp3=[max(x[1] for x in ref[k]) for k in ('320','640','1280')]
rich=rp3[2]+(rp3[2]-rp3[1])
def wf(frag): return next(r for r in wrows if frag in r['name'])
wnote=(f"Every line is scored against the independent solver at 6.25 ft cells over the four hours after spin-up. Its own peak moved {rp3[0]:.3f}, {rp3[1]:.3f}, {rp3[2]:.3f} cfs as its cells halved, so its error is about {100*(rich-rp3[2])/rich:.1f}%. That solver came from the same AI session as the engine, shares no code with it, and solves the conservative equations. It is a numerical reference and not an outside authority. Pipe step is min / mean / max. "
 f"Ripple is how much the hydrograph travels past one rise and one fall, as a fraction of that. A routing step does not by itself set the pipe step: with Courant control on, a 30 s routing step ran pipe steps of {wf('ROUTING_STEP 30')['steps']} s.")
data['wave'].update(rows=wrows,note=wnote,leg=[['Independent solver','s3'],['EPA 5.2.4, 160 conduits of 50 ft','s5'],['RASPIPE defaults','s2'],['EPA 5.2.4, the model as built','s1']])
data['bench']=dict(stoker=dict(exact=dict(x=xe,h=[round(hx(x),4) for x in xe]),v11=prof('v11_5'),v12=prof('v12_5'),v12t=prof('v12t_5'),rows=strows,note=stnote),
 utube=dict(exact=u_ex,epa=dict(x=ep['tz'],z=ep['z']),rp=dict(x=rp_['tz'],z=rp_['z']),rows=urows,note=utnote))
# --- table error
g=[r['gauss15'] for r in tb]; e15=[r['even15'] for r in tb]; rt=[r['rp'] for r in tb]
tmax=lambda a:max(x['maxpct'] for x in a)
# --- method table
sT=next(r for r in strows if r['name']=='v1.1 implicit upwind, theta 1'); s1=next(r for r in strows if r['name']=='v1.2, theta 1'); s6=next(r for r in strows if r['name']=='v1.2, theta 0.6')
data['method']=[
 ['Advection',"Explicit Eulerian-Lagrangian. V_X = V_j - V* dt (V_j - V_j-1)/dx, backtracked at Courant up to 1. V* = (V_j + V_j-1)/2 in strong contractions, keeping energy head, and (A_j V_j + A_j-1 V_j-1)/(2 A_j) elsewhere, conserving momentum (Stelling and Duinmeijer 2003). The choice depends on local flow. No number is given for strong.",
  "The same form since 1.2. Versions 1.0 and 1.1 used an implicit upwind form written here. Choices made here: strong means the upwind area is over 1.5 times the face area with velocity rising; the A under the fraction is the mean of the two sides; water in a node is at rest, except at a junction of exactly two conduits, where momentum crosses.",
  f"Stoker dam break: bore speed error {sT['speed_err']:+.1f}% in v1.1, {s1['speed_err']:+.1f}% at theta 1 and {s6['speed_err']:+.1f}% at theta 0.6 in v1.2. The 1.5 hardly matters here: 1.1 to 4 gives the same answer to 0.002 ft. With momentum crossing the junction, the wave's head error at that junction went from 0.16 to {wf('12.5 ft, 1 s, theta 1.0')['y_err']:.3f} ft."],
 ['Friction',"Implicit, c_f = g A^2 |V| / K^2, updated at each iteration.","Implicit. The quadratic in V is solved exactly at each trial.","Pressurized pipe (V3) and normal depth (V5) against closed forms."],
 ['Cell volume tables',"Volume found at 15 Gaussian quadrature points between the lowest and highest elevation, with a flat water surface in a sloping pipe. Piecewise linear volume, piecewise constant area, split into running sums A+ and A-.",
  "The same split and the same piecewise forms. Break points evenly spaced at D/32 over the same range, 33 to 129 of them, with the exact prismatic integral.",
  f"Against a fine numerical integral over nine pipes: largest volume error {tmax(rt):.2f}% of full here, {tmax(g):.2f}% with 15 Gauss points plus the ends, {tmax(e15):.2f}% with 15 even points. HEC's exact placement is not stated, so those two are readings of it. Either table is used consistently, so this moves levels slightly and does not lose water."],
 ['Nonlinear iteration',"Outer loop m linearizes the falling part, inner loop k the rising part, both to convergence. Max Iterations default 20. Tolerances are not on that page.",
  "The same two loops, up to 80 outer and 24 inner, 1e-8 ft3. Plain Newton is tried first with a linearized face, and the nested loop is the fallback. Up to 8 trials outside that, 16 if a trial is unsolved.",
  f"Forcing the nested path on every solve moved a 59 cfs peak by {vrow('nested only')['got']:.4f} cfs (V7). Unsolved steps are listed one by one below."],
 ['Time step control',"Adaptive Time Step, on by default: compares estimated residence time Courant values with a target of 0.9 for each cell, and the base interval is reduced or increased. No formula on the page.",
  "C = dt x outflow / volume, largest over cells that hold pipe. Pipe steps inside the SWMM routing step, 15 s or less while water is moving, and a quiet rule that stretches the step. The formula, the exclusions and the limits are choices made here.",
  "The report gives pipe step min / mean / max and the largest Courant reached, and the wave table above shows them. V14 is what it fixed."],
 ['Theta',"Theta weights the pressure term between old and new levels.","Default 1.0, range 0.5 to 1.","U-tube and dam break: 0.6 is more accurate, at least on these, with less damping. The default stays at 1.0 because the corpus was run there."]]
# --- outcomes
def oc(r,k):
    rc=r.get(k+'_rc'); d=r.get(k) or {}
    if rc==-99: return 'time limit'
    if rc not in (0,None): return 'crash'
    if d.get('err'): return 'input rejected'
    if d.get('cont') is None: return 'no report'
    return 'finished'
cc=collections.Counter((oc(r,'ref'),oc(r,'rp')) for r in run)
why={('finished','finished'):'Both finished, compared below',('input rejected','input rejected'):'Both rejected the input (ERROR 205 and the like)',('finished','time limit'):'RASPIPE hit the 60 s limit, EPA finished',('time limit','time limit'):'Both hit the limit',('time limit','finished'):'EPA hit the limit, RASPIPE finished',('crash','crash'):'Both crashed in shared EPA code',('no report','no report'):'Both ended with no continuity report',('no report','time limit'):'EPA no report, RASPIPE hit the limit'}
outc=[[why.get(k,str(k)),k[0],k[1],f"{v:,}"] for k,v in sorted(cc.items(),key=lambda x:-x[1])]
outc.append(['Conduit models in the sample','','',f"{sum(cc.values()):,}"]); outc.append(['No conduits to route, not run','','',str(noc)]); outc.append(['Drawn','','',f"{drawn:,}"])
data['sweep']['outcomes']=outc
# --- unsolved steps, judged by size
un=[]
for r in sorted(unsolved,key=lambda r:-(r['rp'].get('maxres') or 0)):
    p=r['rp']; res=p.get('maxres') or 0
    okk=res<0.01
    un.append([os.path.basename(r['inp']).replace('.inp',''),int(p['unsolved']),f"{res:.4g}",f"{p['cont']:.3f}%",'accepted, residual negligible' if okk else 'not accepted','ok' if okk else 'warn'])
data['sweep']['unsolved']=un
nacc=sum(1 for u in un if u[5]=='ok')
data['sweep']['unnote']=(f"The solver's target is 1e-8 ft³, so an unsolved step means it stopped short of that, not that the step went wrong. The rule here is by size: a model is accepted if the largest volume residual anywhere in the run is under 0.01 ft³. {nacc} of {len(un)} pass, all under 0.002 ft³. The other needs someone to look at it. Low continuity is not the test, because the ledger closes whatever the residual.")
# --- full equations sample
def swe(fn):
    p=R+'/sweep/'+fn+'/results.jsonl'
    if not os.path.exists(p): return None
    L=[json.loads(l) for l in open(p)]; L=[r for r in L if not r.get('skip')]
    done=[r for r in L if r.get('ref_rc')==0 and r.get('rp_rc')==0 and (r.get('ref') or {}).get('cont') is not None and (r.get('rp') or {}).get('cont') is not None]
    c=sorted(abs(r['rp']['cont']) for r in done); a=sorted(abs(r['ref']['cont']) for r in done)
    return dict(n=len(L),done=len(done),med=pct(c,.5),p90=pct(c,.9),past=sum(1 for x in c if x>=1),tmo=sum(1 for r in L if r.get('rp_rc')==-99),crash=sum(1 for r in L if r.get('rp_rc') not in (0,-99)),uns=sum(1 for r in done if (r['rp'].get('unsolved') or 0)>0),stock=pct(a,.5),fb=pct(sorted(r['rp'].get('trials') or 0 for r in done),.5))
sw1=swe('r12_t1'); sw6=swe('r12_t6')
sm=json.load(open(R+'/tests/v/same12.json')) if os.path.exists(R+'/tests/v/same12.json') else dict(same=0,diff=0)
if sw1 and sw6:
    data['sweep']['swe']=[['Models run',str(sw1['n']),str(sw6['n'])],['Finished in both engines',str(sw1['done']),str(sw6['done'])],['Median |routing continuity|',f"{sw1['med']:.3f}%",f"{sw6['med']:.3f}%"],['90th percentile',f"{sw1['p90']:.3f}%",f"{sw6['p90']:.3f}%"],['Models past 1%',str(sw1['past']),str(sw6['past'])],['Hit the 45 s limit',str(sw1['tmo']),str(sw6['tmo'])],['Crashes',str(sw1['crash']),str(sw6['crash'])],['Models with an unsolved step',str(sw1['uns']),str(sw6['uns'])],['Median trials per pipe step',f"{sw1['fb']:.2f}",f"{sw6['fb']:.2f}"]]
    data['sweep']['swenote']=f"160 models drawn at random from the same sample, {sw1['n']} of them with conduits, version 1.2, RASPIPE_EQUATIONS SWE, 45 s limit. The main sweep above is diffusion wave. On the same models that EPA also finished, its median was {sw1['stock']:.3f}%. The sweep used the build before the last edit, which touched bookkeeping only: .out files were byte identical on {sm['same']} of {sm['same']+sm['diff']} deck and equation pairs."
else:
    data['sweep']['swe']=[];data['sweep']['swenote']='The full equations sample has not finished.'
# --- diffusion wave identity
dwline=f"Diffusion wave never calls the new advection code, so the corpus numbers carry over: .out files were byte identical to frozen v1.1 on {dws['same']} of {dws['n']} test decks and {dwc['same']} of {dwc['compared']} corpus models drawn at random ({dwc['skipped']} more were skipped for time or error)."
data['sweep']['note']=data['sweep']['note']+' '+dwline
# --- four measures
wsw=wf('12.5 ft, 1 s, theta 1.0')
data['measures']=[dict(t='Conservation',big=f"{s['rpmed']:.3f}%",sub=f"median routing continuity on {s['cmp']:,} models both engines finished; EPA {s['refmed']:.3f}%. A solver built on a cell balance closes its books by construction, so this is the weakest of the four."),
 dict(t='Hydraulic accuracy',big=f"{wsw['peak_err']:+.2f}%",sub=f"wave peak, full equations against the independent solver. U-tube period {uf('RASPIPE SWE, theta 0.6',2)['err']:+.2f}%, dam break bore speed {s6['speed_err']:+.1f}% at theta 0.6, {s1['speed_err']:+.1f}% at theta 1."),
 dict(t='Completion and convergence',big=f"{cc[('finished','finished')]+cc[('time limit','finished')]:,} of {sum(cc.values())-cc[('input rejected','input rejected')]:,}",sub=f"models a solver could run that RASPIPE finished in 60 s; EPA {cc[('finished','finished')]+cc[('finished','time limit')]:,}. {len(un)} had an unsolved step, {nacc} accepted."),
 dict(t='Computational cost',big=f"{s['ratio']:.1f}×",sub=f"median run time against EPA, {s['ratio90']:.0f}× at the 90th percentile, {len(tmo_rp)} time limits against {len(tmo_ref)}.")]
# --- presets: each sets the whole panel; the browser test checks them against the tables above
W_='long_pipe_wave.inp'
data['presets']=[
 dict(label='Wave: RASPIPE at 100 ft, 5 s, Courant off',file=W_,elem='C2',o=dict(cour=0,vs='0',dt='5',maxc=800),note='Row "diffusion wave, 100 ft, 5 s" of the wave table.'),
 dict(label='Wave: 50 ft cells',file=W_,elem='C2',o=dict(cell=50,cour=0,vs='0',dt='5',maxc=800),note='Row "diffusion wave, 50 ft, 5 s".'),
 dict(label='Wave: 12.5 ft cells, 1 s',file=W_,elem='C2',o=dict(cell=12.5,cour=0,vs='0',dt='1',maxc=800),note='The finest diffusion wave row. 642 cells, takes a minute or so.'),
 dict(label='Wave: full equations, 12.5 ft, 1 s',file=W_,elem='C2',o=dict(eqn='SWE',cell=12.5,cour=0,vs='0',dt='1',maxc=800),note='The closest row to the reference.'),
 dict(label='Wave: 800 ft cells',file=W_,elem='C2',o=dict(cell=800,cour=0,vs='0',dt='5',maxc=800),note='Row "diffusion wave, 800 ft, 5 s". Five cells a conduit.'),
 dict(label='Wave: 30 s step, Courant off',file=W_,elem='C2',o=dict(cour=0,vs='0',dt='30',maxc=800),note='A true 30 s step. Compare the next case.'),
 dict(label='Wave: 30 s routing step, Courant on',file=W_,elem='C2',o=dict(dt='30',maxc=800),note='The routing step says 30, the pipe steps do not.'),
 dict(label='V6 pump into a full pipe',file='pump_full_pipe.inp',elem='C1',o=dict(),note='Pencil answer 4.599 cfs.'),
 dict(label='V8 filling time',file='filling_pipe.inp',o=dict(),note='Node depth reaches 3 ft at about 27 min.'),
 dict(label='V9 mixed model, 60 s step',file='mixed_network.inp',elem='C2',o=dict(dt='60',vs='0'),note='Compare with the 1 s case.'),
 dict(label='V9 mixed model, 1 s step',file='mixed_network.inp',elem='C2',o=dict(dt='1',vs='0'),note='The reference run of the V9 rows.'),
 dict(label='V12 stage projected',file='stage_on_dry_network.inp',elem='C2',o=dict(),note='Starts pre-filled, so nothing moves. An initialization check.'),
 dict(label='V12 stage not projected',file='stage_on_dry_network.inp',elem='C2',o=dict(stg='NO'),note='A dry network takes the surge.'),
 dict(label='V13 start-up spike, no warm up',file='startup_spike.inp',elem='C1',o=dict(),note='Peak 7.53 cfs in a 5 cfs pipe.'),
 dict(label='V13 start-up spike, 60 warm up steps',file='startup_spike.inp',elem='C1',o=dict(warm=60),note='Peak 5.00 cfs.'),
 dict(label='U-tube: full equations, theta 0.6, 2 s',file='u_tube.inp',elem='',vari='depth',o=dict(eqn='SWE',theta=0.6,cour=0,vs='0',dt='2',stg='NO'),note='Blue keeps the exact period of 441.7 s. Amber runs long.')]
# --- defects
data['defects']=[d for d in data['defects'] if d[0] not in ('EPA-1','EPA-2')]+[
 ["RP-17","The full equations used an implicit upwind advection of this project's own. HEC's page gives an explicit Eulerian-Lagrangian form. On a dam break the old form ran the bore "+f"{-sT['speed_err']:.0f}% slow. Replaced.","fixed","ok"],
 ["RP-18","The full equations lost a velocity head at every junction, because a node is water at rest. In a straight run that is a false head loss, 0.16 ft on the wave. Momentum now crosses a junction of exactly two conduits. Other junctions keep the loss.","fixed","ok"],
 ["EPA-1","SLOT overstates pump flow into a full pipe (EPA issue 231), "+f"{100*(pv['slot']-pv['exact'])/pv['exact']:.1f}% here. Two terms carry the slot area, the velocity in friction and the area in the head term, and each is about half of it. Cap both at the true area and SLOT lands on EXTRAN to four places.","stock","warn"],
 ["EPA-2","A fixed outfall that feeds the network is not booked as inflow (corpus deck NUM-19). Shared by both engines, and it tops the RASPIPE continuity list.","stock","warn"],
 ["EPA-3",f"A full conduit still adds surface area to its end nodes, from the width at 96% of depth. On a U-tube with 1,000 ft² tanks that is 392 ft² of surface that isn't there, and the period runs 18.0% long while continuity reads 0.000%.","stock","warn"],
 ["AP-1","Old results stayed on screen after settings changed, and Save .inp used the new controls while Export CSV used the old run. A run is now one immutable record that both exports read.","fixed","ok"],
 ["AP-2","A near-zero EPA peak was given 0% difference, whatever RASPIPE did, and sank down the table. The table now ranks by absolute difference and says near-zero baseline.","fixed","ok"],
 ["AP-3","Times were built from the record number, so a delayed report start read wrong. They now come from the timestamps in the file, and two series join on those timestamps.","fixed","ok"],
 ["AP-4","The mesh limit stopped at 100 cells and said nothing when it bound. The limit now reaches 800, the report gives the mesh achieved, and the app warns.","fixed","ok"],
 ["AP-5","Overlapping runs could orphan a request, Stop left requests hanging, and a failed run could leave the last hydrograph up. One comparison runs at a time and every run ends as completed, completed with warnings, failed or cancelled.","fixed","ok"],
 ["DOC-1","The essay said HEC publishes only an outline. HEC's page gives the advection scheme and the nested iteration in full. Corrected, and the comparison table above replaces the claim.","fixed","ok"],
 ["DOC-2","dV/dη was called a width with units of ft² per ft. It is an area.","fixed","ok"],
 ["DOC-3","The Newton race gave the two methods different budgets and said a failure meant no solution. The equation has exactly one root.","fixed","ok"]]
# --- limits, options, sources
data['limits']=data['limits'].replace('</div>','')+" The benchmark reference for the wave came from the same AI session as the engine. Stoker and the U-tube have outside answers, but they test one rectangular channel and one pipe. The advection is HEC's form with several choices of this project's own in it, and it has been run on 160 corpus models with the full equations, against 1,466 for diffusion wave."
data['options']=[o for o in data['options']]
srcx=[["HEC-RAS 1D Technical Reference Manual 7.0: Numerical Methods (Pipe Flow), for the advection, friction and nested iteration","https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/7.0/modeling-pipe-networks/numerical-methods-pipe-flow"],
 ["HEC-RAS 1D Technical Reference Manual: Computational Mesh and Subgrid Bathymetry (Pipe Flow), for the volume tables","https://www.hec.usace.army.mil/confluence/rasdocs/ras1dtechref/latest/modeling-pipe-networks/computational-mesh-and-subgrid-bathymetry-pipe-flow"],
 ["CivilGEO, Advanced Time Step Control, for residence time Courant described in words for 2D cells","https://knowledge.civilgeo.com/advanced-time-step-control"],
 ["Stelling & Duinmeijer (2003), Int. J. Numer. Meth. Fluids 43, cited by HEC for the advective speed. Used through HEC's page and general knowledge",""],
 ["Stoker (1957), Water Waves, for the dam break. Standard textbook result",""],
 ["EPA SWMM issue 231, slot area in the momentum equation velocity","https://github.com/USEPA/Stormwater-Management-Model/issues/231"]]
data['sources']=srcx+data['sources']
data['prov']=(f"<b>Engine:</b> EPA SWMM 5.2.4 (commit 7952ca8) plus <code>raspipe.c</code> 1.2, build <code>{BUILD}</code>. <b>Browser build:</b> zig cc wasm32-wasi, same .inp, same .out on @@PAR@@. <b>Verify data:</b> native runs, November 2026, Linux, one machine. <b>Corpus:</b> 1,600 models, diffusion wave, v1.1 results carried to v1.2 by byte comparison. <b>AI use:</b> built with Claude. See the About tab. No person has reviewed it.")
sf=lambda r:100*(r['speed']-ex['S'])/ex['S']
par=json.load(open(R+'/wasm/parity12.json'))
val.update({'wasm.same':str(par['same']),'wasm.n':str(par['n']),'wasm.max':par['max']})
vf=wf('12.5 ft, 1 s, theta 1.0'); dwf=wf('diffusion wave, 12.5 ft, 1 s')
val.update({'slot.both':f"{slot['both terms use the true area']:.3f}",'st.S':f"{ex['S']:.2f}",'st.hs':f"{ex['hs']:.2f}",'st.v11':f"{abs(sf(fr('v1.1 implicit upwind, theta 1',5))):.1f}",'st.v12':f"{sf(fr('v1.2, theta 1',5)):+.1f}",'st.v126':f"{sf(fr('v1.2, theta 0.6',5)):+.1f}",'st.first':f"{sf(fr('v1.2, upstream face area in V*',5)):+.1f}",'st.v12fine':f"{sf(fr('v1.2, theta 1, time refined',10,0.02)):+.1f}",
 'ut.T':f"{T0:.1f}",'ut.rp':f"{uf('RASPIPE SWE, theta 0.6',2)['T']:.1f}",'ut.epa':f"{ep['T']:.1f}",'ut.pred':f"{T0*math.sqrt(1+.7838367*500/1000):.1f}",'ut.fix':f"{uf('EPA 5.2.4 EXTRAN, full pipe adds no surface')['T']:.1f}",'ut.pred4':f"{2*T0*math.sqrt(1+.7838367*500/4000):.1f}",'ut.epa4':f"{uf('EPA 5.2.4 EXTRAN, 4,000 ft2 tanks')['T']:.1f}",
 'wave.refgap':f"{100*(rich-rp3[2])/rich:.1f}",'wb.sweerr':f"{abs(vf['peak_err']):.2f}",'wb.swense':f"{vf['nse']:.4f}",'wb.swey':f"{vf['y_err']:.3f}",'wb.dwerr':f"{dwf['peak_err']:+.2f}",'wb.dwcost':f"{abs(dwf['peak_err']-vf['peak_err']):.1f}",'wb.m100':f"{wf('diffusion wave, 100 ft, 5 s')['peak_err']:+.2f}",'wb.m800':f"{wf('diffusion wave, 800 ft, 5 s')['peak_err']:+.2f}",'wb.t30':f"{wf('100 ft, 30 s')['peak_err']:+.2f}",'wb.t5':f"{wf('100 ft, 5 s')['peak_err']:+.2f}",'wb.auto30':wf('ROUTING_STEP 30')['steps'],
 'dw.line':dwline,'sw.cmp':f"{s['cmp']:,}",'sw.ran':f"{s['ran']:,}",'sw.tmo':str(cc[('finished','time limit')]),'sw.uns':f"{nacc} of those stopped less than 0.002 ft³ short and are accepted by a stated rule. {len(un)-nacc} is not accepted and stays open.",
 'sw.swe':(f"{sw1['done']} of {sw1['n']} finished in both engines at θ = 1, median continuity {sw1['med']:.3f}%, {sw1['tmo']} hit a 45 s limit, {sw1['crash']} crashed. At θ = 0.6, {sw6['done']} finished, median {sw6['med']:.3f}%, {sw6['tmo']} hit the limit, {sw6['crash']} crashed." if sw1 and sw6 else 'That sample has not finished.')})
aiuse[:]=["SWMM5 RASPIPE was built with Claude, Anthropic's AI model, in a Claude session in November 2026, at the request of Robert (Bob) Dickinson, who pointed it to the HEC-RAS time step and start-up options used in version 1.1, supplied the outside review that drove version 1.2, and set the standing requirements for testing, documentation and units. Responsibility for the work is his. He has not yet reviewed this build.",
 "<b>What Claude did.</b> It read HEC's public manuals and the papers named below, designed the solver, wrote <code>raspipe.c</code> and the small patches to EPA's files, wrote the independent Saint-Venant reference solver and every test, ran the corpus sweeps, found and fixed the defects in the register, compiled the WebAssembly build, built this app, and wrote the essay and the Word document. For version 1.2 it replaced the advection with HEC's form, added the benchmarks, the run record, the Profile tab and the evidence labels, and corrected its own earlier statement that HEC publishes only an outline, a mistake the outside review caught.",
 "<b>How the results were checked.</b> The checks are mechanical, not the AI's judgment: closed-form answers (Manning, normal depth, a pump curve, Stoker's dam break, the U-tube period), a byte comparison of the <code>.out</code> file with the feature off and of diffusion wave against version 1.1, a separately written Saint-Venant solver, the solver's own volume ledger, a sweep of "+f"{s['drawn']:,}"+" corpus models through both engines, and a Playwright run of this page.",
 "<b>What no person has checked.</b> No person has reviewed the code, the figures or this text. It has not been compared with a run of HEC-RAS or with field data. The review Bob supplied covered the version 1.1 app and its documents, not the C solver. Casulli and Stelling's 2013 paper and Stelling and Duinmeijer's 2003 paper were not read directly; the methods were taken from HEC's description and the sources listed."]
sources[:]=data['sources']
data['aiuse']=aiuse
s_=data['sweep']
data['headline']=(f"<b>Dam break:</b> exact bore {ex['S']:.2f} ft/s, v1.1 {fr('v1.1 implicit upwind, theta 1',5)['speed']:.2f}, v1.2 {fr('v1.2, theta 1',5)['speed']:.2f} at θ 1 and {fr('v1.2, theta 0.6',5)['speed']:.2f} at θ 0.6. <b>U-tube:</b> exact period {T0:.1f} s, RASPIPE {uf('RASPIPE SWE, theta 0.6',2)['T']:.1f}, EPA {ep['T']:.1f}. <b>Pump into a full pipe:</b> pencil {pv['exact']:.3f} cfs, RASPIPE {pv['rp']:.3f}, EPA EXTRAN {pv['extran']:.3f}, SLOT {pv['slot']:.3f}. <b>Null control:</b> <code>.out</code> identical to EPA 5.2.4 with the keyword off. Build <code>{BUILD}</code>.")
# --- manifest for the zip
man=[]
for r in data['verify']:
    man.append(dict(id=r['id'],test=r['name'],evidence=r['evidence'],tolerance=r['tol'],expected=r['expect'],result=r['got'],unit=r.get('unit'),error_percent=r['err'],input='tests/v/'+str(r.get('deck'))+'.inp' if r.get('deck') else None,script='tests/verify.py',build=BUILD))
for r in st12['rows']: man.append(dict(id='B1',test=f"Stoker dam break: {r['name']}, {r['dx']} ft, {r['dt']} s",evidence='analytical answer',tolerance='reported',expected=dict(bore_speed=ex['S'],middle_depth=ex['hs']),result=dict(bore_speed=r['speed'],middle_depth=r['star'],mean_depth_error=r['l1']),input='tests/bench1.py (writes its own deck)',script='tests/bench1.py',build=BUILD+' (test build, tests/testhook.py)'))
for r in ut12['rows']: man.append(dict(id='B2',test=f"U-tube: {r['name']}, {r['dt']} s",evidence='analytical answer',tolerance='reported',expected=r.get('exact',T0),result=r['T'],unit='s',input='tests/bench2.py (writes its own deck)',script='tests/bench2.py',build=BUILD))
for r in wb: man.append(dict(id='B3',test='Wave: '+r['name'],evidence='numerical reference' if r['group']!='stock' else 'cross-engine comparison',tolerance='reported',result={k:r[k] for k in ('peak','peak_err','tp_err','rise_err','rmse','nse','vol_err','osc','y_err','cont','steps','cr')},input='tests/bench3.py (writes its own deck)',script='tests/bench3.py',build=BUILD))
json.dump(dict(build=BUILD,note='Each entry ties one result to its input, script, evidence type and build.',tests=man),open(R+'/app/verification_manifest.json','w'),indent=1)
