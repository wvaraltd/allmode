const fs=require('fs'),vm=require('vm'),assert=require('assert');
const s=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const nodes={},calls=[],timers=[];
function element(){return {attrs:{},style:{setProperty(){}},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,f){this[k]=f;},setPointerCapture(){},focus(){c.document.activeElement=this;}};}
for(const id of ['rig-favorite-dial','rig-favorite-connect','rig-favorite-label','rig-favorite-network','rig-favorite-target','rig-favorite-status'])nodes[id]=element();
const c={favorites:[],runtime:{node:'1999',levels:{rx:653,txa:600,txb:500}},station:{modes:['AllStar','DMR','EchoLink']},busy:false,$:id=>nodes[id],document:{},rigSetText:(id,v)=>nodes[id].textContent=v,message(){},dashboard(){c.refreshRigFavorites();},action:async f=>{if(c.busy)return;c.busy=true;try{await f();}finally{c.busy=false;}},api:async(u,d)=>{calls.push({u,d});return {...c.station};},setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){}};
vm.createContext(c);
vm.runInContext(s.slice(s.indexOf('function connectionUnavailable('),s.indexOf('function rememberDestination(')),c);
vm.runInContext(s.slice(s.indexOf('// The large dial selects'),s.indexOf('function rigDialMarkup(')),c);
const knob=nodes['rig-favorite-dial'],connect=nodes['rig-favorite-connect'];
const event=(values={})=>({preventDefault(){},...values});
const good=[{mode:'AllStar',target:'2000',note:'Club'},{mode:'DMR',target:'91',network:'TGIF'},{mode:'DMR',target:'91',network:'BrandMeister'}];
(async()=>{
 c.bindRigFavorites();assert(connect.disabled);assert.equal(knob.attrs['aria-disabled'],'true');
 c.favorites=[null,{mode:'DMR',target:'91'},{mode:'AllStar',target:'1999'},{mode:'DMR',target:'0'},{mode:'TETRA',target:'1234'},...good];
 c.refreshRigFavorites();assert.equal(c.rigFavoriteRows().length,3);assert.equal(c.rigFavoriteSelection().item.target,'2000');
 knob.onpointerdown(event({button:0,clientY:100,pointerId:1}));knob.onpointermove(event({clientY:76}));knob.onpointerup();
 assert.equal(c.rigFavoriteSelection().item.network,'TGIF');
 knob.wheel(event({deltaY:-100}));assert.equal(c.rigFavoriteSelection().item.network,'BrandMeister');
 knob.onkeydown(event({key:'Home'}));assert.equal(c.rigFavoriteSelection().index,0);
 knob.onkeydown(event({key:'End'}));assert.equal(c.rigFavoriteSelection().index,2);
 knob.onkeydown(event({key:'ArrowLeft'}));assert.equal(c.rigFavoriteSelection().item.network,'TGIF');
 knob.onkeydown(event({key:'Enter'}));assert.equal(calls.length,0);assert.deepEqual(c.runtime.levels,{rx:653,txa:600,txb:500});
 for(let i=0;i<100;i++)c.refreshRigFavorites();assert.equal(c.rigFavoriteSelection().item.network,'TGIF');
 c.favorites=[good[2],good[1],good[0]];c.refreshRigFavorites();assert.equal(c.rigFavoriteSelection().item.network,'TGIF');
 c.favorites=[good[2],good[0]];c.refreshRigFavorites();assert.equal(c.rigFavoriteSelection().item.network,'BrandMeister');
 connect.onclick();await new Promise(r=>setImmediate(r));assert.equal(calls.length,1);assert.deepEqual(calls[0].d,{action:'connect-network',mode:'DMR',value:'91',allow_bridge:false,network:'BrandMeister'});
 for(const state of [{pending:true},{readonly:true},{unavailable_modes:{DMR:'No codec'}}]){c.station={modes:['DMR'],...state};c.refreshRigFavorites();assert(connect.disabled);connect.onclick();assert.equal(calls.length,1);}
 c.station={modes:['DMR'],unavailable_modes:{DMR:'No codec'},quick_connect_modes:['DMR']};c.refreshRigFavorites();assert(!connect.disabled);
 c.busy=true;connect.onclick();assert.equal(calls.length,1);c.busy=false;
 c.favorites=[];c.refreshRigFavorites();knob.onkeydown(event({key:'End'}));knob.wheel(event({deltaY:-10}));connect.onclick();assert.equal(calls.length,1);assert(connect.disabled);
 // Revalidation at click: selected saved destination becomes our own node.
 c.station={modes:['AllStar']};c.favorites=[good[0]];c.refreshRigFavorites();c.runtime.node='2000';connect.onclick();assert.equal(calls.length,1);
 // Existing live-gain binding still sends the exact RX / TX A / TX B keys.
 vm.runInContext(s.slice(s.indexOf('function bindLiveAudio(){'),s.indexOf('function audioPage(')),c);
 nodes['audio-form']={};nodes['audio-live-result']={};
 for(const [k,v]of Object.entries({rx:653,txa:600,txb:500})){nodes['level-'+k]={value:String(v)};nodes['out-'+k]={};}
 c.bindLiveAudio();nodes['level-txa'].value='615';nodes['level-txa'].oninput({target:{value:'615'}});await timers.at(-1)();
 assert.deepEqual(calls.at(-1).d,{action:'audio',levels:{rx:653,txa:615,txb:500}});
 assert(s.includes("${rigDialMarkup('rx','RX GAIN')}${rigDialMarkup('txa','TX A')}${rigDialMarkup('txb','TX B')}"));
 assert(/refreshRigFavorites\(\);\r?\n const radio=schema.workflow/.test(s));
 console.log('PASS: pointer/wheel/keyboard selection, no auto connect/gain mutation, exact DMR network, invalid/empty/own-node/unavailable/pending/read-only/busy guards, 100 refreshes, reorder/removal reconciliation, calibrated RX/TXA/TXB mapping');
})().catch(e=>{console.error(e);process.exitCode=1;});
