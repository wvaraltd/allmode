'use strict';
const $=id=>document.getElementById(id);let active=false,busy=false;
function render(s){active=!!s.active;$('mode').disabled=busy||active;$('status').textContent=s.phase+' — '+s.audio+' — '+s.codec+(s.tx_observed?' - TX activity observed':'');$('error').textContent=s.note||'';$('arm').disabled=busy||active||!$('ready').checked;}
async function call(action,data){const r=await fetch('/api/radio-parrot/'+action,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(r.status===401)throw Error('Session expired. Sign in again; the radio test heartbeat will expire.');const s=await r.json();if(!r.ok)throw Error(s.error||'Request failed');render(s);}
$('ready').onchange=()=>{$('arm').disabled=busy||active||!$('ready').checked;};
$('arm').onclick=async()=>{if(busy||active||!$('ready').checked)return;busy=true;$('arm').disabled=true;try{await call('arm',{confirm:'RADIO READY',mode:$('mode').value});}catch(e){$('error').textContent=e.message;}finally{busy=false;$('arm').disabled=active||!$('ready').checked;}};
$('stop').onclick=async()=>{try{await call('stop',{});}catch(e){$('error').textContent=e.message;}};
setInterval(()=>{if(!busy)call(active?'heartbeat':'state',active?{}:undefined).catch(e=>{$('error').textContent=e.message;});},1000);
addEventListener('pagehide',()=>{if(active)fetch('/api/radio-parrot/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{});});
call('state').catch(e=>{$('error').textContent=e.message;});
