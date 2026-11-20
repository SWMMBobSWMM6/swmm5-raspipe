"""Step 2 of the HEC-RAS plan, regenerated: does HEC-RAS 7.0.2 on yoo100 reproduce HEC's shipped results, run to run and
against the files HEC shipped? Copy A and copy B are two runs of the same project; orig holds HEC's own result files.
Copy C changed only the hydrograph output interval to 1 minute. Writes tests/v/ras_rerun.json."""
import h5py,numpy as np,json,sys
sys.path.insert(0,'/root/rp/hecras/cmp'); import rasread
H='/root/rp/hecras'; P=['p01','p02','p03','p04','p06']
def dsets(path):
    f=h5py.File(path,'r'); out={}
    f['Results'].visititems(lambda k,v: out.__setitem__(k,v[()]) if isinstance(v,h5py.Dataset) and 'Compute Messages' not in k and 'Compute Processes' not in k else None)
    return out
same=0; n=0; diff=[]
for p in P:
    a=dsets(f'{H}/runA/ExtranTestImport.{p}.hdf'); b=dsets(f'{H}/runB/ExtranTestImport.{p}.hdf')
    for k in a:
        if k not in b: diff.append((p,k,'missing')); continue
        n+=1
        if (a[k].dtype==b[k].dtype and a[k].shape==b[k].shape and a[k].tobytes()==b[k].tobytes()): same+=1
        else: diff.append((p,k))
def cmp(pa,pb,block=None):
    A=rasread.read(pa,block=block); B=rasread.read(pb,block=block); m=min(len(A['t']),len(B['t']))
    dh=max(float(np.max(np.abs(A['ws'][k][:m]-B['ws'][k][:m]))) for k in A['ws'])
    rows=[]
    for k in A['qmid']:
        pk=max(float(np.max(np.abs(B['qmid'][k][:m]))),0.035); e=np.abs(A['qmid'][k][:m]-B['qmid'][k][:m])/pk; i=int(np.argmax(e))
        rows.append((k,float(e.max()),float(A['t'][i])))
    rows.sort(key=lambda r:-r[1]); return dh,rows,A['version'],B['version']
ship={}; out={}
for p in P:
    dh,rows,va,vb=cmp(f'{H}/runA/ExtranTestImport.{p}.hdf',f'{H}/orig/ExtranTestImport.{p}.hdf','Base Output')
    ship[p]=dict(head=dh,flows=rows[:3],ver=va,shipped=vb)
    dh2,rows2,_,_=cmp(f'{H}/runC/ExtranTestImport.{p}.hdf',f'{H}/runA/ExtranTestImport.{p}.hdf','Base Output')
    out[p]=dict(head=dh2,flows=rows2[:3])
res=dict(ab=dict(same=same,n=n,diff=diff[:5]),shipped=ship,interval=out)
json.dump(res,open('/root/rp/tests/v/ras_rerun.json','w'),indent=1)
print('A vs B',same,'of',n)
for p in P: print(p,'vs shipped head %.3f'%ship[p]['head'],[(k,round(e*100,2),round(t,2)) for k,e,t in ship[p]['flows']],ship[p]['shipped'],'| 1-min copy head %.3f'%out[p]['head'],[(k,round(e*100,1),round(t,2)) for k,e,t in out[p]['flows']])
