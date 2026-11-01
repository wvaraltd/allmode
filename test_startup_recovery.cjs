const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const block=source.slice(source.indexOf('// One startup attempt at a time'),source.indexOf('// Resume setup'));
const apiBlock=source.slice(source.indexOf('async function api('),source.indexOf('\nfunction message'));
function fixture(path='/settings',layout='2'){
 const nodes=Object.fromEntries(['connection-status','live','health'].map(x=>[x,{hidden:true,textContent:''}]));
 let failures={},calls=[],renders=[],listeners={},intervals=[],pending=null,dirty=false,form='typed draft';
 const c={location:{pathname:path,hash:'#review',search:'',replace(){}},path,station:{},schema:{},runtime:{},busy:false,formDirty:false,
  $:id=>nodes[id],setInterval:(fn,ms)=>intervals.push([fn,ms]),addEventListener:(n,fn)=>{(listeners[n]??=[]).push(fn);},
  loadSchema:async()=>{calls.push('schema');await Promise.resolve();if(pending)await pending;if(failures.schema)throw Error('/api/onboarding unavailable');c.schema={complete:false};},
  api:async url=>{calls.push(url);if(failures[url])throw Error(url+' unavailable');return {available:true};},
  loadStationFavorites:async()=>{calls.push('favorites');},
  renderPage:()=>renders.push([c.path,c.location.hash,layout]),health:()=>{nodes.health.textContent='healthy';},
  dashboard:()=>renders.push(['dashboard',layout]),refreshConnectionStatus:()=>{},
 };
 vm.createContext(c);vm.runInContext(block,c);
 return {c,nodes,calls,renders,listeners,intervals,failures,
  hold(){pending=new Promise(r=>this.release=()=>{pending=null;r();});},
  state:()=>vm.runInContext('({startupReady,startupPending:!!startupPending,statusPending})',c)};
}
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 for(const route of ['/settings','/'])for(const layout of ['1','2','3'])for(const failure of ['schema','/api/status']){
  // Initial async schema call pauses until failure flags can be applied.
  const f=fixture(route,layout);f.failures[failure]=true;await flush();
  // schema can have completed synchronously; force the subsequent attempt if needed.
  if(failure==='schema'&&f.state().startupReady){throw Error('fixture schema must fail initial attempt');}
  assert.equal(f.state().startupReady,false);assert.equal(f.renders.length,0);
  assert.match(f.nodes['connection-status'].textContent,/Retrying automatically/);
  await f.c.pollStation();assert.equal(f.renders.length,0,'repeated failure does not render');
  delete f.failures[failure];await f.c.pollStation();
  assert.equal(f.state().startupReady,true);assert.deepEqual(f.renders[0],[route,'#review',layout]);
  assert.equal(f.intervals.length,1);assert.equal(f.intervals[0][1],5000);
  assert.equal(f.listeners.hashchange.length,1);
 }
 const f=fixture();await flush();
 f.c.formDirty=true;const count=f.renders.length;
 f.failures['/api/status']=true;await f.c.pollStation();assert.match(f.nodes['connection-status'].textContent,/Live status update failed/);
 delete f.failures['/api/status'];await f.c.pollStation();assert.equal(f.renders.length,count,'recovery does not rebuild settings or edits');
 assert.equal(f.c.formDirty,true);assert.equal(f.nodes['connection-status'].hidden,true);
 const h=fixture('/settings','3');h.failures['/api/status']=true;await flush();h.c.location.pathname='/';h.c.location.hash='';delete h.failures['/api/status'];await h.c.pollStation();assert.deepEqual(h.renders,[['/','','3']]);
 const g=fixture();g.failures['/api/status']=true;await flush();delete g.failures['/api/status'];g.hold();
 const a=g.c.start(),b=g.c.start(),p=g.c.pollStation();await flush();
 const before=g.calls.filter(x=>x==='schema').length;
 await g.c.pollStation();assert.equal(g.calls.filter(x=>x==='schema').length,before,'no overlap');
 g.c.location.pathname='/settings';g.c.location.hash='#radio';g.listeners.hashchange[0]();
 assert.equal(g.renders.length,0,'pending hash change does not render incomplete schema');
 g.release();await Promise.all([a,b,p]);assert.deepEqual(g.renders,[['/settings','#radio','2']]);
 // Exercise actual API wrapper: timeout/error visibility, GET-only cancellation, no retrying writes.
 let timeout,cleared=0,fetchCalls=[];
 const q={AbortController,setTimeout:fn=>{timeout=fn;return 1},clearTimeout:()=>cleared++,location:{},rememberDestination(){},
  fetch:async(url,opts)=>{fetchCalls.push([url,opts]);return {ok:false,status:503,json:async()=>({error:'helper unavailable'})};}};
 vm.createContext(q);vm.runInContext(apiBlock,q);
 await assert.rejects(q.api('/api/onboarding'),/503/);assert.equal(cleared,1);
 q.fetch=async()=>({ok:true,status:200,json:async()=>{throw Error('html');}});
 await assert.rejects(q.api('/api/status'),/invalid response/);
 q.fetch=async(url,opts)=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Object.assign(Error(),{name:'AbortError'}))));
 const timed=q.api('/api/status');timeout();await assert.rejects(timed,/timed out after 15 seconds/);
 q.fetch=async(url,opts)=>{assert.equal(opts.method,'POST');assert.equal(opts.signal,undefined);return {ok:true,status:200,json:async()=>({ok:true})};};
 await q.api('/api/settings',{group:'station'});
 console.log('PASS startup schema/status failure recovery, layouts/routes, single flight, form preservation, error/timeout reporting and no mutation retries');
})().catch(e=>{console.error(e);process.exit(1)});
