#!/usr/bin/env python3
"""Minimal SWMM .out reader (no deps): returns times, node & link series."""
import struct, sys
def read(path):
    b=open(path,'rb').read()
    i=lambda o: struct.unpack_from('<i',b,o)[0]
    offObj,offRes,nPer,err,magic=struct.unpack_from('<5i',b,len(b)-24+4) if False else (i(len(b)-24),i(len(b)-20),i(len(b)-12) if False else 0,0,0)
    # footer: idNames, objProps, results, nPeriods, errCode, magic
    idp,objp,resp,nper,ecode,mag=struct.unpack_from('<6i',b,len(b)-24)
    m0,ver,units,nS,nN,nL,nP=struct.unpack_from('<7i',b,0)
    pos=idp
    names=[]
    for _ in range(nS+nN+nL+nP):
        n=i(pos); names.append(b[pos+4:pos+4+n].decode()); pos+=4+n
    N=names[nS:nS+nN]; L=names[nS+nN:nS+nN+nL]
    # variable counts
    p=resp-(0)
    # results header: walk back from known layout
    # after objp: props; find variable section
    q=objp
    nc=i(q); q+=4+4*nc+4*nc*0
    q=objp
    # subcatch props 
    k=i(q); q+=4*(1+k)+4*k*nS
    k=i(q); q+=4*(1+k)+4*k*nN
    k=i(q); q+=4*(1+k)+4*k*nL
    nv=[]
    for _ in range(4):
        k=i(q); nv.append(k); q+=4*(1+k)
    # q now holds system vars; then start date, report step
    ns,nn,nl,nsys=nv
    rec=8+4*(ns*nS+nn*nN+nl*nL+nsys)
    rstep=i(resp-4)
    t=[];nd=[];lk=[];sysv=[]
    for r in range(nper):
        o=resp+r*rec
        t.append(struct.unpack_from('<d',b,o)[0])
        o2=o+8+4*ns*nS
        nd.append(struct.unpack_from('<%df'%(nn*nN),b,o2))
        o3=o2+4*nn*nN
        lk.append(struct.unpack_from('<%df'%(nl*nL),b,o3))
    return dict(t=t,N=N,L=L,nn=nn,nl=nl,nd=nd,lk=lk,rstep=rstep,err=ecode)
def node(r,name,var):  # 0 depth 1 head 2 vol 3 lat 4 inflow 5 overflow
    j=r['N'].index(name); return [x[j*r['nn']+var] for x in r['nd']]
def link(r,name,var):  # 0 flow 1 depth 2 vel 3 vol 4 cap
    j=r['L'].index(name); return [x[j*r['nl']+var] for x in r['lk']]
