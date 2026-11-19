# A Pipe With No Slot
How SWMM5 RASPIPE moves water through a full pipe, where the method came from, and what it took to put it inside SWMM

## The trouble with a full pipe
Take a 3 ft pipe running half full. The water has a surface. Push more water in at the top end and the surface rises, and the rise travels down the pipe the way a swell crosses a pond. Every sewer model ever written is built on that fact.

Now fill the pipe to the crown. The surface is gone. Water does not squeeze, not to speak of, so a push at one end is felt at the other almost at once. The equations that worked a moment ago have the width of the water surface in them, and that width just went to zero. Divide by that and the computer will tell you what it thinks of you.

Engineers are practical people and they found two ways around it. The first is the slot. Preissmann and Cunge proposed it in 1961: cut an imaginary narrow slit in the crown of the pipe. Now the pipe always has a free surface, the same equations keep running, and the height of water in the slit stands in for pressure. The second is what EXTRAN does: stop using the surface equation at the crown and switch to a different rule that balances flows at the nodes. SWMM 5 carries both, as `SURCHARGE_METHOD SLOT` and `SURCHARGE_METHOD EXTRAN`.

The slot is a lie told for a good reason. The trouble with a lie is that you have to keep track of it. That slit holds water that does not exist, and every formula that touches the pipe has to remember which area is real. Here is a case where the bookkeeping slipped. A pump pushes into a 1 ft pipe held full by an 8 ft tailwater, a problem you can do with a pump curve and a pencil. The answer is {{pump.exact}} cfs. EXTRAN gets {{pump.extran}}. The slot in EPA SWMM 5.2.4 gets {{pump.slot}}, which is {{pump.sloterr}}% high. That is one implementation on one deck, not a verdict on slots, and further on we will name the two lines of code that do it.

The Hydrologic Engineering Center reached the same opinion. HEC-RAS used the slot through version 6.5. Its manual now says the slot "alters the geometry and physics of the problem, has problems with instabilities," and "incorrectly predicts the propagation speed of surge flows." So they replaced it with a method from Vincenzo Casulli and Guus Stelling, published in 2013. There is no slot in it and no switch at the crown. One set of equations runs from a dry pipe to a pipe under 100 ft of head.

The obvious question is what happens if you put that method inside SWMM. So we did.

## What this engine is
SWMM5 RASPIPE is EPA SWMM 5.2.4 with one new source file and a few small patches that hand it control. Write `FLOW_ROUTING RASPIPE` in the options and the dynamic wave solver steps aside for a semi-implicit finite volume solve over a mesh of pipe cells. Rainfall, runoff, infiltration and controls are EPA's code, unchanged, and the `.out` file is EPA's format. Leave the word out and you have EPA 5.2.4, and the `.out` file comes back identical byte for byte.

HEC-RAS is closed source, so this is an independent build from what HEC has published. The first two versions of this essay said HEC publishes only an outline. That was wrong, and it took an outside reviewer to say so. HEC's page on numerical methods for pipe flow gives the advection scheme, the friction term and the nested iteration, equation by equation, and the mesh page gives the table formulas. Version 1.2 went back and read them properly, and it changed the solver as well as this sentence. The section called Where this departs from HEC lays the two side by side.

## Cut the pipe into cells
SWMM thinks of a conduit as one object with one flow in it. A 4,000 ft pipe gets one number. That is a remarkably good bargain for what it costs, and it is why SWMM runs so fast. It is also why a flood wave going down a long pipe gets smeared.

The new solver cuts each conduit into cells, the way HEC-RAS does. HEC's manual has a 120 ft pipe with a 10 ft cell length, which makes 12 cells. Between two cells is a face. Water levels live in cells and flows live on faces. A manhole is a cell too, and it borrows a piece of each pipe that meets it, so that a short stub of pipe does not turn into a tiny cell that sets the pace for everything else.

{{fig:mesh|Figure 1. One conduit between two manholes. Levels live in cells and flows live on faces. Each manhole cell borrows the first part of each pipe. Where the head is above the crown the cell is simply full, and the level is crown plus pressure head.}}

A cell has one flat level. In a sloping pipe that takes some care, because a flat level in a long cell makes a wedge of water. So each cell carries a table that gives the volume held at every level, computed from the real cross section through SWMM's own geometry routines. Circles, arches, baskets and irregular transects all work with no special cases. HEC calls these sub-grid tables.

## The table that goes flat
Now the whole trick. Plot the volume in a closed pipe cell against the water level. It rises, and at the crown it stops. The cell is full. Raise the head to 100 ft and it holds the same water. That is why no slot is needed: above the crown, level has no effect on volume, so the level is free to be whatever the pressure says. HEC writes it as ceiling elevation plus P/γ.

That flat stretch is good physics and poison for a solver. Newton's method divides by the slope of the function it is working on, and here the slope is zero. The conference paper on the HEC solver says Newton can fail to converge under pressure, and it is right. Near the crown the iteration can throw the level far outside the pipe and never find its way back.

Casulli's way out is a piece of mathematics that any engineer can follow with no help. The slope of the volume table is a storage derivative, dV/dη, the plan area of the water surface in that cell, in square feet. In a level cell that is the top width times the cell length. Call it T. It rises to the springline and falls to zero at the crown. Split it in two. Let T1 be the running sum of every rise and T2 the running sum of every fall. Then T = T1 − T2, and the volume is V = V1 − V2, and neither V1 nor V2 ever curves downward.

{{fig:split|Figure 2. A 3 ft pipe in a 100 ft cell at 0.5% slope, computed by the same table routine the engine uses. T is dV/dη, the plan area of the water surface, in ft². T1 and T2 only rise, and above the crown they are equal, so the volume stops growing.}}

An upward-curving function is the case where Newton has a proof behind it. So the solver runs two loops, one inside the other. The outer loop freezes V2 as a straight line. The inner loop solves the upward-curving remainder. Casulli and Zanolli proved in 2012 that their algorithm walks to the answer under their assumptions, and a proof covers the algorithm it was written for, not every variation somebody builds on it. HEC writes the same two loops out in full, outer index m on the falling part and inner index k on the rising part. They cost more per step, so this engine tries plain Newton first and falls back to the nested loops only when plain Newton fails, which HEC's page does not do. That is a departure of ours and it needs its own evidence. The answer ought to be the same either way, because each cell's equation has only one solution. We checked: forcing the nested path on every solve moved a 59 cfs peak by {{nest.diff}} cfs.

