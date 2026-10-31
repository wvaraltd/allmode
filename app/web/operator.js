'use strict';
const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let bridgeConsent=false;
let station={}, schema={}, runtime={}, busy=false, wizard=0, favorites=[];
const path=location.pathname;
const labels={station:'Station identity',allstar:'AllStar',echolink:'EchoLink',dmr:'DMR identity',brandmeister:'BrandMeister',tgif:'TGIF',dstar:'Digital codec',other:'Digital IDs',audio:'Audio levels',review:'Review & apply'};
const wizardSteps=['welcome','password','station','allstar','echolink','dmr','brandmeister','tgif','dstar','radio','review','audio','finish'];
try{document.documentElement.dataset.theme=localStorage.getItem('ara.theme')||localStorage.getItem('allmode.theme')||'night';favorites=JSON.parse(localStorage.getItem('ara.favorites')||'[]');if(!Array.isArray(favorites))favorites=[];}catch{}
$('theme').onclick=()=>{const t=document.documentElement.dataset.theme==='day'?'night':'day';document.documentElement.dataset.theme=t;try{localStorage.setItem('ara.theme',t);localStorage.setItem('allmode.theme',t);}catch{}};
for(const a of document.querySelectorAll('#navigation a'))if(a.pathname===path)a.setAttribute('aria-current','page');
async function api(url,data){const r=await fetch(url,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});if(r.status===401){location.href='/login';throw Error('Sign in required.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed.');if(url==='/api/command'&&data?.action==='connect-network')rememberDestination(data);return d;}
function message(text){$('feedback').hidden=!text;$('feedback').textContent=text;}
async function action(fn){if(busy)return;busy=true;try{await fn();}catch(e){message(e.message);}finally{busy=false;}}
function panel(title,body){return `<section class="panel"><h2>${title}</h2>${body}</section>`;}
function value(g,k){return schema.groups?.find(x=>x.id===g)?.fields.find(x=>x.key===k)?.value;}
function groupForm(g){const group=schema.groups?.find(x=>x.id===g);if(!group)return '<p>Settings unavailable.</p>';return `<form id="group-form" data-group="${g}"><div class="fields">${group.fields.filter(f=>!(g==='dstar'&&path==='/settings'&&f.key==='enabled')).map(f=>{let val=f.value;if(g==='echolink'&&!val&&['name','location','email'].includes(f.key))val=value('station',f.key);return `<label class="${f.type==='checkbox'?'check':''}">${f.type==='checkbox'?`<input type="checkbox" name="${f.key}" ${val?'checked':''}>`:''}${esc(f.label)}${f.type!=='checkbox'?`<input name="${f.key}" type="${f.type}" value="${esc(val)}" ${f.type==='password'?'autocomplete="new-password"':''} ${f.saved?'placeholder="Saved — leave blank to keep"':''} ${f.type==='number'?`min="${g==='dstar'||f.key.endsWith('_port')?1:0}" max="${g==='dstar'||f.key.endsWith('_port')?65535:f.key==='ysf_dgid'?99:f.key==='nxdn_ran'?63:15}"`:''}>`:''}</label>`;}).join('')}</div><p class="hint">Passwords stay hidden. Leave a saved password blank to keep it.</p><div class="actions"><button>Save${path==='/setup'?' & continue':''}</button>${path==='/settings'?'<button type="submit" name="review" value="yes">Save & review changes →</button>':''}<button type="button" id="cancel" class="secondary">Cancel edits</button></div></form>`;}
function bindGroup(g){prefillDirectorySetup(g);$('group-form').onsubmit=e=>{e.preventDefault();const review=e.submitter?.name==='review';action(async()=>{const fields=schema.groups.find(x=>x.id===g).fields,values={};for(const f of fields){const el=e.target.elements.namedItem(f.key);values[f.key]=!el?f.value:f.type==='checkbox'?el.checked:f.type==='number'?Number(el.value):el.value;}await api('/api/settings',{group:g,values});await loadSchema();message(schema.workflow?.applied?'Saved settings are already applied.':'Saved. Use Review & apply changes to activate these settings.');if(path==='/setup'){wizard++;renderWizard();}else if(review){location.hash='review';renderSettings();}else renderSettings();});};$('cancel').onclick=()=>{if(busy)return;formDirty=false;path==='/setup'?renderWizard():renderSettings();};}
async function loadSchema(){schema=await api('/api/onboarding');runtime=schema.workflow?.runtime||{};$('setup-link').hidden=!!schema.complete;updateApplyNotice();}
function health(){const simulation=station.simulation;$('live').textContent=simulation?'PREVIEW · NO RF':runtime.available?'LIVE STATUS':'SERVICE UNAVAILABLE';$('health').innerHTML=[['Node '+(runtime.node||'not configured'),!!runtime.node],['AllStar '+(runtime.registered?'registered':'offline'),runtime.registered],['Radio '+(runtime.radio_enabled?'enabled':'stopped'),runtime.radio_enabled]].map(([t,on])=>`<span class="${on?'good':''}">${esc(t)}</span>`).join('');}
function eventRows(events){return events.length?events.map(e=>`<tr><td>${esc(new Date(e.time).toLocaleTimeString())}</td><td>${esc(e.message)}</td></tr>`).join(''):'<tr><td colspan="2" class="empty">No activity recorded.</td></tr>';}
function updateDashboard(markup){
 const marker='<div id="dashboard-audio-meters"></div>';
 const [summary,details]=markup.split(marker);
 if(details===undefined)throw Error('Dashboard meter region missing');
 if(!$('dashboard-summary')||!$('dashboard-details')){
  $('content').innerHTML='<div id="dashboard-summary"></div>'+marker+'<div id="dashboard-details"></div>';
 }
 // Keep the live audio subtree connected across status polls and directory updates.
 const top=$('dashboard-summary'),bottom=$('dashboard-details');
 if(top.innerHTML!==summary)top.innerHTML=summary;
 if(bottom.innerHTML!==details)bottom.innerHTML=details;
}
function cpuHealthTile(h){
 const temperature=Number.isFinite(h.cpu_celsius)?(h.cpu_celsius*9/5+32).toFixed(1)+' °F':'Unavailable';
 const usage=Number.isFinite(h.cpu_usage_percent)?h.cpu_usage_percent.toFixed(1)+'%':'Unavailable';
 return `<div class="metric"><small>CPU TEMPERATURE</small><strong>${esc(temperature)}</strong><p class="hint">CPU usage: ${esc(usage)}</p><p class="hint">${esc(h.kernel||'System status unavailable')}</p></div>`;
}
function dashboard(){const radio=schema.workflow?.radio,h=runtime.health||{};updateDashboard(`${!schema.complete?'<div class="setup-note">Station commissioning is incomplete. <a href="/setup">Continue setup →</a></div>':''}<section class="banner"><span class="indicator ${station.receiving?'on':''}">${station.receiving?'RX ACTIVE':'RX IDLE'}</span><div><p class="eyebrow">${station.pending?'CONNECTION IN PROGRESS':'ON YOUR STATION'}</p><strong>${esc(station.connected?station.mode+' · '+connectionLabel(station):'Ready when you are')}</strong><p>${station.connected?'Connected destination':'No active network connection'}</p></div><a class="tag" href="/connections">Open connections →</a></section>${panel(station.connected?'Connected':'Quick Connect',station.connected?'<button id="home-disconnect" class="danger">Disconnect</button>':quickConnectMarkup())}<div class="metric-grid">${rssiCard()}<div class="metric"><small>RADIO FREQUENCY</small><strong>${esc(radio?.rx||'Not programmed')}</strong><p class="hint">${radio?'MHz · last acknowledged write':'Configure in Radio settings'}</p></div><div class="metric"><small>RECEIVE / TRANSMIT TONE</small><strong>${esc(radio?radio.rx_ctcss+' / '+radio.tx_ctcss:'—')}</strong><p class="hint">Hz · not RF readback</p></div>${cpuHealthTile(h)}<div class="metric"><small>STORAGE AVAILABLE</small><strong>${h.storage_free_gb==null?'—':esc(h.storage_free_gb)+' GB'}</strong><p class="hint">${h.storage_used_percent==null?'':esc(h.storage_used_percent)+'% used'}</p></div></div><div id="dashboard-audio-meters"></div><div class="dashboard-grid"><div>${panel('Connected destination',station.connected?`<table><thead><tr><th>NETWORK</th><th>DESTINATION</th></tr></thead><tbody><tr><td>${esc(station.mode)}</td><td>${esc(connectionLabel(station))}</td></tr></tbody></table><div class="actions"><button id="dash-disconnect" class="danger">Disconnect</button></div>`:'<p>No active connection.</p><a href="/connections">All destinations →</a>')}${panel('Station readiness',`<p>${runtime.audio_verified?'Operator audio check recorded.':'Receive and transmit audio have not been verified.'}</p><a href="/settings#audio">Audio levels</a> · <a href="/settings#review">Configuration status</a>`)}</div>${panel('Recent activity',`<table><thead><tr><th>TIME</th><th>EVENT</th></tr></thead><tbody>${eventRows((station.events||[]).slice(0,10))}</tbody></table><p class="hint">Controller events. Per-callsign last-heard data is not available from this adapter yet.</p>`)}</div>`);bindQuickConnect();if($('home-disconnect'))$('home-disconnect').onclick=()=>command('disconnect');if($('dash-disconnect'))$('dash-disconnect').onclick=()=>command('disconnect');if($('rssi-toggle'))$('rssi-toggle').onclick=()=>action(async()=>{await api('/api/hardware',{action:'rssi',paused:!station.rssi?.paused});station=await api('/api/status');dashboard();});}
async function command(actionName,value){await action(async()=>{station=await api('/api/command',{action:actionName,value});message('Request accepted. Status will update when confirmed.');renderPage();});}
function connections(){const modes=[...new Set([...(station.modes||[]),...Object.keys(station.unavailable_modes||{})])];$('content').innerHTML=panel('Your favorites',`<div id="favorites">${favorites.length?favorites.map((f,i)=>`<div class="favorite"><div class="favorite-info"><b>${esc(f.target)}</b> <small>${esc(f.mode)}</small><p class="favorite-note" data-note-text="${i}" ${f.note?'':'hidden'}>${esc(f.note||'')}</p><details class="note-editor"><summary>${f.note?'Edit note':'Add note'}</summary><form data-note="${i}"><label>Note for ${esc(f.target)}<textarea name="note" maxlength="500" rows="3" placeholder="Name, net schedule, or anything you want to remember">${esc(f.note||'')}</textarea></label><div class="actions"><button type="submit">Save note</button><button type="button" data-note-cancel="${i}" class="secondary">Cancel</button></div></form></details></div><button class="secondary" data-favorite="${i}">Select</button><button class="secondary" data-remove="${i}" aria-label="Remove favorite">×</button></div>`).join(''):'<p class="empty">Save a destination below for quick access.</p>'}</div>`)+`<div class="grid">`+modes.map(mode=>{const unavailable=connectionUnavailable(mode);const connected=station.connected&&station.mode===mode;return `<section class="panel network-card"><h2>${esc(mode)} ${connected?'<span class="tag">CONNECTED</span>':''}</h2><p class="hint">${esc(unavailable||(['AllStar','EchoLink'].includes(mode)?'Connect by node number.':'Choose a talkgroup or reflector.'))}</p><form data-connect="${esc(mode)}">${mode==='DMR'?`<label>DMR network<select name="network"><option value="BrandMeister" ${station.dmr_network==='BrandMeister'?'selected':''}>BrandMeister</option><option value="TGIF" ${station.dmr_network==='TGIF'?'selected':''}>TGIF</option></select></label><p class="hint">Choose TGIF or BrandMeister, then enter the talkgroup number. One DMR network at a time.</p>`:''}<label>${['AllStar','EchoLink'].includes(mode)?'Node number':'Talkgroup / reflector'}<input name="target" required maxlength="48" placeholder="${mode==='D-STAR'?'REF030C':'Enter destination'}" ${unavailable?'disabled':''}></label><div class="actions"><button ${unavailable||station.pending||station.readonly?'disabled':''}>Connect</button><button type="button" data-save="${esc(mode)}" class="secondary">☆ Save</button>${connected?'<button type="button" data-disconnect class="danger">Disconnect</button>':''}</div></form></section>`;}).join('')+'</div>'+panel('Connections & bridging',`<label class="check"><input id="allow-bridge" type="checkbox" ${bridgeConsent?'checked':''}>Allow multiple connections / bridging</label><p><strong>Warning:</strong> When checked, Connect keeps existing links and allows audio to pass between connected nodes, digital systems, and your radio. Make sure each network permits bridging; avoid loops and echo-test destinations.</p><p>Unchecked: Connect disconnects existing links before connecting the new destination. Unchecking alone does not end an active bridge; use Disconnect to end all links. Multiple AllStar/EchoLink nodes are supported; digital modes allow one destination per mode.</p>`);
$('allow-bridge').onchange=e=>{bridgeConsent=e.target.checked;refreshConnectionStatus();};document.querySelectorAll('[data-connect]').forEach(form=>{
 form.addEventListener('input',()=>{delete form.dataset.connectError;refreshConnectionStatus();});
 form.onsubmit=e=>{e.preventDefault();action(async()=>{
  const mode=form.dataset.connect,id=form.elements.source_id;
  if(connectionUnavailable(mode)||station.pending||station.readonly)return message(connectionUnavailable(mode)||'Connection controls are unavailable.');
  delete form.dataset.connectError;
  try{
   message(bridgeConsent?'Adding destination to bridge…':'Switching destination: disconnecting any current link, then connecting…');
   station=await api('/api/command',{action:'connect-network',mode,value:form.elements.target.value.trim(),source_id:id?.value.trim()||undefined,allow_bridge:bridgeConsent,...(mode==='DMR'?{network:form.elements.network.value}:{})});
   message('Connection requested.');renderPage();
  }catch(error){form.dataset.connectError=error.message;message(error.message);refreshConnectionStatus();}
 });};
});document.querySelectorAll('[data-save]').forEach(b=>b.onclick=()=>{const target=b.closest('form').elements.target.value.trim();if(!target)return message('Enter a destination first.');if(favorites.length>=20)return message('Maximum 20 favorites.');if(!favorites.some(f=>f.mode===b.dataset.save&&f.target===target&&(f.mode!=='DMR'||f.network===b.closest('form').elements.network.value)))favorites.push({mode:b.dataset.save,target,...(b.dataset.save==='DMR'?{network:b.closest('form').elements.network.value}:{})});localStorage.setItem('ara.favorites',JSON.stringify(favorites));connections();});document.querySelectorAll('[data-disconnect]').forEach(b=>b.onclick=()=>command('disconnect'));document.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{favorites.splice(Number(b.dataset.remove),1);localStorage.setItem('ara.favorites',JSON.stringify(favorites));connections();});document.querySelectorAll('[data-favorite]').forEach(b=>b.onclick=()=>{const f=favorites[Number(b.dataset.favorite)];const form=[...document.querySelectorAll('[data-connect]')].find(el=>el.dataset.connect===f.mode);if(form){form.elements.target.value=f.target;if(f.mode==='DMR'&&f.network)form.elements.network.value=f.network;form.elements.target.focus();}});}
function settingsTabs(){return '<nav class="section-tabs" aria-label="Settings sections">'+Object.entries(labels).filter(([g])=>!['allstar','echolink','dmr','brandmeister','tgif'].includes(g)).map(([g,label])=>`<a class="${(location.hash.slice(1)||'station')===g?'active':''}" href="/settings#${g}">${label}</a>`).join('')+'<a href="/hardware">Radio</a></nav>';}
function renderSettings(){const g=location.hash.slice(1)||'station';if(['allstar','echolink','dmr','brandmeister','tgif'].includes(g)){history.replaceState(null,'','#other');return digitalIdsPage(g);}$('content').innerHTML=settingsTabs();if(g==='other')return digitalIdsPage();if(g==='dstar')return codecSettingsPage();if(g==='audio')return audioPage(false);if(g==='review')return reviewPage(false);$('content').innerHTML+=panel(esc(labels[g]||'Settings'),groupForm(g));if($('group-form'))bindGroup(g);if(g==='dstar'){$('content').insertAdjacentHTML('beforeend',panel('AMBE server check','<p>Save and apply the server settings, then test its AMBE3000 UDP connection and codec response. No RF transmission is sent.</p><button id="settings-test-ambe">Test AMBE server</button><p id="ambe-feedback" role="status"></p>'));$('settings-test-ambe').disabled=!value('dstar','enabled');$('settings-test-ambe').onclick=()=>systemAction('test-ambe');}}
async function systemAction(name,extra={}){await action(async()=>{
 const show=text=>{message(text);if($('audio-feedback'))$('audio-feedback').textContent=text;if($('ambe-feedback'))$('ambe-feedback').textContent=text;};
 show('Working on the station…');
 try{const r=await api('/api/system',{action:name,...extra});await loadSchema();renderPage();
 show(name==='audio-confirm'?'Audio check recorded. You can now finish setup.':r.message||'Operation complete.');
 }catch(e){show(e.message);}
});}
function reviewPage(wiz){const body=`<p><a href="/audio-tools">Audio &amp; codec</a> — requested: ${esc(runtime.codec?.requested||'unknown')}; active: ${esc(runtime.codec?.active||'none')}; ${runtime.codec?.queued?'switch queued':'no queued switch'}. ${esc(runtime.codec?.note||'')}</p><table><tbody>${schema.groups.filter(g=>['station','allstar','echolink','brandmeister','tgif','dstar'].includes(g.id)).map(g=>`<tr><td>${esc(labels[g.id])}</td><td>${esc(g.id==='station'?value('station','callsign')||'Not saved':g.id==='dstar'?(value('dstar','enabled')?'External hardware selected; software excluded':'Software selected (default)'):value(g.id,'enabled')?'Enabled':'Off')}</td></tr>`).join('')}</tbody></table><p class="hint">${schema.workflow?.applied?'Saved configuration matches the applied configuration.':'Saved changes need applying.'} Applying briefly restarts a running radio and checks its USB device. A stopped radio stays stopped. It does not program the SA818.</p>${wiz?'':'<button id="apply-config">Apply saved settings</button>'}<details open><summary>Readiness checks</summary><ul>${(schema.workflow?.blockers||[]).map(b=>`<li>${esc(b)}</li>`).join('')}</ul></details>`;$('content').innerHTML+=panel('Review & apply',body);if(wiz)wizardNav(applyWizardNext);else $('apply-config').onclick=()=>systemAction('apply');}
function bindLiveAudio(){
 const form=$('audio-form'),note=$('audio-live-result');let timer=null,sending=false,pending=null;
 async function send(){
  if(sending||!pending)return;
  const levels=pending;pending=null;sending=true;note.textContent='Applying to radio…';
  try{const result=await api('/api/system',{action:'audio',levels});runtime.levels=result.levels;note.textContent=result.message;if(!pending)formDirty=false;}
  catch(e){note.textContent='Not applied: '+e.message;}
  finally{sending=false;if(pending)send();}
 }
 function queue(){pending=Object.fromEntries(['rx','txa','txb'].map(k=>[k,Number($('level-'+k).value)]));clearTimeout(timer);timer=setTimeout(send,200);}
 for(const k of ['rx','txa','txb'])$('level-'+k).oninput=e=>{$('out-'+k).value=e.target.value;queue();};
 form.onsubmit=e=>{e.preventDefault();queue();clearTimeout(timer);send();};
}
function audioPage(wiz){const levels=runtime.levels||{rx:650,txa:600,txb:500};$('content').innerHTML+=panel('Audio levels',`<form id="audio-form">${[['rx','Receive · radio to network'],['txa','Transmit A · network to radio'],['txb','Transmit B']].map(([key,label])=>`<label class="slider-label" for="level-${key}">${label}<output id="out-${key}">${levels[key]}</output></label><input id="level-${key}" name="${key}" type="range" min="0" max="999" value="${levels[key]}"><br>`).join('')}<p class="hint">Adjust while listening. Levels update live and save automatically; no restart.</p><button ${!runtime.radio_enabled?'disabled':''}>Save audio levels</button><p id="audio-live-result" role="status"></p></form>${wiz?`<details ${wiz?'open':''}><summary>Radio activation & audio check</summary><p>${runtime.radio_enabled?'Radio is running. Start radio is disabled because it is already on.':'Start the radio after confirming the RF setup below.'}</p><p class="hint">This optional test can be skipped for now without starting the radio. This is a manual listening check with another radio. This page does not play an automatic test tone. After checking audio in both directions, record your result below.</p><label class="check"><input id="rf-check" type="checkbox">Correct frequencies and RF load are ready; PTT is secured.</label><button id="activate-radio" ${!schema.workflow?.radio||!schema.workflow?.applied||runtime.radio_enabled?'disabled':''}>Start radio</button><label class="check"><input id="audio-check" type="checkbox" ${runtime.audio_verified?'checked':''}>I have checked receive and transmit audio with another radio.</label><button id="confirm-audio" ${!runtime.radio_enabled||runtime.audio_verified?'disabled':''}>${runtime.audio_verified?'Audio check recorded':'Record audio check'}</button><p id="audio-feedback" role="status" aria-live="polite">${runtime.audio_verified?'Your audio check is saved. Continue to finish setup.':schema.workflow?.audio_status==='skipped'?'Audio test skipped for now; audio remains unverified.':'Audio check not recorded yet.'}</p><button id="audio-skip" class="secondary">Skip for now</button><button id="audio-finish" class="secondary" ${!runtime.audio_verified?'hidden':''}>Continue to finish setup</button></details>`:''}`);bindLiveAudio();if(wiz){$('activate-radio').onclick=()=>{if(!$('rf-check').checked)return message('Confirm the radio and RF load are ready.');systemAction('activate',{confirm:'ACTIVATE'});};$('confirm-audio').onclick=()=>{if(!$('audio-check').checked){$('audio-feedback').textContent='Check receive and transmit audio, then tick the confirmation box before recording.';return;}systemAction('audio-confirm',{checked:true});};$('audio-skip').onclick=()=>action(async()=>{await api('/api/onboarding',{action:'skip-audio'});await loadSchema();wizard=wizardSteps.indexOf('finish');formDirty=false;renderWizard();});$('audio-finish').onclick=()=>{wizard=wizardSteps.indexOf('finish');formDirty=false;renderWizard();};wizardNav(()=>{if(busy)return;if(!runtime.audio_verified)return $('audio-skip').click();wizard=wizardSteps.indexOf('finish');renderWizard();});$('wizard-next').textContent=runtime.audio_verified?'Continue':'Skip for now';}else $('content').insertAdjacentHTML('beforeend','<p class="hint">Audio test status: '+esc(schema.workflow?.audio_status||'untested')+'. <a href="/setup?rerun=1&step=audio">Open optional audio check</a></p><div id="handheld-audio-test"></div>');}
async function applyWizardNext(){
 await action(async()=>{
  const next=$('wizard-next'),back=$('wizard-back');
  next.disabled=true;back.disabled=true;next.textContent='Applying…';
  message('Applying saved settings…');
  try{
   await api('/api/system',{action:'apply'});
   await loadSchema();
   if(!schema.workflow?.applied)throw Error('Settings were not confirmed as applied. Please review and try again.');
   wizard=Math.min(wizardSteps.length-1,wizard+1);
   renderWizard();message('Settings applied.');
  }finally{
   next.disabled=false;back.disabled=false;next.textContent='Next';
  }
 });
}
function wizardNav(onNext){const div=document.createElement('div');div.className='actions';div.innerHTML='<button id="wizard-back" class="secondary">Back</button><button id="wizard-next">Next</button>';$('content').append(div);$('wizard-back').onclick=()=>{if(busy)return;wizard=Math.max(0,wizard-1);renderWizard();};$('wizard-next').onclick=onNext||(()=>{if(busy)return;wizard=Math.min(wizardSteps.length-1,wizard+1);renderWizard();});}
function passwordPage(wiz){$('content').innerHTML+=panel('Web password',`<p class="hint">Choose the password that protects this station.</p><form id="password-form"><div class="fields"><label>Current password<input type="password" name="current" autocomplete="current-password" required></label><label>New password<input type="password" name="password" autocomplete="new-password" minlength="4" maxlength="128" required></label><label>Repeat new password<input type="password" name="repeat" autocomplete="new-password" required></label></div><button>Set password</button></form>`);$('password-form').onsubmit=e=>{e.preventDefault();const f=e.target.elements;if(f.password.value!==f.repeat.value)return message('Passwords do not match.');action(async()=>{await api('/api/password',{current:f.current.value,password:f.password.value});location.href='/login';});};if(wiz)wizardNav();}
function renderWizard(){if(['review','audio','finish'].includes(wizardSteps[wizard])&&!schema.workflow?.radio)wizard=wizardSteps.indexOf('radio');const step=wizardSteps[wizard];$('content').className='wizard';$('content').innerHTML='<div class="wizard-progress">'+wizardSteps.map((_,i)=>`<i class="${i<=wizard?'done':''}"></i>`).join('')+'</div>';$('title').textContent='Welcome to ARA AllMode';if(step==='welcome'){$('content').innerHTML+=panel('Your station starts here',`<p>We’ll set up your identity, the networks you use, and your radio. Optional networks can stay off. You can change everything later in Settings.</p><p class="hint">No radio transmission starts automatically.</p>`);wizardNav();$('wizard-back').disabled=true;return;}if(step==='password')return passwordPage(true);if(step==='review')return reviewPage(true);if(step==='audio')return audioPage(true);if(step==='radio')return radioWizardPage();if(step==='finish')return finishPage();$('content').innerHTML+=panel(esc(labels[step]),groupForm(step));bindGroup(step);const back=document.createElement('button');back.type='button';back.className='secondary';back.textContent='Back';back.onclick=()=>{if(busy)return;formDirty=false;wizard=Math.max(0,wizard-1);renderWizard();};$('group-form').querySelector('.actions').append(back);if(['echolink','dmr','brandmeister','tgif','dstar'].includes(step)){const skip=document.createElement('button');skip.type='button';skip.className='secondary';skip.textContent='Skip for now';skip.onclick=()=>{if(busy)return;formDirty=false;wizard++;renderWizard();};$('group-form').querySelector('.actions').append(skip);}if(step==='dstar'){$('content').insertAdjacentHTML('beforeend','<p class="hint">Software D-STAR is the default. Select external AMBE only to use that hardware exclusively. Saving this choice does not switch a running worker; disconnect before applying. View installed codec support on the Audio & codec page.</p><button id="test-ambe" class="secondary">Test saved server</button>');$('test-ambe').disabled=!value('dstar','enabled');$('test-ambe').onclick=()=>systemAction('test-ambe');}}
async function profilesPage(){$('content').innerHTML=panel('Station profiles','<p>Save the current station accounts and radio draft as a named profile. Recall restores saved settings; applying services and programming RF remain explicit actions.</p><form id="profile-save" class="row"><input name="name" placeholder="Profile name" maxlength="48" required><button>Save profile</button></form><div id="profile-list">Loading…</div><p class="hint">Profiles contain credentials and stay private on this station. A backup is saved before recall.</p>');const d=await api('/api/profiles');$('profile-list').innerHTML=d.profiles.map(p=>`<div class="favorite"><span>${esc(p.name)}</span><button class="secondary" data-recall="${esc(p.name)}">Recall</button></div>`).join('')||'<p class="empty">No profiles yet.</p>';$('profile-save').onsubmit=e=>{e.preventDefault();action(async()=>{await api('/api/profiles',{action:'save',name:e.target.elements.name.value});await profilesPage();message('Profile saved privately.');});};document.querySelectorAll('[data-recall]').forEach(b=>b.onclick=()=>{if(!confirm('Recall '+b.dataset.recall+' into saved settings? Current settings will be backed up. Services and radio will not change yet.'))return;action(async()=>{const d=await api('/api/profiles',{action:'restore',name:b.dataset.recall});await loadSchema();message(d.message);});});}
function logsPage(){$('content').innerHTML=panel('Controller log','<div class="row"><button id="log-refresh" class="secondary">Refresh</button><button id="log-download" class="secondary">Download</button><label class="check"><input id="log-auto" type="checkbox">Auto-refresh</label></div><pre id="log-text"></pre>');const text=()=>(station.events||[]).map(e=>e.time+'  '+e.message).join('\n')||'No controller events.';const update=()=>{$('log-text').textContent=text();};update();$('log-refresh').onclick=()=>action(async()=>{station=await api('/api/status');update();});$('log-download').onclick=()=>{const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text()],{type:'text/plain'}));a.href=url;a.download='ara-allmode-controller.log';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};}
async function networkPage(){$('content').innerHTML=panel('Ethernet & Wi-Fi','<p id="network-info">Loading interfaces…</p>');try{const d=await api('/api/network');$('network-info').outerHTML='<pre>'+esc(d.output)+'</pre><p class="hint">Current interface addresses, routes and DNS servers. Save Wi-Fi below, then connect when ready.</p>';}catch(e){$('network-info').textContent=e.message;}}
function adminPage(){passwordPage(false);$('content').innerHTML+=panel('Radio services',`<p>${runtime.active?'Asterisk is running.':'Asterisk is stopped.'}</p><button id="stop-radio" class="danger">Stop radio services</button><p><a href="/settings#audio">Start radio with readiness check →</a></p><a href="/setup?rerun=1">Run guided setup again</a>`);$('stop-radio').onclick=()=>systemAction('maintenance');}
function renderPage(){$('content').className='';const titles={'/':'Dashboard','/connections':'Connections','/settings':'Settings','/setup':'Guided setup','/profiles':'Profiles & backups','/network':'Network','/logs':'Logs','/admin':'Admin'};$('title').textContent=titles[path]||'Dashboard';health();switch(path){case '/connections':connections();break;case '/settings':renderSettings();break;case '/setup':renderWizard();break;case '/profiles':profilesPage().catch(e=>message(e.message));break;case '/logs':logsPage();break;case '/network':networkPage();break;case '/admin':$('content').innerHTML='';adminPage();break;default:dashboard();}}
addEventListener('hashchange',()=>{if(path==='/settings')renderSettings();});
async function start(){try{await loadSchema();station=await api('/api/status');if(path==='/setup'&&schema.complete&&!location.search.includes('rerun')){location.replace('/');return;}renderPage();}catch(e){message(e.message);}}
start();setInterval(async()=>{if(busy)return;try{station=await api('/api/status');runtime=await api('/api/system');health();if(path==='/')dashboard();if(path==='/connections')refreshConnectionStatus();if(path==='/logs'&&$('log-auto')?.checked)$('log-text').textContent=(station.events||[]).map(e=>e.time+'  '+e.message).join('\n');}catch{}},5000);
// Resume setup after radio configuration or signing in again.
const savedWizard=Number(sessionStorage.getItem('ara.setupStep'));
if(Number.isInteger(savedWizard)&&savedWizard>=0&&savedWizard<wizardSteps.length)wizard=savedWizard;
const savedStepName=sessionStorage.getItem('ara.setupStepName');
if(wizardSteps.includes(savedStepName))wizard=wizardSteps.indexOf(savedStepName);
const requestedSetupStep=new URLSearchParams(location.search).get('step');
if(['radio','audio'].includes(requestedSetupStep))wizard=wizardSteps.indexOf(requestedSetupStep);
const originalWizard=renderWizard;
renderWizard=function(){originalWizard();sessionStorage.setItem('ara.setupStep',String(wizard));sessionStorage.setItem('ara.setupStepName',wizardSteps[wizard]);if(wizardSteps[wizard]==='password'&&sessionStorage.getItem('ara.justClaimed')){wizard++;sessionStorage.removeItem('ara.justClaimed');renderWizard();}};
let formDirty=false;
addEventListener('input',e=>{if(e.target.closest('#group-form,#audio-form,.digital-account,#digital-ids-form'))formDirty=true;});
addEventListener('beforeunload',e=>{if(formDirty){e.preventDefault();e.returnValue='';}});
const originalLoadSchema=loadSchema;
loadSchema=async function(){await originalLoadSchema();formDirty=false;};
const extraNav=[['Schedules','/schedules'],['Airtime','/airtime']];
for(const [label,url]of extraNav){const a=document.createElement('a');a.href=url;a.textContent=label;if(path===url)a.setAttribute('aria-current','page');$('navigation').insertBefore(a,$('navigation').querySelector('a[href="/profiles"]'));}
async function schedulesPage(){const d=await api('/api/features');$('title').textContent='Schedules';$('content').innerHTML=panel('Saved schedules',d.rules.length?d.rules.map(r=>`<div class="favorite"><span><b>${esc(r.label)}</b><p class="hint">${esc(r.operation)} ${esc(r.mode)} ${esc(r.target)} · ${esc(r.time)} ${esc(r.timezone)}<br>${esc(r.last_result)}</p></span><button data-toggle="${r.id}" data-enabled="${!r.enabled}" class="secondary">${r.enabled?'Disable':'Enable'}</button><button data-delete="${r.id}" class="danger">Delete</button></div>`).join(''):'<p class="empty">No schedules yet.</p>')+panel('Add a schedule',`<form id="schedule-form"><div class="fields"><label>Name<input name="label" maxlength="60" required></label><label>Time zone<select name="timezone">${['America/New_York','America/Chicago','America/Denver','America/Los_Angeles','UTC'].map(z=>`<option>${z}</option>`).join('')}</select></label><label>Action<select name="operation"><option value="connect">Connect if idle</option><option value="disconnect">Disconnect this destination</option></select></label><label>Network<select name="mode">${(station.modes||[]).map(m=>`<option>${esc(m)}</option>`).join('')}</select></label><label>Destination<input name="target" required maxlength="48"></label><label>Time<input type="time" name="time" required></label></div><div class="row">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map((day,i)=>`<label class="check"><input type="checkbox" name="day" value="${i}">${day}</label>`).join('')}</div><p class="hint">New schedules start disabled. Connect rules skip if another link is active; disconnect rules only affect the specified destination. Stopped radios stay stopped.</p><button>Save schedule</button></form>`)+panel('Recent results',d.history.length?d.history.map(h=>`<p><b>${esc(h.label)}</b> · ${esc(h.time)}<br>${esc(h.result)}</p>`).join(''):'<p class="empty">Nothing has run yet.</p>');$('schedule-form').onsubmit=e=>{e.preventDefault();const f=e.target.elements;action(async()=>{await api('/api/features',{action:'add',label:f.label.value,timezone:f.timezone.value,operation:f.operation.value,mode:f.mode.value,target:f.target.value,time:f.time.value,days:[...e.target.querySelectorAll('[name=day]:checked')].map(x=>Number(x.value))});await schedulesPage();message('Schedule saved disabled. Enable it when ready.');});};document.querySelectorAll('[data-toggle]').forEach(b=>b.onclick=()=>action(async()=>{await api('/api/features',{action:'toggle',id:b.dataset.toggle,enabled:b.dataset.enabled==='true'});await schedulesPage();}));document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>action(async()=>{await api('/api/features',{action:'delete',id:b.dataset.delete});await schedulesPage();}));}
async function airtimePage(){const d=await api('/api/features');$('title').textContent='Airtime';const rows=Object.entries(d.airtime).reverse().flatMap(([month,modes])=>Object.entries(modes).map(([mode,v])=>`<tr><td>${esc(month)}</td><td>${esc(mode)}</td><td>${(v.seconds/60).toFixed(1)} min</td><td>${v.count}</td></tr>`));$('content').innerHTML=panel('Observed RF receive activity',`<table><thead><tr><th>MONTH (UTC)</th><th>SELECTED MODE</th><th>RECEIVE TIME</th><th>RX PERIODS</th></tr></thead><tbody>${rows.join('')||'<tr><td colspan="4" class="empty">No receive activity recorded yet.</td></tr>'}</tbody></table><p class="hint">Estimated from the radio receive indicator sampled every two seconds. Short transmissions can be missed. This is not calibrated airtime or a per-callsign ranking. Thirteen months are retained locally.</p>`);}
const baseRenderPage=renderPage;
renderPage=function(){if(path==='/schedules'){health();schedulesPage().catch(e=>message(e.message));return;}if(path==='/airtime'){health();airtimePage().catch(e=>message(e.message));return;}baseRenderPage();};
const basicNetworkPage=networkPage;
networkPage=async function(){await basicNetworkPage();$('content').insertAdjacentHTML('beforeend',panel('Wi-Fi networks','<button id="wifi-scan" class="secondary">Scan networks</button><div id="wifi-results"></div>')+panel('Add a Wi-Fi network','<form id="wifi-form"><div class="fields"><label>Network name<input name="ssid" required maxlength="32" autocomplete="off"></label><label>WPA/WPA2 password<input name="password" type="password" minlength="8" maxlength="64" autocomplete="new-password" required></label></div><button>Save network</button></form><p id="wifi-message" role="status"></p><button id="wifi-connect" hidden>Connect now</button><p class="hint">Saving does not switch your connection. Connecting may interrupt this page.</p>'));$('wifi-scan').onclick=()=>action(async()=>{const d=await api('/api/system',{action:'wifi-scan'});$('wifi-results').innerHTML='<table><thead><tr><th>NETWORK</th><th>SIGNAL</th><th>SECURITY</th></tr></thead><tbody>'+d.networks.map(n=>`<tr><td>${esc(n.ssid)}</td><td>${esc(n.signal)}%</td><td>${esc(n.security)}</td></tr>`).join('')+'</tbody></table>';});let savedId=null;$('wifi-form').onsubmit=e=>{e.preventDefault();action(async()=>{const d=await api('/api/system',{action:'wifi-save',ssid:e.target.elements.ssid.value,password:e.target.elements.password.value});e.target.elements.password.value='';savedId=d.id;$('wifi-message').textContent=d.message;$('wifi-connect').hidden=false;});};$('wifi-connect').onclick=()=>{if(!confirm('Switch Wi-Fi now? This browser connection may close.'))return;action(async()=>{const d=await api('/api/system',{action:'wifi-connect',id:savedId});message(d.message);});};};
const basicConnections=connections;
connections=function(){
 basicConnections();
 $('content').insertAdjacentHTML('afterbegin','<section class="panel connection-status" aria-label="Current connection"><h2>Current connection</h2><p id="connection-live" role="status" aria-live="polite"></p><button id="connection-disconnect" class="danger" hidden>Disconnect</button></section>');
 $('connection-disconnect').onclick=()=>command('disconnect');
 bindFavoriteNotes();restoreConnectionDrafts();refreshConnectionStatus();bindDigitalDirectories();
};

