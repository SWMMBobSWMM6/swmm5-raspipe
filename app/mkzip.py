#!/usr/bin/env python3
"""Engine zip: source, patch against EPA 5.2.4, wasm, tests, results, README."""
import json, os, shutil, subprocess, zipfile, glob
R='/root/rp'; O=R+'/app/dist/zipdir'; Z=R+'/app/dist/SWMM5-RASPIPE-engine.zip'
v=json.load(open(R+'/app/vals.json')); val=v['val']; sw=json.load(open(R+'/app/sweep_summary.json'))['sweep']
shutil.rmtree(O,ignore_errors=True)
os.makedirs(O+'/tests'); os.makedirs(O+'/hecras/runC'); os.makedirs(O+'/hecras/decks'); os.makedirs(O+'/sweep'); os.makedirs(O+'/results'); os.makedirs(O+'/wasm'); os.makedirs(O+'/bin')
SRC=os.environ.get('ENGSRC',R+'/engine/src')
shutil.copytree(SRC,O+'/src',ignore=shutil.ignore_patterns('*.o','__t.inp'))
p=subprocess.run(['diff','-ruN','-x','raspipe.c','epa524/src',os.path.relpath(SRC,R)],cwd=R,capture_output=True,text=True).stdout
open(O+'/epa-5.2.4-to-raspipe.patch','w').write(p)
for f in ('gen.py','gen2.py','outread.py','verify.py','wave.py','wave2.py','wave3.py','refsol.py','bench1.py','bench2.py','bench3.py','tabs15.py','dwsame.py','same12.py','bench4.py','semi_matrix.py'): shutil.copy(R+'/tests/'+f,O+'/tests/')
shutil.copy('/tmp/claude-0/pw/hook.py',O+'/tests/testhook.py'); shutil.copy('/tmp/claude-0/pw/slot.py',O+'/tests/slot_terms_patch.py')
os.makedirs(O+'/tests/v')
for f in glob.glob(R+'/tests/v/*.inp'): shutil.copy(f,O+'/tests/v/')
for f in ('sweep.py','summ.py','cmp1.py','final.txt'): shutil.copy(R+'/sweep/'+f,O+'/sweep/')
for f in ('verify.json','wave3.json','wave3.log','stoker.json','utube.json','wavebudget.json','tabs15.json','slot_terms.json','dwsame.json','dwsame_corpus.json','same12.json','sixcmp.json','semi_matrix.json','shortbox.json','shortbox_series.json','sixcmp_latest.json'): shutil.copy(R+'/tests/v/'+f,O+'/results/')
shutil.copy(R+'/app/verification_manifest.json',O+'/verification_manifest.json')
for f in ('r12_t1','r12_t6'):
    if os.path.exists(R+'/sweep/'+f+'/results.jsonl'): shutil.copy(R+'/sweep/'+f+'/results.jsonl',O+'/results/sweep_swe_'+f+'.jsonl')
