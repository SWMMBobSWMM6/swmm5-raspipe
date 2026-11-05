#!/usr/bin/env python3
"""Analytic and control tests for the RASPIPE solver. Writes verify.json."""
import sys, os, re, json, math, subprocess, hashlib
sys.path.insert(0, '/root/rp/tests')
import gen, gen2, outread as o
D = '/root/rp/tests/v/'
os.makedirs(D, exist_ok=True)
import os
RP = os.environ.get('RPBIN','/root/rp/bin/swmm5_rp'); REF = '/root/rp/ref/swmm5_ref'
PHI = 1.486
R = []
LAST=[None]
def run(txt, name, exe=RP, env=None):
    p = D + name
    LAST[0]=name
    open(p + '.inp', 'w').write(txt)
    e = dict(os.environ)
    if env: e.update(env)
    subprocess.run([exe, p + '.inp', p + '.rpt', p + '.out'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=e, timeout=300)
    return open(p + '.rpt', errors='replace').read(), o.read(p + '.out')
def cont(t):
    m = re.findall(r'Continuity Error \(%\) \.+\s+(-?[\d.]+)', t)
    return float(m[-1]) if m else None
def counters(t):
    g = lambda p: (float(re.search(p, t).group(1)) if re.search(p, t) else None)
    return dict(trials=g(r'Trials per step \.+ ([\d.]+)'), fact=g(r'Factorizations per step \. ([\d.]+)'), nested=g(r'Nested Newton solves \.+ ([\d.]+)'), fail=g(r'Unconverged nested solves (\d+)'))
def add(id, name, expect, got, unit, note=''):
    err = None
    if isinstance(expect, (int, float)) and isinstance(got, (int, float)) and expect != 0:
        err = 100 * (got - expect) / expect
    R.append(dict(id=id, name=name, expect=expect, got=got, unit=unit, err=err, note=note, deck=LAST[0]))
    print(f"{id:5s} {name:46s} expect {expect}  got {got}  {unit}  err {err if err is None else round(err,4)}%  {note}")
def Kfull(d, n):
    a = math.pi * d * d / 4
    return PHI / n * a * (d / 4) ** (2 / 3)
def yn(q, d, s, n):
    lo, hi = 1e-5, 0.8 * d
    for _ in range(200):
        y = (lo + hi) / 2
        th = 2 * math.acos(1 - 2 * y / d); a = d * d / 8 * (th - math.sin(th)); pp = th * d / 2
        if PHI / n * a * (a / pp) ** (2 / 3) * s ** .5 < q: lo = y
        else: hi = y
    return y

# --- V1 null control: keyword off
for nm, txt in dict(mixed=gen2.mixed('DYNWAVE'), mixedvs=gen2.mixed('DYNWAVE', extra='VARIABLE_STEP 0.75'), slot=gen2.mixed('DYNWAVE', extra='SURCHARGE_METHOD SLOT'), fill=gen.sealed(route='DYNWAVE')).items():
    a = run(txt, 'n_ref_' + nm, REF); b = run(txt, 'n_rp_' + nm, RP)
    same = open(D + 'n_ref_' + nm + '.out', 'rb').read() == open(D + 'n_rp_' + nm + '.out', 'rb').read()
    add('V1', 'null control, .out identical: ' + nm, 'identical', 'identical' if same else 'DIFFERENT', '')

# --- V2 lake at rest
t, r = run(gen.lake(), 'lake')
qmax = max(max(abs(x) for x in o.link(r, L, 0)) for L in r['L'])
dmax = max(max(o.node(r, N, 1)) - min(o.node(r, N, 1)) for N in r['N'])
add('V2', 'lake at rest, largest conduit flow', 0.0, qmax, 'cfs')
add('V2', 'lake at rest, largest head change', 0.0, dmax, 'ft', 'float32 .out')

# --- V3 full pipe, two fixed heads
t, r = run(gen.fullpipe(), 'full')
h1 = o.node(r, 'J1', 1)[-1]
add('V3', 'pressurized pipe, Manning', Kfull(1, .013) * math.sqrt((h1 - 10) / 1000), float(o.link(r, 'C1', 0)[-1]), 'cfs')
t, r = run(gen.fullpipe(extra='RASPIPE_EQUATIONS SWE'), 'full_swe')
h1 = o.node(r, 'J1', 1)[-1]
k = Kfull(1, .013); a = math.pi / 4
q = k * math.sqrt((h1 - 10) / 1000)
for _ in range(50): q = k * math.sqrt((h1 - 10 - (q / a) ** 2 / (2 * 32.2)) / 1000)
add('V3', 'pressurized pipe, SWE (velocity head lost at exit)', q, float(o.link(r, 'C1', 0)[-1]), 'cfs')

# --- V4 sealed series: every cell at T = 0, nothing but the head boundary
txt = gen.head('sealed series', end='02:00:00') + """
[OUTFALLS]
O1 5 FIXED 40
O2 4 FIXED 20
[JUNCTIONS]
J1 5 2 0 50 0
J2 5 2 0 50 0
[CONDUITS]
C0 O1 J1 500 0.013 0 0 0 0
C1 J1 J2 800 0.013 0 0 0 0
C2 J2 O2 700 0.013 0 0 0 0
[XSECTIONS]
C0 CIRCULAR 1 0 0 0 1
C1 CIRCULAR 1 0 0 0 1
C2 CIRCULAR 1 0 0 0 1
""" + gen.TAIL
t, r = run(txt, 'series')
add('V4', 'sealed series, no free surface anywhere', Kfull(1, .013) * math.sqrt(20 / 2000), float(o.link(r, 'C1', 0)[-1]), 'cfs')

# --- V5 normal depth
for q, d, s, n in [(5, 2, .002, .013), (12, 3, .001, .015), (1, 1.5, .01, .012), (20, 4, .0005, .013)]:
    t, r = run(gen.uniform(q=q, D=d, S=s, n=n, L=4000), 'unif')
    add('V5', f'normal depth Q={q} D={d} S={s}', yn(q, d, s, n), float(o.link(r, 'C1', 1)[-1]), 'ft')

# --- V6 pump on a pressurized pipe: the slot bias of EPA issue 231
pump = lambda route, extra: gen.head('pump', route, end='03:00:00', dt='1', extra=extra) + """
[STORAGE]
WW 0 40 10 FUNCTIONAL 10000000 0 0 0 0
[JUNCTIONS]
J1 0 40 8 0 0
[OUTFALLS]
O1 0 FIXED 8
[CONDUITS]
C1 J1 O1 1000 0.013 0 0 0 0
[PUMPS]
P1 WW J1 PC1 ON 0 0
[XSECTIONS]
C1 CIRCULAR 1 0 0 0 1
[CURVES]
PC1 Pump3 0 10
PC1 10 6
PC1 20 3
PC1 40 0
""" + gen.TAIL
def pumpcurve(h):
    pts = [(0, 10), (10, 6), (20, 3), (40, 0)]
    if h <= 0: return 10.0
    for (a, b), (c, e) in zip(pts, pts[1:]):
        if h <= c: return b + (e - b) * (h - a) / (c - a)
    return 0.0
for label, route, extra, exe in [('RASPIPE', 'RASPIPE', '', RP), ('EXTRAN', 'DYNWAVE', 'SURCHARGE_METHOD EXTRAN', REF), ('SLOT', 'DYNWAVE', 'SURCHARGE_METHOD SLOT', REF)]:
    t, r = run(pump(route, extra), 'pump_' + label, exe)
    ww = o.node(r, 'WW', 1)[-1]
    lo, hi = 0.0, 10.0
    for _ in range(200):
        m = (lo + hi) / 2
        h1 = 8 + 1000 * (m / Kfull(1, .013)) ** 2
        if pumpcurve(h1 - ww) > m: lo = m
        else: hi = m
    add('V6', 'pump into full pipe, ' + label, m, float(o.link(r, 'C1', 0)[-1]), 'cfs')

# --- V7 nested Newton and plain Newton solve the same system
a = run(gen2.mixed(dt='1'), 'nest_a')
b = run(gen2.mixed(dt='1', extra='RASPIPE_NESTED_ONLY YES'), 'nest_b')
qa = o.link(a[1], 'C1', 0); qb = o.link(b[1], 'C1', 0)
add('V7', 'nested only vs plain first, largest C1 difference', 0.0, max(abs(x - y) for x, y in zip(qa, qb)), 'cfs', json.dumps(counters(b[0])))

# --- V8 fill volume: time to reach the crown of a dead-end pipe
t, r = run(gen.sealed(q=2, D=2, L=1000, dt='1'), 'fill')
y = o.node(r, 'J2', 0)
n = next(i for i, v in enumerate(y) if v >= 3.0)
# volume to head of 3 ft at J2 in a flat pipe = full pipe + 2 shafts to about 3 ft
v = math.pi * 2 ** 2 / 4 * 1000 + 2 * 12.566 * 3
add('V8', 'time for 2 cfs to fill pipe and shafts to 3 ft', v / 2 / 60, (n + 1) * 1.0, 'min', 'report step 1 min')

# --- V9 time step: unsteady peak should hold as the step grows
base = None
for dt in ['1', '5', '15', '30', '60']:
    t, r = run(gen2.mixed(dt=dt, extra='VARIABLE_STEP 0'), 'dt')
    p = max(o.link(r, 'C2', 0)); h = max(o.node(r, 'J2', 0))
    base = base or (p, h)
    add('V9', f'mixed model, step {dt} s, C2 peak', base[0], float(p), 'cfs', 'continuity %s %s' % (cont(t), json.dumps(counters(t))))

# --- V10 volume ledger on the mixed model
t, r = run(gen2.mixed(dt='5'), 'ledger')
m = re.search(r'Volume ledger.*?= (-?[\d.e+-]+)', t)
add('V10', 'volume ledger closure, mixed model', 0.0, float(m.group(1)), 'ft3', 'on 304,200 ft3 of inflow')
# --- V11 the three v1.1 options off must give back the v1.0 engine, byte for byte
FROZEN = '/root/rp/bin/swmm5_rp_final2'
if os.path.exists(FROZEN):
    n = 0; decks = [('mixed', gen2.mixed(dt='5')), ('fill', gen.sealed(q=2, D=2, L=1000, dt='1')), ('pump', pump('RASPIPE', ''))]
    for name, txt in decks:
        off = txt.replace('[OPTIONS]\n', '[OPTIONS]\nRASPIPE_COURANT 0\nRASPIPE_INITIAL_STAGE NO\n', 1)
        run(off, 'c11a'); run(txt, 'c11b', FROZEN)
        n += open(D + 'c11a.out', 'rb').read() == open(D + 'c11b.out', 'rb').read()
    add('V11', 'v1.1 options off, .out identical to v1.0', len(decks), n, 'decks')

# --- V12 stage boundary against a dry network: projection should leave it at rest
stage = lambda route, extra: gen.head('stage', route, end='02:00:00', dt='5', extra=extra) + """
[JUNCTIONS]
J1 100 20 0 0 0
J2 98 20 0 0 0
[OUTFALLS]
O1 96 FIXED 101
[CONDUITS]
C1 J1 J2 1000 0.013 0 0 0 0
C2 J2 O1 1000 0.013 0 0 0 0
[XSECTIONS]
C1 CIRCULAR 3 0 0 0 1
C2 CIRCULAR 3 0 0 0 1
""" + gen.TAIL
peak = lambda r, l: max(abs(x) for x in o.link(r, l, 0))
t, r = run(stage('RASPIPE', ''), 'st1'); add('V12', 'stage boundary, dry start, stage projected: largest flow', 0.0, float(peak(r, 'C2')), 'cfs')
t, r = run(stage('RASPIPE', 'RASPIPE_INITIAL_STAGE NO'), 'st2'); add('V12', 'same, stage not projected: the surge HEC warns of', 0.0, float(peak(r, 'C2')), 'cfs')
t, r = run(stage('DYNWAVE', ''), 'st3', REF); add('V12', 'same, EPA 5.2.4 DYNWAVE', 0.0, float(peak(r, 'C2')), 'cfs')

# --- V13 warm up: a full manhole dumping into a dry pipe at the first step
warm = lambda route, extra: gen.head('warm', route, end='02:00:00', dt='5', extra=extra) + """
[JUNCTIONS]
J1 100 12 8 0 0
J2 99 12 0 0 0
[OUTFALLS]
O1 98 FREE
[CONDUITS]
C1 J1 J2 500 0.013 0 0 0 0
C2 J2 O1 500 0.013 0 0 0 0
[XSECTIONS]
C1 CIRCULAR 2 0 0 0 1
C2 CIRCULAR 2 0 0 0 1
[TIMESERIES]
H 0:00 5
H 2:00 5
[INFLOWS]
J1 FLOW H FLOW 1 1 0
""" + gen.TAIL
t, r = run(warm('RASPIPE', ''), 'w1'); add('V13', 'start up spike, no warm up: peak in a 5 cfs pipe', 5.0, float(peak(r, 'C1')), 'cfs', 'continuity %s' % cont(t))
t, r = run(warm('RASPIPE', 'RASPIPE_WARMUP 60'), 'w2'); add('V13', 'same, RASPIPE_WARMUP 60', 5.0, float(peak(r, 'C1')), 'cfs', 'continuity %s' % cont(t))

# --- V14 a front that outruns the cells: 164 cfs down steep pipes, stock floods 0.02 ac-ft
F14 = '/root/rp/corpus/SWMM5_NCIMM/diversion_weir_network.inp'
hit = subprocess.run(['grep', '-m1', '/diversion_weir_network.inp', '/root/rp/sweep/final.txt'], capture_output=True, text=True).stdout.strip()
if hit:
    txt = re.sub(r'(?m)^\s*FLOW_ROUTING\s+\S+', 'FLOW_ROUTING RASPIPE', open(hit, errors='replace').read())
    fl = lambda t: float(re.search(r'Flooding Loss \.+\s+([\d.]+)', t).group(1))
    t, r = run(txt, 'f1'); a = fl(t)
    t, r = run(txt.replace('[OPTIONS]', '[OPTIONS]\nRASPIPE_COURANT 0', 1), 'f2'); b = fl(t)
    add('V14', 'false flood on a steep deck, target Courant 0.9', 0.02, a, 'ac-ft', 'EPA 5.2.4 floods 0.02')
    add('V14', 'same, Courant control off', 0.02, b, 'ac-ft', 'the v1.0 result')
json.dump(R, open(D + 'verify.json', 'w'), indent=1)
