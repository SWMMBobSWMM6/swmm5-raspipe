// How complex is SWMM5 RASPIPE, on the SWMM App Complexity Meter's scale (HydroCouple = 100).
// Analyzer: meter-core.js copied from the Meter artifact (LkChM9gVnmhNpZcX5Lo55m), baseline HC-2026-11-10-h.
// Fed: the hand-written source only. raspipe.c, the page source, the build and data scripts, the tests and the
// HEC-RAS comparison scripts. Left out: EPA SWMM 5.2.4's own C files (third party, patched only lightly), the
// compiled wasm, the WASI shim and the SWMM6 glue (third party), data files and the essay prose.
// Usage: node complexity.js <shipped.html> > complexity.json
const fs=require('fs'),path=require('path');const SACM=require('./meter-core.js');
const ANCHOR={bulk:6607205,branches:123080,routines:38818,checks:27339,stack:31.573,dependencies:77,formats:43,swmm:226},ANCHOR_ID='HC-2026-11-10-h';
const R='/root/rp';
const list=[R+'/engine/src/solver/raspipe.c',R+'/app/app.src.html',R+'/app/tools/complexity.js']
 .concat(['mkdata.py','mkdata12.py','mkdata13.py','mkdata14.py','mkfigs.py','build.py','mkdocx.js','mkzip.py','mkmd.py'].map(f=>R+'/app/'+f))
 .concat(fs.readdirSync(R+'/tests').filter(f=>f.endsWith('.py')).map(f=>R+'/tests/'+f))
 .concat(fs.readdirSync(R+'/hecras/cmp').filter(f=>f.endsWith('.py')).map(f=>R+'/hecras/cmp/'+f))
 .concat([R+'/build13.sh',R+'/wasm/build13.sh',R+'/wasm/runwasi.mjs'])
 .filter(f=>fs.existsSync(f));
const files=list.map(f=>({path:path.relative(R,f),text:fs.readFileSync(f,'utf8')}));
function score(files){const A=SACM.analyzeSet(files);const g=SACM.grade(A.measure,ANCHOR,undefined,undefined,'soft');return {A,g};}
const all=score(files);
const shipped=process.argv[2]?score([{path:path.basename(process.argv[2]),text:fs.readFileSync(process.argv[2],'utf8')}]):null;
const grp=g=>Object.fromEntries(Object.entries(g.groups).map(([k,v])=>[k,typeof v==='object'?+(+v.score).toFixed(1):+(+v).toFixed(1)]));
const rows=g=>g.rows.map(r=>({key:r.key,name:r.name,value:r.value,anchor:r.anchor,score:+(+r.score).toFixed(1)}));
const out={analyzer:SACM.VERSION,baseline:ANCHOR_ID,files:files.map(f=>f.path),nfiles:files.length,
  index:+all.g.total.toFixed(1),groups:grp(all.g),rows:rows(all.g),
  shipped:shipped?{index:+shipped.g.total.toFixed(1),groups:grp(shipped.g)}:null};
console.log(JSON.stringify(out,null,1));
