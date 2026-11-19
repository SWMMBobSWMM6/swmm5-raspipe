#!/usr/bin/env python3
"""One source, two outputs: doc/essay.md becomes the Doc tab and the .docx. Then the single-file app."""
import json, re, base64, subprocess, os, html, sys
sys.path.insert(0,'/root/rp/app'); sys.path.insert(0,'/root/rp/tests')
import mkfigs, gen, gen2
A='/root/rp/app'; D=A+'/dist'
v=json.load(open(A+'/vals.json')); data=json.load(open(A+'/data.json')); val=v['val']
W=json.load(open('/root/rp/tests/v/wave3.json'))
sw=data['sweep']; figs=mkfigs.all_figs(v['pump'],W,sw,v['opt'])
figs['sixdam']=mkfigs.fig_sixdam(data['six']['chart'])
figs['shortbox']=mkfigs.fig_shortbox(data['six']['series'])
figs['ras']=mkfigs.fig_ras(data['ras']['ser']); figs['rasvol']=mkfigs.fig_rasvol(data['ras']['vol'])
figs.update(mkfigs.more_figs(v['pump'],json.load(open('/root/rp/tests/v/slot_terms.json')),data['bench'],data['wave']['rows']))
TABLES=dict(opts=dict(head=data['six']['opt']['head'],rows=data['six']['opt']['rows'],w=[2260,880,720,1000,1000,680,680,1070,1070]),box=dict(head=data['six']['box']['head'],rows=data['six']['box']['rows'],w=[4200,1900,1630,1630]),semi=dict(head=data['six']['semi']['head'],rows=data['six']['semi']['rows'],w=[2360,1200,1500,1500,1300,1500]),six=dict(head=data['six']['head'],rows=data['six']['rows'],w=[2360,780,780,860,960,960,1000,830,830]),method=dict(head=['Part','HEC documentation','RASPIPE 1.3','Difference, and the test'],rows=data['method'],w=[1050,2850,2850,2610]),outcomes=dict(head=['Outcome','EPA 5.2.4','RASPIPE','Models'],rows=sw['outcomes'],w=[4860,1600,1600,1300]))
RAS14=json.load(open('/root/rp/tests/v/ras14.json'))
# --- samples
exec(open('/root/rp/tests/wave.py').read().split('def run(')[0].split('RP=')[0] if False else '')
src_w=open('/root/rp/tests/wave.py').read()
ns={}; exec(src_w[:src_w.index('def run(')],ns)
wavedeck=ns['deck']('DYNWAVE','','5').replace('REPORT_STEP 00:00:30','REPORT_STEP 00:01:00')
assert 'REPORT_STEP 00:01:00' in wavedeck
utsrc=open('/root/rp/tests/bench2.py').read(); uns={}; exec(utsrc[:utsrc.index('def run(')],uns); utdeck=uns['deck']('DYNWAVE','VARIABLE_STEP 0',2)
samples=[dict(name='Long pipe wave, 8,000 ft',file='long_pipe_wave.inp',inp=wavedeck,pick='C2',note='The wave from the Verify tab: two 4,000 ft conduits, 2 cfs for two hours, then the wave. Stock smears it. Shorten Cell length and raise Most cells to see the peak come up.'),
 dict(name='Mixed network',file='mixed_network.inp',inp=gen2.mixed('DYNWAVE',extra='VARIABLE_STEP 0.75'),pick='C2',note='Storage, pumps, an orifice, a weir, an outlet and a flap gate, written for this project. Peaks agree within about 2%.'),
 dict(name='Pump into a full pipe',file='pump_full_pipe.inp',inp=open('/root/rp/tests/v/pump_EXTRAN.inp').read(),pick='C1',note='The pipe stays full under an 8 ft tailwater. Pencil answer 4.599 cfs. This sample runs EXTRAN against RASPIPE, and both land on it.'),
 dict(name='Inverted siphon',file='siphon_larger_SW5.inp',inp=open('/root/rp/corpus/EPA/siphon_larger_SW5.inp',errors='replace').read(),pick='',note='From the EPA folder of the 1729 corpus, 2,000 cfs through big pipes. Stock oscillates, RASPIPE holds steady.'),
 dict(name='Outfall stage on a dry network',file='stage_on_dry_network.inp',inp=open('/root/rp/tests/v/st3.inp').read(),pick='C2',note='A stage 5 ft up the outfall and no water in the pipes. Stock surges. RASPIPE projects the stage up the pipes and nothing moves. Turn Project stage off to see the surge.'),
 dict(name='Start-up spike',file='startup_spike.inp',inp=open('/root/rp/tests/v/w1.inp').read().replace('RASPIPE','DYNWAVE',1),pick='C1',note='A full manhole dumps into a dry 5 cfs pipe. Set Warm up steps to 60 and the spike goes away.'),
 dict(name='Filling a dead-end pipe',file='filling_pipe.inp',inp=open('/root/rp/tests/v/fill.inp').read(),pick='',note='Two cfs fills a sealed pipe and its shafts. Watch node depth as the crown is reached.'),
 dict(name='Dam break as a plain deck',file='dam_break_chain.inp',inp=open('/root/rp/tests/v/chain.inp').read(),pick='K150',note='Ten feet of water behind two feet, across 200 conduits of 20 ft. Read depth, not flow. Use the case in the list above for the settings the Verify tab used.'),
 dict(name='Full pipe between two stages',file='full_pipe.inp',inp=open('/root/rp/tests/v/full.inp').read().replace('RASPIPE','DYNWAVE',1),pick='C1',note='A 1 ft pipe, 1,000 ft long, under a 10 ft head difference. Manning gives 3.563 cfs.'),
 dict(name='Short wide box at 30 s',file='short_box_30s.inp',inp=open('/root/rp/app/samples_short_box.txt').read(),pick='C2',note='One cfs through a box 36 ft long and 200 ft wide at a fixed 30 s step. EPA blows up. Use the case in the list above to run it through every engine.'),
 dict(name='EXTRAN 1 as HEC-RAS 7.0.2 stores it',file='extran1_hecras.inp',inp=RAS14['sample']['inp'].replace('FLOW_ROUTING DYNWAVE','FLOW_ROUTING DYNWAVE',1),pick='1602',pickN='82309',ref=RAS14['sample']['ref'],note="HEC's EXTRAN 1, built from the geometry in HEC-RAS 7.0.2's own results file, with RAS's stage at 16009 as the outfall and the rim at 80608 raised to RAS's ponded peak. The dashed line is RAS's stored result. Use the three HEC-RAS cases above for the settings the Verify tab used: 100 ft cells, up to 100 a conduit."),
 dict(name='U-tube, two tanks',file='u_tube.inp',inp=utdeck,pick='S1',note='Water sloshes between two tanks through a full pipe. The exact period is 441.7 s. Use the U-tube case in the list above: diffusion wave has no inertia and will not oscillate.')]

