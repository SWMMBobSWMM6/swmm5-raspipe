# SWMM5 RASPIPE app 1.4, engine 1.3, build 239a0d3a930f

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

Without `FLOW_ROUTING RASPIPE` the engine is EPA 5.2.4, and the `.out` file is byte-identical to a stock build on 4 of 4 control decks. The pipes run their own steps inside SWMM's routing step at a target Courant number of 0.9, HEC's default. If `VARIABLE_STEP` is on, which is SWMM's default, the step stays at 15 s or less while water is moving and stretches to `ROUTING_STEP` when the target allows it. With `RASPIPE_COURANT 0` and `RASPIPE_INITIAL_STAGE NO` the `.out` matches version 1.0 byte for byte. The trial count is always up to 8, and the deck's `MAX_TRIALS` is ignored.

## Build

`./build.sh` compiles the engine into `bin/swmm5_rp` and stamps the build id, which shows in the report. On Ubuntu 24 keep `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`, and keep `-ffp-contract=off` for byte parity with EPA 5.2.4. `wasm/build13.sh` builds the WebAssembly engine with `zig cc`, and `wasm/parity13.py` compares it with the native build (40 of 44 runs byte for byte; on the others the largest flow difference was 0.01 cfs on an 8 cfs link).

## What is here

- `app/dist/SWMM5-RASPIPE.html` the single-file app, which runs in a browser with no server; `app/dist/SWMM5-RASPIPE.docx` the write-up; and `app/dist/SWMM5-RASPIPE.md` the technical summary for engineers and AI tools. `app/` holds the source they are built from (`build.py`, the `mkdata*.py` data scripts, `doc/essay.md` and `doc/essay.json`, and `tools/complexity.js` with the SWMM App Complexity Meter's analyzer). The built page also carries the OpenSWMM 6.0.0-alpha.4 WebAssembly engine, which is not kept here as a separate file.
- `src/` the full engine. New file: `src/solver/raspipe.c`. Patches to EPA's files are in `epa-5.2.4-to-raspipe.patch`.
- `tests/` deck generators, `verify.py` (V1 to V14), `bench1.py` (Stoker dam break, with `testhook.py`, which makes the test build), `bench2.py` (U-tube), `bench3.py` (the wave, one cause at a time), `tabs15.py` (cell table error), `slot_terms_patch.py` (SLOT one term at a time), `dwsame.py` (diffusion wave byte comparison with v1.1), the wave tables, and `refsol.py`, the independent Saint-Venant solver.
- `sweep/sweep6b.py` runs each SWMM6 option alone over the corpus sample, and `tests/semi_matrix.py` tests `NODE_CONTINUITY SEMI_IMPLICIT` deck by deck. `tests/short_box_30s.inp` is the clean deck. `tests/swmm6_semi_test.patch` is the switch those tests used, applied to `DynamicWave.cpp` at swmm6_rel 9648837. It is a diagnostic and not a fix: it closes the balance on the short box and makes the box flow ring.
- `tests/bench4.py` runs EPA 5.2.4, SWMM6 (modified DW and FV) and RASPIPE on the same decks, and `tests/run6.js` drives the SWMM6 engine. The app embeds OpenSWMM 6.0.0-alpha.4, Apache License 2.0; see `NOTICE-OpenSWMM` and `LICENSE-OpenSWMM`.
- `hecras/` the HEC-RAS 7.0.2 check. `app14.py` builds SWMM decks from the geometry stored in RAS's results files (`runC/`, copy C of HEC's EXTRAN example project with a 1-minute hydrograph output), runs EPA 5.2.4 and RASPIPE on them, scores them against RAS and writes `results/ras14.json`; `rerun14.py` checks RAS against itself and against HEC's shipped files (those files are not included); `rasvol2.py` is the volume check that found RAS's full-pipe storage. `decks/` holds every deck it ran.
- `verification_manifest.json` ties every result to its input, script, evidence type and build.
- `sweep/` the corpus runner and the stratified list of 1,600 models (seed 1729).
- `results/` the verification records, the wave table, and one line per model from the final sweep.

## What was found

