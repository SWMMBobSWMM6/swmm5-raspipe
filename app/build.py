#!/usr/bin/env python3
"""One source, two outputs: doc/essay.md becomes the Doc tab and the .docx. Then the single-file app."""
import json, re, base64, subprocess, os, html, sys
sys.path.insert(0,'/root/rp/app'); sys.path.insert(0,'/root/rp/tests')
import mkfigs, gen, gen2
A='/root/rp/app'; D=A+'/dist'
v=json.load(open(A+'/vals.json')); data=json.load(open(A+'/data.json')); val=v['val']
W=json.load(open('/root/rp/tests/v/wave3.json'))
sw=data['sweep']; figs=mkfigs.all_figs(v['pump'],W,sw,v['opt'])
figs.update(mkfigs.more_figs(v['pump'],json.load(open('/root/rp/tests/v/slot_terms.json')),data['bench'],data['wave']['rows']))
TABLES=dict(method=dict(head=['Part','HEC documentation','RASPIPE 1.2','Difference, and the test'],rows=data['method'],w=[1050,2850,2850,2610]),outcomes=dict(head=['Outcome','EPA 5.2.4','RASPIPE','Models'],rows=sw['outcomes'],w=[4860,1600,1600,1300]))
src=open(A+'/doc/essay.md').read()
for k,x in val.items(): src=src.replace('{{'+k+'}}',str(x))
left=re.findall(r'\{\{(?!fig:|table:|aiuse|sources)[^}]*\}\}',src); assert not left,left

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
        blocks.append(dict(t='ul',x=[(s[0]+(' — '+s[1] if s[1] else '')) for s in v['sources']],links=v['sources'])); i+=1; continue
    if l.startswith('- '):
        it=[]
        while i<len(lines) and lines[i].startswith('- '): it.append(lines[i][2:]); i+=1
        blocks.append(dict(t='ul',x=it)); continue
    if re.match(r'\d+\. ',l):
        it=[]
        while i<len(lines) and re.match(r'\d+\. ',lines[i]): it.append(re.sub(r'^\d+\. ','',lines[i])); i+=1
        blocks.append(dict(t='ol',x=it)); continue
    blocks.append(dict(t='p',x=l)); i+=1
nfig=sum(1 for b in blocks if b['t']=='fig'); assert nfig>=6

# --- html
def inl(s):
    s=html.escape(s,quote=False)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    return s
h=f'<h2 style="margin-top:16px;font-size:26px">{inl(title)}</h2><p style="color:var(--ink-dim)">{inl(sub)}</p>'
secs=[b['x'] for b in blocks if b['t']=='h2']; slug=lambda s:'d-'+re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
h+='<nav class="toc" aria-label="Contents">'+''.join(f'<a href="#{slug(s)}">{inl(s)}</a>' for s in secs)+'</nav>'
op=False
for b in blocks:
    t=b['t']
    if t=='h2':
        if op: h+='</details>'
        h+=f'<details open id="{slug(b["x"])}"><summary><h2>{inl(b["x"])}</h2></summary>'; op=True
    elif t=='p': h+=f'<p>{inl(b["x"])}</p>'
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
json.dump(dict(title=title,sub=sub,blocks=blocks,sizes=sizes,d=D),open(D+'/essay.json','w'))
subprocess.run(['node',A+'/mkdocx.js',D+'/essay.json',D+'/SWMM5-RASPIPE.docx'],check=True,env=dict(os.environ,NODE_PATH='/opt/npm-tools/node_modules'))

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
 dict(name='U-tube, two tanks',file='u_tube.inp',inp=utdeck,pick='S1',note='Water sloshes between two tanks through a full pipe. The exact period is 441.7 s. Use the U-tube case in the list above: diffusion wave has no inertia and will not oscillate.')]

# --- assemble
t=open(A+'/app.src.html').read()
wasm=base64.b64encode(open(os.environ.get('WASMFILE','/root/rp/wasm/swmm5_rp.wasm'),'rb').read()).decode()
docx=base64.b64encode(open(D+'/SWMM5-RASPIPE.docx','rb').read()).decode()
shim=json.dumps(open('/root/rp/wasm/shim/shim.iife.js').read())
sub_=lambda s:s.replace('</script','<\\/script').replace('<!--','<\\!--')
t=t.replace('/*@@DATA@@*/null',sub_(json.dumps(data,separators=(',',':'))))
t=t.replace('/*@@SAMPLES@@*/[]',sub_(json.dumps(samples,separators=(',',':'))))
t=t.replace('/*@@WASM@@*/',wasm).replace('/*@@DOCX@@*/',docx).replace('/*@@SHIM@@*/\'\'',sub_(shim))
t=t.replace('<!--@@DOC@@-->',h)
par=json.load(open('/root/rp/wasm/parity12.json')) if os.path.exists('/root/rp/wasm/parity12.json') else dict(text='not yet measured')
t=t.replace('@@PAR@@',par['text'])
open(D+'/raspipe.html','w').write(t)
sa='<!doctype html>\n<html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'+t+'\n</html>\n'
open(D+'/SWMM5-RASPIPE.html','w').write(sa)
print('app',len(t)//1024,'KB; figures',nfig,'; blocks',len(blocks))