TABLES['rasscore']=dict(head=data['ras']['score']['head'],rows=data['ras']['score']['rows'],w=[2760,1220,1220,1340,1340,1480])
TABLES['rasho']=dict(head=data['ras']['ho']['head'],rows=data['ras']['ho']['rows'],w=[2160,1440,1440,1440,1440,1440])
# --- complexity, measured with the Meter's own analyzer (tools/complexity.js); the shipped-file line uses the last build
CX=json.loads(subprocess.run(['node',A+'/tools/complexity.js',D+'/SWMM5-RASPIPE.html'],capture_output=True,text=True,check=True).stdout)
json.dump(CX,open(A+'/complexity.json','w'),indent=1)
G=CX['groups']; val.update({'cx.index':f"{CX['index']:.1f}",'cx.ship':f"{CX['shipped']['index']:.1f}" if CX['shipped'] else 'not measured','cx.files':str(CX['nfiles']),'cx.size':f"{G['size']:.1f}",'cx.struct':f"{G['structure']:.1f}",'cx.tests':f"{G['tests']:.1f}",'cx.swmm':f"{G['swmm']:.1f}"})
GN={'bulk':'Size','branches':'Structure','routines':'Structure','checks':'Test evidence','stack':'Structure','dependencies':'Structure','formats':'Structure','swmm':'SWMM vocabulary'}
fmtn=lambda x:f"{x:,.0f}" if float(x)>=100 else f"{x:g}"
TABLES['cxs']=dict(head=['Dimension','Group','This app','HydroCouple','Score'],rows=[[r['name'],GN.get(r['key'],''),fmtn(r['value']),fmtn(r['anchor']),f"{r['score']:.1f}"] for r in CX['rows']]+[['Complexity index','all eight','','',f"**{CX['index']:.1f}**"]],w=[2400,1900,1700,1700,1660])
ntest=len([f for f in os.listdir('/root/rp/tests') if f.endswith('.py')])+len([f for f in os.listdir('/root/rp/hecras/cmp') if f.endswith('.py')])
tabs=open(A+'/app.src.html').read().count('role="tab" id=')
CARRY=[['Engines','EPA SWMM 5.2.4 with RASPIPE 1.3 in one WebAssembly file, and OpenSWMM 6.0.0-alpha.4 with its modified dynamic wave and FV'],['Tabs',str(tabs)],['Sample models',str(len(samples))],['Cases that reproduce a published figure',str(len(data['presets']))],['Tests in the Verify table, each with its kind of evidence',str(len(data['verify']))],['HEC-RAS 7.0.2 plans compared, and runs scored against them','4 plans, '+str(4*6)+' runs'],['Browser against native runs compared byte for byte',str(json.load(open('/root/rp/wasm/parity13.json'))['parity']['n'])],['Test and comparison scripts',str(ntest)],['Figures in this essay','@@NF@@']]
TABLES['cxc']=dict(head=['What the app carries','Count'],rows=CARRY,w=[5200,4160])
META=json.load(open(A+'/doc/essay.json'))
src=open(A+'/doc/essay.md').read()
for k,x in val.items(): src=src.replace('{{'+k+'}}',str(x))
left=re.findall(r'\{\{(?!fig:|table:|aiuse|sources|related)[^}]*\}\}',src); assert not left,left

