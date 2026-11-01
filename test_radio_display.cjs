const fs=require('fs'),vm=require('vm'),assert=require('assert');
const s=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const css=fs.readFileSync(__dirname+'/app/web/operator.css','utf8');
const nodes=Object.fromEntries(['rig-connected-destination','rig-active-mode','rig-rf-mode','rig-current-speaker','rig-speaker-detail','rig-overlay'].map(id=>[id,{textContent:'',dataset:{},hidden:true,innerHTML:''}]));
let now=1000,resolveRequest,requests=0,response={active:true,identity:'K1TEST',mode:'D-STAR',state:'active',expires_in_ms:1000};
const c={$:id=>nodes[id],station:{connected:true,mode:'YSF',active_connections:[{mode:'D-STAR',target:'REF001C'}]},runtime:{radio_enabled:true},path:'/',performance:{now:()=>now},document:{documentElement:{dataset:{layout:'3'}},hidden:false,addEventListener(){}},location:{},setInterval(){},setTimeout(){return 1},clearTimeout(){},AbortController,connectionLabel:r=>r.mode+' '+r.target,rigSetText:(id,t)=>{if(nodes[id])nodes[id].textContent=t;},fetch:async()=>{requests++;return {ok:true,status:200,json:async()=>response};}};
vm.createContext(c);
vm.runInContext(s.slice(s.indexOf('// The front panel uses confirmed links'),s.indexOf('// The large dial selects')),c);
(async()=>{
 assert.equal(c.rigTrafficSummary(c.station).mode,'D-STAR','pending selected YSF must not replace active DSTAR');
 for(const mode of ['AllStar','EchoLink','DMR','D-STAR','YSF','P25','NXDN','M17']){
  c.station.active_connections=[{mode,target:'TEST'}];assert.equal(c.rigTrafficSummary(c.station).mode,mode);
 }
 c.station.active_connections=[{mode:'DMR',target:'91'},{mode:'AllStar',target:'12345'}];assert.equal(c.rigTrafficSummary(c.station).mode,'MULTI-LINK');
 c.station.connected=false;assert.equal(c.rigTrafficSummary(c.station).mode,'NO LINK');assert.equal(c.rigTrafficSummary(c.station).destination,'Not connected');
 assert.equal(c.rigSpeakerText(response,false,now,2000).text,'Not connected');
 assert.equal(c.rigSpeakerText(response,true,now,2000).text,'K1TEST');
 assert.equal(c.rigSpeakerText(response,true,2000,2000).text,'Listening');
 assert.equal(c.rigSpeakerText({...response,identity:null},true,now,2000).text,'Identity unavailable');
 assert.equal(c.rigSpeakerText({active:false,identity:'STALE'},true,now,2000).text,'Listening');
 c.station={connected:true,active_connections:[{mode:'DMR',target:'91'}]};c.refreshRigTraffic();assert.equal(nodes['rig-rf-mode'].textContent,'RF · FM');
 c.runtime.radio_enabled=false;c.refreshRigTraffic();assert.equal(nodes['rig-rf-mode'].textContent,'RADIO STOPPED');
 await c.refreshRigSpeaker();assert.equal(nodes['rig-current-speaker'].textContent,'K1TEST');
 now+=1001;c.refreshRigTraffic();assert.equal(nodes['rig-current-speaker'].textContent,'Listening');assert.equal(nodes['rig-current-speaker'].dataset.active,'false');
 // Slow response cannot extend an old talker's lifetime.
 c.fetch=async()=>{now+=2000;return {ok:true,json:async()=>response};};await c.refreshRigSpeaker();assert.equal(nodes['rig-current-speaker'].textContent,'Listening');
 // Disconnect or newer connection invalidates an in-flight result.
 c.fetch=()=>new Promise(r=>{resolveRequest=r});const pending=c.refreshRigSpeaker();c.station.connected=false;c.refreshRigTraffic();resolveRequest({ok:true,json:async()=>response});await pending;
 assert.equal(nodes['rig-current-speaker'].textContent,'Not connected');
 // Other layouts never perform speaker polling.
 c.document.documentElement.dataset.layout='1';c.station.connected=true;let sent=false;c.fetch=async()=>{sent=true};await c.refreshRigSpeaker();assert.equal(sent,false);
 // Text is inserted using textContent; no received identity is interpreted as HTML.
 assert(s.includes("rigSetText('rig-current-speaker',speaker.text)"));assert(!s.includes("$('rig-current-speaker').innerHTML"));
 // New hierarchy and responsive rules retain meter, frequencies and tones.
 const markup=s.slice(s.indexOf('<div class="rig-screen-upper">'),s.indexOf('<div class="rig-destination">',s.indexOf('<div class="rig-screen-upper">')));
 assert(markup.indexOf('rig-meter-host')<markup.indexOf('rig-traffic'));assert(markup.indexOf('rig-traffic')<markup.indexOf('rig-frequencies'));
 for(const id of ['rig-frequency-rx','rig-frequency-tx','rig-rx-tone','rig-tx-tone','rig-connected-destination','rig-active-mode','rig-current-speaker'])assert(markup.includes(id));
 assert(css.includes('html[data-layout="3"] .rig-frequencies{grid-column:3'));assert(css.includes('html[data-layout="3"] .rig-frequencies{grid-column:2;grid-row:1'));
 // Existing panel Back/Exit closes without a command and returns focus.
 vm.runInContext(s.slice(s.indexOf('function rigClose(){'),s.indexOf('function rigOpen(')),c);
 c.rigPanel='menu';let focused=0;c.rigFocus={isConnected:true,focus(){focused++}};nodes['rig-overlay'].hidden=false;nodes['rig-overlay'].innerHTML='menu';c.rigClose();
 assert(nodes['rig-overlay'].hidden);assert.equal(nodes['rig-overlay'].innerHTML,'');assert.equal(c.rigPanel,null);assert.equal(focused,1);
 assert(s.includes("$('rig-back').onclick=()=>name==='menu'?rigClose():rigOpen('menu');$('rig-exit').onclick=rigClose;"));
 console.log('PASS: actual active modes, all-mode labels, speaker freshness/expiry/delay/disconnect, no fake identity, layout-only polling, far-right RX/TX PL, phone rules, panel close/focus and Back/Exit');
})().catch(e=>{console.error(e);process.exitCode=1});
