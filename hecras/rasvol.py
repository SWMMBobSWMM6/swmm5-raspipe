"""Volume check on a RAS pipe network: stored volume from RAS's own cell tables against the water that went in and out."""
import h5py,numpy as np,sys
p=sys.argv[1]
f=h5py.File(p,'r')
G='Geometry/Pipe Networks/Base/'
cp=f[G+'Cell Property Table'][:]; info=f[G+'Cell Property Table Info'][:]; val=f[G+'Cell Property Table Values'][:]
B='Results/Unsteady/Output/Output Blocks/DSS Hydrograph Output/Unsteady Time Series/'
T=f[B+'Time'][:]*86400.0
ws=f[B+'Pipe Networks/Base/Cell Water Surface'][:]
def vol(c,z,extrap=0.0):
    s,n=info[cp[c]['Info Index']]; t=val[s:s+n]; d=z-cp[c]['Min Elevation']
    if d<=0: return 0.0
    if d>=t[-1,1]: return float(t[-1,0])+extrap*(d-t[-1,1])*cp[c]['Area']
    return float(np.interp(d,t[:,1],t[:,0]))
def top(c):
    s,n=info[cp[c]['Info Index']]; return cp[c]['Min Elevation']+val[s+n-1,1]
V=np.array([sum(vol(c,ws[i,c]) for c in range(len(cp))) for i in range(len(T))])
# above-table head per cell (ft x area) to test a storage term above the crown
over=np.array([sum(max(0.0,ws[i,c]-top(c)) for c in range(len(cp))) for i in range(len(T))])
nodes=[r['Name'].decode() for r in f['Geometry/Pipe Nodes/Attributes'][:]]
ni=f[G+'Node Indices'][:]
inl=f[B+'Pipe Networks/Base/Nodes/Top + Side Inlet Flow'][:]
qds=f[B+'Pipe Networks/Base/Pipes/Pipe Flow DS'][:]
conds=[r['Name'].decode() for r in f['Geometry/Pipe Conduits/Attributes'][:]]; ci=f[G+'Conduit Indices'][:]
qout=qds[:,[j for j,k in enumerate(ci) if conds[k]=='Outfall'][0]]
# inflow hydrographs at 15-min ordinates
def hyd(t,peak): return np.interp(t,[0,900,10800,11700,1e9],[0,peak,peak,0,0])
qin=hyd(T,45)+hyd(T,50)+hyd(T,40)
net=qin-qout+inl.sum(1)      # inlet flow is negative when water leaves for the surface
cum=np.concatenate([[0],np.cumsum(0.5*(net[1:]+net[:-1])*np.diff(T))])
print('time  table-volume  inflow-minus-outflow  gap  sum(depth above top of table)')
for m in range(25,61,1):
    i=int(np.argmin(np.abs(T-60*m))); print(f'{m:3d} min {V[i]-V[0]:10.0f} {cum[i]:10.0f} {cum[i]-(V[i]-V[0]):8.0f} {over[i]:8.2f}')
for m in (90,150,175,185,190,200,240,300,360):
    i=int(np.argmin(np.abs(T-60*m))); print(f'{m:3d} min {V[i]-V[0]:10.0f} {cum[i]:10.0f} {cum[i]-(V[i]-V[0]):8.0f} {over[i]:8.2f}')