function connectionRows(){return station.active_connections?.length?station.active_connections:station.connected?[{mode:station.mode,target:station.target}]:[];}
const connectionDirectories=new Map();
function connectionLabel(r){
 const source=r.mode==='DMR'?(r.network||station.dmr_network||'TGIF'):r.mode;
 const base=r.mode==='DMR'?`${source} · TG ${r.target}`:String(r.target||'');
 if(!['BrandMeister','TGIF','YSF','NXDN','P25','M17','D-STAR'].includes(source))return base;
 if(!connectionDirectories.has(source)){
  connectionDirectories.set(source,null);
  api('/api/directory?source='+encodeURIComponent(source)).then(data=>{
   connectionDirectories.set(source,new Map((data.rows||[]).map(row=>[row.target,row])));
   if(path==='/connections')refreshConnectionStatus();else if(path==='/')dashboard();
  }).catch(()=>connectionDirectories.set(source,new Map()));
 }
 const key=source==='D-STAR'?base.replace(/\s/g,'').slice(0,6):source==='M17'?base.split(' ')[0]:source==='YSF'?base.padStart(5,'0'):String(r.target);
 const row=connectionDirectories.get(source)?.get(key);
 const name=row&&(row.name!==row.target?row.name:row.host);
 return name?`${name} · ${base}`:base;
}
function refreshConnectionStatus(){
  const rows=connectionRows();
  if($('connection-live')){
    const text=station.connected?`Connected · ${station.mode} · ${connectionLabel(station)}`:station.pending?'Connecting — waiting for the other station to respond…':'Not connected';
    $('connection-live').innerHTML=rows.length?`<div class="active-links">${rows.map(r=>`<div class="active-link"><span>${esc(r.mode)}</span><strong>${esc(connectionLabel(r))}</strong><small>Connected${station.bridge_enabled?' · bridged':''}</small></div>`).join('')}</div>`:esc(text);
    $('connection-live').className=station.connected?'connected':'';
    $('connection-disconnect').hidden=!station.connected;$('connection-disconnect').textContent=station.bridge_enabled?'Disconnect all / stop bridge':'Disconnect';
    if(station.connected&&/^Connection requested|^Request accepted|could not start or connect\.$/.test($('feedback').textContent))message(text);
    if(!station.connected&&!station.pending&&/^Connection requested/.test($('feedback').textContent))message((station.events||[])[0]?.message||'No connection established.');
  }
  document.querySelectorAll('[data-connect]').forEach(form=>{
    const mode=form.dataset.connect, unavailable=connectionUnavailable(mode);
    form.querySelector('button').disabled=!!(unavailable||station.pending||station.readonly);
    let reason=form.querySelector('.connect-reason');
    if(!reason){reason=document.createElement('p');reason.className='connect-reason hint';reason.setAttribute('role','status');form.append(reason);}
    const state=station.runtime||runtime;
    reason.classList.toggle('connection-error',!!form.dataset.connectError);
    if(form.dataset.connectError)reason.textContent=form.dataset.connectError;
    else if(unavailable)reason.textContent=unavailable;
    else if(station.readonly)reason.innerHTML=state.radio_enabled===false?'Radio is stopped. <a href="/settings#audio">Open radio controls →</a> Confirm readiness and press Start radio, then return here to connect.':'Connection controls are unavailable. <a href="/settings#review">Review station status →</a>';
    else if(station.pending)reason.textContent='Waiting for the current connection request to complete.';
    else if(station.connected)reason.textContent=bridgeConsent?'Connect adds this destination and bridges audio with existing links.':'Connect will disconnect the current destination first.';
    else reason.textContent='Ready to connect.';
    const card=form.closest('section'),h=card.querySelector('h2'),links=rows.filter(r=>r.mode===mode),isConnected=links.length>0;
    h.textContent=mode+(isConnected?' · CONNECTED':station.pending&&station.mode===mode?' · CONNECTING':'');
    card.classList.toggle('network-connected',isConnected);
    let destination=card.querySelector('.card-destination');
    if(!destination){destination=document.createElement('div');destination.className='card-destination';destination.setAttribute('role','status');h.after(destination);}
    destination.innerHTML=isConnected?`<small>CONNECTED TO</small><strong>${links.map(r=>esc(connectionLabel(r))).join('<br>')}</strong>`:'<small>CURRENT CONNECTION</small><span>Not connected</span>';
    form.querySelector('button').textContent=station.connected?(bridgeConsent?'Add connection':'Switch connection'):'Connect';
    let button=form.querySelector('[data-disconnect]');
    if(isConnected&&!button){button=document.createElement('button');button.type='button';button.className='danger';button.dataset.disconnect='';button.textContent='Disconnect';button.onclick=()=>command('disconnect');form.querySelector('.actions').append(button);}
    if(button&&!isConnected)button.remove();else if(button)button.textContent=station.bridge_enabled?'Disconnect all':'Disconnect';
  });
}
// Keep edits intact when switching settings tabs until the operator discards them.
document.addEventListener('click',e=>{const link=e.target.closest('.section-tabs a,.apply-cta');if(link&&formDirty){if(!confirm('Discard unsaved edits and open this section?')){e.preventDefault();return;}formDirty=false;}},true);

