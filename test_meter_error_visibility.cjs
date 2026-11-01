const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/app/web/audio-meter.js','utf8');
const css=fs.readFileSync(__dirname+'/app/web/operator.css','utf8');
const nodes={};function node(id){return nodes[id]??={textContent:'',attrs:{},setAttribute(k,v){this.attrs[k]=v;},classList:{toggle(){},remove(){}},querySelectorAll(){return [];}};}
const box={isConnected:true,querySelector:node};
let response={active:false,error:'Passive meter module unavailable'},now=1000;const intervals=[];
const c={busy:false,host:null,held:{rx:-96,tx:-96},expires:{rx:0,tx:0},lastSequence:-1,lastDelivery:0,lastFeedError:'',
 document:{hidden:false},mount:()=>box,performance:{now:()=>now},AbortController,setTimeout:()=>1,clearTimeout(){},
 setInterval:(fn,ms)=>intervals.push({fn,ms}),updateSharedMeter:(b,s)=>{c.latest=s;},
 fetch:async()=>({ok:true,json:async()=>response})};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('async function update()'),source.lastIndexOf('})();')),c);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 await flush();assert.match(node('#meter-state').textContent,/module unavailable/);
 now+=1000;intervals.find(x=>x.ms===100&&x.fn!==c.update).fn();
 assert.match(node('#meter-state').textContent,/module unavailable/,'watchdog must not overwrite the actual failure reason');
 response={active:true,sequence:1,rx:{available:true,rms_db:-96,peak_db:-96,age_ms:0},tx:{available:true,rms_db:-12,peak_db:-6,age_ms:0}};
 await c.update();assert.match(node('#meter-state').textContent,/Live/);assert.equal(c.lastFeedError,'');assert(c.latest.active);
 now+=400;intervals.find(x=>x.ms===100&&x.fn!==c.update).fn();assert.match(node('#meter-state').textContent,/Waiting for fresh audio/);
 assert(!css.includes('#rig-meter-host .audio-console-footer,#rig-meter-host .audio-meter-help'));
 assert.match(css,/#rig-meter-host \.audio-console-footer\{display:block/);
 assert(source.includes("lastFeedError=s.error||''"));
 console.log('PASS Radio3 meter error visible, retained through watchdog, cleared on recovery; stale audio remains unavailable');
})().catch(e=>{console.error(e);process.exit(1)});
