const $ = id => document.getElementById(id);
let state, busy = false, favorites = [];
let audioDirty=false;
let audioMode=null;
let reflectorListKey='';
let audioListKey='';
let destinations={}, bridgeDraft=false, bridgeRowsKey='';
let currentView='console';
const viewTitles={console:'Radio console',destinations:'Your destinations',setup:'Node setup',activity:'Activity log'};
function showView(view) {
  currentView=view;
  if(view==='setup') loadSetup();
  document.querySelectorAll('[data-page]').forEach(el=>el.hidden=el.dataset.page!==view);
  document.querySelectorAll('[data-view]').forEach(el=>{el.classList.toggle('active',el.dataset.view===view);el.setAttribute('aria-current',el.dataset.view===view?'page':'false');});
  document.querySelector('h1').textContent=viewTitles[view];
}
document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>showView(el.dataset.view));
showView(currentView);
document.querySelectorAll('main button,main input').forEach(el=>el.disabled=true);
try { const saved = JSON.parse(localStorage.getItem('allmode.favorites') || '[]'); if (Array.isArray(saved)) favorites = saved.filter(f => f && typeof f.mode === 'string' && typeof f.target === 'string').slice(0, 20); } catch {}
const hints = {AllStar:'AllStar node number',EchoLink:'Station callsign or node ID',DMR:'Talkgroup number',YSF:'Reflector ID',NXDN:'Reflector ID',P25:'Reflector ID',M17:'Reflector and module', 'D-STAR':'Reflector and module (REF030C, DCS001C or XLX681A)'};
async function api(action, value) {
  const response = await fetch(action ? './api/command' : './api/status', action ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,value})} : {});
  const data = await response.json();
  if (response.status === 401) { location.href='/login'; throw new Error('Session expired.'); }
  if (!response.ok) throw new Error(data.error || 'Controller unavailable.');
  return data;
}
function render() {
  renderBridge();
  renderDestinationList();
  document.querySelectorAll('[data-view]').forEach(el=>el.disabled=false);
  $('audio-panel').hidden=state.simulation;
  if(!audioMode)audioMode=state.audio_modes?.[state.mode]?state.mode:'DMR';
  const audioModes=Object.keys(state.audio_modes || {});
  if(audioListKey!==audioModes.join(',')){
    audioListKey=audioModes.join(',');
    $('audio-mode').replaceChildren(...audioModes.map(mode=>{const option=document.createElement('option');option.value=mode;option.textContent=mode;return option;}));
  }
  $('audio-mode').value=audioMode;
  if(state.audio_modes?.[audioMode] && !audioDirty) {
    $('receive-gain').value=state.audio_modes[audioMode].receive;
    $('transmit-gain').value=state.audio_modes[audioMode].transmit;
    audioLabels();
  }
  ['audio-mode','receive-gain','transmit-gain','audio-apply','audio-reset'].forEach(id=>$(id).disabled=busy || !audioModes.length);
  document.querySelector('.badge').textContent=state.simulation?'SIMULATION':'LIVE STATUS';
  document.querySelector('.notice').textContent=state.simulation?'Preview environment · Connections are simulated. No RF or network audio is transmitted.':`SHARI node ${state.node} · Live AllStar status. AllStar and ${state.dmr_network || 'TGIF'} radio controls.`;
  document.querySelector('.aside-note').firstChild.textContent='SHARI HAT';
  $('connection').textContent = state.connected ? `${state.mode} / ${state.target}` : 'Ready when you are';
  if(state.pending) $('connection').textContent=state.phase==='connecting'?'Connecting…':'Disconnecting…';
  const rssi=state.rssi?.value;
  const signal=document.querySelector('.signal');
  signal.querySelector('small').textContent=state.simulation?'RF OFF':Number.isInteger(rssi)?`RSSI ${rssi} · ${state.receiving?'RX':'IDLE'}`:state.receiving?'RF RX':'RF IDLE';
  signal.title=Number.isInteger(rssi)?'Live relative RSSI from the radio; not calibrated dBm.':'RSSI unavailable';
  signal.querySelectorAll('span').forEach((bar,i)=>{bar.style.background=state.receiving && Number.isInteger(rssi) && rssi>=[0,30,60,90,120][i]?'var(--accent)':'#526247';});
  $('description').textContent = !state.simulation ? `Node ${state.node} · ${state.system} · ${state.receiving?'Receiving RF':'No incoming RF'}` : state.connected ? 'Simulated connection active · RF remains disabled' : `${state.mode} selected · No active connection`;
  $('modes').replaceChildren(...state.modes.map(mode => {
    const button = document.createElement('button'); button.textContent = mode;
    button.className = state.mode === mode ? 'selected' : '';
    button.setAttribute('aria-pressed', String(state.mode === mode));
    button.disabled = state.readonly || state.pending || state.connected || state.bridge_enabled || busy;
    button.onclick = () => command('mode', mode); return button;
  }));
  Object.entries(state.unavailable_modes || {}).forEach(([mode,reason])=>{
    const button=document.createElement('button');button.textContent=mode;button.disabled=true;button.title=reason;button.setAttribute('aria-label',mode+': '+reason);$('modes').append(button);
  });
  $('mode-notes').textContent=Object.entries(state.unavailable_modes || {}).map(([mode,reason])=>mode+': '+reason).join(' · ');
  if(state.bridge_error)$('feedback').textContent=state.bridge_error;
  else if(state.connected && !state.pending)$('feedback').textContent='Connected.';
  else if(state.pending)$('feedback').textContent='Waiting for connection confirmation…';
  else if(['Connected.','Waiting for connection confirmation…','Request sent; waiting for node confirmation.','D-STAR reflector connection lost. Radio link disconnected.'].includes($('feedback').textContent))$('feedback').textContent='';
  $('target-help').textContent = state.mode==='FCS'?'FCS room (e.g. 00120)':hints[state.mode] || 'Destination';
  if(!state.simulation && state.mode==='DMR') $('target-help').textContent=(state.dmr_network || 'TGIF')+' talkgroup number';
  $('target').inputMode=state.mode==='D-STAR'?'text':'numeric';
  $('target').disabled = state.connected || state.pending || busy;
  $('connect').disabled = state.readonly || state.pending || state.connected || state.pending || busy;
  $('disconnect').disabled = state.readonly || !state.connected || state.pending || busy || state.bridge_enabled;
  $('save').disabled = busy;
  $('events').replaceChildren(...state.events.map(event => {
    const li = document.createElement('li'), time = document.createElement('time'), message = document.createElement('span');
    time.dateTime = event.time; time.textContent = new Date(event.time).toLocaleTimeString();
    message.textContent = event.message; li.append(time,message); return li;
  }));
  renderFavorites();
}
function renderFavorites() {
  $('favorites').replaceChildren();
  if (!favorites.length) { const p = document.createElement('p'); p.className='empty'; p.textContent='No destinations saved yet.'; $('favorites').append(p); }
  favorites.forEach((favorite, index) => {
    const row=document.createElement('div'), label=document.createElement('div'), small=document.createElement('small'), use=document.createElement('button'), remove=document.createElement('button');
    row.className='favorite'; label.textContent=favorite.target; small.textContent=favorite.mode; label.append(small);
    use.textContent='Select'; use.disabled=state.readonly || busy || state.connected;
    use.onclick=async () => { if (await command('mode',favorite.mode)) { $('target').value=favorite.target; showView('console'); } };
    remove.textContent='×'; remove.setAttribute('aria-label',`Remove ${favorite.target}`);
    remove.onclick=()=>{favorites.splice(index,1); persist(); renderFavorites();}; row.append(label,use,remove); $('favorites').append(row);
  });
}
function persist() { try { localStorage.setItem('allmode.favorites',JSON.stringify(favorites)); } catch { $('feedback').textContent='Browser storage unavailable; favorites last for this session only.'; } }
async function command(action,value) {
  if (busy) return false;
  busy=true; render();
  try { state=await api(action,value); $('feedback').textContent=action==='connect'?(state.simulation?'Simulated connection established.':'Request sent; waiting for node confirmation.'):'Console updated.'; return true; }
  catch(error) { $('feedback').textContent=error.message; return false; }
  finally { busy=false; render(); }
}
$('connect-form').onsubmit=event=>{event.preventDefault(); command('connect',$('target').value.trim());};
$('disconnect').onclick=()=>command('disconnect');
$('save').onclick=()=>{
  const target=(state.target || $('target').value).trim();
  if (!target) { $('feedback').textContent='Enter a destination first.'; return; }
  if (favorites.length>=20) { $('feedback').textContent='Maximum 20 favorites. Remove one first.'; return; }
  if (!favorites.some(f=>f.mode===state.mode && f.target===target)) favorites.push({mode:state.mode,target});
  persist(); renderFavorites();
};
async function refresh() { if (busy) return; try { state=await api(); render(); } catch { $('connection').textContent='Controller offline'; $('description').textContent='Restart the local service to continue.'; document.querySelectorAll('main button,main input').forEach(el=>el.disabled=true); } }
fetch('./api/destinations').then(r=>r.json()).then(data=>{destinations=data;bridgeRowsKey="";if(state){renderDestinationList();renderBridge();}}).catch(()=>{});
refresh(); setInterval(refresh,3000);

