// Runs one .inp through the OpenSWMM 6 alpha.4 engine from Seven SWMM Engines. Usage: node run6.js in.inp out.rpt out.out
const fs=require('fs'),path=require('path');
const createSwmm6=require('/root/rp/swmm6/openswmm6a4_glue.cjs');
(async()=>{const [inp,rpt,out]=process.argv.slice(2);const log=[];
 const t0=Date.now();
 const m=await createSwmm6({print:s=>log.push(s),printErr:s=>log.push(s),noInitialRun:true});
 m.FS.writeFile('/model.inp',fs.readFileSync(inp));
 const h=m._swmm_engine_create();const lastErr=()=>{try{const p=m._swmm_get_last_error_msg(h);return p?m.UTF8ToString(p):'';}catch(e){return '';}};
 let err=m.ccall('swmm_engine_open','number',['number','string','string','string','number'],[h,'/model.inp','/run.rpt','/run.out',0]),msg='',steps=0,el=0;
 if(!err)err=m._swmm_engine_initialize(h);if(!err)err=m._swmm_engine_start(h,1);
 const p=m._malloc(8);if(!err){do{err=m._swmm_engine_step(h,p);el=m.getValue(p,'double');steps++;}while(!err&&el>0&&steps<2e8);}
 m._free(p);if(err)msg=lastErr();
 let cont=null;try{const pe=m._malloc(16);m._swmm_get_runoff_continuity_error(h,pe);m._swmm_get_routing_continuity_error(h,pe+8);cont=m.getValue(pe+8,'double')*100;m._free(pe);}catch(e){}
 const e2=m._swmm_engine_end(h);if(!err&&e2){err=e2;msg=lastErr();}const e3=m._swmm_engine_report(h);if(!err&&e3){err=e3;msg=lastErr();}
 m._swmm_engine_close(h);m._swmm_engine_destroy(h);
 const rd=q=>{try{return m.FS.readFile(q);}catch(e){return null;}};const r=rd('/run.rpt'),o=rd('/run.out');if(r)fs.writeFileSync(rpt,r);if(o)fs.writeFileSync(out,o);
 console.log(JSON.stringify({err,msg,steps,cont,ms:Date.now()-t0,log:log.slice(-3)}));
})().catch(e=>{console.log(JSON.stringify({err:-1,msg:String(e&&e.message||e)}));process.exit(0);});
