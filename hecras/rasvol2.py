"""Local volume check on RAS's upper subsystem (pipes 8040, 8060, 1602 and nodes 80408, 80608, 82309)."""
import h5py,numpy as np,sys,json
p=sys.argv[1]; f=h5py.File(p,'r')
G='Geometry/Pipe Networks/Base/'; B='Results/Unsteady/Output/Output Blocks/DSS Hydrograph Output/Unsteady Time Series/'
cp=f[G+'Cell Property Table'][:]; info=f[G+'Cell Property Table Info'][:]; val=f[G+'Cell Property Table Values'][:]
cn=f[G+'Cells Node and Conduit IDs'][:]
nodes=[r['Name'].decode() for r in f['Geometry/Pipe Nodes/Attributes'][:]]; conds=[r['Name'].decode() for r in f['Geometry/Pipe Conduits/Attributes'][:]]
ni=list(f[G+'Node Indices'][:]); ci=list(f[G+'Conduit Indices'][:])
keepC={conds.index(c) for c in ('8040','8060','1602')}; keepN={nodes.index(n) for n in ('80408','80608','82309')}
cells=[c for c in range(len(cp)) if (cn[c,1] in keepC) or (cn[c,0] in keepN)]
T=f[B+'Time'][:]*86400.0; ws=f[B+'Pipe Networks/Base/Cell Water Surface'][:]
def tab(c):
    s,n=info[cp[c]['Info Index']]; return val[s:s+n]
def vol(c,z):
    t=tab(c); d=z-cp[c]['Min Elevation']
    return 0.0 if d<=0 else (float(t[-1,0]) if d>=t[-1,1] else float(np.interp(d,t[:,1],t[:,0])))
top={c:cp[c]['Min Elevation']+tab(c)[-1,1] for c in cells}
V=np.array([sum(vol(c,ws[i,c]) for c in cells) for i in range(len(T))])
over=np.array([sum(max(0.0,ws[i,c]-top[c]) for c in cells) for i in range(len(T))])
npress=np.array([sum(1 for c in cells if ws[i,c]>top[c]) for i in range(len(T))])
qds=f[B+'Pipe Networks/Base/Pipes/Pipe Flow DS'][:]; q1602=qds[:,ci.index(conds.index('1602'))]
inl=f[B+'Pipe Networks/Base/Nodes/Top + Side Inlet Flow'][:]; spill=inl[:,ni.index(nodes.index('80608'))]+inl[:,ni.index(nodes.index('80408'))]
hyd=lambda t,pk: np.interp(t,[0,900,10800,11700,1e9],[0,pk,pk,0,0])
net=hyd(T,45)+hyd(T,40)-q1602+spill
cum=np.concatenate([[0],np.cumsum(0.5*(net[1:]+net[:-1])*np.diff(T))])
gap=cum-(V-V[0])
print(len(cells),'cells')
print(' min  table vol  in-out    gap   pressurized cells  sum head above crown  gap per ft')
out=[]
for m in list(range(28,62,2))+[90,150,178,182,184,186,188,190,195,200,240,360]:
    i=int(np.argmin(np.abs(T-60*m))); r=gap[i]/over[i] if over[i]>1 else float('nan')
    out.append(dict(m=m,V=float(V[i]-V[0]),cum=float(cum[i]),gap=float(gap[i]),n=int(npress[i]),over=float(over[i])))
    print(f'{m:4d} {V[i]-V[0]:9.0f} {cum[i]:9.0f} {gap[i]:7.0f} {npress[i]:5d} {over[i]:9.1f} {r:8.2f}')
json.dump(out,open('/root/rp/tests/v/ras_slot_volume.json','w'))
