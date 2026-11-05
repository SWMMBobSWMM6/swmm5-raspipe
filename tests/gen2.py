#!/usr/bin/env python3
import sys
sys.path.insert(0,'/root/rp/tests')
from gen import head, TAIL
def mixed(route='RASPIPE', extra='', dt='5', pond=False):
    "Storage + orifice + weir + pump + outlet + flap gate + flooding, one storm-shaped inflow."
    e = extra + ('\nALLOW_PONDING YES' if pond else '')
    return head('mixed', route, end='06:00:00', dt=dt, extra=e) + """
[JUNCTIONS]
J1 110 10 0 0 {pa}
J2 105 10 0 0 0
J3 100 8 0 0 0
J4 96 6 0 0 0
J5 96 12 0 0 0
[OUTFALLS]
O1 90 FREE NO
O2 92 FIXED 94 YES
[STORAGE]
S1 100 12 0 FUNCTIONAL 2000 0 0 0 0
W1 90 15 2 TABULAR WC 0 0
[CONDUITS]
C1 J1 J2 600 0.013 0 0 0 0
C2 J2 S1 500 0.013 0 0 0 0
C3 J3 J4 400 0.013 0 0 0 0
C4 J4 O1 300 0.013 0 0 0 0
C5 J5 O2 200 0.015 0 0 0 0
[PUMPS]
P1 S1 W1 PC3 ON 0 0
P2 W1 J5 PC4 ON 0 0
[ORIFICES]
OR1 S1 J3 SIDE 0 0.65 NO 0
[WEIRS]
WR1 S1 J4 TRANSVERSE 6 3.33 NO 0 0
[OUTLETS]
OT1 J5 J4 2 TABULAR/DEPTH OC NO
[XSECTIONS]
C1 CIRCULAR 3 0 0 0 1
C2 CIRCULAR 3 0 0 0 1
C3 CIRCULAR 2 0 0 0 1
C4 CIRCULAR 2.5 0 0 0 1
C5 CIRCULAR 2 0 0 0 1
OR1 CIRCULAR 1.25 0 0 0
WR1 RECT_OPEN 2 6 0 0
[CURVES]
PC3 Pump3 0 40
PC3 4 30
PC3 8 10
PC3 14 0
PC4 Pump4 0 0
PC4 2 2
PC4 8 8
WC Storage 0 500
WC 15 500
OC Rating 0 0
OC 6 3
[TIMESERIES]
HYD 0:00 0
HYD 0:30 8
HYD 1:00 40
HYD 1:30 60
HYD 2:00 30
HYD 3:00 8
HYD 4:00 0
[INFLOWS]
J1 FLOW HYD FLOW 1 1 0
""".format(pa=2000 if pond else 0) + TAIL
if __name__ == '__main__':
    d=sys.argv[1]
    open(d+'/mixed.inp','w').write(mixed())
    open(d+'/mixedref.inp','w').write(mixed('DYNWAVE',extra='VARIABLE_STEP 0.75'))
    open(d+'/mixedp.inp','w').write(mixed(pond=True))