Pump into a full pipe: pencil 4.599 cfs, RASPIPE 4.599, EXTRAN 4.599, SLOT 5.141. Wave down 8,000 ft of pipe: independent solver 14.97 cfs, stock two conduits 13.05, RASPIPE defaults 14.64. Corpus: median routing continuity 0.795% stock against 0.005% RASPIPE, median run time 2.6 times stock. HEC-RAS 7.0.2 on HEC's EXTRAN 1, flooded rim matched: mean head difference 0.192 ft for RASPIPE, 0.111 ft with `RASPIPE_PRESSURE_AREA 12.566`, 0.382 ft for EPA 5.2.4. See the app's Verify tab and the Word document.

The test and app scripts were run from `/root/rp` and carry that path, so change it to run them elsewhere.

## Evidence

Each test is labeled analytical answer, numerical reference, initialization check, regression check, conservation check or cross-engine comparison. The stage and warm up tests are initialization checks, not accuracy tests. The wave reference came from the same AI session as the engine. The corpus sweep is diffusion wave on the v1.1 build, carried to v1.2 by byte comparison; the full equations ran on 160 models.

## Limits

No field data. HEC-RAS 7.0.2 on four EXTRAN plans only, and every plan misses the pass band set beforehand. Interior cell states are not in hot start files. A manhole stores water up to its MaxDepth, unlike EXTRAN. Water hammer is not modeled. Where the engines disagree in the corpus, nobody has sorted out which is right.

## License

EPA SWMM is public domain software. The additions here carry no further restriction from their author.

## AI use

SWMM5 RASPIPE was built with Claude, Anthropic's AI model, in a Claude session in November 2026, at the request of Robert (Bob) Dickinson, who pointed it to the HEC-RAS time step and start-up options used in version 1.1, supplied the outside review that drove version 1.2, asked for SWMM6 FV and the SWMM6 modified dynamic wave to be compared in version 1.3, installed HEC-RAS 7.0.2 and ran it on his own machine for version 1.4, and set the standing requirements for testing, documentation and units. Responsibility for the work is his. He has not yet reviewed this build.

**What Claude did.** It read HEC's public manuals and the papers named below, designed the solver, wrote `raspipe.c` and the small patches to EPA's files, wrote the independent Saint-Venant reference solver and every test, ran the corpus sweeps, found and fixed the defects in the register, compiled the WebAssembly build, built this app, and wrote the essay and the Word document. For version 1.2 it replaced the advection with HEC's form, added the benchmarks, the run record, the Profile tab and the evidence labels, and corrected its own earlier statement that HEC publishes only an outline, a mistake the outside review caught. For version 1.3 it reused the OpenSWMM 6 alpha.4 engine from the Seven SWMM Engines app, built the latest SWMM6 natively, wrote the shared comparison decks and scoring, and added SWMM6 to this page. It also ran SWMM6 option by option to find why water went missing, read the SWMM6 source, and tried a change behind a switch in a private test copy. That change is not in this page's engines and is not a proposed fix. For version 1.4 it planned the check against HEC-RAS, wrote the batch files Bob ran, read RAS's HDF5 results, built SWMM decks from the geometry RAS stores, scored the engines, measured the storage RAS keeps in full pipes from RAS's own cell tables, added `RASPIPE_PRESSURE_AREA` to the engine, and rebuilt this page and its documents.

**How the results were checked.** The checks are mechanical, not the AI's judgment: closed-form answers (Manning, normal depth, a pump curve, Stoker's dam break, the U-tube period), a byte comparison of the `.out` file with the feature off and of diffusion wave against version 1.1, a separately written Saint-Venant solver, the solver's own volume ledger, a sweep of 1,600 corpus models through both engines, and a Playwright run of this page.

**What no person has checked.** No person has reviewed the code, the figures or this text. It has not been compared with field data. The HEC-RAS comparison covers four of HEC's EXTRAN examples, and no person has checked the deck translation line by line. The review Bob supplied covered the version 1.1 app and its documents, not the C solver. Casulli and Stelling's 2013 paper and Stelling and Duinmeijer's 2003 paper were not read directly; the methods were taken from HEC's description and the sources listed.
