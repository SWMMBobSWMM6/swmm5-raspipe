# SWMM5 RASPIPE 1.2, build 3d60128204be

EPA SWMM 5.2.4 with a semi-implicit pipe solver built from the published HEC-RAS 6.6+/7.0 pipe network method. There is no Preissmann slot and no EXTRAN switch at the crown. Water surface above a closed cell is ceiling plus P/gamma.

This is not HEC-RAS and contains no HEC code. It is an independent implementation from HEC's public manuals and the papers they cite, and it has not been compared with a run of HEC-RAS. HEC and the Corps of Engineers did not make, review or endorse it.

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
RASPIPE_NESTED_ONLY   NO      ; for testing
```

Without `FLOW_ROUTING RASPIPE` the engine is EPA 5.2.4, and the `.out` file is byte-identical to a stock build on 4 of 4 control decks. The pipes run their own steps inside SWMM's routing step at a target Courant number of 0.9, HEC's default. If `VARIABLE_STEP` is on, which is SWMM's default, the step stays at 15 s or less while water is moving and stretches to `ROUTING_STEP` when the target allows it. With `RASPIPE_COURANT 0` and `RASPIPE_INITIAL_STAGE NO` the `.out` matches version 1.0 byte for byte. The trial count is always up to 8, and the deck's `MAX_TRIALS` is ignored.

## Build

`./build.sh` compiles the engine into `bin/swmm5_rp` and stamps the build id, which shows in the report. On Ubuntu 24 keep `-U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`, and keep `-ffp-contract=off` for byte parity with EPA 5.2.4.

## What is here

- `app/dist/SWMM5-RASPIPE.html` the single-file app, which runs in a browser with no server, and `app/dist/SWMM5-RASPIPE.docx` the write-up. `app/` also holds the source they are built from.
- `src/` the full engine. New file: `src/solver/raspipe.c`. Patches to EPA's files are in `epa-5.2.4-to-raspipe.patch`.
- `tests/` deck generators, `verify.py` (V1 to V14), `bench1.py` (Stoker dam break, with `testhook.py`, which makes the test build), `bench2.py` (U-tube), `bench3.py` (the wave, one cause at a time), `tabs15.py` (cell table error), `slot_terms_patch.py` (SLOT one term at a time), `dwsame.py` (diffusion wave byte comparison with v1.1), the wave tables, and `refsol.py`, the independent Saint-Venant solver.
- `verification_manifest.json` ties every result to its input, script, evidence type and build.
- `sweep/` the corpus runner and the stratified list of 1,600 models (seed 1729).
- `results/` the verification records, the wave table, and one line per model from the final sweep.

## What was found

Pump into a full pipe: pencil 4.599 cfs, RASPIPE 4.599, EXTRAN 4.599, SLOT 5.141. Wave down 8,000 ft of pipe: independent solver 14.97 cfs, stock two conduits 13.05, RASPIPE defaults 14.64. Corpus: median routing continuity 0.795% stock against 0.005% RASPIPE, median run time 2.6 times stock. See the app's Verify tab and the Word document.

The test and app scripts were run from `/root/rp` and carry that path, so change it to run them elsewhere.

## Evidence

Each test is labeled analytical answer, numerical reference, initialization check, regression check, conservation check or cross-engine comparison. The stage and warm up tests are initialization checks, not accuracy tests. The wave reference came from the same AI session as the engine. The corpus sweep is diffusion wave on the v1.1 build, carried to v1.2 by byte comparison; the full equations ran on 160 models.

## Limits

No field data. No run of HEC-RAS. Interior cell states are not in hot start files. A manhole stores water up to its MaxDepth, unlike EXTRAN. Water hammer is not modeled. Where the engines disagree in the corpus, nobody has sorted out which is right.

## License

EPA SWMM is public domain software. The additions here carry no further restriction from their author.

## AI use

SWMM5 RASPIPE was built with Claude, Anthropic's AI model, in a Claude session in November 2026, at the request of Robert (Bob) Dickinson, who pointed it to the HEC-RAS time step and start-up options used in version 1.1, supplied the outside review that drove version 1.2, and set the standing requirements for testing, documentation and units. Responsibility for the work is his. He has not yet reviewed this build.

**What Claude did.** It read HEC's public manuals and the papers named below, designed the solver, wrote `raspipe.c` and the small patches to EPA's files, wrote the independent Saint-Venant reference solver and every test, ran the corpus sweeps, found and fixed the defects in the register, compiled the WebAssembly build, built this app, and wrote the essay and the Word document. For version 1.2 it replaced the advection with HEC's form, added the benchmarks, the run record, the Profile tab and the evidence labels, and corrected its own earlier statement that HEC publishes only an outline, a mistake the outside review caught.

**How the results were checked.** The checks are mechanical, not the AI's judgment: closed-form answers (Manning, normal depth, a pump curve, Stoker's dam break, the U-tube period), a byte comparison of the `.out` file with the feature off and of diffusion wave against version 1.1, a separately written Saint-Venant solver, the solver's own volume ledger, a sweep of 1,600 corpus models through both engines, and a Playwright run of this page.

**What no person has checked.** No person has reviewed the code, the figures or this text. It has not been compared with a run of HEC-RAS or with field data. The review Bob supplied covered the version 1.1 app and its documents, not the C solver. Casulli and Stelling's 2013 paper and Stelling and Duinmeijer's 2003 paper were not read directly; the methods were taken from HEC's description and the sources listed.
