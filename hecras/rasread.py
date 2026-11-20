"""Read HEC-RAS 7 pipe network results from a plan HDF: node water surfaces and conduit flows, columns mapped to names."""
import h5py,numpy as np
OB='Results/Unsteady/Output/Output Blocks/'
def read(path,net='Base',block=None):
    f=h5py.File(path,'r')
    if block is None:
        block='DSS Hydrograph Output' if (OB+'DSS Hydrograph Output/Unsteady Time Series/Pipe Networks') in f else 'Base Output'
    B=OB+block+'/Unsteady Time Series/'
    nodes=[r['Name'].decode() for r in f['Geometry/Pipe Nodes/Attributes'][:]]
    conds=[r['Name'].decode() for r in f['Geometry/Pipe Conduits/Attributes'][:]]
    G=f'Geometry/Pipe Networks/{net}/'
    ni=f[G+'Node Indices'][:]; ci=f[G+'Conduit Indices'][:]
    P=B+f'Pipe Networks/{net}/'
    t=f[B+'Time'][:]*24.0   # hours
    out=dict(t=t,
      ws={nodes[k]:f[P+'Nodes/Water Surface'][:,j] for j,k in enumerate(ni)},
      inlet={nodes[k]:f[P+'Nodes/Top + Side Inlet Flow'][:,j] for j,k in enumerate(ni)},
      qus={conds[k]:f[P+'Pipes/Pipe Flow US'][:,j] for j,k in enumerate(ci)},
      qds={conds[k]:f[P+'Pipes/Pipe Flow DS'][:,j] for j,k in enumerate(ci)},
      version=f.attrs['File Version'].decode(),
      summary={k:(v.decode() if isinstance(v,bytes) else v) for k,v in f['Results/Unsteady/Summary'].attrs.items()},
      plan={k:(v.decode() if isinstance(v,bytes) else v) for k,v in f['Plan Data/Plan Information'].attrs.items()})
    out['geom_nodes']={r['Name'].decode():dict(inv=float(r['Invert Elevation']),base=float(r['Base Area']),terr=float(r['Terrain Elevation']),depth=float(r['Depth']),type=r['Node Type'].decode(),inlet=r['Top Inlet Type'].decode()) for r in f['Geometry/Pipe Nodes/Attributes'][:]}
    out['geom_conds']={r['Name'].decode():dict(us=r['US Node'].decode(),ds=r['DS Node'].decode(),L=float(r['Conduit Length']),cell=float(r['Max Cell Length']),shape=r['Shape'].decode(),rise=float(r['Rise']),span=float(r['Span']),n=float(r["Manning's n"]),uoff=float(r['US Offset']),doff=float(r['DS Offset']),ue=float(r['US Elevation']),de=float(r['DS Elevation'])) for r in f['Geometry/Pipe Conduits/Attributes'][:]}
    fc=f[G+'Faces Conduit ID and Stations'][:]; ff=f[P+'Face Flow'][:]
    out['qmid']={}; out['midst']={}
    for j,k in enumerate(ci):
        idx=[i for i in range(len(fc)) if fc['ConduitID'][i]==k]
        if not idx: continue
        L=out['geom_conds'][conds[k]]['L']
        b=min(idx,key=lambda i:abs(fc['ConduitStation'][i]-L/2))
        out['qmid'][conds[k]]=ff[:,b]; out['midst'][conds[k]]=float(fc['ConduitStation'][b])
    return out