function audioLabels() {
  $('receive-value').textContent=Number($('receive-gain').value).toFixed(2)+'×';
  $('transmit-value').textContent=Number($('transmit-gain').value).toFixed(2)+'×';
}
['receive-gain','transmit-gain'].forEach(id=>$(id).oninput=()=>{audioDirty=true;audioLabels();});
async function saveAudio(values) {
  const saved=await command('audio',{mode:audioMode,...values});
  $('audio-feedback').textContent=saved?audioMode+' levels saved'+(state.digital_health?.[audioMode]?.ready?' and applied.':'; applied on next connection.'):'Audio settings were not applied; see the controller message above.';
  if(saved) {audioDirty=false;render();}
}
$('audio-form').onsubmit=event=>{event.preventDefault();saveAudio({receive:Number($('receive-gain').value),transmit:Number($('transmit-gain').value)});};
$('audio-reset').onclick=()=>saveAudio({receive:1,transmit:1});
$('audio-mode').onchange=()=>{audioMode=$('audio-mode').value;audioDirty=false;$('audio-feedback').textContent='';render();};



let setupLoaded=false;
async function loadSetup(force=false) {
  if(setupLoaded && !force) return;
  const container=$('setup-sections');
  try {
    const response=await fetch('./api/setup');
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'Settings unavailable.');
    container.replaceChildren();
    if (!data.groups.length) {
      const note=document.createElement('p');
      note.textContent='Hardware commissioning is available now. Live AllStar node and network account setup has not been completed. Console connections are simulated.';
      const link=document.createElement('a');link.className='setup-link';link.href='/setup';link.textContent='Open first-run station and network setup →';
      container.append(note,link);
    }
    const setupOrder=['allstar','radio','usb-options','usb','dmr','echolink'];
    const titles={'allstar':'1. Node setup','radio':'2. Radio frequency and tone','usb-options':'3. Radio options','usb':'4. AllStar radio audio','dmr':'5. DMR account','echolink':'6. EchoLink account'};
    data.groups.sort((a,b)=>setupOrder.indexOf(a.id)-setupOrder.indexOf(b.id)).forEach(group=>{
      const details=document.createElement('details');details.className='setup-section panel';details.id='setup-'+group.id;
      const summary=document.createElement('summary');summary.textContent=titles[group.id] || group.title;details.append(summary);
      const form=document.createElement('form');
      if(group.id==='radio') {
        const note=document.createElement('p');note.className='hint';note.textContent='Enter the frequency for your installed VHF or UHF module. Bandwidth: 0 = narrow, 1 = wide. Current radio settings cannot be read back; only settings saved here are shown.';form.append(note);
      }
      if(group.id==='dmr') {
        const note=document.createElement('p');note.className='hint';note.textContent='Choose TGIF or BrandMeister. Timeslot: 2. Use hotspot passwords, not website passwords. Blank passwords keep the saved value for each network. Saving restarts the digital bridge.';form.append(note);
      }
      if(group.id==='usb-options'){const note=document.createElement('p');note.className='hint';note.textContent='Saving restarts the radio service. Keep the current settings unless you are correcting wiring or audio filtering.';form.append(note);}
      if(group.id==='echolink') {
        const note=document.createElement('p');note.className='hint';note.textContent='Enter your validated EchoLink account. Save configures and loads EchoLink. Leave the password blank to keep it.';form.append(note);
      }
      const inputs={};
      group.fields.forEach(field=>{
        const row=document.createElement('label');row.className='setting-input';
        const caption=document.createElement('span');caption.textContent=field.label;
        const input=document.createElement(field.type==='choice'?'select':'input');input.name=field.key;
        if(field.type==='choice')field.limits.forEach(value=>{const option=document.createElement('option');option.value=value;option.textContent=value;input.append(option);});
        if(field.type!=='choice') input.type=field.type==='bool'?'checkbox':field.type==='password'?'password':['int','frequency','tone'].includes(field.type)?'number':'text';
        if(input.type==='checkbox')input.checked=field.value;else input.value=field.value;
        if(field.limits && field.type!=='choice'){input.min=field.limits[0];input.max=field.limits[1];}
        if(field.type==='frequency'||field.type==='tone')input.step='any';
        if(field.type==='password'){input.placeholder='Unchanged';input.autocomplete='new-password';}
        else if(input.type!=='checkbox')input.required=true;
        row.append(caption,input);form.append(row);inputs[field.key]=input;
      });
      const save=document.createElement('button');save.textContent=group.id==='usb'?'Save AllStar radio audio':'Save '+group.title.replace(' setup','').toLowerCase();save.className='secondary';
      const feedback=document.createElement('p');feedback.className='hint';feedback.setAttribute('role','status');
      form.append(save,feedback);
      form.onsubmit=async event=>{
        event.preventDefault();
        const values={};group.fields.forEach(field=>{const el=inputs[field.key];values[field.key]=field.type==='bool'?el.checked:el.value;});
        Array.from(form.elements).forEach(el=>el.disabled=true);
        const ok=await command('setup',{group:group.id,values});
        if(ok && group.id==='radio') updateRadioSummary(values);
        feedback.textContent=ok?(group.id==='usb-options'?'Saved. Radio service is restarting.':group.id==='dmr'?'Saved. Digital bridge is restarting.':'Saved. Settings are now applied.'):$('feedback').textContent;
        Object.values(inputs).forEach(input=>{if(input.type==='password')input.value='';});
        Array.from(form.elements).forEach(el=>el.disabled=false);
      };
      details.append(form);container.append(details);
    });
    const details=document.createElement('details');details.className='setup-section panel';
    const title=document.createElement('summary');title.textContent='System information';details.append(title);
    const radioGroup=data.groups.find(group=>group.id==='radio');
    const savedRadio=Object.fromEntries((radioGroup?.fields || []).map(field=>[field.key,field.value]));
    Object.entries({...data.system,...data.radio}).forEach(([key,value])=>{
      const row=document.createElement('div');row.className='setting-row';const label=document.createElement('span'),val=document.createElement('strong');label.textContent=key;val.textContent=value;
      if(key==='Frequency and tone'){
        val.id='radio-summary';
        const link=document.createElement('a');link.className='setup-link';link.href='#setup-radio';link.textContent='Set frequency and tone ›';
        link.onclick=()=>{const radio=$('setup-radio');if(radio)radio.open=true;};
        row.append(label,val,link);
      } else row.append(label,val);
      details.append(row);
    });container.append(details);updateRadioSummary(savedRadio);setupLoaded=true;
  } catch(error){container.textContent=error.message;setupLoaded=false;}
}

