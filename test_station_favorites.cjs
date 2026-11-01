const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const calls=[],nodes={},stored={};
const c={favorites:[],favoriteRevision:null,favoriteRF:{available:false},favoriteLoadError:'',legacyFavorites:[],legacyFavoriteError:'',station:{},localStorage:{getItem:k=>stored[k]??null},esc:v=>String(v??'').replace(/</g,'&lt;'),$:id=>nodes[id],confirm:()=>true,action:fn=>fn(),message:msg=>{c.lastMessage=msg;},connections:()=>{},api:async(u,d)=>{calls.push({u,d});return {revision:2,favorites:d?.favorites||[],rf:{available:true}};}};
vm.createContext(c);vm.runInContext(source.slice(source.indexOf('// Station favorites are authoritative.')),c);
(async()=>{
 assert.equal(c.memoryCommand('1'),'*51');assert.equal(c.memoryCommand('999'),'*5999');for(const s of ['0','01','1000','1;','-1','1.0',''])assert.equal(c.memoryCommand(s),'');
 stored['ara.favorites']='{bad';c.readLegacyFavorites();assert(c.legacyFavoriteError);assert.equal(c.legacyFavorites.length,0);assert.equal(stored['ara.favorites'],'{bad');
 stored['ara.favorites']=JSON.stringify([{mode:'DMR',target:'91',note:'<script>'}]);c.readLegacyFavorites();assert.equal(c.legacyFavorites.length,1);assert(c.legacyImportMarkup(false).includes('&lt;script>'));assert(c.legacyImportMarkup(false).includes('Choose DMR network'));
 const backup=stored['ara.favorites'];await c.loadStationFavorites();assert.equal(stored['ara.favorites'],backup);assert.equal(c.favorites.length,0);assert.equal(calls.length,1);assert.equal(calls[0].d,undefined);
 c.api=async()=>{throw Object.assign(Error('stale'),{status:409});};const previous=[{id:'a',mode:'AllStar',target:'2000',slot:'1',enabled:false}];c.favorites=previous;c.favoriteRevision=4;
 await assert.rejects(()=>c.saveStationFavorites([]),/Reload station favorites/);assert.strictEqual(c.favorites,previous);assert.equal(c.favoriteRevision,4);
 c.api=async()=>{throw Error('offline');};await c.loadStationFavorites();assert.equal(c.favoriteRevision,null);assert(!c.favoriteRF.available);assert(c.favoriteLoadError.includes('offline'));await assert.rejects(()=>c.saveStationFavorites([]),/Load station favorites/);
 c.favoriteLoadError='';c.favoriteRevision=4;c.favorites=previous;c.favoriteRF={available:false,reason:'Missing include'};const html=c.favoriteControlsMarkup();assert(html.includes('Missing include'));assert(html.includes('value="1"'));assert(html.includes('*51'));assert(html.includes('name="enabled" type="checkbox"  disabled'));assert(!html.includes('*501'));
 // DOM binding: typing never writes; save carries stable IDs and preserves unrelated rows.
 const row={dataset:{memoryId:'a'},slot:{value:'7'},enabled:{checked:true},output:{},querySelector(q){return q==='[name=slot]'?this.slot:q==='[name=enabled]'?this.enabled:this.output;}};
 nodes['favorites-reload']={};nodes['favorite-memory-form']={querySelectorAll:()=>[row]};nodes['favorite-import-form']=null;
 c.favoriteRF={available:true};c.api=async(u,d)=>{calls.push({u,d});return {revision:5,favorites:d.favorites,rf:{available:true}};};c.bindFavoriteControls();const n=calls.length;row.slot.oninput();assert.equal(row.output.textContent,'*57');assert.equal(calls.length,n);
 await nodes['favorite-memory-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert.equal(calls.length,n+1);assert.equal(calls.at(-1).d.favorites[0].id,'a');assert.equal(calls.at(-1).d.favorites[0].slot,'7');assert(calls.at(-1).d.favorites[0].enabled);
 // RF unavailable still permits saving a disabled assignment; only enabling is gated.
 c.favoriteRF={available:false,reason:'Missing include'};row.enabled.checked=false;row.slot.value='9';
 await nodes['favorite-memory-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));
 assert.equal(calls.at(-1).d.favorites[0].slot,'9');assert.equal(calls.at(-1).d.favorites[0].enabled,false);
 // Match the backend identity: source ID is metadata, not a duplicate destination escape.
 assert.equal(c.favoriteDestinationKey({mode:'DMR',target:'91',network:'TGIF',source_id:'1'}),c.favoriteDestinationKey({mode:'DMR',target:'91',network:'TGIF',source_id:'2'}));
 c.favorites=[{id:'station',mode:'DMR',target:'91',network:'TGIF',note:'Station note',source_id:'123'}];
 assert(c.importFavoriteConflict({mode:'DMR',target:'91',network:'TGIF',note:'Other',source_id:'123'}));
 assert(c.importFavoriteConflict({mode:'DMR',target:'91',network:'TGIF',note:'Station note',source_id:'456'}));
 assert(!c.importFavoriteConflict({mode:'DMR',target:'91',network:'TGIF',note:'Station note',source_id:'123'}));
 assert(!c.importFavoriteConflict({mode:'DMR',target:'91',network:'BrandMeister',note:'Other'}));
 c.legacyFavorites=[{mode:'DMR',target:'91',note:'Browser note'}];
 let network='',selected=true;nodes['favorite-import-form']={querySelectorAll:()=>selected?[{value:'0'}]:[],querySelector:()=>({value:network})};
 c.action=async fn=>{c.lastError='';try{await fn();}catch(e){c.lastError=e.message;}};
 c.bindFavoriteControls();const initial=calls.length;
 nodes['favorite-import-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert(c.lastError.includes('Choose a DMR network'));assert.equal(calls.length,initial);
 network='TGIF';nodes['favorite-import-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert(c.lastError.includes('station note or source ID differs'));assert.equal(calls.length,initial);
 selected=false;nodes['favorite-import-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert(c.lastError.includes('Select at least one'));assert.equal(calls.length,initial);
 selected=true;network='BrandMeister';nodes['favorite-import-form'].onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert.equal(calls.length,initial+1);assert.equal(calls.at(-1).u,'/api/favorites/import');assert.equal(calls.at(-1).d.favorites[0].network,'BrandMeister');assert.equal(stored['ara.favorites'],backup);
 const startup=source.slice(source.indexOf('async function start()'),source.indexOf('async function pollStation()'));
 assert(startup.indexOf('await loadStationFavorites();')>=0&&startup.indexOf('await loadStationFavorites();')<startup.indexOf('renderPage();'));
 assert(!source.includes("localStorage.setItem('ara.favorites'"));
 console.log('PASS: memory ranges/leading zero, escaped import review, malformed browser JSON preservation, explicit import/no automatic writes, stale atomic UI state, unavailable fail-closed, mocked DOM preview/save stable IDs, disabled saves when RF unavailable, import note/source conflicts and explicit DMR selection.');
})().catch(e=>{console.error(e);process.exitCode=1;});