function finishPage(){
 const steps=schema.workflow?.steps||[],missing=steps.filter(s=>!s.complete&&!s.optional);
 const destinations={station:'station',networks:'allstar',radio:'radio',review:'review',audio:'audio'};
 $('content').innerHTML+=panel(missing.length?'One last check':'Ready to finish setup',
  `<p>${missing.length?'Complete the items below before finishing setup.':'All required setup checks are recorded. Finish setup to open your dashboard and hide guided setup.'}</p>
  <ul class="finish-checks">${steps.map(s=>`<li>${esc(s.title)}${s.complete?' - complete':s.optional?` - ${esc(s.status||'untested')} (optional) <button type="button" class="secondary" data-finish-step="audio">Open audio test</button>`:` - not complete <button type="button" class="secondary" data-finish-step="${esc(destinations[s.id]||'review')}">Open ${esc(s.title.toLowerCase())}</button>`}</li>`).join('')}</ul>
  ${steps.some(s=>s.optional&&!s.complete)?'<p class="hint">Audio testing is optional. Finish now and test later in Settings - Audio levels. Skipping does not confirm audio quality or start the radio.</p>':''}
  <p id="finish-feedback" role="status" aria-live="polite"></p>
  <div class="actions"><button id="finish" ${!steps.length||missing.length?'disabled':''}>Finish setup</button><button id="finish-refresh" class="secondary">Recheck status</button><button id="finish-back" class="secondary">Back</button></div>`);
 document.querySelectorAll('[data-finish-step]').forEach(b=>b.onclick=()=>{wizard=wizardSteps.indexOf(b.dataset.finishStep);renderWizard();});
 $('finish-back').onclick=()=>{wizard--;renderWizard();};
 $('finish-refresh').onclick=()=>action(async()=>{try{await loadSchema();renderWizard();$('finish-feedback').textContent='Status refreshed.';}catch(e){$('finish-feedback').textContent=e.message;}});
 $('finish').onclick=()=>action(async()=>{
  const button=$('finish');button.disabled=true;$('finish-feedback').textContent='Finishing setup…';
  try{await api('/api/finish',{});sessionStorage.removeItem('ara.setupStep');formDirty=false;location.href='/';}
  catch(e){try{await loadSchema();renderWizard();}catch{}$('finish-feedback').textContent=e.message;}
 });
}