# --- parse
lines=src.split('\n'); title=lines[0][2:]; sub=lines[1]; blocks=[]; i=2
while i<len(lines):
    l=lines[i]
    if not l.strip(): i+=1; continue
    if l.startswith('## '): blocks.append(dict(t='h2',x=l[3:])); i+=1; continue
    if l.startswith('```'):
        i+=1; c=[]
        while not lines[i].startswith('```'): c.append(lines[i]); i+=1
        blocks.append(dict(t='code',x='\n'.join(c))); i+=1; continue
    m=re.match(r'\{\{fig:(\w+)\|(.*)\}\}$',l)
    if m: blocks.append(dict(t='fig',k=m.group(1),x=m.group(2))); i+=1; continue
    m=re.match(r'\{\{table:(\w+)\}\}$',l)
    if m: blocks.append(dict(t='table',**TABLES[m.group(1)])); i+=1; continue
    if l.strip()=='{{aiuse}}':
        for p in v['aiuse']: blocks.append(dict(t='p',x=re.sub(r'</?code>','`',p).replace('<b>','**').replace('</b>','**')))
        i+=1; continue
    if l.strip()=='{{sources}}':
        blocks.append(dict(t='ul',x=[(s[0]+(': '+s[1] if s[1] else '')) for s in v['sources']],links=v['sources'])); i+=1; continue
    if l.startswith('- '):
        it=[]
        while i<len(lines) and lines[i].startswith('- '): it.append(lines[i][2:]); i+=1
        blocks.append(dict(t='ul',x=it)); continue
    if re.match(r'\d+\. ',l):
        it=[]
        while i<len(lines) and re.match(r'\d+\. ',lines[i]): it.append(re.sub(r'^\d+\. ','',lines[i])); i+=1
        blocks.append(dict(t='ol',x=it)); continue
    blocks.append(dict(t='p',x=l)); i+=1
