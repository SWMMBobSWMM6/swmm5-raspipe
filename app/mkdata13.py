# --- version 1.3: SWMM6 on the same decks. Everything here comes from tests/bench4.py and sweep/sweep6.py.
six=json.load(open(R+'/tests/v/sixcmp.json')); sixn=json.load(open(R+'/tests/v/sixcmp_latest.json'))
T=six['tests']; MO=[m for m,_ in six['modes']]; LB=dict(six['modes'])
LB.update({'s6ex':'SWMM6, EXTRAN (the null control)','s6dw':'SWMM6 modified DW','s6fv':'SWMM6 FV, defaults (4 cells, order 1)','s6fv2':'SWMM6 FV, matched mesh, order 2','rpsw':'RASPIPE full equations, theta 0.6'})
def g(t,m,k):
    v=T[t][m]
    return v.get(k)
def cell(x,d=3,pre=''):
    return '–' if x is None else (pre+f"{x:.{d}f}")
rows=[['Answer','3.563 cfs','4.599 cfs','0 cfs',f"{six['T0']:.1f} s",f"{six['S']:.2f} ft/s",'0 ft','0%','0 cfs']]
for m in MO:
    p=g('pipe',m,'got'); pu=g('pump',m,'got'); l=g('lake',m,'got'); ut=g('utube',m,'T'); d=g('dambreak',m,'speed'); e=g('dambreak',m,'l1'); w=g('wave',m,'peak_err'); rm=g('wave',m,'rmse')
    rows.append([LB[m],cell(abs(p) if p is not None else None),cell(pu),('0' if l==0 else cell(l,3) if l>=1e-3 else f"{l:.0e}"),('no oscillation' if ut is None else f"{ut:.1f}"),cell(d,2),cell(e,3),f"{w:+.2f}%",cell(rm,3)])
same=all(abs((g(t,'s6ex',k) or 0)-(g(t,'ex5',k) or 0))<=1e-3*max(1,abs(g(t,'ex5',k) or 0)) for t,k in (('pipe','got'),('series','got'),('lake','got'),('pump','got'),('utube','T'),('dambreak','l1'),('dambreak','speed'),('wave','peak'),('wave','rmse')))
assert same
sf2=g('pipe','s6fv','got'); e4=[r for r in T['utube'].values()]
notes=["SWMM6 as written, with EXTRAN, matches EPA 5.2.4 on every line, which is the control that makes the other SWMM6 rows mean something.",
 f"The browser engine is the October 17 alpha.4 build. A native build of swmm6_rel from October 29 gave the same flows and heads on all eight decks. Its FV continuity reads 0.000% where the October 17 build reads up to {abs(min(g(t,'s6fv2','cont') or 0 for t in ('pipe','lake','series'))):.1f}%, so that part has been fixed since.",
 f"Open question for the OpenSWMM team: on the pipe deck FV's steady flow moves with FV_SLOT_CELERITY, 4.60 cfs at 30 ft/s, 2.28 at 100, 1.03 at 300, and a steady state shouldn't depend on it. Make both conduits the same size and it gives 3.50 cfs against EPA's 3.55 on that deck. The pump deck moves the same way. The cause has not been traced, and it may be a setting that hasn't been tried.",
 "DYNAMIC_SLOT gets the right flows, but its continuity reads -44.8% on water at rest: stored volume is 0.195 ac-ft at the start and 0.282 at the end with nothing moving, so the final figure appears to count slot volume that the initial figure doesn't.",
 "Open question for the OpenSWMM team: NODE_CONTINUITY SEMI_IMPLICIT loses water while heads are moving. On the short wide box below it stays stable at a 30 s step where EPA and SWMM6 EXTRAN blow up, but 15% of the water goes missing on the way to steady flow. The Doc tab shows the code, the test and the part still not traced.",
 "FV's 8 to 10 cfs on water at rest is a start-up surge: flow is back to zero within the first quarter of the run, and it stays there.",
 "EPA SLOT and SWMM6 SLOT both fail the pipe deck: the junction falls to its invert in the first report period and stays there. That row is not diagnosed.",
 "The wave deck is two 4,000 ft conduits. Modified DW keeps SWMM's one flow per conduit, so it sits with EPA here. FV and RASPIPE cut the conduits into cells. Mesh is the difference, not the equation set."]
