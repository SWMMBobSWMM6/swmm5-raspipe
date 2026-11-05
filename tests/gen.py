#!/usr/bin/env python3
"""Small analytic test decks for the solver. US units, one conduit at a time."""
import sys
HEAD = """[TITLE]
{title}

[OPTIONS]
FLOW_UNITS CFS
INFILTRATION HORTON
FLOW_ROUTING {route}
START_DATE 01/01/2020
START_TIME 00:00:00
REPORT_START_DATE 01/01/2020
REPORT_START_TIME 00:00:00
END_DATE 01/01/2020
END_TIME {end}
SWEEP_START 01/01
SWEEP_END 12/31
DRY_DAYS 0
REPORT_STEP 00:{rep}
WET_STEP 00:01:00
DRY_STEP 01:00:00
ROUTING_STEP {dt}
ALLOW_PONDING NO
MIN_SURFAREA 12.566
{extra}
"""
TAIL = """
[REPORT]
INPUT NO
CONTROLS NO
NODES ALL
LINKS ALL
"""
def head(title, route='RASPIPE', end='06:00:00', rep='01:00', dt='5', extra=''):
    return HEAD.format(title=title, route=route, end=end, rep=rep, dt=dt, extra=extra)

def lake(route='RASPIPE', extra=''):
    "Three pipes on a slope, one outfall sealed by a fixed stage. Nothing should move."
    return head('lake at rest', route, extra=extra) + """
[JUNCTIONS]
J1 100 20 11 0 0
J2  99 20 12 0 0
J3  98 20 13 0 0
[OUTFALLS]
O1 97 FIXED 111
[CONDUITS]
C1 J1 J2 400 0.013 0 0 0 0
C2 J2 J3 400 0.013 0 0 0 0
C3 J3 O1 400 0.013 0 0 0 0
[XSECTIONS]
C1 CIRCULAR 3 0 0 0 1
C2 CIRCULAR 3 0 0 0 1
C3 CIRCULAR 3 0 0 0 1
""" + TAIL

def uniform(q=5.0, D=2.0, L=2000, S=0.002, n=0.013, route='RASPIPE', extra='', dt='5'):
    "Long pipe, steady inflow, normal depth outfall: the answer is Manning."
    z1 = 100.0; z2 = z1 - S*L
    return head('uniform flow', route, end='12:00:00', dt=dt, extra=extra) + f"""
[JUNCTIONS]
J1 {z1} 20 0 0 0
[OUTFALLS]
O1 {z2} NORMAL
[CONDUITS]
C1 J1 O1 {L} {n} 0 0 0 0
[XSECTIONS]
C1 CIRCULAR {D} 0 0 0 1
[INFLOWS]
J1 FLOW "" FLOW 1 1 {q}
""" + TAIL

def fullpipe(h1=20.0, h2=10.0, D=1.0, L=1000, z1=5.0, z2=4.0, n=0.013, route='RASPIPE', extra='', dt='5'):
    "Pipe between two fixed heads, both far above the crown. Answer: Q = K sqrt(dh/L)."
    return head('full pipe', route, end='02:00:00', dt=dt, extra=extra) + f"""
[OUTFALLS]
O1 {z1} FIXED {h1}
O2 {z2} FIXED {h2}
[JUNCTIONS]
J1 {z1} {h1-z1+30} {h1-z1} 0 0
[CONDUITS]
C0 J1 O1 10 {n} 0 0 0 0
C1 J1 O2 {L} {n} 0 0 0 0
[XSECTIONS]
C0 CIRCULAR 6 0 0 0 1
C1 CIRCULAR {D} 0 0 0 1
""" + TAIL

def sealed(q=2.0, D=2.0, L=1000, route='RASPIPE', extra='', dt='5'):
    "Dead-end flat pipe filled from one end through a small manhole."
    return head('filling', route, end='02:00:00', dt=dt, rep='01:00', extra=extra) + f"""
[JUNCTIONS]
J1 100 20 0 0 0
J2 100 {D} 0 0 0
[OUTFALLS]
O1 90 FREE
[CONDUITS]
C1 J1 J2 {L} 0.013 0 0 0 0
C2 J2 O1 10 0.013 {D+3} 0 0 0
[XSECTIONS]
C1 CIRCULAR {D} 0 0 0 1
C2 CIRCULAR 1 0 0 0 1
[INFLOWS]
J1 FLOW "" FLOW 1 1 {q}
""" + TAIL
if __name__ == '__main__':
    import os
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name, txt in dict(lake=lake(), uniform=uniform(), fullpipe=fullpipe(), sealed=sealed()).items():
        open(f'{out}/{name}.inp', 'w').write(txt)