function updateApplyNotice(){
 let notice=$('apply-notice');
 if(!notice){notice=document.createElement('aside');notice.id='apply-notice';notice.className='apply-notice';notice.setAttribute('aria-label','Pending configuration changes');$('content').before(notice);}
 notice.hidden=!schema.saved||!!schema.workflow?.applied||path==='/setup'||path==='/connections';
 if(notice.hidden)return;
 const savedNode=value('allstar','node'),liveNode=runtime.node;
 const nodeChange=value('allstar','enabled')&&savedNode&&liveNode&&String(savedNode)!==String(liveNode);
 notice.innerHTML=`<div><strong>Saved changes are not active yet</strong><p>${nodeChange?`New node: <b>${esc(savedNode)}</b> · Currently running: <b>${esc(liveNode)}</b>. `:''}Review and apply to activate your saved settings. A running radio restarts automatically after applying.</p></div><a class="apply-cta" href="/settings#review">Review & apply changes →</a>`;
}

function saveConnectionDrafts(){
 if(path!=='/connections')return;
 try{sessionStorage.setItem('ara.connectionDrafts',JSON.stringify(Object.fromEntries([...document.querySelectorAll('[data-connect]')].map(f=>[f.dataset.connect,f.elements.target.value]))));}catch{}
}
function restoreConnectionDrafts(){
 try{const values=JSON.parse(sessionStorage.getItem('ara.connectionDrafts')||'{}');document.querySelectorAll('[data-connect]').forEach(f=>{if(typeof values[f.dataset.connect]==='string')f.elements.target.value=values[f.dataset.connect].slice(0,48);});}catch{}
}
addEventListener('pagehide',saveConnectionDrafts);
document.addEventListener('click',e=>{if(e.target.closest('a'))saveConnectionDrafts();},true);

function bindFavoriteNotes(){
 document.querySelectorAll('[data-note]').forEach(form=>{
  const i=Number(form.dataset.note);
  form.onsubmit=e=>{e.preventDefault();const note=form.elements.note.value.trim(),old=favorites[i].note;
   favorites[i].note=note;
   try{localStorage.setItem('ara.favorites',JSON.stringify(favorites));}
   catch{favorites[i].note=old;message('Could not save the note. Browser storage is unavailable.');return;}
   const text=document.querySelector(`[data-note-text="${i}"]`);text.textContent=note;text.hidden=!note;
   const details=form.closest('details');details.querySelector('summary').textContent=note?'Edit note':'Add note';details.open=false;
   message('Favorite note saved in this browser.');
  };
  form.querySelector('[data-note-cancel]').onclick=()=>{form.elements.note.value=favorites[i].note||'';form.closest('details').open=false;};
 });
}

function rssiCard(){
 const r=station.rssi||{},valid=!r.paused&&Number.isFinite(r.value),level=valid?Math.max(0,Math.min(5,Math.floor(Math.max(0,r.value)*5/123))):0;
 const signal=valid?`${level} of 5 signal bars, relative RSSI ${r.value}`:r.paused?'Signal reading paused':'Signal reading unavailable';
 return `<div class="metric"><small>RADIO SIGNAL / RSSI</small><div class="rssi-reading"><strong>${r.paused?'Paused':!valid?'Unavailable':esc(r.value)}</strong><span class="rssi-bars" role="img" aria-label="${esc(signal)}" title="${esc(signal)}">${[1,2,3,4,5].map(n=>`<i class="${n<=level?'lit':''}" aria-hidden="true"></i>`).join('')}</span></div><p class="hint">Relative RSSI / full bars at 123</p><button id="rssi-toggle" class="secondary" ${station.simulation?'disabled':''}>${r.paused?'Resume RSSI':'Pause RSSI'}</button><p class="hint">Pauses during web programming. Pause here before manual programming.</p></div>`;
}