## One equation for every cell
The equations are shorter than you may fear. For a cell, the water it holds at the end of the step is what it held, plus what came in, minus what left through its faces. For a face, velocity is set by the head difference across it, slowed by friction. SWMM's dynamic wave solves those two one after the other and iterates. Here the second goes into the first, and the whole network is solved at once as one matrix.

{{fig:eq|Figure 3. The cell equation. V is the table, so the crown takes care of itself. The face flow is the only thing that ties one cell to the next, and it is implicit, so a pressure wave crossing a cell in a fraction of a second sets no limit on the time step.}}

Two equation sets are offered, as in HEC-RAS. Diffusion wave drops inertia, and friction balances the slope of the water surface exactly, so steady flow is Manning. Full shallow water keeps inertia and advection. HEC's tutorial for importing a SWMM model selects diffusion wave, and that is the default here.

Advection is the term that carries velocity along with the water, and since version 1.2 it is HEC's. Ask what a parcel of water brought with it. It arrives at a face with the velocity it had a time step ago, at the spot it started from. So walk back upstream a distance V* Δt, read the old velocity there, and call it V_X. HEC's formula is one line, and the only art is in V*. Where the flow chokes down hard, V* is the plain average of the two velocities, which keeps energy head constant. Everywhere else it is flow over area, which conserves momentum. That is the Stelling and Duinmeijer idea, and it matters because a hydraulic jump loses energy and keeps momentum, and a sudden contraction does the reverse. Get that backward and a bore runs at the wrong speed, as we are about to see.

The matrix has a pleasant shape. Off the diagonal every entry is negative or zero, and the diagonal dominates, which mathematicians call an M-matrix. Nothing needs pivoting. In a sewer most cells have two neighbors, so a sparse factorization with a minimum degree ordering is hardly more work than a tridiagonal solve. There is no iteration on the linear system at all.

