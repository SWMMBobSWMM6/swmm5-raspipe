p='/root/rp/slotx/src/solver/dwflow.c'; s=open(p).read()
s=s.replace('#include "headers.h"\n','#include "headers.h"\n#include <stdlib.h>\nstatic int SlotVar(void){ static int v=-1; if(v<0){ char*e=getenv("SLOTVAR"); v=e?atoi(e):0;} return v; }\n',1)
old="""    v = qLast / aMid;
    if ( fabs(v) > MAXVELOCITY )  v = MAXVELOCITY * SGN(qLast);
"""
new="""    v = qLast / aMid;
    if ( SlotVar() & 1 ) v = qLast / MIN(aMid, xsect->aFull);
    if ( fabs(v) > MAXVELOCITY )  v = MAXVELOCITY * SGN(qLast);
"""
assert old in s; s=s.replace(old,new)
old="""    dq2 = dt * GRAVITY * aWtd * (h2 - h1) / length;
"""
new="""    if ( SlotVar() & 2 ) aWtd = MIN(aWtd, xsect->aFull);
    dq2 = dt * GRAVITY * aWtd * (h2 - h1) / length;
"""
assert old in s; s=s.replace(old,new)
open(p,'w').write(s)