# --- related apps
for i,b in enumerate(blocks):
    if b['t']=='p' and b['x'].strip()=='{{related}}':
        blocks[i]=dict(t='ul',x=[f"{r['t']} ({r['where']}): {r['why']}" for r in META['related']],links=[[f"{r['t']} ({r['where']}): {r['why']}",r['url']] for r in META['related']])
# --- template values in the essay source of summaries and questions
def subv(t):
    for k,x in val.items(): t=t.replace('{{'+k+'}}',str(x))
    left=re.findall(r'\{\{[^}]*\}\}',t); assert not left,left; return t
SM=META['summaries']; SEC={k:subv(v) for k,v in SM['sections'].items()}
words=lambda t:len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.,'’%²³/+-]*",t))
U=subv(META['unique']); S1=subv(SM['one_sentence']); S2=subv(SM['one_paragraph']); S3=[subv(x) for x in SM['one_page']]; Q=[dict(q=subv(x['q']),a=subv(x['a'])) for x in META['questions']]
WC=dict(unique=words(U),one_sentence=words(S1),one_paragraph=words(S2),one_page=sum(words(x) for x in S3))
assert 60<=WC['unique']<=120 and WC['one_sentence']<=40 and 90<=WC['one_paragraph']<=130 and 350<=WC['one_page']<=480 and 4<=len(S3)<=6 and 3<=len(Q)<=5,WC
img=SM['one_page_image']; assert img['fig'] in figs
front=[dict(t='h2',x='What is unique about this app'),dict(t='p',x=U),dict(t='panelopen'),dict(t='h3',x='In one sentence'),dict(t='p',x=S1),dict(t='h3',x='In one paragraph'),dict(t='p',x=S2),
  dict(t='h3',x=f"{['Three','Four','Five'][len(Q)-3]} questions to answer before you read on"),dict(t='p',x='Try to answer each one before you read on. Working out an answer yourself helps you remember it. The answers are at the end.'),dict(t='ol',x=[q['q'] for q in Q]),dict(t='h3',x='In one page')]
for i,x in enumerate(S3):
    front.append(dict(t='p',x=x))
    if i==img['after']: front.append(dict(t='fig',k=img['fig'],x=subv(img['caption'])))
front.append(dict(t='panelclose'))
back=[dict(t='h2',x='Answers to the opening questions')]
for q in Q: back+= [dict(t='p',x='**'+q['q']+'**'),dict(t='p',x=q['a'])]
nf_body=sum(1 for b in blocks if b['t']=='fig')
TABLES['cxc']['rows']=[[a,b.replace('@@NF@@',str(nf_body))] for a,b in TABLES['cxc']['rows']]
back+=[dict(t='h2',x='How complex is this app'),dict(t='p',x=f"The SWMM App Complexity Meter grades a program's source on eight counted dimensions against the HydroCouple GitHub organization, which is fixed at 100. It was run here with its own analyzer, meter-core.js {CX['analyzer']}, against baseline {CX['baseline']}, on the {CX['nfiles']} hand-written source files behind this page: raspipe.c, the page source, the build and data scripts, the tests and the HEC-RAS comparison scripts."),
  dict(t='table',**TABLES['cxs']),dict(t='p',x=f"Sub-indexes: Size {G['size']:.1f}, Structure {G['structure']:.1f}, Test evidence {G['tests']:.1f}, SWMM vocabulary {G['swmm']:.1f}. The shipped .html file alone scores {val['cx.ship']}."),
  dict(t='table',**TABLES['cxc']),
  dict(t='p',x=f"Read it with three cautions. The index measures how much program there is, not whether it is right; that is what the Verify tab is for. The scale is logarithmic, 25 points for every factor of ten, so an index of {CX['index']:.1f} sits {(100-CX['index'])/25:.1f} factors of ten below HydroCouple, not at {CX['index']:.0f}% of it. And it reads low on test evidence for a reason: the checks here are Python scripts that compare numbers and write JSON, not test frameworks with assertion markers the Meter can count. EPA SWMM 5.2.4's own C files, the compiled WebAssembly, the WASI shim and the SWMM6 glue are left out, because they are not this project's code.")]