data['presets'][:0]=[
 dict(label='Four engines: wave, 100 ft cells',file='long_pipe_wave.inp',elem='C2',o=dict(maxc=800),note='RASPIPE and FV at 100 ft. EPA and modified DW keep one flow per conduit.'),
 dict(label='Four engines: dam break, plain deck',file='dam_break_chain.inp',elem='K150',vari='depth',o=dict(eqn='SWE',theta=0.6,cell=25,cour=0,vs='0',stg='NO'),note='200 conduits of 20 ft. The node 3,000 ft along sees the bore arrive just before 60 s.'),
 dict(label='Four engines: U-tube',file='u_tube.inp',elem='S1',vari='depth',o=dict(eqn='SWE',theta=0.6,cour=0,vs='0',dt='2',stg='NO',maxc=800),note='Exact period 441.7 s. EPA runs long, SWMM6 FV runs a little long.'),
 dict(label='Four engines: pump into a full pipe',file='pump_full_pipe.inp',elem='C1',o=dict(maxc=800),note='Pencil answer 4.599 cfs. See the open question on the Verify tab.'),
 dict(label='Four engines: full pipe between two stages',file='full_pipe.inp',elem='C1',o=dict(maxc=800),note='Manning 3.563 cfs. See the open question on the Verify tab.'),
 dict(label='Four engines: short wide box at 30 s',file='short_box_30s.inp',elem='C2',o=dict(maxc=800),note='One cfs through a 36 ft by 200 ft box at a fixed 30 s step. EPA blows up. Modified DW holds together but takes 12 hours to reach 1 cfs, and water goes missing on the way. Untick SEMI_IMPLICIT and it blows up too.')]
# --- corpus sample
def sw6():
    p=R+'/sweep/r6_results.jsonl'
    if not os.path.exists(p): return None
    A={}
    for l in open(p):
        r=json.loads(l); A[r['inp']]=r
    return A
A6=sw6(); S1=[json.loads(l) for l in open(R+'/sweep/r12_t1/results.jsonl')]; S1={r['inp']:r for r in S1 if not r.get('skip')}
M0={r['inp']:r for r in (json.loads(l) for l in open(R+'/app/sweep_merged.jsonl')) if not r.get('skip')}
sxc=[];sxn=''
if A6 and len(A6)>=len(S1)-1:
    ok6=lambda d:d and d.get('rc')==0 and d.get('cont') is not None and not d.get('err')
    ks=[k for k in S1 if k in A6]
    def col(name,fin,cont,tmo,sec):
        done=[k for k in ks if fin(k)]
        return dict(name=name,done=len(done),tmo=sum(1 for k in ks if tmo(k)),fin=fin,cont=cont,sec=sec)
    fr=lambda k:S1[k].get('ref_rc')==0 and (S1[k].get('ref') or {}).get('cont') is not None and not (S1[k].get('ref') or {}).get('err')
    fs=lambda k:S1[k].get('rp_rc')==0 and (S1[k].get('rp') or {}).get('cont') is not None and not (S1[k].get('rp') or {}).get('err')
    fd=lambda k:k in M0 and M0[k].get('rp_rc')==0 and (M0[k].get('rp') or {}).get('cont') is not None and not (M0[k].get('rp') or {}).get('err')
    cols=[col('EPA 5.2.4',fr,lambda k:S1[k]['ref']['cont'],lambda k:S1[k].get('ref_rc')==-99,lambda k:S1[k].get('ref_t')),
     col('SWMM6 modified DW',lambda k:ok6(A6[k]['dw']),lambda k:A6[k]['dw']['cont'],lambda k:A6[k]['dw']['rc']==-99,lambda k:A6[k]['dw']['sec']),
     col('SWMM6 FV, 100 ft, order 2',lambda k:ok6(A6[k]['fv']),lambda k:A6[k]['fv']['cont'],lambda k:A6[k]['fv']['rc']==-99,lambda k:A6[k]['fv']['sec']),
     col('RASPIPE diffusion wave',fd,lambda k:M0[k]['rp']['cont'],lambda k:k in M0 and M0[k].get('rp_rc')==-99,lambda k:M0[k].get('rp_t')),
     col('RASPIPE full equations',fs,lambda k:S1[k]['rp']['cont'],lambda k:S1[k].get('rp_rc')==-99,lambda k:S1[k].get('rp_t'))]
    both=[k for k in ks if all(c['fin'](k) for c in cols)]
    E0=lambda k:abs(cols[0]['cont'](k)); D0=lambda k:abs(cols[1]['cont'](k))
    ctail=dict(n=len(both),w=sum(1 for k in both if D0(k)>=E0(k)+5),b=sum(1 for k in both if D0(k)<=E0(k)-5),e10=sum(1 for k in both if E0(k)>=10),d10=sum(1 for k in both if D0(k)>=10))
    for c in cols:
        v=sorted(abs(c['cont'](k)) for k in both); t=sorted((c['sec'](k) or 0)/max(cols[0]['sec'](k) or 1e-3,1e-3) for k in both)
        sxc.append([c['name'],str(c['done']),str(c['tmo']),f"{pct(v,.5):.3f}%",f"{pct(v,.9):.3f}%",str(sum(1 for x in v if x>=1)),f"{pct(t,.5):.1f}×"])
    sxn=f"{len(ks)} conduit models drawn at random from the corpus. Finished and time limit are out of those {len(ks)}. Continuity and run time are on the {len(both)} models all five finished, so each column is the same models. RASPIPE diffusion wave ran with a 60 s limit, the rest 45 s. SWMM6 here is the native October 29 build. Run times are single runs on one machine, not interleaved pairs, so read only the order of magnitude. Run time is the median ratio to EPA. Continuity is each engine's own report of itself, so it can't prove a run right, as the options table below shows."
