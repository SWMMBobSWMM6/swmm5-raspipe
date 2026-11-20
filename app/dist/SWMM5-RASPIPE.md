---
name: SWMM5 RASPIPE
file: SWMM5-RASPIPE.html
version: 1.4.0
date: 2026-11-19
author: Robert Dickinson
links: {artifact: "https://claude.ai/artifact/3zBb9jAAvucjovoDtCFcCo", netlify: none, repo: "https://github.com/SWMMBobSWMM6/swmm5-raspipe"}
engines:
  - {name: EPA SWMM, version: 5.2.4, source: commit 7952ca8, license: public domain}
  - {name: RASPIPE, version: 1.3, file: src/solver/raspipe.c, build: 239a0d3a930f, license: public domain additions}
  - {name: OpenSWMM, version: 6.0.0-alpha.4, branch: swmm6_rel, commit: 3c30f1e, license: Apache-2.0}
  - {name: HEC-RAS, version: 7.0.2, use: reference runs on Bob's Windows machine; not shipped, no HEC code used}
units: US customary (CFS, ft); SI when the model's FLOW_UNITS says so
complexity: {index: 65.4, baseline: HC-2026-11-10-h, analyzer: meter-core.js 1.7.0}
ai_use: built with Claude (Anthropic); see AI use
---

# SWMM5 RASPIPE: HEC-RAS's slot-free pipe method inside EPA SWMM 5.2.4

SWMM5 RASPIPE runs HEC-RAS's slot-free pipe method inside EPA SWMM 5.2.4, and on HEC's own EXTRAN 1 its mean head difference from HEC-RAS 7.0.2 is 0.192 ft, against 0.382 ft for EPA's dynamic wave.

SWMM5 RASPIPE is EPA SWMM 5.2.4 with one new solver file. Write FLOW_ROUTING RASPIPE and each conduit becomes a row of cells whose volume tables go flat at the crown, so a full pipe needs no Preissmann slot, and the whole network is solved at once with a nested Newton iteration. It reproduces Manning in a full pipe, a pump curve, Stoker's dam break, and a U-tube period of 441.7 s against an exact 441.7 s, and it has run a random sample of the 1729 corpus. On four of HEC's EXTRAN examples it comes closer to HEC-RAS 7.0.2 than EPA's dynamic wave does, though every plan misses the pass band set beforehand. There is no field data.

## What it does
Runs one SWMM5 .inp through EPA SWMM 5.2.4 DYNWAVE, RASPIPE (a semi-implicit finite volume pipe solver written from HEC's published HEC-RAS 6.6/7.0 pipe network method) and, optionally, OpenSWMM 6 modified dynamic wave and FV, all in the browser, and compares flows and heads conduit by conduit and node by node. For whom: modelers deciding whether a cell-based, slot-free pipe solve changes their answer, and anyone checking it against HEC-RAS. Out come hydrographs, profiles, a peak-difference table, CSV and the .inp of each run.

## How it computes
1. `FLOW_ROUTING RASPIPE` hands dynamic wave link and node updates to `raspipe.c`. Hydrology, controls, quality, statistics and the .out format stay EPA's.
2. Each conduit is cut into cells of `RASPIPE_CELL_LENGTH` (default 100 ft), at most `RASPIPE_MAX_CELLS` (20). Levels live in cells, flows on faces. A junction cell borrows the end piece of each pipe that meets it.
3. Each cell has a volume table V(eta) from SWMM's own cross-section geometry, flat level in a sloping cell. dV/deta = T is split into running sums of rises and falls, T = T1 - T2, V = V1 - V2 (Casulli and Stelling 2013). Above a closed crown V is constant and the level is crown + P/gamma: no slot.
4. Cell balance: V(eta_new) = V_old + dt * (sum of face flows in - out + lateral). Face flow: diffusion wave (default; friction balances the water surface slope, steady flow is Manning) or full shallow water (`RASPIPE_EQUATIONS SWE`, HEC's Eulerian-Lagrangian advection). Pressure term weighted by theta (`RASPIPE_THETA`, default 1.0).
5. The network is one sparse M-matrix, factored by LDL^T with minimum degree ordering. Plain Newton first; on failure, nested Newton on V1 and V2 (outer loop m, inner loop k).
6. Pipe steps run inside the SWMM routing step at a target residence time Courant number (`RASPIPE_COURANT`, 0.9, HEC's default): C = dt * outflow / volume.
7. Engine 1.3 adds `RASPIPE_PRESSURE_AREA` (default 0): each full cell stores this plan area per unit head above its crown (`raspipe.c:1395` `tabSplit(t, RasPipePressArea * p->barrels)`), and each junction cell the same per barrel of the highest pipe it borrows from (`raspipe.c:1366-1367`). Parsed in `project.c:800`, converted to internal ft2 in `dynwave.c:198`. 12.566 ft2 is what HEC-RAS 7.0.2 held on EXTRAN 1.

Engine options. The app writes all of them but `RASPIPE_NESTED_ONLY` into the RASPIPE run, plus `ROUTING_STEP` and `VARIABLE_STEP` when those controls are set; every other line of the model is unchanged.

| Option | Default | Meaning |
|---|---|---|
| `FLOW_ROUTING RASPIPE` | - | Turns the solver on. Anything else is EPA 5.2.4. |
| `RASPIPE_COURANT` | 0.9 | Target residence time Courant number for the pipe steps, HEC's default. 0 turns it off. |
| `RASPIPE_INITIAL_STAGE` | YES | Projects FIXED, TIDAL and TIMESERIES outfall stages up the conduits at the start. |
| `RASPIPE_WARMUP` | 0 | Warm up steps before the clock starts. Inflows ramp over the first 2/3. HEC asks for 30 or more. |
| `RASPIPE_EQUATIONS` | DW | DW diffusion wave, SWE full shallow water with HEC's Eulerian-Lagrangian advection. |
| `RASPIPE_CELL_LENGTH` | 100 ft | Target cell length, in model length units. |
| `RASPIPE_MAX_CELLS` | 20 | Most interior cells per conduit. Long pipes need this raised. |
| `RASPIPE_THETA` | 1.0 | Implicit weighting, 0.5 to 1. 0.6 keeps sharp fronts and oscillations better; 1.0 is what the corpus ran. The fallback always uses 1. |
| `RASPIPE_NESTED_ONLY` | NO | YES skips plain Newton. For testing. |
| `RASPIPE_PRESSURE_AREA` | 0 | Storage above the crown of each full pipe cell, ft² per cell per ft of head (m² in SI models). 0 keeps a full pipe rigid, as in 1.2. 12.566 is what HEC-RAS 7.0.2 held on EXTRAN 1. New in engine 1.3. |

## Inputs and outputs
- Reads: SWMM5 .inp (US or SI). Samples built in: 12 decks, including EXTRAN 1 built from the geometry in HEC-RAS 7.0.2's own results file, with RAS's stored series drawn as a reference line.
- Writes: per-run CSV of the plotted series (with a header naming run, model hash, settings asked for and achieved, engines and builds), the peak-difference table, the profile table, the .inp of the RASPIPE run, a GIF, the Doc as .docx, and this file.
- The app removes any `RASPIPE_*` lines from the model, then writes its own; for SWMM6 runs it sets `SURCHARGE_METHOD DYNAMIC_SLOT`, `NODE_CONTINUITY SEMI_IMPLICIT`, `ANDERSON_ACCEL YES` (modified DW) or `FLOW_ROUTING FV` with `FV_CELL_LENGTH` and `FV_ORDER 2` (FV).

## Checks
Mechanical checks. All but the last ran on a native build with the scripts in the engine zip; the last ran in a browser.

- Null control: 22 of 22 runs with the new option absent match engine 1.2 byte for byte (engine 1.3 against 1.2, option absent). With `FLOW_ROUTING` not RASPIPE the .out is EPA 5.2.4's, byte for byte, on 4 of 4 decks.
- Browser against native, engine 1.3: 40 of 44 runs byte for byte; on the others the largest flow difference was 0.01 cfs on an 8 cfs link.
- Verify table: 32 tests, each labeled with its kind of evidence (analytical answer, numerical reference, initialization check, regression check, conservation check, cross-engine comparison).
- Pump into a full 1 ft pipe: pencil 4.599 cfs, RASPIPE 4.599, EPA EXTRAN 4.599, EPA SLOT 5.141.
- Stoker dam break, exact bore 17.01 ft/s: speed error -3.3% at theta 1, +0.2% at theta 0.6.
- U-tube, exact period 441.7 s: RASPIPE SWE 441.7 s, EPA 5.2.4 521.2 s.
- HEC-RAS 7.0.2 rerun check: HEC-RAS 7.0.2 reproduces HEC's shipped results. Two runs of the same five plans on Bob's Windows machine match to the last bit in all 1,075 result datasets. Against the files HEC shipped, made with 7.0 and 7.0.1, heads agree within 0.044 ft on every plan, and mid-pipe flows within 0.4% of peak away from the outfall. The two conduits that meet at the outfall differ by up to 1.0% on the other plans, and on EXTRAN 1 by 1.1% on pipe 1600 and 7% on the 50 ft outfall box at 0:40. Changing only the hydrograph output interval to 1 minute moved RAS's results by up to 0.028 ft, and 9.4% of peak at one instant on the outfall box.
- HEC-RAS 7.0.2, EXTRAN 1 (deck built from RAS's stored geometry, RAS stage at 16009, diffusion wave, 100 ft cells, Courant 0.9, every minute for 6 h):

| Run against HEC-RAS 7.0.2 | Heads within 0.1 ft | Flows within 2% of peak | Mean head difference | Mean flow difference | Nodes / pipes passing 90% of instants |
|---|---|---|---|---|---|
| RASPIPE | 52% | 87% | 0.237 ft | 1.18% | 1 of 8 / 1 of 8 |
| RASPIPE, rim at 80608 raised to RAS’s ponded head | 66% | 87% | 0.192 ft | 1.06% | 1 of 8 / 1 of 8 |
| RASPIPE with full-pipe storage | 53% | 89% | 0.161 ft | 0.96% | 1 of 8 / 3 of 8 |
| RASPIPE with full-pipe storage, rim raised | 66% | 89% | 0.111 ft | 0.84% | 1 of 8 / 3 of 8 |
| EPA 5.2.4 DYNWAVE | 24% | 52% | 0.411 ft | 3.74% | 1 of 8 / 0 of 8 |
| EPA 5.2.4, rim raised | 33% | 53% | 0.382 ft | 3.57% | 1 of 8 / 0 of 8 |

- Other HEC-RAS plans, value set on EXTRAN 1 and not retuned, rim matched:

| HEC-RAS plan | RASPIPE, mean head difference | With full-pipe storage | RASPIPE, mean flow difference | With full-pipe storage | EPA 5.2.4, mean head difference |
|---|---|---|---|---|---|
| EXTRAN 1 (storage value set here) | 0.192 ft | 0.111 ft | 1.06% | 0.84% | 0.382 ft |
| EXTRAN 2 | 0.187 ft | 0.113 ft | 1.09% | 1.01% | 0.374 ft |
| EXTRAN 4, weir | 0.157 ft | 0.157 ft | 1.34% | 1.34% | 0.327 ft |
| EXTRAN 5, orifice | 0.710 ft | 0.721 ft | 4.98% | 4.74% | 0.894 ft |

- Full-pipe storage in HEC-RAS, read from its own cell tables: 10,862 ft3 beyond the tables in pipes 8040, 8060 and 1602 while full, 12.57 ft2 per full cell per ft of head on EXTRAN 1, 12.39 on EXTRAN 2; under 100 ft3 after draining.
- Complexity (SWMM App Complexity Meter, HydroCouple = 100): index 65.4 on 39 hand-written source files (Size 55.2, Structure 74, Test evidence 20.3, SWMM vocabulary 83.8); shipped .html alone 56.4. Baseline HC-2026-11-10-h.
- Page: Playwright run of every tab in both themes, at 375 px, with no console errors; contrast measured in both themes.

Human review: none. No person has reviewed the code, the figures or the text.

## What this does not show
1. No field data anywhere. Agreement with closed forms, another solver or HEC-RAS is not a prediction of a real sewer.
2. HEC-RAS 7.0.2 was run on four of HEC's EXTRAN examples, on one Windows machine. Every plan misses the pass band set beforehand (90% of nodes and pipes within 0.1 ft and 2% of peak at 90% of instants).
3. The full-pipe storage is read from RAS's results, not from HEC's code or manuals, and it was set on EXTRAN 1. A real pipe stores far less.
4. Open items in the register:
   - RP-9 (behavior): A manhole stores water to its MaxDepth, EXTRAN does not. Decks with a fake 1,000 ft depth take hours to settle.
   - RP-16 (open): Hot start files carry no interior cell states.
   - EPA-1 (stock): SLOT overstates pump flow into a full pipe (EPA issue 231), 11.8% here. Two terms carry the slot area, the velocity in friction and the area in the head term, and each is about half of it. Cap both at the true area and SLOT lands on EXTRAN to four places.
   - EPA-2 (stock): A fixed outfall that feeds the network is not booked as inflow (corpus deck NUM-19). Shared by both engines, and it tops the RASPIPE continuity list.
   - EPA-3 (stock): A full conduit still adds surface area to its end nodes, from the width at 96% of depth. On a U-tube with 1,000 ft² tanks that is 392 ft² of surface that isn't there, and the period runs 18.0% long while continuity reads 0.000%.
   - RP-17 (option): A full pipe cell held no water above its crown. HEC-RAS 7.0.2 holds about 12.6 ft² per cell per ft of head on EXTRAN 1, so RASPIPE's upper nodes rose to the plateau up to 7 minutes early. RASPIPE_PRESSURE_AREA added in engine 1.3, off by default.
   - RP-18 (open): 81009 sits 0.19 ft above RAS on EXTRAN 1, at Manning's normal depth. Which engine is right is not settled.
   - RP-19 (open): EXTRAN 5's mean head difference is 0.7 ft, with or without full-pipe storage. Not traced.
5. EXTRAN 7 (pump station with rules) is not compared. Quality routing and hot starts are not validated. Water hammer is not modeled.
6. SWMM6 is alpha software; the browser build is from October 17, 2026.

## How to reproduce
From the engine zip (`SWMM5-RASPIPE-engine.zip`):

```
bash build.sh                       # native engine, build id printed
bash wasm/build13.sh                # WebAssembly engine (zig cc)
python3 wasm/parity13.py            # null control and browser parity
python3 tests/verify.py             # V1 to V14
python3 tests/bench1.py; python3 tests/bench2.py; python3 tests/bench3.py   # Stoker, U-tube, wave
python3 hecras/rerun14.py           # HEC-RAS against itself and HEC's shipped files (needs runA, runB, orig)
python3 hecras/app14.py             # decks from RAS geometry, EPA and RASPIPE runs, scores, volume check
```

HEC-RAS inputs: HEC's SWMM EXTRAN example project for HEC-RAS 7, run in 7.0.2 with one change to each plan, Output Interval 1MIN; the plan HDF files used are in `hecras/runC/`.

## Credits and licenses
- EPA SWMM 5.2.4, U.S. Environmental Protection Agency, public domain. Lewis Rossman and the EPA SWMM team.
- HEC-RAS 7.0.2 and its EXTRAN example projects, U.S. Army Corps of Engineers Hydrologic Engineering Center. Used as a reference; no HEC code is in this app. HEC did not make, review or endorse it.
- The method: V. Casulli and G. S. Stelling (2013); V. Casulli and P. Zanolli (2012); G. S. Stelling and S. P. A. Duinmeijer (2003); as described in HEC's HEC-RAS manuals.
- OpenSWMM Engine (HydroCouple), swmm6_rel, Copyright 2026 HydroCouple Developers, Apache License 2.0, with public domain EPA SWMM material. The USEPA does not endorse this product. See NOTICE-OpenSWMM and LICENSE-OpenSWMM in the engine zip.
- Robert Dickinson: EPA SWMM is public domain software, and the additions here carry no further restriction from their author.

## AI use
SWMM5 RASPIPE was built with Claude, Anthropic's AI model, in a Claude session in November 2026, at the request of Robert (Bob) Dickinson, who pointed it to the HEC-RAS time step and start-up options used in version 1.1, supplied the outside review that drove version 1.2, asked for SWMM6 FV and the SWMM6 modified dynamic wave to be compared in version 1.3, installed HEC-RAS 7.0.2 and ran it on his own machine for version 1.4, and set the standing requirements for testing, documentation and units. Responsibility for the work is his. He has not yet reviewed this build.

**What Claude did.** It read HEC's public manuals and the papers named below, designed the solver, wrote `raspipe.c` and the small patches to EPA's files, wrote the independent Saint-Venant reference solver and every test, ran the corpus sweeps, found and fixed the defects in the register, compiled the WebAssembly build, built this app, and wrote the essay and the Word document. For version 1.2 it replaced the advection with HEC's form, added the benchmarks, the run record, the Profile tab and the evidence labels, and corrected its own earlier statement that HEC publishes only an outline, a mistake the outside review caught. For version 1.3 it reused the OpenSWMM 6 alpha.4 engine from the Seven SWMM Engines app, built the latest SWMM6 natively, wrote the shared comparison decks and scoring, and added SWMM6 to this page. It also ran SWMM6 option by option to find why water went missing, read the SWMM6 source, and tried a change behind a switch in a private test copy. That change is not in this page's engines and is not a proposed fix. For version 1.4 it planned the check against HEC-RAS, wrote the batch files Bob ran, read RAS's HDF5 results, built SWMM decks from the geometry RAS stores, scored the engines, measured the storage RAS keeps in full pipes from RAS's own cell tables, added `RASPIPE_PRESSURE_AREA` to the engine, and rebuilt this page and its documents.

**How the results were checked.** The checks are mechanical, not the AI's judgment: closed-form answers (Manning, normal depth, a pump curve, Stoker's dam break, the U-tube period), a byte comparison of the `.out` file with the feature off and of diffusion wave against version 1.1, a separately written Saint-Venant solver, the solver's own volume ledger, a sweep of 1,600 corpus models through both engines, and a Playwright run of this page.

**What no person has checked.** No person has reviewed the code, the figures or this text. It has not been compared with field data. The HEC-RAS comparison covers four of HEC's EXTRAN examples, and no person has checked the deck translation line by line. The review Bob supplied covered the version 1.1 app and its documents, not the C solver. Casulli and Stelling's 2013 paper and Stelling and Duinmeijer's 2003 paper were not read directly; the methods were taken from HEC's description and the sources listed.

## Changes
- `1.4.0 (2026-11-19)`: engine 1.3 with `RASPIPE_PRESSURE_AREA` (off by default, .out identical to 1.2 when off); HEC-RAS 7.0.2 check on four EXTRAN plans (Verify card, EXTRAN 1 sample with RAS's stored line, three cases); defects RP-17 to RP-19; Doc opens with what is unique, three summaries and four questions, closes with a measured complexity box; this file.
- `1.3.0 (2026-11)`: SWMM6 modified DW and FV on the same decks; SEMI_IMPLICIT water loss traced; short wide box deck.
- `1.2.0 (2026-11)`: HEC's Eulerian-Lagrangian advection for the full equations; Stoker, U-tube and wave benchmarks; Profile tab; evidence labels.
- `1.1.0 (2026-11)`: HEC's adaptive time step, initial stage projection and warm up.
- `1.0.0 (2026-11)`: first release; 1729 corpus sample sweep.
