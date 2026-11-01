const fs=require('fs'),vm=require('vm'),assert=require('assert');
const s=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const block=s.slice(s.indexOf('function wifiSecurity('),s.indexOf('\nconst basicConnections'));
function fixture(){
 const nodes={},requests=[],confirmations=[];
 for(const id of ['content','wifi-form','wifi-scan','wifi-results','wifi-scan-status','wifi-password-label','wifi-connect','wifi-save-only','wifi-cancel','wifi-message','wifi-security-note'])
  nodes[id]={innerHTML:'',textContent:'',disabled:false,hidden:false,insertAdjacentHTML(where,html){this.innerHTML+=html;},focus(){this.focused=true;}};
 const fields=nodes['wifi-form'].elements={ssid:{value:''},security:{value:'wpa-psk'},password:{value:'',focus(){this.focused=true;}},hidden:{checked:false}};
 nodes['wifi-form'].reportValidity=()=>!!fields.ssid.value&&(fields.security.value==='open'||fields.password.value.length>=8);
 nodes['wifi-form'].reset=()=>{fields.ssid.value='';fields.security.value='wpa-psk';fields.password.value='';fields.hidden.checked=false;};
 let response={networks:[]},hold=null,fail=false,consent=true;
 const c={$:id=>nodes[id],busy:false,formDirty:false,basicNetworkPage:async()=>{},panel:(t,b)=>'<h2>'+t+'</h2>'+b,
  esc:x=>String(x).replace(/[&<>"']/g,v=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[v])),
  confirm:text=>{confirmations.push(text);return consent;},
  api:async(url,data)=>{requests.push({url,data:JSON.parse(JSON.stringify(data))});if(hold)await hold;if(fail)throw Error('Synthetic backend unavailable');return response;}
 };
 vm.createContext(c);vm.runInContext(block,c);
 return {c,nodes,fields,requests,confirmations,setResponse:r=>response=r,setFail:x=>fail=x,setConsent:x=>consent=x,
  hold(){hold=new Promise(r=>this.release=()=>{hold=null;r();});},
  click(index){nodes['wifi-results'].onclick({target:{closest:()=>({dataset:{wifiIndex:String(index)}})}});},
  submit(){nodes['wifi-form'].onsubmit({preventDefault(){}});}
 };
}
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const f=fixture();await f.c.networkPage();
 assert(!f.nodes['wifi-connect'].hidden);assert.match(f.nodes.content.innerHTML,/>Connect<\/button>/);
 const evil='<script>synthetic & "ssid"</script>';
 f.setResponse({networks:[
  {ssid:evil,signal:'90',security:'WPA2',security_mode:'wpa-psk'},
  {ssid:evil,signal:'30',security:'WPA2',security_mode:'wpa-psk'},
  {ssid:'SyntheticOpen',signal:'80',security:'--',security_mode:'open'},
  {ssid:'SyntheticEnterprise',signal:'70',security:'WPA2 802.1X',security_mode:null},
  {ssid:'SyntheticWEP',signal:'60',security:'WEP',security_mode:null},
  {ssid:'SyntheticSAE',signal:'50',security:'WPA3',security_mode:null},
  {ssid:evil,signal:'40',security:'--',security_mode:'open'}
 ]});
 await f.nodes['wifi-scan'].onclick();
 assert.equal(f.requests.length,1);assert.equal(f.requests[0].data.action,'wifi-scan');
 assert(!f.nodes['wifi-results'].innerHTML.includes('<script>'));assert.match(f.nodes['wifi-results'].innerHTML,/2 access points/);
 f.click(0);assert.equal(f.fields.ssid.value,evil);assert.equal(f.requests.length,1);assert(f.fields.password.focused);
 f.fields.password.value='synthetic-secret';f.setConsent(false);f.submit();assert.equal(f.requests.length,1);assert.equal(f.fields.password.value,'');
 f.setConsent(true);f.fields.password.value='synthetic-secret';f.setResponse({message:'Connection scheduled; not confirmed.'});f.hold();
 f.submit();f.submit();f.click(1);await flush();
 assert.equal(f.requests.length,2,'repeated Connect/selection while pending cannot duplicate writes');
 assert.equal(f.requests[1].data.connect,true);assert.equal(f.requests[1].data.security,'wpa-psk');assert.equal(f.fields.password.value,'');
 assert(f.nodes['wifi-connect'].disabled);f.release();await flush();
 assert.match(f.nodes['wifi-message'].textContent,/scheduled/);assert(f.nodes['wifi-connect'].disabled);const afterSchedule=f.requests.length;f.submit();await flush();assert.equal(f.requests.length,afterSchedule,'scheduled connection cannot be submitted twice without changing selection');
 f.click(1);assert.equal(f.fields.security.value,'open');assert(f.fields.password.disabled);assert(f.nodes['wifi-password-label'].hidden);
 f.submit();await flush();assert.equal(f.requests.at(-1).data.password,'');assert.match(f.confirmations.at(-1),/unencrypted/);
 for(const i of [2,3,4]){f.click(i);assert(f.nodes['wifi-connect'].disabled);const n=f.requests.length;f.fields.password.value='synthetic-secret';f.submit();await flush();assert.equal(f.requests.length,n);}
 // Manual hidden entry remains available, with explicit security choice.
 f.fields.ssid.value='SyntheticHidden';f.fields.ssid.oninput();f.fields.security.value='wpa-psk';f.fields.security.onchange();
 f.fields.hidden.checked=true;f.fields.password.value='another-secret';f.nodes['wifi-save-only'].onclick();await flush();
 assert.equal(f.requests.at(-1).data.hidden,true);assert.equal(f.requests.at(-1).data.connect,false);
 f.fields.password.value='cancel-secret';f.nodes['wifi-cancel'].onclick();assert.equal(f.fields.password.value,'');assert.equal(f.fields.ssid.value,'');assert.match(f.nodes['wifi-message'].textContent,/were not undone/);assert.equal(f.nodes['wifi-cancel'].textContent,'Clear form');
 f.fields.ssid.value='SyntheticFailure';f.fields.password.value='failure-secret';f.setFail(true);const n=f.requests.length;f.submit();await flush();
 assert.equal(f.requests.length,n+1);assert.match(f.nodes['wifi-message'].textContent,/No automatic retry/);assert.equal(f.fields.password.value,'');
 assert(!f.nodes['wifi-connect'].disabled);await flush();assert.equal(f.requests.length,n+1);
 f.setFail(true);f.fields.ssid.value='PreservedSynthetic';f.fields.password.value='preserved-secret';await f.nodes['wifi-scan'].onclick();assert.equal(f.fields.ssid.value,'PreservedSynthetic');assert.equal(f.fields.password.value,'preserved-secret');assert.match(f.nodes['wifi-scan-status'].textContent,/Scan failed/);
 assert.equal(f.c.wifiSecurity({security:'WPA2 802.1X',security_mode:'wpa-psk'}),null);
 assert.equal(f.c.wifiSecurity({security:'WEP',security_mode:'open'}),null);
 assert.equal(f.c.wifiSecurity({security:'WPA3',security_mode:'wpa-psk'}),null);
 assert.equal(f.c.wifiSecurity({security:'WPA2 WPA3',security_mode:'wpa-psk'}),'wpa-psk');
 assert(!block.includes('localStorage'));assert(!block.includes('sessionStorage'));
 console.log('PASS actual Wi-Fi handlers: scan/select/password/explicit Connect, cancellation, open/unsupported security, escaping, duplicates, hidden/manual, single-flight, error cleanup and no browser credential storage');
})().catch(e=>{console.error(e);process.exit(1)});