def sw6b():
    p=R+'/sweep/r6b_results.jsonl'
    if not os.path.exists(p): return None
    return [json.loads(l) for l in open(p)]
OB=sw6b(); sxo=[]; sxon=''; oval={}
if OB and A6 and len(OB)>=(int(os.environ.get('PARTIAL','0')) or 140):
    ok7=lambda d:d and d.get('rc')==0 and d.get('cont') is not None and not d.get('err')
    OM=[('plain','SWMM6 EXTRAN, nothing added'),('slot','DYNAMIC_SLOT alone'),('accel','ANDERSON_ACCEL alone'),('noSemi','DYNAMIC_SLOT and ANDERSON_ACCEL'),('semi','SEMI_IMPLICIT alone'),('semiN','SEMI_IMPLICIT, test patch'),('all','All three, the modified DW')]
    for r in OB: r['all']=A6[r['inp']]['dw'] if r['inp'] in A6 else None
    fin=[r for r in OB if all(ok7(r[m]) for m,_ in OM)]
    for m,lab in OM:
        v=sorted(abs(r[m]['cont']) for r in fin)
        wo=sum(1 for r in fin if abs(r[m]['cont'])>=abs(r['plain']['cont'])+5); be=sum(1 for r in fin if abs(r[m]['cont'])<=abs(r['plain']['cont'])-5)
        sxo.append([lab,str(sum(1 for r in OB if ok7(r[m]))),str(sum(1 for r in OB if r[m] and r[m].get('rc')==-99)),f"{pct(v,.5):.3f}%",f"{pct(v,.9):.3f}%",str(sum(1 for x in v if x>=1)),str(sum(1 for x in v if x>=10)),str(wo),str(be)])
        oval.update({f'six.o.{m}.med':f"{pct(v,.5):.3f}%",f'six.o.{m}.p90':f"{pct(v,.9):.3f}%",f'six.o.{m}.worse':str(wo),f'six.o.{m}.better':str(be),f'six.o.{m}.p10':str(sum(1 for x in v if x>=10))})
    oval['six.o.n']=str(len(fin)); oval['six.o.total']=str(len(OB))
    q=lambda m,k:oval[f'six.o.{m}.{k}']
    rr=lambda n:next(r for r in OB if r['inp'].endswith('/'+n))
    fc=lambda x:f"{x:,.0f}%" if abs(x)>=100 else f"{x:.3f}%"
    oval['six.o.reading']=(f"Read each row against the first. None of these options is all good or all bad. `DYNAMIC_SLOT` alone moves {q('slot','worse')} of the {len(fin)} models at least five points the wrong way and {q('slot','better')} the right way, and the right way can be dramatic: `CWCD` goes from {fc(rr('CWCD.inp')['plain']['cont'])} to {fc(rr('CWCD.inp')['slot']['cont'])}. Anderson acceleration moves {q('accel','worse')} and {q('accel','better')}. `SEMI_IMPLICIT` alone moves {q('semi','worse')} and {q('semi','better')}, the largest count in either direction, and all three together come to {q('all','worse')} and {q('all','better')}. `Peter`, `IMPERIAL` and `pump_exam` are all on the wrong-way list for `SEMI_IMPLICIT`, so that is the branch we read first. The `DYNAMIC_SLOT` wrong-way list, `FLOOD1` and `routing_inertial_partial` among them, has not been sorted out.")
    sxon=f"{len(OB)} conduit models from the same sample, native October 29 build, 45 s limit, each run with DYNWAVE. Continuity columns are on the {len(fin)} models every row finished. Worse and better count models whose continuity error moved at least 5 points from the first row, so one wild deck can't swing the reading. The test patch is a diagnostic, not a fix."