blocks=front+blocks+back
# one-sentence summary under every h2
out=[]
for b in blocks:
    out.append(b)
    if b['t']=='h2':
        assert b['x'] in SEC, 'no section sentence for '+b['x']
        out.append(dict(t='lede',x=SEC[b['x']]))
blocks=out
nfig=sum(1 for b in blocks if b['t']=='fig'); assert nfig>=7
assert sum(1 for b in front if b['t']=='fig')==1
for b in blocks:
    for x in ([b.get('x')] if isinstance(b.get('x'),str) else (b.get('x') or [])):
        assert '—' not in x, x[:60]
json.dump(dict(words=WC,questions=len(Q),figures=nfig,sections=len([b for b in blocks if b['t']=='h2'])),open(A+'/doc_gate.json','w'))

# --- html
def inl(s):
    s=html.escape(s,quote=False)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return s
h=f'<h2 style="margin-top:16px;font-size:26px">{inl(title)}</h2><p style="color:var(--ink-dim)">{inl(sub)}</p><p class="status" style="margin:0 0 8px">Robert Dickinson · SWMM5 RASPIPE 1.4, engine 1.3 · November 2026</p>'
secs=[b['x'] for b in blocks if b['t']=='h2']; slug=lambda s:'d-'+re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
h+='<nav class="toc" aria-label="Contents">'+''.join(f'<a href="#{slug(s)}">{inl(s)}</a>' for s in secs)+'</nav>'
op=False
for b in blocks:
    t=b['t']
    if t=='h2':
        if op: h+='</details>'
        h+=f'<details open id="{slug(b["x"])}"><summary><h2>{inl(b["x"])}</h2></summary>'; op=True
    elif t=='p': h+=f'<p>{inl(b["x"])}</p>'
    elif t=='lede': h+=f'<p class="lede1"><i>{inl(b["x"])}</i></p>'
    elif t=='h3': h+=f'<h3 class="dh3">{inl(b["x"])}</h3>'
    elif t=='panelopen':
        if op: h+='</details>'; op=False
        h+='<div class="box panel sum3" id="d-three-sizes">'
    elif t=='panelclose': h+='</div>'
    elif t=='code': h+=f'<pre>{html.escape(b["x"])}</pre>'
    elif t=='fig': h+=f'<figure>{figs[b["k"]]}<figcaption>{inl(b["x"])}</figcaption></figure>'
    elif t=='table': h+='<div class="tw"><table><tr>'+''.join(f'<th>{inl(c)}</th>' for c in b['head'])+'</tr>'+''.join('<tr>'+''.join(f'<td>{inl(str(c))}</td>' for c in r)+'</tr>' for r in b['rows'])+'</table></div>'
    elif t=='ol': h+='<ol>'+''.join(f'<li>{inl(x)}</li>' for x in b['x'])+'</ol>'
    elif t=='ul':
        if 'links' in b: h+='<ul>'+''.join(f'<li>'+(f'<a href="{s[1]}" target="_blank" rel="noopener">{inl(s[0])}</a>' if s[1] else inl(s[0]))+'</li>' for s in b['links'])+'</ul>'
        else: h+='<ul>'+''.join(f'<li>{inl(x)}</li>' for x in b['x'])+'</ul>'
if op: h+='</details>'

