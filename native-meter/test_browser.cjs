const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let clock=0,requests=0,intervals=[],timeouts=[],behavior,hidden=false;
class Element {
 constructor(){this.textContent='';this.attrs={};this.classes=new Set();this.isConnected=true;this.children=[];
 this.classList={toggle:(n,b)=>b?this.classes.add(n):this.classes.delete(n),remove:(...ns)=>ns.forEach(n=>this.classes.delete(n)),add:n=>this.classes.add(n)};}
 setAttribute(k,v){this.attrs[k]=v;} querySelectorAll(){return this.children;}
}
const elements={};
for(const key of ['rig-led-fill','rig-meter-value','rig-needle','rig-meter-mode'])elements['#'+key]=new Element();
for(const key of ['state','rx','tx','number-rx','number-tx','text-rx','text-tx'])elements['#meter-'+key]=new Element();
for(const k of ['rx','tx'])elements['#meter-'+k].children=Array.from({length:30},()=>new Element());
const box=new Element();box.querySelector=s=>elements[s];
const doc={documentElement:{dataset:{}},get hidden(){return hidden;},getElementById:id=>id==='dashboard-audio-meters'?{}:id==='live-audio-meters'?box:null};
const sample=(sequence,db=-12)=>({active:true,sequence,rx:{available:true,age_ms:0,rms_db:db,peak_db:db},tx:{available:false,age_ms:null,rms_db:-96,peak_db:-96}});
let payload=sample(1);behavior=async()=>({ok:true,json:async()=>payload});
const context={document:doc,performance:{now:()=>clock},AbortController,
 fetch:(url,opts)=>{requests++;assert.equal(url,'/api/audio-meter');assert.equal(opts.cache,'no-store');return behavior(opts);},
 setInterval:(fn,ms)=>{assert.equal(ms,100);intervals.push(fn);},
 setTimeout:(fn,ms)=>{const t={fn,ms,active:true};timeouts.push(t);return t;},clearTimeout:t=>t.active=false};
vm.runInNewContext(fs.readFileSync(__dirname+'/../app/web/audio-meter.js','utf8'),context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await flush();assert.equal(elements['#meter-rx'].attrs['aria-valuenow'],'-12.0');assert.match(elements['#meter-state'].textContent,/Live/);
 assert.equal(intervals.length,2);const [watch,update]=intervals;
 clock=100;payload=sample(2,-30);await update();assert.equal(elements['#meter-rx'].attrs['aria-valuenow'],'-30.0');
 // Two-second peak marker does not hold the current RMS bars.
 assert.match(elements['#meter-text-rx'].textContent,/Peak -12.0/);
 clock=500;watch();assert.equal(Number(elements['#meter-rx'].attrs['aria-valuenow']),-60);
 assert.equal(elements['#rig-needle'].attrs.opacity,'.15');assert.equal(elements['#rig-led-fill'].attrs.width,'0');
 await update();assert.doesNotMatch(elements['#meter-state'].textContent,/Live/);
 hidden=true;const count=requests;await update();assert.equal(requests,count);hidden=false;
 clock=600;payload=sample(3);await update();assert.match(elements['#meter-state'].textContent,/Live/);
 // Slow response is not relabeled fresh on receipt.
 behavior=async()=>{clock+=500;return {ok:true,json:async()=>sample(4)};};
 await update();assert.equal(Number(elements['#meter-rx'].attrs['aria-valuenow']),-60);
 // Hanging HTTP aborts, cannot overlap, and stale bars clear independently.
 behavior=opts=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>{let e=new Error();e.name='AbortError';reject(e);}));
 const pending=update();await flush();const before=requests;await update();assert.equal(requests,before);
 const timeout=timeouts.find(t=>t.active);assert.equal(timeout.ms,1000);timeout.fn();await pending;
 assert.match(elements['#meter-state'].textContent,/timed out/);
 behavior=async()=>({ok:true,json:async()=>sample(5,-6)});clock+=100;await update();
 assert.equal(elements['#meter-rx'].attrs['aria-valuenow'],'-6.0');
 behavior=async()=>({ok:false});await update();assert.equal(Number(elements['#meter-rx'].attrs['aria-valuenow']),-60);
 console.log('PASS browser: 100ms cadence, RMS/peak separation, stale/repeated sequence, hidden tab, delayed response, timeout, no overlap, recovery, HTTP failure');
})().catch(e=>{console.error(e);process.exitCode=1;});