SB=json.load(open(R+'/tests/v/shortbox.json')); SS=json.load(open(R+'/tests/v/shortbox_series.json')); SM=json.load(open(R+'/tests/v/semi_matrix.json'))
BR=[('EPA 5.2.4, 1 s step (the reference)','EPA 5.2.4, 1 s'),('EPA 5.2.4, 30 s','EPA 5.2.4, 30 s'),('SWMM6 EXTRAN, 30 s','SWMM6 EXTRAN'),('SWMM6 SEMI_IMPLICIT alone, 30 s','SWMM6 SEMI_IMPLICIT only'),('SWMM6 modified DW, 30 s','SWMM6 modified DW'),('SEMI_IMPLICIT with the test patch, 30 s','SWMM6 SEMI_IMPLICIT, test patch'),('SWMM6 FV, 25 ft cells, order 2, 30 s','SWMM6 FV, 25 ft, order 2'),('RASPIPE diffusion wave, 30 s','RASPIPE diffusion wave'),('RASPIPE full equations, 30 s','RASPIPE full equations')]
boxr=[[l,f"{SB[k]['o']:.3f}",f"{SB[k]['fl']:.3f}",f"{SB[k]['c']:+.3f}%"] for l,k in BR]
bx=SS['patched semi 30 s']['box']; c2=SS['modDW 30 s']['c2']; c2r=SS['EPA 1 s']['c2']
hr=lambda q:next((i+1)*5/60 for i,x in enumerate(q) if x>=.99)
oval.update({'six.box.lo':f"{min(bx):.0f}",'six.box.hi':f"{max(bx):+.0f}",'six.box.hr':f"{hr(c2):.0f}",'six.box.hr0':f"{hr(c2r):.0f}",'six.box.dw':f"{SB['SWMM6 modified DW']['o']:.3f}",'six.box.ref':f"{SB['EPA 5.2.4, 1 s']['o']:.3f}"})
assert max(c2[-12:])>=.99
data_semi=dict(head=['Deck','SWMM6 EXTRAN','SEMI_IMPLICIT as written','As written, head tolerance 1e-8','Test patch','Test patch, head tolerance 1e-8'],rows=[[k.split('/')[-1].replace('.inp','')]+[f"{SM[k][m]['cont']:.3f}%" for m in ('plain','semi','semit','patch','patcht')] for k in SM])
data['six']=dict(head=['Engine','Full pipe','Pump','At rest, largest flow','U-tube period','Dam break bore','Dam break mean depth error','Wave peak','Wave RMSE'],rows=rows,notes=notes,
  chart=dict(exact=dict(x=xe,h=[round(hx(x),4) for x in xe]),**{m:dict(x=[a for a,b in T['dambreak'][m]['prof']],h=[b for a,b in T['dambreak'][m]['prof']]) for m in ('ex5','s6dw','s6fv2','rpsw')}),corpus=sxc,corpusnote=sxn,opt=dict(head=['Options','Finished','Time limit','Median error','90th percentile','Past 1%','Past 10%','Worse by 5 points','Better by 5 points'],rows=sxo,note=sxon),box=dict(head=['Engine and step','Out the outfall (ac-ft)','Flooded (ac-ft)','Continuity'],rows=boxr,note='One cfs for 12 hours into a box 36 ft long and 200 ft wide, then a 2 ft pipe to a free outfall. EPA and SWMM6 EXTRAN come apart at 30 s. SEMI_IMPLICIT holds together, and loses water while the head rises. The test patch closes the balance, but the box flow rings. The browser engine and the native build agree on the SWMM6 continuity figures here.'),semi=data_semi,series=SS)