# --- figures to PNG, light palette
LIGHT={'--bg':'#ffffff','--ink':'#334155','--ink-dim':'#566274','--head':'#1e3a5f','--face':'#ffffff','--grid':'#e5e9f0','--axis':'#566274','--line':'#c9d2df','--panel':'#eff6ff','--panel-line':'#bfd7f5','--panel-ink':'#1e3a5f','--s1':'#b45309','--s2':'#2563eb','--s3':'#15803d','--s4':'#be185d','--s5':'#7c3aed','--water':'#3b82f6','--steel':'#64748b','--mono':'DejaVu Sans Mono'}
os.makedirs(D+'/fig',exist_ok=True)
sizes={}
for k,s in figs.items():
    x=re.sub(r'var\((--[\w-]+)\)',lambda m:LIGHT[m.group(1)],s)
    vb=re.search(r'viewBox="0 0 (\d+) (\d+)"',x); w,he=int(vb.group(1)),int(vb.group(2))
    x=x.replace('<svg ',f'<svg xmlns="http://www.w3.org/2000/svg" font-family="Liberation Sans" ',1).replace('width="100%"',f'width="{w}" height="{he}"').replace('style="display:block;height:auto"','')
    open(f'{D}/fig/{k}.svg','w').write(x)
    subprocess.run(['rsvg-convert','-z','2','-b','#ffffff','-o',f'{D}/fig/{k}.png',f'{D}/fig/{k}.svg'],check=True)
    sizes[k]=(w,he)
json.dump(dict(title=title,sub=sub,byline='Robert Dickinson · SWMM5 RASPIPE 1.4, engine 1.3 · November 2026',blocks=blocks,sizes=sizes,d=D),open(D+'/essay.json','w'))
subprocess.run(['node',A+'/mkdocx.js',D+'/essay.json',D+'/SWMM5-RASPIPE.docx'],check=True,env=dict(os.environ,NODE_PATH='/opt/npm-tools/node_modules'))

# --- technical summary, same numbers as the page
import mkmd
MD=mkmd.make(data,val,CX,S1,S2,'2026-11-19'); assert '</script' not in MD
open(D+'/SWMM5-RASPIPE.md','w').write(MD); open(D+'/SWMM5-RASPIPE-v1.4.0.md','w').write(MD)
# --- assemble
t=open(A+'/app.src.html').read()
wasm=base64.b64encode(open(os.environ.get('WASMFILE','/root/rp/wasm/swmm5_rp13.wasm'),'rb').read()).decode()
docx=base64.b64encode(open(D+'/SWMM5-RASPIPE.docx','rb').read()).decode()
shim=json.dumps(open('/root/rp/wasm/shim/shim.iife.js').read())
sub_=lambda s:s.replace('</script','<\\/script').replace('<!--','<\\!--')
t=t.replace('/*@@DATA@@*/null',sub_(json.dumps(data,separators=(',',':'))))
t=t.replace('/*@@SAMPLES@@*/[]',sub_(json.dumps(samples,separators=(',',':'))))
t=t.replace('/*@@WASM@@*/',wasm).replace('/*@@DOCX@@*/',docx).replace('/*@@SHIM@@*/\'\'',sub_(shim))
t=t.replace('<!--@@DOC@@-->',h)
t=t.replace('<!--@@MD@@-->','<script type="text/markdown" id="app-md">\n'+MD+'</script>')
glue=open('/root/rp/swmm6/openswmm6a4_glue.js').read(); assert '</script' not in glue
t=t.replace('<!--@@S6@@-->','<script type="text/plain" id="d-s6">'+glue+'</script>')
par=json.load(open('/root/rp/wasm/parity13.json'))['parity']
t=t.replace('@@PAR@@',par['text'][0].lower()+par['text'][1:])
open(D+'/raspipe.html','w').write(t)
sa='<!doctype html>\n<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'+t+'\n</html>\n'
open(D+'/SWMM5-RASPIPE.html','w').write(sa)
print('app',len(t)//1024,'KB; figures',nfig,'; blocks',len(blocks))