function prefillDirectorySetup(group){
 if(group!=='other')return;
 try{
  const draft=JSON.parse(sessionStorage.getItem('ara.directorySetup')||'null');if(!draft)return;
  for(const [key,val] of Object.entries(draft)){const el=$('group-form').elements.namedItem(key);if(el)el.value=val;}
  sessionStorage.removeItem('ara.directorySetup');formDirty=true;
  message('Reflector details filled in. Complete your identity fields, save, then review and apply.');
 }catch{}
}
function bindDigitalDirectories(){
 document.querySelectorAll('[data-connect]').forEach(form=>{
  const mode=form.dataset.connect;if(!['DMR','D-STAR','YSF','NXDN','P25','M17'].includes(mode))return;
  const box=document.createElement('details');box.className='digital-directory';
  box.innerHTML='<summary>Browse '+esc(mode==='DMR'?'talkgroups':'reflectors')+'</summary><label>Search directory<input type="search" placeholder="Number, name, or hostname"></label>'+(['D-STAR','M17'].includes(mode)?'<label>Module<select class="directory-module">'+Array.from({length:26},(_,i)=>String.fromCharCode(65+i)).map(m=>`<option ${m===(mode==='D-STAR'?'C':'A')?'selected':''}>${m}</option>`).join('')+'</select></label>':'')+'<p class="hint directory-info" role="status"></p><div class="directory-results"></div><div class="actions"><button type="button" class="secondary directory-prev">Previous</button><button type="button" class="secondary directory-next">Next</button></div>';
  form.after(box);let data=null,page=0,source='',loading=false;
  const search=box.querySelector('input'),info=box.querySelector('.directory-info'),results=box.querySelector('.directory-results');
  function draw(){
   if(!data)return;
   const q=search.value.toLowerCase().replace(/[\s_-]+/g,''),rows=(data.rows||[]).filter(r=>(r.target+' '+r.name+' '+(r.host||'')).toLowerCase().replace(/[\s_-]+/g,'').includes(q)),pages=Math.max(1,Math.ceil(rows.length/20));page=Math.min(page,pages-1);
   info.textContent=`${source}: ${rows.length} entries · page ${page+1}/${pages}. ${data.updated?'Updated '+new Date(data.updated*1000).toLocaleString()+'. ':''}${data.error||''} ${data.attribution||''}. Directory listing, not live availability.`;
   results.replaceChildren();
   for(const row of rows.slice(page*20,(page+1)*20)){
    const item=document.createElement('div');item.className='directory-row';const label=document.createElement('span');label.textContent=row.target+' · '+row.name;const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent='Select';
    button.onclick=()=>{const module=box.querySelector('.directory-module')?.value,target=row.target+(module?(mode==='M17'?' ':'')+module:'');
     form.elements.target.value=target;saveConnectionDrafts();box.open=false;message(mode+' destination selected: '+target+'. Server details are filled automatically when you connect.');form.elements.target.focus();
    };item.append(label,button);results.append(item);
   }
   box.querySelector('.directory-prev').disabled=page===0;box.querySelector('.directory-next').disabled=page>=pages-1;
  }
  async function load(){
   const wanted=mode==='DMR'?form.elements.network.value:mode;if(data&&source===wanted)return draw();if(loading)return;loading=true;source=wanted;info.textContent='Loading cached directory…';
   try{data=await api('/api/directory?source='+encodeURIComponent(source));page=0;draw();}catch(e){info.textContent=e.message;}finally{loading=false;if(mode==='DMR'&&form.elements.network.value!==source){data=null;load();}}
  }
  box.ontoggle=()=>{if(box.open)load();};search.oninput=()=>{page=0;draw();};box.querySelector('.directory-prev').onclick=()=>{page--;draw();};box.querySelector('.directory-next').onclick=()=>{page++;draw();};
  if(mode==='DMR')form.elements.network.addEventListener('change',()=>{data=null;results.replaceChildren();if(box.open)load();});
 });
}

async function digitalIdsPage(openGroup=null){
 try{
  const data=await api('/api/digital-identities');
  if(location.hash!=='#other')return;
  $('content').innerHTML=settingsTabs()+panel('Digital IDs',`<p>Enter these once. Destinations and server addresses are handled automatically on Connections.</p><form id="digital-ids-form"><div class="fields"><label>NXDN radio ID<input name="nxdn" inputmode="numeric" pattern="[0-9]+" value="${esc(data.values.nxdn)}" placeholder="Optional until you use NXDN"></label><label>P25 radio ID<input name="p25" inputmode="numeric" pattern="[0-9]+" value="${esc(data.values.p25)}" placeholder="Optional until you use P25"></label><label>M17 callsign<input name="m17" maxlength="9" value="${esc(data.values.m17)}"></label></div><p class="hint">M17 uses a callsign, not a numeric radio ID. Changes take effect on your next connection.</p><button>Save IDs</button><p id="digital-ids-result" role="status"></p></form>`);
  const accounts=document.createElement('section');accounts.className='panel digital-accounts';
  accounts.innerHTML='<h2>Network accounts & IDs</h2><p>Your account details in one place. Open a network to edit it.</p>'+['allstar','echolink','dmr','brandmeister','tgif'].map(g=>`<details data-account="${g}" ${g===openGroup?'open':''}><summary>${esc(labels[g])}</summary>${groupForm(g).replace('id="group-form"',`id="account-${g}" class="digital-account"`).replace('id="cancel"',`id="cancel-${g}"`)}</details>`).join('');
  $('content').querySelector('.section-tabs').after(accounts);
  accounts.querySelector('h2').textContent='Digital IDs';
  const idsForm=$('digital-ids-form'),oldPanel=idsForm.closest('.panel');
  const fields=[...idsForm.querySelectorAll('.fields > label')];
  idsForm.querySelector('.fields').remove();idsForm.querySelector('.hint').remove();idsForm.querySelector('button').remove();
  for(const [i,label] of fields.entries()){
   const details=document.createElement('details');details.dataset.account=['nxdn','p25','m17'][i];
   const summary=document.createElement('summary');summary.textContent=['NXDN','P25','M17'][i];details.append(summary);
   const body=document.createElement('div');body.className='identity-fields';body.append(label);
   if(i===2){const hint=document.createElement('p');hint.className='hint';hint.textContent='M17 uses your callsign instead of a numeric radio ID.';body.append(hint);}
   const save=document.createElement('button');save.type='submit';save.textContent='Save';body.append(save);details.append(body);idsForm.insertBefore(details,idsForm.querySelector('#digital-ids-result'));
  }
  accounts.append(idsForm);oldPanel.remove();

  accounts.querySelectorAll('form.digital-account').forEach(form=>{
   const g=form.dataset.group;
   form.onsubmit=e=>{e.preventDefault();action(async()=>{
    const values={};for(const f of schema.groups.find(x=>x.id===g).fields){const el=form.elements.namedItem(f.key);values[f.key]=!el?f.value:f.type==='checkbox'?el.checked:f.type==='number'?Number(el.value):el.value;}
    try{await api('/api/settings',{group:g,values});await loadSchema();formDirty=false;
     if(e.submitter?.name==='review'){location.hash='review';renderSettings();}
     else{await digitalIdsPage(g);message(labels[g]+' saved. Review & apply activates account changes.');}
    }catch(error){let result=form.querySelector('.account-result');if(!result){result=document.createElement('p');result.className='account-result connection-error';result.setAttribute('role','alert');form.append(result);}result.textContent=error.message;}
   });};
   $('cancel-'+g).onclick=()=>{formDirty=false;digitalIdsPage(g);};
  });
  $('digital-ids-form').onsubmit=e=>{e.preventDefault();action(async()=>{try{const f=e.target.elements;await api('/api/system',{action:'digital-identities-save',values:{nxdn:f.nxdn.value.trim(),p25:f.p25.value.trim(),m17:f.m17.value.trim()}});formDirty=false;$('digital-ids-result').textContent='Saved. Ready for your next connection.';}catch(error){$('digital-ids-result').textContent=error.message;}});};
 }catch(error){message(error.message);}
}