data['headline']=data['headline'].replace('<b>Null control:</b>','<b>SWMM6:</b> compared with both its modified DW and its FV below. <b>Null control:</b>')
data['sweep']['six']=None
val.update({'six.same':'eight','six.ex5':f"{g('dambreak','ex5','speed_err'):+.1f}",'six.s6dw':f"{g('dambreak','s6dw','speed_err'):+.1f}",'six.s6fv':f"{g('dambreak','s6fv2','speed_err'):+.1f}",'six.rp':f"{g('dambreak','rpsw','speed_err'):+.1f}",
 'six.fvl':f"{g('dambreak','s6fv2','l1'):.3f}",'six.rpl':f"{g('dambreak','rpsw','l1'):.3f}",'six.exl':f"{g('dambreak','ex5','l1'):.2f}",'six.ut5':f"{g('utube','ex5','err'):+.1f}",'six.utd':f"{g('utube','s6dw','err'):+.1f}",'six.utf':f"{g('utube','s6fv2','err'):+.1f}",'six.utr':f"{g('utube','rpsw','err'):+.2f}",
 'six.w5':f"{g('wave','ex5','peak_err'):+.1f}",'six.wd':f"{g('wave','s6dw','peak_err'):+.1f}",'six.wf0':f"{g('wave','s6fv','peak_err'):+.1f}",'six.wf':f"{g('wave','s6fv2','peak_err'):+.1f}",'six.wr':f"{g('wave','rpdw','peak_err'):+.1f}",'six.wrs':f"{g('wave','rpsw','peak_err'):+.1f}",
 'six.spike':f"{max(h for x,h in T['dambreak']['ex5']['prof'] if x>2000):.1f}",'six.spiked':f"{max(h for x,h in T['dambreak']['s6dw']['prof'] if x>2000):.1f}",'six.pipef':f"{abs(g('pipe','s6fv','got')):.2f}",'six.pumpf':f"{g('pump','s6fv','got'):.2f}",'six.pumpf2':f"{g('pump','s6fv2','got'):.2f}",
 'six.dwmed':(sxc[1][3] if sxc else '?'),'six.tail.n':(str(ctail['n']) if sxc else '?'),'six.tail.w':(str(ctail['w']) if sxc else '?'),'six.tail.b':(str(ctail['b']) if sxc else '?'),'six.tail.e10':(str(ctail['e10']) if sxc else '?'),'six.tail.d10':(str(ctail['d10']) if sxc else '?'),'six.epamed':(sxc[0][3] if sxc else '?'),'six.corpus':(f"On {len(both)} random corpus models that all five runs finished, median continuity was {sxc[0][3]} for EPA, {sxc[1][3]} for modified DW, {sxc[2][3]} for FV, {sxc[3][3]} for RASPIPE diffusion wave and {sxc[4][3]} for its full equations. The medians for run time against EPA were {sxc[1][6]}, {sxc[2][6]}, {sxc[3][6]} and {sxc[4][6]}, from single runs, so read only the order of magnitude. Time limits took {sxc[1][2]}, {sxc[2][2]}, {sxc[3][2]} and {sxc[4][2]} of the {len(ks)} against {sxc[0][2]} for EPA." if sxc else 'The corpus sample has not finished.')})
aiuse[0]=aiuse[0].replace('supplied the outside review that drove version 1.2,','supplied the outside review that drove version 1.2, asked for SWMM6 FV and the SWMM6 modified dynamic wave to be compared in version 1.3,')
aiuse[1]=aiuse[1].replace("a mistake the outside review caught.","a mistake the outside review caught. For version 1.3 it reused the OpenSWMM 6 alpha.4 engine from the Seven SWMM Engines app, built the latest SWMM6 natively, wrote the shared comparison decks and scoring, and added SWMM6 to this page. It also ran SWMM6 option by option to find why water went missing, read the SWMM6 source, and tried a change behind a switch in a private test copy. That change is not in this page's engines and is not a proposed fix.")
val.update(oval)
data['aiuse']=aiuse
sources[:0]=[["OpenSWMM Engine (HydroCouple), swmm6_rel, Apache License 2.0. Copyright 2026 HydroCouple Developers","https://github.com/HydroCouple/openswmm.engine"]]
data['sources']=sources
data['prov']=data['prov'].replace('<b>Browser build:</b>','<b>SWMM6:</b> OpenSWMM 6.0.0-alpha.4, swmm6_rel 3c30f1e, Apache 2.0. <b>Browser build:</b>')

exec(open(R+'/app/mkdata14.py').read())