shutil.copy(R+'/app/sweep_merged.jsonl',O+'/results/sweep_final.jsonl'); shutil.copy(R+'/app/sweep_summary.json',O+'/results/')
if os.path.exists(R+'/app/timing.txt'): shutil.copy(R+'/app/timing.txt',O+'/results/')
for f in ('build13.sh','runwasi.mjs','wasi_shims.h','parity13.py','parity13.json'): shutil.copy(R+'/wasm/'+f,O+'/wasm/')
for f in ('app14.py','rerun14.py','rasread.py','mkdeck_extran.py','cmp13.py','rasvol2.py','rasvol.py','cmp1.py'): shutil.copy(R+'/hecras/cmp/'+f,O+'/hecras/')
for f in glob.glob(R+'/hecras/cmp/a14/*.inp'): shutil.copy(f,O+'/hecras/decks/')
for pl in ('p02','p03','p04','p06'): shutil.copy(R+f'/hecras/runC/ExtranTestImport.{pl}.hdf',O+'/hecras/runC/')
for f in ('ras14.json','ras_rerun.json','ras_slot_volume.json'): shutil.copy(R+'/tests/v/'+f,O+'/results/')
shutil.copy(os.environ.get('WASMFILE',R+'/wasm/swmm5_rp13.wasm'),O+'/wasm/swmm5_rp.wasm')
shutil.copy(R+'/build13.sh',O+'/build.sh')
shutil.copy(R+'/bin/swmm5_rp13',O+'/bin/swmm5_rp_linux_x86_64')
shutil.copy(R+'/swmm6/run6.js',O+'/tests/run6.js'); shutil.copy(R+'/sweep/sweep6.py',O+'/sweep/sweep6.py'); shutil.copy(R+'/sweep/sweep6b.py',O+'/sweep/sweep6b.py'); shutil.copy(R+'/app/samples_short_box.txt',O+'/tests/short_box_30s.inp'); shutil.copy(R+'/tests/swmm6_semi_test.patch',O+'/tests/swmm6_semi_test.patch')
if os.path.exists(R+'/sweep/r6b_results.jsonl'): shutil.copy(R+'/sweep/r6b_results.jsonl',O+'/results/sweep_swmm6_options.jsonl')
if os.path.exists(R+'/sweep/r6_results.jsonl'): shutil.copy(R+'/sweep/r6_results.jsonl',O+'/results/sweep_swmm6.jsonl')
shutil.copy(R+'/swmm6/src6/NOTICE',O+'/NOTICE-OpenSWMM'); shutil.copy(R+'/swmm6/src6/LICENSE',O+'/LICENSE-OpenSWMM')
BUILD=open(R+"/build_id13.txt").read().strip()
readme=f"""# SWMM5 RASPIPE app 1.4, engine 1.3, build {BUILD}

EPA SWMM 5.2.4 with a semi-implicit pipe solver built from the published HEC-RAS 6.6+/7.0 pipe network method. There is no Preissmann slot and no EXTRAN switch at the crown. Water surface above a closed cell is ceiling plus P/gamma.

This is not HEC-RAS and contains no HEC code. It is an independent implementation from HEC's public manuals and the papers they cite. Its results have been compared with HEC-RAS 7.0.2 runs of four of HEC's EXTRAN examples, and they differ; see `hecras/`. HEC and the Corps of Engineers did not make, review or endorse it.

## Turn it on

```
[OPTIONS]
FLOW_ROUTING          RASPIPE
RASPIPE_EQUATIONS     DW      ; DW or SWE
RASPIPE_CELL_LENGTH   100     ; ft or m
RASPIPE_MAX_CELLS     20
RASPIPE_THETA         1.0     ; 0.5 to 1.0
RASPIPE_COURANT       0.9     ; target residence time Courant, 0 = off
RASPIPE_INITIAL_STAGE YES     ; project outfall stage up the pipes at the start
RASPIPE_WARMUP        0       ; warm up steps before the clock starts
RASPIPE_PRESSURE_AREA 0       ; storage above the crown of a full cell, ft2 per cell (engine 1.3)
RASPIPE_NESTED_ONLY   NO      ; for testing
```

Without `FLOW_ROUTING RASPIPE` the engine is EPA 5.2.4, and the `.out` file is byte-identical to a stock build on {val['null.n']} of {val['null.n']} control decks. The pipes run their own steps inside SWMM's routing step at a target Courant number of 0.9, HEC's default. If `VARIABLE_STEP` is on, which is SWMM's default, the step stays at 15 s or less while water is moving and stretches to `ROUTING_STEP` when the target allows it. With `RASPIPE_COURANT 0` and `RASPIPE_INITIAL_STAGE NO` the `.out` matches version 1.0 byte for byte. The trial count is always up to 8, and the deck's `MAX_TRIALS` is ignored.

## Build

`build.sh` holds the gcc line (paths assume this tree sits at `~/rp/engine/src`; adjust as needed). On Ubuntu 24 keep `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`, and keep `-ffp-contract=off`. `wasm/build13.sh` builds the WebAssembly engine with `zig cc`, and `wasm/parity13.py` compares it with the native build ({val['ras.par']}). `bin/` holds a Linux x86-64 binary.

## What is here

- `src/` the full engine. New file: `src/solver/raspipe.c`. Patches to EPA's files are in `epa-5.2.4-to-raspipe.patch`.
- `tests/` deck generators, `verify.py` (V1 to V14), `bench1.py` (Stoker dam break, with `testhook.py`, which makes the test build), `bench2.py` (U-tube), `bench3.py` (the wave, one cause at a time), `tabs15.py` (cell table error), `slot_terms_patch.py` (SLOT one term at a time), `dwsame.py` (diffusion wave byte comparison with v1.1), the wave tables, and `refsol.py`, the independent Saint-Venant solver.
- `sweep/sweep6b.py` runs each SWMM6 option alone over the corpus sample, and `tests/semi_matrix.py` tests `NODE_CONTINUITY SEMI_IMPLICIT` deck by deck. `tests/short_box_30s.inp` is the clean deck. `tests/swmm6_semi_test.patch` is the switch those tests used, applied to `DynamicWave.cpp` at swmm6_rel 9648837. It is a diagnostic and not a fix: it closes the balance on the short box and makes the box flow ring.
- `tests/bench4.py` runs EPA 5.2.4, SWMM6 (modified DW and FV) and RASPIPE on the same decks, and `tests/run6.js` drives the SWMM6 engine. The app embeds OpenSWMM 6.0.0-alpha.4, Apache License 2.0; see `NOTICE-OpenSWMM` and `LICENSE-OpenSWMM`.
- `hecras/` the HEC-RAS 7.0.2 check. `app14.py` builds SWMM decks from the geometry stored in RAS's results files (`runC/`, copy C of HEC's EXTRAN example project with a 1-minute hydrograph output), runs EPA 5.2.4 and RASPIPE on them, scores them against RAS and writes `results/ras14.json`; `rerun14.py` checks RAS against itself and against HEC's shipped files (those files are not included); `rasvol2.py` is the volume check that found RAS's full-pipe storage. `decks/` holds every deck it ran.
- `verification_manifest.json` ties every result to its input, script, evidence type and build.
- `sweep/` the corpus runner and the stratified list of {sw['drawn']:,} models (seed 1729).
- `results/` the verification records, the wave table, and one line per model from the final sweep.

## What was found

Pump into a full pipe: pencil {val['pump.exact']} cfs, RASPIPE {v['pump']['rp']:.3f}, EXTRAN {val['pump.extran']}, SLOT {val['pump.slot']}. Wave down 8,000 ft of pipe: independent solver {val['wave.ref']} cfs, stock two conduits {val['wave.stock']}, RASPIPE defaults {val['wave.rp']}. Corpus: median routing continuity {sw['refmed']:.3f}% stock against {sw['rpmed']:.3f}% RASPIPE, median run time {sw['ratio']:.1f} times stock. HEC-RAS 7.0.2 on HEC's EXTRAN 1, flooded rim matched: mean head difference {val['ras.h_rp']} ft for RASPIPE, {val['ras.h_pa']} ft with `RASPIPE_PRESSURE_AREA 12.566`, {val['ras.h_epa']} ft for EPA 5.2.4. See the app's Verify tab and the Word document.

## Evidence

Each test is labeled analytical answer, numerical reference, initialization check, regression check, conservation check or cross-engine comparison. The stage and warm up tests are initialization checks, not accuracy tests. The wave reference came from the same AI session as the engine. The corpus sweep is diffusion wave on the v1.1 build, carried to v1.2 by byte comparison; the full equations ran on 160 models.

## Limits

No field data. HEC-RAS 7.0.2 on four EXTRAN plans only, and every plan misses the pass band set beforehand. Interior cell states are not in hot start files. A manhole stores water up to its MaxDepth, unlike EXTRAN. Water hammer is not modeled. Where the engines disagree in the corpus, nobody has sorted out which is right.

## License

EPA SWMM is public domain software. The additions here carry no further restriction from their author.

## AI use

"""+'\n\n'.join(x.replace('<b>','**').replace('</b>','**').replace('<code>','`').replace('</code>','`') for x in v['aiuse'])+"\n"
open(O+'/README.md','w').write(readme)
with zipfile.ZipFile(Z,'w',zipfile.ZIP_DEFLATED) as z:
    for root,_,files in os.walk(O):
        for f in files:
            full=os.path.join(root,f); z.write(full,'swmm5-raspipe/'+os.path.relpath(full,O))
print(Z,os.path.getsize(Z)//1024,'KB')