async function codecSettingsPage(){
 try{
  const [state,libraries]=await Promise.all([api('/api/codec/state'),api('/api/codec/libraries')]);
  if(location.hash!=='#dstar')return;
  $('content').innerHTML=settingsTabs()+panel('Digital codec',`<label>Codec source<select id="codec-backend"><option value="software" ${state.requested==='software'?'selected':''}>Software</option><option value="hardware" ${state.requested==='hardware'?'selected':''}>External AMBE hardware</option></select></label><button id="codec-use">Use selected codec</button><p id="codec-selection-result" role="status">Selected: ${esc(state.requested)}. ${esc(state.note||'')}</p>`)+panel('Installed software codecs',`<table><thead><tr><th>Modes</th><th>Software</th><th>Installed build</th></tr></thead><tbody>${libraries.installed.map(r=>`<tr><td>${esc(r.modes)}</td><td>${esc(r.name)}<br><small>${esc(r.file)}</small></td><td>${r.installed?`<code title="${esc(r.sha256)}">${esc(r.sha256.slice(0,12))}</code>`:'Not installed'}</td></tr>`).join('')}</tbody></table><p class="hint">Build fingerprints identify the exact installed files. Software is used when selected; external hardware support depends on the mode.</p>`)+panel('External AMBE server',`<details><summary>Hardware connection settings</summary>${groupForm('dstar')}<button id="settings-test-ambe" type="button" class="secondary">Test saved hardware server</button></details>`)+panel('Upload your codec',`<form id="codec-upload-form"><div class="fields"><label>Codec interface<select name="profile">${libraries.installed.map(r=>`<option value="${esc(r.profile)}">${esc(r.modes)}</option>`).join('')}</select></label><label>ARM64 Linux library (.so, up to 16 MiB)<input name="file" type="file" accept=".so" required></label></div><p class="hint">Libraries must implement the selected ALLMODE interface. Upload checks the architecture and exported functions. Uploaded files are stored for testing; they do not replace the installed codec or become active automatically.</p><button>Upload codec</button><p id="codec-upload-result" role="status"></p></form><div id="codec-upload-list">${libraries.uploads.map(r=>`<p><strong>${esc(r.name)}</strong> · ${esc(r.profile)} · ${esc(r.status)}<br><small>${esc(r.checks)}</small></p>`).join('')}</div>`);
  bindGroup('dstar');$('settings-test-ambe').onclick=()=>systemAction('test-ambe');
  $('codec-use').onclick=()=>action(async()=>{try{const s=await api('/api/codec/select',{backend:$('codec-backend').value});await loadSchema();$('codec-selection-result').textContent='Selected: '+s.requested+'. '+(s.note||'');}catch(e){$('codec-selection-result').textContent=e.message;}});
  $('codec-upload-form').onsubmit=async e=>{e.preventDefault();const form=e.target,file=form.elements.file.files[0],button=form.querySelector('button');button.disabled=true;
   try{if(!file||file.size>16*1024*1024)throw Error('Choose a codec library no larger than 16 MiB.');$('codec-upload-result').textContent='Uploading and checking library…';const response=await fetch('/api/codec/upload',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Codec-Profile':form.elements.profile.value,'X-Codec-Name':file.name.replace(/[^a-zA-Z0-9_.-]/g,'_')},body:file});const r=await response.json();if(!response.ok)throw Error(r.error||'Upload failed');$('codec-upload-result').textContent=r.name+': '+r.status+'. '+r.checks;form.reset();}catch(error){$('codec-upload-result').textContent=error.message;}finally{button.disabled=false;}
  };
 }catch(error){message(error.message);}
}

function radioWizardPage(){sessionStorage.setItem('ara.setupStepName','radio');location.replace('/hardware?return=setup');}

// Home shortcuts retain the exact network and require a fresh, manual request.
let homeTargetSelection=0;
function connectionUnavailable(mode){
 const supported=['AllStar','EchoLink','D-STAR','DMR','YSF','P25','M17','NXDN'];
 if(!supported.includes(mode)||![...(station.modes||[]),...(station.quick_connect_modes||[]),...Object.keys(station.unavailable_modes||{})].includes(mode))return 'Mode is unavailable.';
 return station.quick_connect_modes?.includes(mode)?null:station.unavailable_modes?.[mode]||null;
}
function validShortcut(item){
 if(!item||typeof item.target!=='string'||item.target!==item.target.trim()||item.target.length>48)return false;
 const target=item.target;
 if(item.mode==='AllStar')return /^[0-9]{4,6}$/.test(target)&&target!==String(runtime.node||'');
 if(item.mode==='EchoLink')return /^[0-9]{1,6}$/.test(target)&&Number(target)>0;
 if(['DMR','YSF','P25','NXDN'].includes(item.mode))return /^[0-9]+$/.test(target)&&Number(target)>=(item.mode==='YSF'?0:1)&&Number(target)<=(item.mode==='NXDN'?65535:item.mode==='YSF'?99999:16777215);
 if(item.mode==='D-STAR')return /^(REF|DCS|XRF)[0-9]{3} ?[A-Z]$/.test(target);
 if(item.mode==='M17')return /^M17-[A-Z0-9]{3} [A-Z]$/.test(target);
 return false;
}
function rememberDestination(data){
 const item={mode:data.mode,target:data.value,network:data.network,source_id:data.source_id};
 try{const old=JSON.parse(localStorage.getItem('ara.recentDestinations')||'[]');
 localStorage.setItem('ara.recentDestinations',JSON.stringify([item,...(Array.isArray(old)?old:[]).filter(x=>JSON.stringify(x)!==JSON.stringify(item))].slice(0,8)));}catch{}
}
function quickDestinations(){
 let recent=[];try{recent=JSON.parse(localStorage.getItem('ara.recentDestinations')||'[]');}catch{}
 const rows=[],seen=new Set();
 for(const item of [...favorites,...(Array.isArray(recent)?recent:[])]){
  if(!validShortcut(item))continue;
  // Old DMR favorites lack a network: let the full Connect page resolve it.
  if(item.mode==='DMR'&&!['TGIF','BrandMeister'].includes(item.network))continue;
  const key=JSON.stringify([item.mode,item.target,item.network,item.source_id]);
  if(!seen.has(key)){seen.add(key);rows.push(item);}
 }
 return rows.slice(0,20);
}
function quickConnectMarkup(){
 const rows=quickDestinations();
 return rows.length?`<form id="home-connect"><label for="home-target">Favorite or recent destination</label><select id="home-target">${rows.map((r,i)=>`<option value="${i}" ${i===homeTargetSelection?'selected':''}>${esc(r.mode)}${r.network?' / '+esc(r.network):''} · ${esc(r.target)}</option>`).join('')}</select><button type="submit" ${station.pending||station.readonly||connectionUnavailable(rows[homeTargetSelection]?.mode)?'disabled':''}>Quick Connect</button><p class="hint">Connects only when pressed. Existing links are replaced; bridging stays off.</p></form>`:'<p class="empty">No favorites or recent destinations yet.</p>';
}
function bindQuickConnect(){
 const form=$('home-connect');if(!form)return;
 const rows=quickDestinations();
 $('home-target').onchange=e=>{homeTargetSelection=Number(e.target.value);form.querySelector('button').disabled=!!(station.pending||station.readonly||connectionUnavailable(rows[homeTargetSelection]?.mode));};
 form.onsubmit=e=>{e.preventDefault();if(station.pending||station.readonly)return;
  const item=rows[Number($('home-target').value)];if(!validShortcut(item)||connectionUnavailable(item.mode))return message('This destination is unavailable. Open Connect to review its status.');
  action(async()=>{const button=form.querySelector('button');button.disabled=true;
   try{station=await api('/api/command',{action:'connect-network',mode:item.mode,value:item.target,allow_bridge:false,...(item.network?{network:item.network}:{}),...(item.source_id?{source_id:item.source_id}:{})});message('Connection requested.');dashboard();}
   finally{button.disabled=false;}
  });
 };
}
function initPhoneNavigation(){
 const audio=path==='/settings'&&location.hash==='#audio'||['/audio-tools','/parrot','/radio-parrot','/browser-parrot','/codec'].includes(path);
 const active=path==='/'?'Home':path==='/connections'?'Connect':audio?'Audio':'Settings';
 let nav=$('phone-navigation');if(!nav){nav=document.createElement('nav');nav.id='phone-navigation';nav.setAttribute('aria-label','Phone navigation');document.body.append(nav);}
 nav.innerHTML=[['Home','/'],['Connect','/connections'],['Audio','/settings#audio'],['Settings','/settings']].map(([label,url])=>`<a href="${url}" ${active===label?'aria-current="page"':''}>${label}</a>`).join('');
 if(path==='/settings'&&!$('phone-more')){
  const more=document.createElement('details');more.id='phone-more';more.className='panel phone-more';
  more.innerHTML='<summary>More station tools</summary><div class="phone-tool-links">'+[...document.querySelectorAll('#navigation a')].filter(a=>!['/','/connections','/settings'].includes(a.pathname)).map(a=>`<a href="${esc(a.getAttribute('href'))}">${esc(a.textContent)}</a>`).join('')+'<a href="/hardware">Radio setup</a><a href="/audio-tools">Audio &amp; codec tools</a><a href="/radio-parrot">Handheld radio test</a><a href="/browser-parrot">Browser audio test</a><a href="/settings#review">Review & apply</a></div>';
  $('content').before(more);
 }
}
initPhoneNavigation();
addEventListener('hashchange',initPhoneNavigation);

// Three layouts recovered verbatim in structure from PihatUBETA, 2026-10-28.
function radioConnectionMap(){
 const links=Array.isArray(station.active_connections)?station.active_connections:[];
 const node=String(runtime.node||station.node||'');
 const publicUrl=/^[0-9]{4,10}$/.test(node)?`https://stats.allstarlink.org/stats/${node}/networkMap`:null;
 const cx=320,cy=118;
 const peers=links.slice(0,12).map((link,i)=>{
  const angle=2*Math.PI*i/Math.min(links.length,12)-Math.PI/2;
  const x=cx+Math.cos(angle)*230,y=cy+Math.sin(angle)*78;
  return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#42617a" stroke-width="1.5"/><g><rect x="${x-55}" y="${y-22}" width="110" height="44" rx="4" fill="#122c3d" stroke="#618eab"/><text x="${x}" y="${y-4}" text-anchor="middle" fill="#dbeefa" font-size="12">${esc(link.target)}</text><text x="${x}" y="${y+12}" text-anchor="middle" fill="#8baec4" font-size="9">${esc(link.mode)}</text></g>`;
 }).join('');
 return `<section class="rig-map"><div class="rig-map-heading"><span>CONNECTION MAP</span><span>${links.length} DIRECT LINK${links.length===1?'':'S'}</span></div><svg viewBox="0 0 640 235" role="img" aria-label="Local node ${esc(node)} with ${links.length} direct connections"><defs><pattern id="map-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M 24 0 L 0 0 0 24" fill="none" stroke="#132331" stroke-width=".7"/></pattern></defs><rect width="640" height="235" fill="url(#map-grid)"/>${peers}<circle cx="${cx}" cy="${cy}" r="39" fill="#102c3d" stroke="#85bddb" stroke-width="1.5"/><text x="${cx}" y="${cy-3}" text-anchor="middle" fill="#f0f8ff" font-size="15">${esc(node||'LOCAL')}</text><text x="${cx}" y="${cy+14}" text-anchor="middle" fill="#8fbbd5" font-size="9">YOUR STATION</text>${links.length?'':'<text x="320" y="194" text-anchor="middle" fill="#7395ad" font-size="11">No connected nodes</text>'}</svg><div class="rig-map-footer"><span>Local link status · updates every 5 seconds${links.length>12?' · first 12 shown':''}</span>${publicUrl?`<a href="${publicUrl}" target="_blank" rel="noopener noreferrer">Full AllStar network ↗</a>`:''}</div></section>`;
}

// AR-03 shares station APIs with the original operator interface.
const classicDashboard=dashboard;
let rigPanel=null,rigFocus=null;
const rigIcon=name=>{
 const paths={map:'M4 5h6v6H4zM19 5h6v6h-6zM11 21h7v6h-7zM7 11v5h15v-5M15 16v5',audio:'M5 14v4M10 9v14M15 4v24M20 10v12M25 14v4',memory:'M6 4h18v24H6zM10 9h10M10 14h10M10 19h7',codec:'M9 9h12v12H9zM5 11h4M5 19h4M21 11h4M21 19h4M11 5v4M19 5v4M11 21v4M19 21v4',radio:'M15 15v13M10 28h10M8 8a10 10 0 0 0 0 14M22 8a10 10 0 0 1 0 14M11 11a6 6 0 0 0 0 8M19 11a6 6 0 0 1 0 8',settings:'M5 8h20M5 16h20M5 24h20M11 4v8M21 12v8M9 20v8',network:'M4 13q11-14 22 0M8 18q7-9 14 0M12 23q3-4 6 0M15 28h.1',clock:'M15 5a11 11 0 1 0 .1 0M15 9v8l6 3',logs:'M6 4h18v24H6zM10 10h10M10 16h10M10 22h7'};
 return `<svg viewBox="0 0 30 32" aria-hidden="true"><path d="${paths[name]||paths.settings}" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
};
function rigSetText(id,text){const el=$(id);if(el&&el.textContent!==String(text))el.textContent=text;}
function rigClose(){const panel=$('rig-overlay');if(panel){panel.hidden=true;panel.innerHTML='';}rigPanel=null;if(rigFocus?.isConnected)rigFocus.focus();}
function rigOpen(name){
 const panel=$('rig-overlay');if(!panel)return;
 if(!rigPanel)rigFocus=document.activeElement;
 rigPanel=name;panel.hidden=false;
 const title={menu:'STATION MENU',memory:'MEMORY CHANNELS',quick:'QUICK CONTROLS',mode:'NETWORK MODE',frequency:'RADIO FREQUENCY',audio:'AUDIO & METER',connect:'QUICK CONNECT'}[name]||'STATION MENU';
 let body='';
 if(name==='menu')body=`<div class="rig-menu-grid">${[['map','LINK MAP','map'],['memory','MEMORY','memory'],['audio','AUDIO','audio'],['codec','CODEC','/settings#dstar'],['radio','RADIO','frequency'],['clock','SCHEDULE','/schedules'],['network','LAN / WI-FI','/network'],['logs','ACTIVITY','/logs'],['settings','SETTINGS','/settings']].map(([icon,label,target])=>target.startsWith('/')?`<a class="rig-tile" href="${target}">${rigIcon(icon)}<span>${label}</span></a>`:`<button class="rig-tile" data-rig-panel="${target}">${rigIcon(icon)}<span>${label}</span></button>`).join('')}</div>`;
 if(name==='memory')body=`<div class="rig-memory-list">${favorites.length?favorites.map((f,i)=>`<button data-rig-memory="${i}"><span class="memory-index">${String(i+1).padStart(2,'0')}</span><span><strong>${esc(f.target)}</strong><small>${esc(f.note||f.mode)}</small></span><em>${esc(f.mode)}</em><b>CONNECT ↗</b></button>`).join(''):'<p>No saved memories yet.</p>'}</div><a class="rig-text-link" href="/connections">Manage favorites & connections ↗</a><p id="rig-memory-result" role="status"></p>`;
 if(name==='quick')body=`<div class="rig-quick-list"><button data-rig-panel="connect">Connect to a node <strong>OPEN ↗</strong></button><button id="rig-dim">Display brightness <strong>${document.body.classList.contains('rig-dimmed')?'DIM':'NORMAL'}</strong></button><button id="rig-lock">Audio dial lock <strong>${document.body.classList.contains('rig-locked')?'LOCKED':'UNLOCKED'}</strong></button><button data-rig-panel="mode">Network mode <strong>${esc(station.mode||'Standby')}</strong></button><a href="/settings#review">Applied configuration <strong>VIEW ↗</strong></a></div>`;
 if(name==='mode')body=`<p class="rig-help">Select a network to open its connection controls.</p><div class="rig-mode-grid">${(station.modes||[]).map(m=>`<button data-rig-mode="${esc(m)}">${esc(m)}</button>`).join('')}</div><p id="rig-mode-result" role="status"></p>`;

 if(name==='connect')body=`<div class="rig-connect-panel"><div class="rig-connect-current"><small>CURRENT LINK</small><strong id="rig-quick-current">${esc(station.connected?connectionLabel(station):'Not connected')}</strong></div><div class="rig-connect-fields"><label>Network<select id="rig-connect-mode">${[...new Set([...(station.modes||['AllStar']),...(station.quick_connect_modes||[])])].map(m=>`<option ${m===station.mode?'selected':''}>${esc(m)}</option>`).join('')}</select></label><label id="rig-dmr-network-label" hidden>DMR network<select id="rig-connect-network"><option ${station.dmr_network==='BrandMeister'?'selected':''}>BrandMeister</option><option ${station.dmr_network==='TGIF'?'selected':''}>TGIF</option></select></label><label class="rig-target-label"><span id="rig-target-label">Node number</span><input id="rig-connect-target" maxlength="48" autocomplete="off" placeholder="Enter node number"></label></div><div class="rig-connect-actions"><button id="rig-connect-go">CONNECT</button><button id="rig-connect-unlink">DISCONNECT</button><button data-rig-panel="memory">MEMORIES</button></div><p class="rig-connect-note">Connect switches from the current destination to the new one.</p><p id="rig-connect-result" role="status"></p></div>`;

 if(name==='frequency')body=`<div class="rig-frequency-info"><small>PROGRAMMED RADIO</small><strong>${esc(schema.workflow?.radio?.rx||'—')} <small>MHz RX</small></strong><strong>${esc(schema.workflow?.radio?.tx||'—')} <small>MHz TX</small></strong><p>Set frequencies, tones and squelch in Radio programming.</p><a class="rig-screen-action" href="/hardware">OPEN RADIO PROGRAMMING ↗</a></div>`;
 if(name==='audio')body=`<div class="rig-audio-info"><label class="rig-meter-choice">Meter style<select id="rig-meter-style">${[['analog','Precision needle'],['vintage','Classic amber needle'],['led','Segmented LED'],['digital','Large digital readout']].map(([id,label])=>`<option value="${id}" ${document.documentElement.dataset.meterStyle===id?'selected':''}>${label}</option>`).join('')}</select></label><p id="rig-meter-choice-result" role="status">Changes immediately · remembered in this browser.</p><p>All styles show live audio in dBFS. RX and TX share one meter; TX takes priority when both carry audio.</p><div class="rig-menu-grid"><a class="rig-tile" href="/settings#audio">${rigIcon('audio')}<span>AUDIO & TEST</span></a><a class="rig-tile" href="/settings#dstar">${rigIcon('codec')}<span>DIGITAL CODEC</span></a><button class="rig-tile" data-rig-panel="quick">${rigIcon('settings')}<span>DIAL LOCK</span></button></div></div>`;
 if(name==='map'){rigClose();return;}
 panel.innerHTML=`<div class="rig-overlay-heading"><button id="rig-back" aria-label="Back to station menu">‹</button><h2>${title}</h2><button id="rig-exit" aria-label="Close radio menu">×</button></div><div class="rig-overlay-body">${body}</div>`;
 panel.querySelectorAll('button').forEach(b=>b.type='button');

 if(name==='connect'){
  const mode=$('rig-connect-mode'),target=$('rig-connect-target'),go=$('rig-connect-go'),unlink=$('rig-connect-unlink');
  const refresh=()=>{go.disabled=busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode);unlink.disabled=busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode)||!station.connected;};
  mode.onchange=()=>{const numeric=['AllStar','EchoLink','DMR','NXDN','P25'].includes(mode.value);target.inputMode=numeric?'numeric':'text';target.placeholder=['AllStar','EchoLink'].includes(mode.value)?'Enter node number':mode.value==='D-STAR'?'REF030C':'Enter talkgroup / reflector';rigSetText('rig-target-label',['AllStar','EchoLink'].includes(mode.value)?'Node number':'Talkgroup / reflector');$('rig-dmr-network-label').hidden=mode.value!=='DMR';refresh();};mode.onchange();refresh();
  go.onclick=()=>{
   if(busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode))return;
   const destination=target.value.trim();if(!validShortcut({mode:mode.value,target:destination})){rigSetText('rig-connect-result','Enter a destination first.');target.focus();return;}
   const payload={action:'connect-network',mode:mode.value,value:destination,allow_bridge:false,...(mode.value==='DMR'?{network:$('rig-connect-network').value}:{})};
   action(async()=>{go.disabled=true;unlink.disabled=true;try{rigSetText('rig-connect-result','Connecting…');station=await api('/api/command',payload);dashboard();rigSetText('rig-connect-result','Request sent. Waiting for connection confirmation.');}catch(e){rigSetText('rig-connect-result',e.message);}finally{go.disabled=station.pending||station.readonly;unlink.disabled=station.pending||station.readonly||!station.connected;}});
  };
  target.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();go.click();}};
  unlink.onclick=()=>{if(busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode))return;action(async()=>{go.disabled=true;unlink.disabled=true;try{station=await api('/api/command',{action:'disconnect'});dashboard();rigSetText('rig-connect-result','Disconnect requested.');}catch(e){rigSetText('rig-connect-result',e.message);}finally{go.disabled=station.pending||station.readonly;unlink.disabled=station.pending||station.readonly||!station.connected;}});};
 }

 if($('rig-meter-style'))$('rig-meter-style').onchange=e=>{
  document.documentElement.dataset.meterStyle=e.target.value;
  try{localStorage.setItem('ara.meterStyle',e.target.value);rigSetText('rig-meter-choice-result','Meter style saved. Press EXIT to see it.');}catch{rigSetText('rig-meter-choice-result','Meter style applied for this visit. Browser storage is unavailable.');}
 };
 $('rig-back').onclick=()=>name==='menu'?rigClose():rigOpen('menu');$('rig-exit').onclick=rigClose;
 panel.querySelectorAll('[data-rig-panel]').forEach(b=>b.onclick=()=>rigOpen(b.dataset.rigPanel));
 panel.querySelectorAll('[data-rig-memory]').forEach(b=>b.onclick=()=>{
  if(busy||station.pending||station.readonly)return;
  const f=favorites[Number(b.dataset.rigMemory)];if(!validShortcut(f)||connectionUnavailable(f.mode)||(f.mode==='DMR'&&!['TGIF','BrandMeister'].includes(f.network)))return rigSetText('rig-memory-result','Destination unavailable. Review it on Connections.');
  action(async()=>{try{rigSetText('rig-memory-result','Connecting…');station=await api('/api/command',{action:'connect-network',mode:f.mode,value:f.target,allow_bridge:false,...(f.network?{network:f.network}:{})});rigClose();dashboard();message('Connection requested.');}catch(e){rigSetText('rig-memory-result',e.message);}});
 });
 panel.querySelectorAll('[data-rig-mode]').forEach(b=>b.onclick=()=>{location.href='/connections#'+encodeURIComponent(b.dataset.rigMode);});
 if($('rig-dim'))$('rig-dim').onclick=()=>{document.body.classList.toggle('rig-dimmed');try{localStorage.setItem('ara.rigDim',document.body.classList.contains('rig-dimmed')?'1':'0');}catch{}rigOpen('quick');};
 if($('rig-lock'))$('rig-lock').onclick=()=>{const locked=document.body.classList.toggle('rig-locked');for(const k of ['rx','txa','txb'])$('level-'+k).disabled=locked||runtime.radio_enabled!==true||!Number.isFinite(runtime.levels?.[k]);rigOpen('quick');};
 $('rig-exit').focus();
}

const rigContacts=new Map();
function rigConnectionDetails(){
 const rows=connectionRows(),r=rows[0];
 if(!r)return {callsign:'—',location:'No active connection',duration:'—',node:'STANDBY'};
 const source=r.mode==='DMR'?(r.network||station.dmr_network||'TGIF'):r.mode;
 if(source==='AllStar'&&!rigContacts.has(source)){
  rigContacts.set(source,null);
  api('/api/directory?source=AllStar').then(d=>{rigContacts.set(source,new Map((d.rows||[]).map(row=>[String(row.target),row])));if($('rig-contact-callsign'))dashboard();}).catch(()=>rigContacts.set(source,new Map()));
 }
 const info=rigContacts.get(source)?.get(String(r.target));
 const secs=r.connected_seconds;
 const duration=Number.isFinite(secs)&&secs>=0?[Math.floor(secs/3600),Math.floor(secs/60)%60,Math.floor(secs)%60].map(v=>String(v).padStart(2,'0')).join(':'):'Unavailable';
 return {callsign:info?.callsign|| (source==='AllStar'&&info?.name?info.name.split(' · ')[0]:'—'),location:info?.location||(rigContacts.get(source)===null?'Looking up node…':'Location unavailable'),duration,node:r.mode+' '+r.target+(rows.length>1?' · +'+(rows.length-1)+' links':'')};
}

// The large dial selects saved destinations only. No input event sends a command.
let rigFavoriteKey=null;
const rigFavoriteIdentity=f=>JSON.stringify([f.mode,f.target,f.network||'',f.source_id||'']);
function rigFavoriteRows(){
 const seen=new Set();
 return favorites.filter(f=>{
  if(!validShortcut(f)||(f.mode==='DMR'&&!['TGIF','BrandMeister'].includes(f.network)))return false;
  const key=rigFavoriteIdentity(f);if(seen.has(key))return false;seen.add(key);return true;
 });
}
function rigFavoriteSelection(){
 const rows=rigFavoriteRows();
 let index=rows.findIndex(f=>rigFavoriteIdentity(f)===rigFavoriteKey);
 if(index<0)index=rows.length?0:-1;
 const item=rows[index];rigFavoriteKey=item?rigFavoriteIdentity(item):null;
 return {rows,index,item};
}
function rigFavoritesMarkup(){return `<div class="rig-main-dial-label">FAVORITES</div><div class="rig-control-slot rig-control-favorites"><div id="rig-favorite-dial" class="radio-knob" role="slider" tabindex="0" aria-label="Favorite destination" aria-describedby="rig-favorite-detail rig-favorite-status"></div><div id="rig-favorite-detail" class="rig-favorite-detail" aria-live="polite"><strong id="rig-favorite-label"></strong><small id="rig-favorite-network"></small><span id="rig-favorite-target"></span></div><button id="rig-favorite-connect" class="rig-hardware-key" type="button">CONNECT</button></div><div class="rig-dial-help">DRAG / WHEEL / ARROWS TO SELECT</div><p id="rig-favorite-status" role="status"></p>`;}
function refreshRigFavorites(){
 const knob=$('rig-favorite-dial');if(!knob)return;
 const {rows,index,item}=rigFavoriteSelection();
 knob.setAttribute('aria-valuemin','0');knob.setAttribute('aria-valuemax',String(Math.max(0,rows.length-1)));
 knob.setAttribute('aria-valuenow',String(Math.max(0,index)));knob.setAttribute('aria-disabled',String(!rows.length));
 knob.tabIndex=rows.length?0:-1;
 knob.style.setProperty('--angle',(-135+(rows.length>1?index/(rows.length-1)*270:0))+'deg');
 const label=item?(item.label||item.note||item.target):'No saved favorites';
 const network=item?item.mode+(item.network?' / '+item.network:''):'';
 knob.setAttribute('aria-valuetext',item?`${label}, ${network}, ${item.target}, ${index+1} of ${rows.length}`:'No valid saved favorites');
 rigSetText('rig-favorite-label',label);rigSetText('rig-favorite-network',network);rigSetText('rig-favorite-target',item?item.target:'Save a destination in Connections.');
 const unavailable=item&&connectionUnavailable(item.mode);
 $('rig-favorite-connect').disabled=!item||busy||!!station.pending||!!station.readonly||!!unavailable;
 rigSetText('rig-favorite-status',!item?'No valid saved destinations.':unavailable?'Destination unavailable. Review Connections.':station.readonly?'Read-only station.':station.pending?'Connection in progress.':'Selected only — press Connect to connect.');
}
function selectRigFavorite(index){
 const {rows}=rigFavoriteSelection();if(!rows.length)return;
 rigFavoriteKey=rigFavoriteIdentity(rows[Math.max(0,Math.min(rows.length-1,Math.round(index)))]);
 refreshRigFavorites();
}
function bindRigFavorites(){
 const knob=$('rig-favorite-dial');if(!knob)return;
 let drag=null;
 knob.onpointerdown=e=>{if(e.button!==0||!rigFavoriteSelection().rows.length)return;e.preventDefault();drag={y:e.clientY,index:rigFavoriteSelection().index};knob.setPointerCapture(e.pointerId);knob.focus();};
 knob.onpointermove=e=>{if(drag)selectRigFavorite(drag.index+Math.round((drag.y-e.clientY)/24));};
 knob.onpointerup=knob.onpointercancel=knob.onlostpointercapture=()=>{drag=null;};
 knob.onkeydown=e=>{const {index,rows}=rigFavoriteSelection(),delta={ArrowUp:1,ArrowRight:1,ArrowDown:-1,ArrowLeft:-1,PageUp:5,PageDown:-5}[e.key];if(delta!==undefined||['Home','End'].includes(e.key)){e.preventDefault();selectRigFavorite(e.key==='Home'?0:e.key==='End'?rows.length-1:index+delta);}else if(e.key==='Enter')e.preventDefault();};
 knob.addEventListener('wheel',e=>{if(document.activeElement!==knob||!e.deltaY)return;e.preventDefault();selectRigFavorite(rigFavoriteSelection().index+(e.deltaY<0?1:-1));},{passive:false});
 $('rig-favorite-connect').onclick=()=>{
  const {item}=rigFavoriteSelection();
  if(busy||station.pending||station.readonly||!validShortcut(item)||connectionUnavailable(item.mode)||(item.mode==='DMR'&&!['TGIF','BrandMeister'].includes(item.network))){refreshRigFavorites();return;}
  action(async()=>{refreshRigFavorites();try{station=await api('/api/command',{action:'connect-network',mode:item.mode,value:item.target,allow_bridge:false,...(item.network?{network:item.network}:{}),...(item.source_id?{source_id:item.source_id}:{})});message('Connection requested.');dashboard();}finally{refreshRigFavorites();}});
 };
 refreshRigFavorites();
}

function rigDialMarkup(key,label){return `<div class="rig-control-slot rig-control-${key}"><label class="slider-label" for="level-${key}">${label}<output id="out-${key}">${Number(runtime.levels?.[key]||0)}</output></label><input id="level-${key}" name="${key}" aria-label="${label}" type="range" min="0" max="999" value="${Number(runtime.levels?.[key]||0)}"></div>`;}
dashboard=function(){
 const enabled=document.documentElement.dataset.layout==='3';document.body.classList.toggle('radio-home',enabled);
 if(!enabled){rigPanel=null;classicDashboard();return;}
 if(!$('transceiver')){
  $('content').innerHTML=`<section id="transceiver" class="transceiver"><div class="rig-topline"><div class="rig-wordmark">ALLMODE<span>NETWORK TRANSCEIVER</span></div><div class="rig-model">AR<span>03</span> <small>STATION CONTROL</small></div></div><form id="audio-form" class="rig-controls-form"><div class="rig-left-controls"><div class="rig-service-light"><i></i><span id="rig-radio-status">RADIO</span></div>${rigDialMarkup('rx','RX GAIN')}${rigDialMarkup('txa','TX A')}${rigDialMarkup('txb','TX B')}<p id="audio-live-result" role="status">Live gain control · saves automatically</p><a class="rig-hardware-key" href="/settings#audio">AUDIO TEST</a><button class="rig-hardware-key" type="button" data-rig-panel="quick">QUICK</button></div><div class="rig-center"><div class="rig-screen-bezel"><div class="rig-screen" id="rig-screen"><div class="rig-screen-status"><button type="button" data-rig-panel="mode" id="rig-mode">MODE</button><span id="rig-call"></span><span id="rig-live-state"></span></div><div class="rig-screen-upper"><div class="rig-frequencies"><button type="button" class="rig-main-frequency" data-rig-panel="frequency"><span class="rig-vfo-label">RX <small>PROGRAMMED · MHz</small></span><strong id="rig-frequency-rx">—</strong><span id="rig-rx-tone"></span></button><button type="button" class="rig-sub-frequency" data-rig-panel="frequency"><span>TX</span><strong id="rig-frequency-tx">—</strong><small>MHz</small></button></div><div id="rig-meter-host"></div><aside class="rig-contact" aria-label="Connected node details"><small id="rig-contact-node">STANDBY</small><strong id="rig-contact-callsign">—</strong><span id="rig-contact-location">No active connection</span><div><small>CONNECTED</small><time id="rig-contact-duration">—</time></div></aside></div><div class="rig-destination"><div><small id="rig-connection-label">NETWORK LINK</small><strong id="rig-destination">Not connected</strong></div><button type="button" data-rig-panel="memory">MEMORY ↗</button></div><div id="rig-map-host"></div><div class="rig-screen-softkeys"><button type="button" data-rig-panel="mode">MODE</button><button type="button" data-rig-panel="memory">MEMORY</button><button type="button" data-rig-panel="audio">METER</button><a href="/connections">CONNECT</a><button type="button" id="rig-disconnect">UNLINK</button></div><div id="rig-overlay" role="dialog" aria-label="Radio controls" hidden></div></div></div><div class="rig-key-row"><button type="button" data-rig-panel="menu">MENU</button><button type="button" data-rig-panel="memory">MEMORY</button><button type="button" data-rig-panel="map">MAP</button><button type="button" data-rig-panel="quick">QUICK</button><button type="button" id="rig-close-key">EXIT</button></div></div><div class="rig-right-controls"><div class="rig-function-bank"><button type="button" data-rig-panel="mode">MODE</button><a href="/settings#dstar">CODEC</a><a href="/hardware">RADIO</a><a href="/schedules">TIMER</a><a href="/connections">LINK</a><button type="button" data-rig-panel="quick">LOCK / DIM</button></div>${rigFavoritesMarkup()}</div></form><div class="rig-chassis-footer"><span>ARA / ALLMODE</span><span id="rig-system-state"></span><span class="rig-chassis-led">LOCAL CONTROL</span></div></section>`;
  for(const k of ['rx','txa','txb'])$('level-'+k).disabled=runtime.radio_enabled!==true||!Number.isFinite(runtime.levels?.[k]);
  bindLiveAudio();decorateRadioKnobs();bindRigFavorites();
  $('transceiver').querySelectorAll('[data-rig-panel]').forEach(b=>b.onclick=()=>rigOpen(b.dataset.rigPanel));
  $('rig-close-key').onclick=rigClose;$('rig-disconnect').onclick=()=>command('disconnect');
  try{document.body.classList.toggle('rig-dimmed',localStorage.getItem('ara.rigDim')==='1');}catch{}
 }
 refreshRigFavorites();
 const radio=schema.workflow?.radio,h=runtime.health||{};
 rigSetText('rig-mode',station.mode||'STANDBY');rigSetText('rig-call',value('station','callsign')||'NODE '+(runtime.node||'—'));
 rigSetText('rig-live-state',station.receiving?'● RX':station.pending?'● LINKING':'● LIVE');
 rigSetText('rig-frequency-rx',radio?.rx||'—');rigSetText('rig-frequency-tx',radio?.tx||'—');rigSetText('rig-rx-tone','CTCSS '+(radio?.rx_ctcss||'—')+' Hz');
 rigSetText('rig-connection-label',station.pending?'CONNECTION IN PROGRESS':station.connected?'CONNECTED / '+station.mode:'NETWORK LINK');
 rigSetText('rig-destination',station.connected?connectionLabel(station):'Not connected');
 if(rigPanel==='connect'){rigSetText('rig-quick-current',station.pending?'Connection change in progress…':station.connected?connectionLabel(station):'Not connected');if($('rig-connect-go'))$('rig-connect-go').disabled=busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode);if($('rig-connect-unlink'))$('rig-connect-unlink').disabled=busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode)||!station.connected;}
 const contact=rigConnectionDetails();for(const field of ['node','callsign','location','duration'])rigSetText('rig-contact-'+field,contact[field]);
 rigSetText('rig-radio-status',runtime.radio_enabled?'RADIO ONLINE':'RADIO STOPPED');
 $('rig-disconnect').disabled=!station.connected||busy||station.pending||station.readonly||connectionUnavailable($('rig-connect-mode')?.value||station.mode);
 const map=radioConnectionMap();if($('rig-map-host').innerHTML!==map)$('rig-map-host').innerHTML=map;
rigSetText('rig-system-state','NODE '+(runtime.node||'-')+' · '+(Number.isFinite(h.cpu_celsius)?(h.cpu_celsius*9/5+32).toFixed(1)+' °F':'Temperature unavailable')+' · '+(h.storage_free_gb==null?'-':h.storage_free_gb+' GB FREE'));
 let cpu=$('rig-cpu-usage');if(!cpu){cpu=document.createElement('span');cpu.id='rig-cpu-usage';$('rig-system-state').after(cpu);}rigSetText('rig-cpu-usage','CPU usage: '+(Number.isFinite(h.cpu_usage_percent)?h.cpu_usage_percent.toFixed(1)+'%':'Unavailable'));
};
document.addEventListener('click',e=>{if(document.documentElement.dataset.layout==='3'&&$('transceiver')&&e.target.closest('.radio-menu')){e.preventDefault();e.stopImmediatePropagation();rigOpen('menu');}},true);
document.addEventListener('keydown',e=>{
 if(!rigPanel||!$('rig-overlay'))return;
 if(e.key==='Escape'){e.preventDefault();rigClose();return;}
 if(e.key==='Tab'){
  const items=[...$('rig-overlay').querySelectorAll('button,a,input,select')].filter(el=>!el.disabled);
  const first=items[0],last=items[items.length-1];
  if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
 }
});

function decorateRadioKnobs(){
 if(document.documentElement.dataset.layout!=='3')return;
 for(const input of document.querySelectorAll('#audio-form input[type="range"]')){
  if(input.previousElementSibling?.classList.contains('radio-knob'))continue;
  const knob=document.createElement('div');knob.className='radio-knob';knob.tabIndex=0;knob.setAttribute('role','slider');
  knob.setAttribute('aria-label',input.name==='rx'?'Receive level':input.name==='txa'?'Transmit A level':'Transmit B level');
  knob.setAttribute('aria-valuemin',input.min);knob.setAttribute('aria-valuemax',input.max);
  const label=input.previousElementSibling;
  const wrap=document.createElement('div');wrap.className='radio-dial-control';
  input.before(wrap);if(label?.tagName==='LABEL')wrap.append(label);wrap.append(knob,input);
  const paint=()=>{knob.style.setProperty('--angle',(-135+Number(input.value)/999*270)+'deg');knob.setAttribute('aria-valuenow',input.value);};
  const change=v=>{if(input.disabled||document.body?.classList.contains('rig-locked'))return;input.value=String(Math.max(Number(input.min),Math.min(Number(input.max),Math.round(v))));input.dispatchEvent(new Event('input',{bubbles:true}));paint();};
  let drag=null;
  knob.onpointerdown=e=>{if(e.button!==0||input.disabled||document.body?.classList.contains('rig-locked'))return;e.preventDefault();drag={y:e.clientY,value:Number(input.value)};knob.setPointerCapture(e.pointerId);knob.focus();};
  knob.onpointermove=e=>{if(drag)change(drag.value+(drag.y-e.clientY)*5);};
  knob.onpointerup=knob.onpointercancel=knob.onlostpointercapture=()=>{drag=null;};
  knob.onkeydown=e=>{const delta={ArrowUp:5,ArrowRight:5,ArrowDown:-5,ArrowLeft:-5,PageUp:50,PageDown:-50}[e.key];if(delta!==undefined||['Home','End'].includes(e.key)){e.preventDefault();change(e.key==='Home'?0:e.key==='End'?999:Number(input.value)+delta);}};
  knob.addEventListener('wheel',e=>{if(document.activeElement!==knob)return;e.preventDefault();change(Number(input.value)+(e.deltaY<0?1:-1)*(e.shiftKey?25:2));},{passive:false});
  input.addEventListener('input',paint);paint();
 }
}
document.addEventListener('allmode-layout-change',()=>{if(path==='/'&&schema.workflow)dashboard();decorateRadioKnobs();});
new MutationObserver(decorateRadioKnobs).observe($('content'),{childList:true,subtree:true});

(() => {
  let choice='2';
  try { choice=localStorage.getItem('ara.layout')||'2'; } catch {}
  if(!['1','2','3'].includes(choice))choice='2';
  document.documentElement.dataset.layout=choice;
  document.addEventListener('DOMContentLoaded',()=>{
    const nav=document.getElementById('navigation'),header=document.querySelector('.mast');
    if(!nav||!header)return;
    const original=nav.innerHTML;
    const picker=document.createElement('label');picker.className='layout-picker';
    picker.innerHTML='Layout<select aria-label="Page layout"><option value="1">Layout 1 · Original</option><option value="2">Layout 2 · Sidebar</option><option value="3">Layout 3 · Radio</option></select>';
    header.append(picker);picker.querySelector('select').value=choice;
    const links=[['Overview','/'],['Connections','/connections'],['Audio','/settings#audio'],['Digital codec','/settings#dstar'],['Schedules','/schedules'],['Radio settings','/hardware'],['Ethernet & Wi-Fi','/network'],['Station settings','/settings'],['Digital identities','/settings#other'],['Profiles & backups','/profiles'],['Logs','/logs'],['Airtime','/airtime'],['System & maintenance','/admin']];
    const menu=document.createElement('button');menu.className='radio-menu secondary';menu.textContent='MENU';menu.setAttribute('aria-expanded','false');header.append(menu);
    menu.onclick=()=>{const opened=document.body.classList.toggle('menu-open');menu.setAttribute('aria-expanded',String(opened));};
    function select(){
      const setup=nav.querySelector('#setup-link');
      const hidden=setup?setup.hidden:true;
      document.documentElement.dataset.layout=choice;
      nav.innerHTML=choice==='1'?original:links.map(([label,href])=>`<a href="${href}">${label}</a>`).join('')+'<a href="/setup" id="setup-link">Finish setup</a>';
      if(nav.querySelector('#setup-link'))nav.querySelector('#setup-link').hidden=hidden;
      for(const a of nav.querySelectorAll('a')){a.removeAttribute('aria-current');if(a.pathname===location.pathname&&a.hash===location.hash)a.setAttribute('aria-current','page');}
      document.body.classList.remove('menu-open');menu.setAttribute('aria-expanded','false');
      document.dispatchEvent(new Event('allmode-layout-change'));
    }
    picker.querySelector('select').onchange=e=>{choice=e.target.value;try{localStorage.setItem('ara.layout',choice);}catch{}select();};
    window.addEventListener('hashchange',select);select();
  });
})();