{{fig:path|Figure 4. One routing step. SWMM supplies inflows and takes back node depths and link flows. Everything between is new. If a trial's Newton fails, that trial falls back to a symmetric form of the faces and nested Newton.}}

## What sits on the faces
A face between two pipe cells is simple. The interesting faces are at the ends of things.

A pipe set above a manhole floor is a sill. When the water on the far side is below the sill, the head difference across the face stops meaning anything, because the water is falling. The flow is held to critical flow at the crest and the far side is ignored. A free outfall is the same thing, a control on the last face and not a depth imposed from outside.

That last point was not learned cheaply. The first version took outfall depth from the last flow, the way stock SWMM does, in this line inside the trial loop:

```
for (i = 0; i < Nobjects[LINK]; i++) link_setOutfallDepth(i);
```

On a siphon with 44 ft pipes, depth and flow fed each other until the model reported 732,000 cfs in a 2,000 cfs system. With the control on the face, the same model runs steady at exactly 2,000 cfs.

Orifices, weirs, outlets and pumps use SWMM's own functions. The solver gets their flow, then finds its slope by nudging each end node 0.001 ft and asking again. HEC's way with gates is to change the friction of the face until it delivers the gate flow, and the fallback form here does much the same.

## Where this departs from HEC
You should know where HEC's description stops and this code's own work begins, because that is the first place a reviewer ought to dig. An outside reviewer dug, and asked for this table.

{{table:method}}

Beyond the table, these came from here and not from HEC:
- How a face picks its wetted area. It takes the lesser of the area at the upstream level and the mean area of the upstream cell, so a thin film can drain out of a sloping cell and normal depth comes out right.
- The Newton linearization, including how flow changes with upstream wetted area. Without that term a surcharged small manhole chatters. With it the same deck takes about 2 trials a step.
- The sparse solver and a level floor.
- The rule for a face that is dry at the start of a trial, described below.
- Leaving out manhole cells that hold no pipe when the Courant number is computed.
- Letting momentum cross a junction that joins exactly two conduits.

For four versions no run of real HEC-RAS had been made. One has now, and the section called Asking HEC-RAS itself says where the two part company.

## What was tested
A closed-form answer, a second solver and a start-up check don't prove the same thing, and for a while this write-up let them stand in one line as if they did. So each test now wears a label: analytical answer, numerical reference, initialization check, regression check, or cross-engine comparison. The Verify tab has the full list, with tolerances, and the engine zip has a manifest that ties each one to its deck and to the build that ran it.

Start with problems that have exact answers. A full pipe between two fixed heads gave {{full.got}} cfs against {{full.exp}} from Manning. Three full pipes in series, with no free surface anywhere in the system, gave {{series.got}} against {{series.exp}}. Normal depth in four pipes came within {{yn.max}}%. Water at rest in a sloping network stayed at rest, with zero flow to the last digit. Turning the feature off gave a byte-identical `.out` on {{null.n}} of {{null.n}} decks, and that control is what lets you trust every other comparison.

Back to the pump, and to a sentence that claimed too much. Earlier versions said the slot's phantom water was the reason, and left it there. A reviewer asked which term, in which implementation, and what removes it. Fair questions. Here is the steady momentum balance in EPA's `dwflow.c`, in two lines:

```
v = qLast / aMid;
dq2 = dt * GRAVITY * aWtd * (h2 - h1) / length;
```

Both `aMid` and `aWtd` include the slot area. The first feeds the friction term and the second is the push from the head difference. At steady flow friction balances the push, and when you work that through, Q² goes as `aMid` times `aWtd`. The slot inflates each one by the same factor, so each should carry about half the error. So we tried it, one term at a time, in a test copy of EPA's file.

{{fig:slot|Figure 5. Pump into a full 1 ft pipe, steady flow, with SLOT changed one term at a time in a test copy of EPA 5.2.4. Each term alone removes about half the error. Both together land on EXTRAN and the pencil answer to four places. RASPIPE has no slot to keep track of and gets there as well.}}

That is the whole of it, for this implementation on this deck. Cap the area at the true full area in both places and SLOT gives {{slot.both}} cfs. It says nothing about slots in general, and it says nothing about what those two caps would do to SLOT's stability on other decks, because we didn't test that. EPA issue 231 is the place to follow that question.

## Problems nobody here wrote
Every test so far was set up by the same party that wrote the solver, and the reviewer put a finger on the sore spot. The wave reference below is a separate solver with no shared code, but it came from the same AI session, so it could share the same mistaken idea. What you want is a test with an answer that was on paper before any of this existed. So we took two.

The first is Stoker's dam break, from the 1950s. Ten feet of water stands behind a gate, two feet in front of it, and the gate lifts. A bore runs downstream at a speed you can get from mass and momentum with a pocket calculator: {{st.S}} ft/s, with {{st.hs}} ft of water behind it. Nothing in the mesh knows that. We ran it in a 4,000 ft rectangular channel with almost no friction, and read the water surface at 60 s.

{{fig:stoker|Figure 6. Depth along the pipe 60 s after the gate lifts, 5 ft cells. The old advection runs the bore short and stands the water too high behind it. HEC's form with θ = 0.6 sits on the exact line. Cells are 5 ft and the step is 0.125 s.}}

Version 1.1 ran the bore {{st.v11}}% slow. Halving the cells and the step together did nothing for it, which is the mark of a scheme headed for the wrong answer, and diffusion wave and the corpus had never gone near it. HEC's formula with the face area taken from upstream, the way this engine's faces work, gave {{st.first}}%. Taking the area under V* as the mean of the two sides gave {{st.v12}}% at θ = 1 and {{st.v126}}% at θ = 0.6. That mean is what conservation of momentum across a jump needs, and it is our reading of Stelling and Duinmeijer. HEC's page doesn't say which area it uses. HEC doesn't give a number for how strong a contraction has to be, so we chose 1.5. Trying 1.1 through 4 on this problem moved nothing, which also means this problem doesn't test that choice.

The θ result is worth a moment. θ = 1 holds the pressure term all at the new time while the advection looks at the old time. We think that mismatch is why the bore lags, though we haven't proved it. The lag closes up as the step shrinks, to {{st.v12fine}}% at 0.02 s. θ = 0.6 gets it at ordinary steps. The default stays at 1.0, because that is what the corpus ran and it is the safer setting, but if a sharp front is what you care about, try 0.6.

The second is a U-tube: two tanks, one frictionless pipe, and water sloshing between them. The period is 2π√(L A_s / (2 g A_p)), which is {{ut.T}} s for this deck. RASPIPE with the full equations gets {{ut.rp}} s. So far so good. Then we ran stock SWMM as a control, expecting a dull line in the table, and it came back {{ut.epa}} s, 18% long.

{{fig:utube|Figure 7. Tank level against time. RASPIPE keeps the exact period and loses height to the velocity head given up at each end of the pipe. EPA 5.2.4 hardly loses any height at all and runs 18% long, with continuity at 0.000%.}}

A period that long means something is acting like extra tank, and EXTRAN's node update is where to look. A full pipe has no free surface, but this line in `dwflow.c` gives it one anyway:

```
if (y / xsect->yFull >= CrownCutoff && !xsect_isOpen(xsect->type))
    y = CrownCutoff * xsect->yFull;
```

So the pipe reports the width at 96% of depth, and half its length of that goes onto each end node, and then `dynwave.c` does `dy = dV / surfArea;`. For this pipe that's 392 ft² of water surface that isn't there, on a 1,000 ft² tank. Multiply the period by the square root of 1.392 and you get {{ut.pred}} s. Measured, {{ut.epa}}. With 4,000 ft² tanks the same arithmetic says {{ut.pred4}} and the run says {{ut.epa4}}. Zero out that area in a test copy when the pipe is full and the period drops to {{ut.fix}} s. And all the while routing continuity reads 0.000%, because the books balance over a full swing. That is one more thing continuity can't see. It matters when the pipe is big next to the tank, and it is register entry EPA-3.

## One cause at a time
The more interesting test has no closed form, so we made a reference. A hydrograph rises from 2 to 16 cfs and back, down 8,000 ft of 3 ft pipe at 0.1% slope, built in SWMM as two 4,000 ft conduits, with 2 cfs running steady before the wave starts. To learn the truth we wrote a separate shock-capturing solver of the full Saint-Venant equations, sharing no code with SWMM, and ran it with cells of 25, 12.5 and 6.25 ft. Its peak 6,000 ft down the pipe is {{wave.ref}} cfs, and it is still rising about {{wave.refgap}}% as the cells halve. It is a numerical reference, written in the same session, and that is all it is.

{{fig:wave|Figure 8. Flow 6,000 ft down an 8,000 ft pipe. Stock SWMM with two long conduits flattens the wave. RASPIPE at its defaults sits close to the independent solution. Cutting the stock model into 160 pieces overshoots it.}}

Peak flow is one number, and it flatters. So the wave is now scored on the whole hydrograph, on arrival, on the head at the junction, on volume, and with one cause moved at a time. The numbers are in the Verify table. Here is the budget.

{{fig:budget|Figure 9. Peak error against the independent solver, one cause at a time. Full equations on a fine mesh are the floor. Diffusion wave adds its own small share, the mesh adds more, and a long true time step adds more again. Stock SWMM as built is off the same chart. Every row is version 1.2.}}

The full equations at 12.5 ft and 1 s come within {{wb.sweerr}}% of the reference at the peak, with an NSE of {{wb.swense}} and {{wb.swey}} ft of head error at the junction. That is the numerical floor. Drop inertia and keep the mesh, and the peak goes to {{wb.dwerr}}%, so the diffusion wave approximation costs about {{wb.dwcost}} of a percent on this pipe. Go to 100 ft cells at 5 s and it is {{wb.m100}}%; go to 800 ft and it is {{wb.m800}}%. So the mesh is the big lever. A true 30 s step, with the Courant control off, gives {{wb.t30}}% against {{wb.t5}}% at 5 s.

That head figure has a story. Our first run of the new advection had the junction 0.16 ft off, where diffusion wave was 0.01 ft off, and the fancier equations shouldn't lose to the simpler ones. The reason was this: a node holds water at rest, so water going through a junction stopped and restarted, and paid a full velocity head. In a straight run that is false. Momentum now crosses a junction that joins exactly two conduits, and the error fell to {{wb.swey}} ft. Junctions with more than two get the old treatment, and that may be too much loss or too little. That's an open question.

Stock SWMM as built gives {{wave.stock}} cfs, {{wave.stockerr}}% low, and it loses {{wave.stockcont}}% of continuity doing it. That is the one-number-per-conduit smear. Cut the same pipe into 160 short conduits and stock SWMM gives {{wave.fine}}, {{wave.fineerr}}% high.

{{fig:mesh2|Figure 10. Peak flow against cell length, RASPIPE diffusion wave, Courant control on. Accuracy is limited by the mesh first. The full equations at 12.5 ft reach {{wave.swe}} cfs.}}

One warning for anyone repeating this. Changing `ROUTING_STEP` is not a clean time step study when the Courant control is on, because pipe steps run inside it. A routing step of 30 s ran pipe steps of {{wb.auto30}} s here, min, mean and max. The report now prints those three numbers, and the app shows them.

## Bringing in SWMM6
The next question anyone will ask is how this stacks up against the engine the community is building now. OpenSWMM 6 gives you two routes worth testing. The modified dynamic wave keeps SWMM's link and node picture and adds three things: `DYNAMIC_SLOT`, `SEMI_IMPLICIT` node continuity and Anderson acceleration. FV is a different animal, an explicit finite volume solver that cuts conduits into cells and solves the full equations with a Riemann flux. So now there are three families in the ring: one flow per conduit, explicit cells, and implicit cells.

Every engine got the same plain `.inp` decks. That ruled out Stoker's test as we ran it earlier, because that used a test build. So we rebuilt the dam break as a deck: 200 conduits of 20 ft, with the step across one of them. First the control. SWMM6 with EXTRAN matched EPA 5.2.4 on all {{six.same}} decks, so the two share a baseline.

{{table:six}}

{{fig:sixdam|Figure 11. The dam break as a plain deck, read at 60 s. SWMM6 FV and RASPIPE's full equations both sit on the exact line. EPA and the modified dynamic wave run the bore short, ripple behind it, and throw a spike at the front. This chart comes from nodes, 20 ft apart, so the bore is 20 ft wide at best.}}

On the dam break, the bore speed came out {{six.ex5}}% for EPA, {{six.s6dw}}% for the modified dynamic wave, {{six.s6fv}}% for FV and {{six.rp}}% for RASPIPE at θ = 0.6. FV and RASPIPE are a dead heat, with mean depth errors of {{six.fvl}} and {{six.rpl}} ft against EPA's {{six.exl}}. EPA and the modified dynamic wave also throw a spike right behind the bore, up to {{six.spike}} and {{six.spiked}} ft in a place where the exact depth is 5.08. Higher than the water behind the gate, for a moment, which no real bore does. Two very different methods got there: one explicit with a Riemann solver, one implicit with backtracking. When two independent roads reach the same town, you start to believe in the town.

On the U-tube, the modified dynamic wave came to {{six.utd}}%, against EPA's {{six.ut5}}%, so the phantom surface is gone. FV came to {{six.utf}}% and RASPIPE {{six.utr}}%. On the wave, what matters is the mesh, not the equations. EPA and the modified dynamic wave both keep one flow per conduit and both sit at {{six.w5}}%. FV at its default of four cells gives {{six.wf0}}%. Give it 100 ft cells and second order and it gives {{six.wf}}%, next to RASPIPE at {{six.wr}}% and {{six.wrs}}%.

Then two rows that need saying plainly, because they are questions and not verdicts. FV gave {{six.pipef}} cfs on the full pipe where Manning says 3.56, and {{six.pumpf}} cfs on the pump deck where a pencil says 4.60. Its steady answer moves with `FV_SLOT_CELERITY`: 4.60, 2.28 and 1.03 cfs at 30, 100 and 300 ft/s. A steady state has no business knowing how fast a pressure wave travels. Make both conduits the same size and it comes back to 3.50 against EPA's 3.55 on that deck. We have not traced the cause. SWMM6 is alpha software, and we may have missed a setting, so that goes to the OpenSWMM people as a question.

`DYNAMIC_SLOT` got the right flows, but its continuity read -44.8% on water at rest. Stored volume went from 0.195 to 0.282 ac-ft with nothing moving, so the final figure appears to count slot volume and the initial one doesn't. It's the same lesson as the pump deck: a slot holds water that isn't there, and you have to keep track of it everywhere.

{{six.corpus}}

So there is no champion here. For a sharp front in the full equations, FV and RASPIPE agree, and they are the ones to use. For pressurized steady flow, as of this build, EXTRAN, the modified dynamic wave and RASPIPE give the closed form, and FV doesn't on these decks. What you pick depends on what question you are asking.

## Where the water went
The totals look fine. On the {{six.tail.n}} corpus models every engine finished, the modified dynamic wave's median continuity error came to {{six.dwmed}}, a little better than EPA's {{six.epamed}}, and models past 10% came to {{six.tail.d10}} against {{six.tail.e10}}. But a tie can hide a trade. It beat EPA by at least five points on {{six.tail.b}} of those models and lost by at least five on {{six.tail.w}}. Many of the big numbers belong to the corpus, because EPA itself reports 84% on some of those old decks. A few belong to SWMM6 alone. `Peter` is one, a small deck of five junctions and a tank. EPA and SWMM6's EXTRAN each send 0.24 of the 0.26 ac-ft out the outfall. With the modified dynamic wave the outflow is 0.000, the final storage is 0.000, and the water is simply gone. A reporting quirk can't do that, because the flow at the outfall is gone too.

When a result surprises you, change one thing at a time. We ran each option alone over the whole sample.

{{table:opts}}

{{six.o.reading}}

Here is the update, from `setNodeDepth` in `DynamicWave.cpp`, exactly as it stands:

```
double denom = surf_area + 0.5 * dt * xnode_.sumdqdh[ui];
if (nodes.storage_area[ui] == 0.0)
    denom = std::max(denom, min_surf_area_);

double dy = dV / denom;
y_new = y_old + dy;
```

Read it as a balance sheet. `dV` is the volume the node gained this step, and dividing by area turns that into a rise. The extra term in the denominator says some of that volume will leave anyway, because a higher head pushes more water down the pipes. That's true, and it's a fair correction the first time you make it. But SWMM iterates. Each trial recomputes the flows at the latest head, so `dV` already knows about the higher head. The denominator then takes the same water out a second time.

Follow it to where the iteration settles and you get (A + ½Δt ΣdQ/dH) ΔH = dV. The node's storage rises by A ΔH, so ½Δt ΣdQ/dH ΔH of volume is left over at every step, on nobody's ledger. A plain junction books no storage, so it has nowhere to show. When the head stops moving, ΔH is zero and the leak closes. That's why steady flows come out right, and why a steady test would never catch it.

The manual's Equation 3-45 has the same form. Its text and the comment above the code both say the flow is linearized about the current head estimate. The current estimate is `y_last`. The equation and the code start from the old head, `y_old`. On the first trial those are the same number, and after that they aren't.

That is a theory, and a theory needs a test. We put a switch in a test copy that starts from the current estimate:

```
dy = (dV - surf_area * (y_last - y_old)) / denom;
y_new = y_last + dy;
```

{{table:semi}}

Read across. Tightening `HEAD_TOLERANCE` to 1e-8 does almost nothing to the code as written. `Peter` stays at 99.998%, so the iteration had already converged, on the wrong answer. The switch brings `CALIBR` and `mod59` most of the way back to plain SWMM6 and gets much of `Peter`'s outflow back. Then the tight tolerance starts to help, which is the second thing we learned. A big denominator makes each step small, so the head test passes while water is still unaccounted for. `IMPERIAL` needs both and still isn't home. `pump_exam` doesn't respond to either. There, External Inflow itself jumps from 0.54 to 6.07 ac-ft, so something else is going on, and we haven't traced it. Over the whole sample the switch takes `SEMI_IMPLICIT`'s wrong-way count from {{six.o.semi.worse}} to {{six.o.semiN.worse}} and its right-way count from {{six.o.semi.better}} to {{six.o.semiN.better}}, so it explains some of the losses and not all of them.

Those are old decks, and some have odd geometry, so we built a clean one. One cfs enters the head of a box 36 ft long and 200 ft wide, and a 2 ft pipe carries it to a free outfall, at a fixed 30 s step.

{{table:box}}

{{fig:shortbox|Figure 12. Flow in the pipe below the box. All three end near 1 cfs, so a steady check sees nothing wrong. The modified dynamic wave takes {{six.box.hr}} hours to get there where the 1 s run takes {{six.box.hr0}}, and the difference is the missing water. The test patch closes the balance, but look how it shakes.}}

Now be fair to `SEMI_IMPLICIT`, because this deck shows why it exists. At 30 s EPA and SWMM6's EXTRAN both come apart, with all the water flooded and a continuity error of -67.95%. `SEMI_IMPLICIT` holds together where they can't. What it charges for that is about 15% of the water: {{six.box.dw}} ac-ft out the outfall against {{six.box.ref}} at a 1 s step. The browser build and the October 29 native build agree on those continuity figures, so this isn't an old bug in an old build.

And don't mistake the switch for a fix. It closes the books at -0.006%, but the flow in the box then rings between {{six.box.lo}} and {{six.box.hi}} cfs. It tells you where the water went. It doesn't tell you how to keep the water and stay stable. That belongs to the OpenSWMM team, who know this code and may know a reason we don't. The manual recommends `SEMI_IMPLICIT` for virtual junctions and TPA, and nothing here tests either one.

## What the corpus did to it
A solver that passes its textbook problems has proved that it can pass textbook problems. The test of a sewer solver is a sewer, and the test of the fellow who wrote it is whether he reads the list of his worst results from the top.

So we drew {{sweep.drawn}} models at random from the 1729 corpus, stratified by file size, and ran each through EPA 5.2.4 and RASPIPE with a 60 s limit per run. The first pass looked fine. The median continuity error was small. Then we sorted the list worst first and started finding real defects, none of which any textbook problem had touched.

Seepage took water the cells did not have. SWMM limits a conduit's loss to the conduit's volume, and that volume includes the pieces the manholes borrow. The loss then came out of the interior cells alone, in this line:

```
Cell[p->c0 + i].src -= r * Cell[p->c0 + i].vOld / tot;
```

When r times the step exceeded tot, the cell had a negative right side, no solution existed, and the solver thrashed through a thousand factorizations a step. Worse, the bookkeeping quietly reported the rate it had not delivered. The loss is now capped at what the cells hold, and the reported rate is cut to match.

A sealed run of full cells has no storage. Line up several full cells between a manhole and a closed face and the matrix for that run is singular, because nothing in it can store anything. The true answer is that the head rises until a manhole overflows, and a singular matrix cannot say so. Nested Newton just sat there. A trace on a model with pipes set 58 ft up the shaft showed it plainly: zero movement, residual of 1,207 ft³. A vanishingly small area on the diagonal gives Newton a direction to raise the whole run.

A dry face is a wall. Face areas are taken from the previous trial, which means a face dry at the start of a trial stays shut for that trial. A front moving more than a cell per step in a steep pipe piles into its own closed door, and the head goes up and out the nearest manhole. On a model that stock SWMM floods by a hair, the first cure for the sealed run produced 83,000 ft³ of flood that was pure artifact. It looked fine by continuity. Continuity will always look fine. It took a side-by-side with the stock numbers to catch it. Now a dry face opens as soon as the level upstream passes its invert, at about critical velocity, and the next trial replaces that with the real thing.

Four trials were not enough. One deck set `MAX_TRIALS 4`, a harmless number for stock SWMM. With fronts to chase, RASPIPE needs more. That deck flooded 21.6 ac-ft that stock did not. At 8 trials it flooded 0.1 and stock flooded 0.02. The engine now always allows 8 and stops early when it has converged.

Demand at a dry node has no solution either. A negative lateral inflow at a cell that has run dry, with nothing able to reach it in this step, is an impossible request. The unmet part is now dropped for the step and stays out of the volume ledger, so the solver no longer beats its head against it. The report shows it honestly as a continuity error.

Quality routing assumed one flow. EPA's quality code mixes each conduit using a single flow and makes up the difference from the change in volume. RASPIPE has a different flow at each end, so handing it the mid-conduit flow created or lost pollutant mass, 21% on one model. Quality routing now gets the flow that actually crosses each end. The same model came down to {{q.fix}}%, against {{q.stock}}% on stock. This is the one place EPA's logic outside the hand-off changes, and only when RASPIPE is on.

Models that had been failing started to run. One that had timed out at 60 s finished in {{fix.t}} s.

So we froze the engine and ran the sample again, and it was not done with us. Two models segfaulted, inside EPA's culvert routine, because the first face of a conduit can sit below the culvert inlet when the end cell borrows the top of the pipe, and this line then handed the FHWA equations a head below the inlet:

```
Qc = MIN(Qc, p->barrels * culvert_getInflow(j, Q / p->barrels, etaL));
```

A flat outlet channel at a `NORMAL` outfall passed 58 cfs where stock passed 1,415, because normal flow on a zero slope is next to nothing. SWMM tops normal depth out at the crown and lets head drive the flow above that, and now so does this code. And a chain of short steep chutes off a fixed-stage outfall carried 11.3 cfs from 0.54 ft of head. Diffusion wave has no inertia, so nothing told the water it had to be accelerated from rest. A hand calculation of critical flow says 2.0 cfs. Stock says 2.6. Flow leaving a node is now held to critical, and that chute carries 2.0. The fix cost something: a steep run through a junction now stands about 0.6% deeper than normal depth, and it is in the table above.

That made nine. We froze it, ran the sample a third time, and called that version 1.0.

## A clock for the pipes
One deck stayed wrong in version 1.0. Pipes set 58 ft up 60 ft shafts, steep runs, 164 cfs. It surged and flooded 7.2 ac-ft where stock floods 0.02. The entry cap that fixed the chute had made it worse, and it went out the door as an open item.

Then Bob Dickinson pointed out what the HEC-RAS pipe network options actually do about instability, and the first thing to say is that the answer was on HEC's own page the whole time. Most modelers meet instability by cutting the time step for the entire model. HEC-RAS doesn't have to. It gives the pipe network its own clock.

The option is called Adaptive Time Step, and it is on by default. The pipe interval is adjusted "by comparing the estimated residence time Courant values to the Target Courant value for each cell," and the default target is 0.9. Residence time is how long water stays in a cell: what it holds over what leaves. HEC's pages give no formula. CivilGEO's note on the 2D version says it in words, the flow leaving a cell over the step divided by the volume in the cell, and that is how this engine reads it. For each cell, C = Δt × outflow / volume. Hold the largest C in the network at 0.9.

Look at what that does to the bug. Face areas are frozen for a trial, so a dry face is a wall until the trial after, and the whole trouble was a front moving more than a cell per step. At a Courant number under 1 a front has no time to. The defect isn't so much patched as starved.

So a SWMM routing step now runs as many pipe steps inside it as the target needs, and the rest of SWMM never knows. Hydrology, controls, the report and the `.out` file keep their own step, and mean flows go back at the end so SWMM's totals see what really moved. That steep deck takes about 10 pipe steps per routing step, floods nothing, and sends {{opt.out}} ac-ft out the end against stock's 89.12. That is one engine against another, not against an exact answer, but flooding 7 ac-ft that stock doesn't flood wasn't a close call.

It paid twice. A step can now also grow. HEC says the base interval is "reduced or increased," and SWMM's own variable step stretches through dry weather, so when the target would allow the whole `ROUTING_STEP` and next to nothing is arriving, RASPIPE takes it. While water is moving the step stays at 15 s or less. An 8 month continuous run that used to hit the time limit now finishes in {{opt.t10}} s, and time step sensitivity on the mixed model fell to about a third: at a 60 s step the peak is within {{opt.dt60}}%, where it was 1.46%.

{{fig:options|Figure 13. What HEC's start-up and time step options do on three test decks. The bars in each row are scaled to that row, so compare within a row and not between rows.}}

Two more options deal with the first moments of a run, where a model can throw a spike nobody asked for.

Use Initial Stage. HEC recommends it for stage boundaries: "the first value in the stage timeseries will be projected into the upstream conduits and that flat water surface used as the initial condition." Without it, a tide standing 5 ft up an outfall pours into a dry network on the first step. We tested exactly that. RASPIPE without the option surged {{opt.surge}} cfs and stock surged {{opt.stock}} cfs, against nothing at all with it on. Be clear about what that shows. A network that really is dry under a higher stage would take that inflow. Zero flow doesn't mean the solver got a transient right. It means the run began from a different state, already filled, which is what HEC intends and usually what a modeler wants. That's an initialization check and not an accuracy test. Here it covers `FIXED`, `TIDAL` and `TIMESERIES` outfalls, runs up open conduits only, and stops at flap gates and at the top of a manhole. It is on by default, as at HEC.

Warm Up. HEC ramps the water surfaces feeding the network "over the first 2/3 of the warmup period," then holds them, and insists on 30 or more steps. SWMM has no such period, so `RASPIPE_WARMUP` runs one before the clock starts: inflows come up over the first 2/3, then hold, nothing is reported, and whatever ends up in the pipes goes to initial storage and not to inflow. A full manhole dumping into a dry 5 cfs pipe peaked at {{opt.spike}} cfs without it and 5.00 with 60 warm up steps. That shows spin-up works, nothing more. It is off by default, because it changes what a run starts from.

HEC's fourth item, Compute Every 2D Iteration, has no SWMM counterpart. There is no 2D area to couple to.

One defect came out of all this. On a deck with 492 ft pipes, where a 6 inch pipe was entered in the wrong units, a dead dry network made 328 ft³ of water from nothing. A rounding error in a dry cell became a flow through an opening face, and the next dry cell, with no width to hold it, turned that into a big level. It now takes 0.001 ft of water to open a dry face.

All three options switch off, and with `RASPIPE_COURANT 0` and `RASPIPE_INITIAL_STAGE NO` the `.out` matches version 1.0 byte for byte on {{null.n11}} of {{null.n11}} decks.

## The final count
Version 1.2 changed the full equations and left diffusion wave alone, and the corpus sweep is diffusion wave. So we didn't have to take that on faith. {{dw.line}} Every corpus number here comes from the version 1.1 build for that reason. Run time didn't move either: on two decks timed in interleaved pairs against version 1.1, the ratios ran 0.95 to 1.01 and 0.95 to 1.12, which is inside the noise.

Version 1.1 went through the sample, and it caught its own mistake on the way. The new quiet rule let the very first step run the whole `ROUTING_STEP`, an hour on some decks, before any inflow was known, and reported continuity went from 0.01% to 10%. The step now can't stretch until the run is under way, and never past 300 s. Models with a long `ROUTING_STEP` and `VARIABLE_STEP` on were rerun, 40 others were rerun to show they hadn't moved, and every corpus number here comes from that build.

{{fig:corpus|Figure 14. Routing continuity error across the corpus sample, version 1.1. The corpus is rich in stress tests, so the stock numbers describe those decks and are not typical of a well-built model.}}

{{sweep.para1}}

{{sweep.para2}}

{{sweep.para3}}

A reviewer pointed out that those paragraphs account for {{sw.cmp}} models out of {{sw.ran}}, and asked what became of the rest. Fair enough. Conservation is one measure, and a solver that times out has no continuity error to report.

{{table:outcomes}}

{{sw.tmo}} models hit the limit on RASPIPE and finished on stock. That is the real cost of this method on those models, and it doesn't show in a continuity table. Fourteen models finished with a step the solver couldn't close to its target. {{sw.uns}} The list is on the Verify tab, one line each.

The full equations had never seen the corpus, so version 1.2 ran them on a random 160. {{sw.swe}}

## Asking HEC-RAS itself
Everything so far compared this engine with arithmetic, with EPA's engine, with SWMM6 and with a solver written in the same session. None of that is HEC-RAS. The method came from HEC's pages, and a page is not a program. So Bob installed HEC-RAS 7.0.2 on his Windows machine, and we asked it.

HEC ships a set of pipe network examples made from SWMM's own EXTRAN test decks, together with the SWMM files they came from and HEC's own result files. That is about as fair a meeting ground as you could ask for. HEC chose the decks, HEC built the RAS models, and HEC ran them first.

The first job was to check the referee. Run the same five plans twice and you ought to get the same answer, and you do: all {{ras.ab}} result datasets matched to the last bit. Against the files HEC shipped, made with versions 7.0 and 7.0.1, heads agreed within {{ras.shiph}} ft and mid-pipe flows within {{ras.shipq}}% of peak away from the outfall. Changing nothing but the output interval moved RAS's own answer by up to {{ras.ivh}} ft. That is the noise floor, and a difference smaller than that is not a difference.

Then the deck. A SWMM file and a RAS file can describe the same sewer in slightly different words, and if they disagree you will spend a week chasing a typo. So the SWMM deck was built from the geometry RAS stores in its own results file: every invert, length, roughness and diameter as RAS read them. Below the last node RAS has a 2D area where SWMM has an open channel, so RAS's water surface there became the outfall stage. Both engines ran diffusion wave with 100 ft cells and a Courant target of 0.9, and RASPIPE's mid-pipe flow was set against RAS's mid-pipe face, every minute, for six hours.

{{table:rasscore}}

On EXTRAN 1 RASPIPE's mean head difference came to {{ras.h_rp0}} ft, against {{ras.h_epa0}} ft for EPA 5.2.4 on the same deck. Closer, but not close enough. The pass band, written down before any run, asked for 90% of nodes and pipes to stay within 0.1 ft and 2% of peak at 90% of instants, and it missed.

Three things carried most of the miss. One manhole, 80608, floods. RAS spills the overflow onto a 2D surface and lets the head climb to {{ras.peak80608}} ft, and SWMM stops it at the 135.0 ft rim. Raise that one rim to RAS's peak and the plateau head at 82309 agrees to the hundredth of a foot, {{ras.h82p}} against {{ras.h82r}}, with pipe 1602 carrying {{ras.q16p}} cfs against {{ras.q16r}}. The second is node 81009, where RASPIPE sits at {{ras.h81p}} ft, which is Manning's normal depth, and RAS sits at {{ras.h81r}}. We don't know why yet. The third was the interesting one.

{{fig:ras|Figure 15. Head at node 82309 on HEC's EXTRAN 1, with the rim at 80608 matched. HEC-RAS 7.0.2's stored result is dashed. RASPIPE as in version 1.2 reaches the plateau up to {{ras.early}} minutes early. With 12.566 ft² of storage per full cell it rises with RAS, and both hold RAS's plateau to the hundredth of a foot.}}

RASPIPE's three upper manholes rose through a level 2 ft below their plateau at {{ras.fillP}}. RAS's rose at {{ras.fillR}}. A lead of {{ras.early}} minutes is a long time in a storm sewer, and it is far too big to be noise.

Here is what a full pipe does in this engine. Its cell table goes flat at the crown, so a full cell holds a fixed volume, and any more water has to go somewhere else, up a manhole, which here is a 12.566 ft² shaft. Fill three long pipes and the head jumps as much as {{ras.jump}} ft in two minutes. RAS's never climbed more than {{ras.rasrate}} ft in a minute. Something in RAS was storing water that this engine was not.

The place to look was RAS's own bookkeeping. Its results file holds each cell's property table, and those tables end at the crown, just as ours do. So add up what went into the three upper pipes, take away what came out, and compare it with what their tables say they can hold. While they run full, {{ras.gap}} ft³ more water is in them than their tables allow. Divide by the head above the crowns, summed over the {{ras.n6}} full cells, and you get {{ras.r6}} ft² per cell per foot of head. On EXTRAN 2 it is {{ras.r2}}. When the pipes drain, the difference falls to almost nothing.

{{fig:rasvol|Figure 16. Water in pipes 8040, 8060 and 1602 beyond what RAS's own cell tables hold, against 12.566 ft² times the summed head above the crown of each full cell. The two track each other through filling, the plateau and draining. This is read from RAS's results, not from its code or its manuals.}}

That number rang a bell. EPA's default minimum surface area for a node, `MIN_SURFAREA`, is 12.566 ft², the plan area of a 4 ft manhole. It looks as though RAS gives every full pipe cell that much water surface above its crown. HEC's pages don't say so, and this is a reading of its results, not of its code. In slot terms it is a slit {{ras.slotw}} ft wide in a 100 ft cell, which in a 4 ft pipe makes a pressure wave run at about {{ras.c4}} ft/s. A real one runs at thousands.

So engine 1.3 has a new option, `RASPIPE_PRESSURE_AREA`. Set it, and every full cell stores that plan area per foot of head above its crown, and each junction cell the same for every barrel of the highest pipe it borrows from. It is off by default, and with it off the engine writes what version 1.2 wrote: {{ras.null}}. With 12.566 the upper nodes rise at {{ras.fillS}}, within a minute of RAS, and the mean head difference on EXTRAN 1 falls from {{ras.h_rp}} to {{ras.h_pa}} ft with the rim matched, against EPA's {{ras.h_epa}}.

A value tuned on one plan proves little on that plan. So it went, unchanged, onto the others.

{{table:rasho}}

EXTRAN 2 is the real test, a different storm through the same pipes, and it moved the same way, {{ras.x2_rp}} to {{ras.x2_pa}} ft. EXTRAN 4 never fills its pipes, so nothing changed, which is what ought to happen. EXTRAN 5 got a little worse in heads and a little better in flows, {{ras.x5_rp}} to {{ras.x5_pa}} ft, and its mean head errors of {{ras.x5_rp}} ft come from somewhere we have not traced. Every plan still misses the pass band. EXTRAN 7 is left out, because RAS runs its pump through a pump station and rules, and the deck builder doesn't translate those.

Be clear about what this settles. It shows where this engine and HEC-RAS part company, and by how much. It does not say which of them is right about a real sewer. A pipe under pressure does store a little water, in the stretch of its walls and the squeeze of the water, but nowhere near this much. So the option stays off by default. If you want this engine to agree with HEC-RAS where pipes run full, turn it on. If you want a rigid pipe, leave it off.

## What this does not show
- No field data appears anywhere in this work. Agreement with Manning, with a pump curve and with another solver shows the arithmetic is right. It says nothing about whether a model predicts a real sewer.
- HEC-RAS 7.0.2 has been run on four of HEC's own EXTRAN examples, on one Windows machine. Every plan misses the pass band set beforehand. Node 81009 and EXTRAN 5's 0.7 ft errors are not explained, and EXTRAN 7's pump is not tested. The full-pipe storage value is read from RAS's results, not from HEC's code or manuals, and it was set on EXTRAN 1.
- Where the two engines disagree in the corpus, nobody has yet sorted out which is right, model by model. A few we looked at are startup transients in nearly dry pipes, and one is a sill control limiting a backflow that stock lets through.
- A manhole here is a real tank up to its MaxDepth. EXTRAN stores nothing above the crown. A deck with a fake 1,000 ft MaxDepth gets 1,000 ft tanks. On one pressure network the heads now start at the outfall stage and sink slowly toward their steady values, and after 2 hours they are still on their way, where stock sits at steady head from the first step.
- A conduit holds one concentration, as in EPA's code, while its flow now varies along the cells. {{sweep.qnote}}
- Hot start files carry node and link states, not cell states, so a restart begins from a slightly different profile inside each conduit.
- Pressure transients such as water hammer are not modeled. HEC says the same of its own solver.
- The WebAssembly build matched the native `.out` byte for byte on {{wasm.same}} of {{wasm.n}} test decks. On the others the largest difference was {{wasm.max}}, from a different math library.
- Timing here is one machine. Treat the ratio as an order of magnitude.
- HEC does not publish its Courant formula or how far its interval may move. Residence time as outflow over volume is this engine's reading of their words.
- The Stoker test uses a test build, because a deck can't place a step inside a conduit and the `.out` file doesn't hold cells. The advection code is the same. It is one rectangular channel, and the U-tube is one pipe.
- What counts as a strong contraction is our number, and the benchmarks here don't exercise it. Neither does anything here test a real contraction, such as a pipe stepping down in size.
- Momentum crosses a junction of two conduits and stops at any other junction. Real junctions are somewhere in between, and no test here measures them.
- The wave reference was written in the same AI session as the engine. It shares no code, and it could share a mistaken idea.
- The full equations have run on 160 corpus models, against 1,466 for diffusion wave.
- The slot finding is one term by term test on one deck.
- SWMM6 is alpha software, moving fast, and the browser build is from October 17. The comparison uses eight small decks and a random sample. The FV shortfall on full pipes is an open question, not a diagnosis.
- The `SEMI_IMPLICIT` test patch is a diagnostic in a private copy, and it makes the box flow ring. Its cause is traced on some decks and not on `pump_exam`. Virtual junctions and TPA, the cases the manual recommends it for, were not tested.
- No HEC-RAS, SWMM6 or EPA developer has looked at this comparison.
- The defect list above is what the sample found. The other 2,900 models in the local corpus have not been run on the final engine.
- No person has reviewed this code yet.

## How to use it
1. Put `FLOW_ROUTING RASPIPE` in `[OPTIONS]`. That is all you must do.
2. Run at your usual `ROUTING_STEP`. The pipes keep their own clock at a target Courant number of 0.9, and `RASPIPE_COURANT` changes it. If instability shows up, lower the target before you touch the step for the whole model. `RASPIPE_COURANT 0` turns it off.
3. Set `RASPIPE_CELL_LENGTH`, and raise `RASPIPE_MAX_CELLS` for long pipes. Run it twice, halving the cell length, and watch whether your answer moves. If it moves, you were not done.
4. Read the RASPIPE block near the end of the report. It gives the build, the mesh you really got, how many conduits hit the cell limit, the pipe steps, the largest Courant number, the volume ledger and any steps left unsolved.
5. Tick the SWMM6 lines to add its modified dynamic wave and FV to any run. Use `RASPIPE_EQUATIONS SWE` when inertia matters. Try `RASPIPE_THETA 0.6` with it when a sharp front matters, and hold the step down if you do. Water loses a velocity head at any junction of three or more pipes.
6. If the first minutes throw a spike, try `RASPIPE_WARMUP 60`. Stage boundaries already project up the pipes, and `RASPIPE_INITIAL_STAGE NO` turns that off.
7. To agree with HEC-RAS where pipes run full, add `RASPIPE_PRESSURE_AREA 12.566`. Leave it out for a rigid pipe.

## Related apps
{{related}}

## Use of AI
{{aiuse}}

## Sources
{{sources}}