function updateRadioSummary(values) {
  const summary=$('radio-summary');if(!summary)return;
  summary.textContent=values.frequency?`${values.frequency} MHz · ${Number(values.tone)===0?'No tone':values.tone+' Hz'} · Last saved here`:'Not saved here yet';
}

function renderDestinationList() {
  const rows=destinations[state.mode] || [];
  $('target').placeholder=state.mode==='D-STAR'?'e.g. REF030C — change the final letter for the module':state.mode==='FCS'?'e.g. 00120':'Enter a destination';
  const key=state.mode+JSON.stringify(rows);
  const select=$('reflector-select');select.hidden=!rows.length;select.disabled=state.connected || state.pending || busy;
  if(key===reflectorListKey)return;
  reflectorListKey=key;
  $('destination-list').replaceChildren(...rows.map(row=>{const option=document.createElement('option');option.value=row.target;option.label=row.name;return option;}));
  const prompt=document.createElement('option');prompt.value='';prompt.textContent='Choose a reflector…';
  select.replaceChildren(prompt,...rows.map(row=>{const option=document.createElement('option');option.value=row.target;option.textContent=row.target+' · '+row.name;return option;}));
}
$('reflector-select').onchange=()=>{if($('reflector-select').value)$('target').value=$('reflector-select').value;};
function renderBridge() {
  if(state.simulation){document.querySelector('.bridge-panel').hidden=true;return;}
  const modes=state.modes;
  const key=modes.join(',');
  if(key!==bridgeRowsKey){
    bridgeRowsKey=key;$('bridge-selections').replaceChildren();
    modes.forEach(mode=>{
      const row=document.createElement('label');row.className='bridge-selection';row.dataset.mode=mode;
      const check=document.createElement('input');check.type='checkbox';check.className='bridge-select';check.setAttribute('aria-label','Include '+mode);
      const label=document.createElement('span');label.textContent=mode;
      const input=document.createElement('input');input.className='bridge-target';input.placeholder=mode==='FCS'?'Room (00120)':'Destination';input.setAttribute('aria-label',mode+' destination');input.inputMode=mode==='D-STAR'?'text':'numeric';
      if(mode==='DMR')input.value=state.mode==='DMR' && state.target?state.target:'30410';
      check.onchange=()=>input.required=check.checked;
      const list=document.createElement('datalist');list.id='bridge-list-'+mode;input.setAttribute('list',list.id);
      list.replaceChildren(...(destinations[mode] || []).map(destination=>{const option=document.createElement('option');option.value=destination.target;option.label=destination.name;return option;}));
      row.append(check,label,input,list);$('bridge-selections').append(row);
    });
  }
  $('bridge-override').disabled=busy;
  $('bridge-override').checked=state.bridge_enabled || bridgeDraft;
  $('bridge-controls').hidden=!$('bridge-override').checked;
  $('bridge-start').disabled=busy || state.pending || state.connected || state.bridge_enabled;
  $('bridge-stop').hidden=!(state.bridge_enabled || state.pending);
  $('bridge-stop').disabled=busy;
  $('bridge-stop').textContent=state.bridge_enabled?'Stop bridge':'Cancel connection';
  $('bridge-links').replaceChildren(...(state.active_connections || []).map(row=>{const line=document.createElement('p');line.textContent=row.mode+' → '+row.target+' · '+(row.network_status || 'Radio linked');return line;}));
  if(state.bridge_error)$('bridge-feedback').textContent=state.bridge_error;
  else if(state.bridge_enabled)$('bridge-feedback').textContent=state.pending?'Starting bridge…':'Bridge enabled. Incoming audio is forwarded between selected connections.';
  else $('bridge-feedback').textContent='';
}
$('bridge-override').onchange=async()=>{
  bridgeDraft=$('bridge-override').checked;
  if(!bridgeDraft && (state.bridge_enabled || state.pending)){await command('stop-bridge');$('bridge-feedback').textContent='Bridge stopped.';}
  renderBridge();
};
$('bridge-form').onsubmit=async event=>{
  event.preventDefault();
  const connections=Array.from(document.querySelectorAll('.bridge-selection')).filter(row=>row.querySelector('.bridge-select').checked).map(row=>({mode:row.dataset.mode,target:row.querySelector('.bridge-target').value.trim()}));
  const ok=await command('bridge',{enabled:true,connections});
  if(!ok)$('bridge-feedback').textContent=$('feedback').textContent;
};
$('bridge-stop').onclick=async()=>{bridgeDraft=false;await command('stop-bridge');$('bridge-feedback').textContent='Bridge stopped.';renderBridge();};

