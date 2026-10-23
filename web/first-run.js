'use strict';
let schema, current, dirty=false, busy=false;
const $=id=>document.getElementById(id);
const order=['station','networks','radio','review','audio'];
const groupNames={station:'Station identity',allstar:'AllStar',echolink:'EchoLink',dmr:'DMR identity',brandmeister:'BrandMeister',tgif:'TGIF',dstar:'D-STAR external AMBE audio',other:'Other digital networks'};
async function request(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});if(r.status===401){location.href='/login';throw Error('Sign in required.');}const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed.');return d;}
function message(text){$('feedback').textContent=text;}
function isAvailable(step){return schema.workflow.steps.find(s=>s.id===step)?.available;}
function fieldValue(group,key){return schema.groups.find(g=>g.id===group)?.fields.find(f=>f.key===key)?.value;}
function displayFields(){const root=$('groups');root.replaceChildren();for(const g of schema.groups.filter(g=>current==='station'?g.id==='station':g.id!=='station')){
 const box=document.createElement(g.id==='other'?'details':'div');box.className='setup-group';
 const title=document.createElement(g.id==='other'?'summary':'h3');title.textContent=groupNames[g.id];box.append(title);
 if(g.id==='other'){const hint=document.createElement('p');hint.textContent='Optional preferences only. These do not install a bridge or activate a mode.';box.append(hint);}
 const grid=document.createElement('div');grid.className='grid';
 for(const f of g.fields){const label=document.createElement('label');label.textContent=f.label;const input=document.createElement('input');input.type=f.type;input.name=g.id+'.'+f.key;input.autocomplete=f.type==='password'?'new-password':'off';
 if(f.type==='checkbox'){input.checked=f.value;label.className='check';input.addEventListener('change',()=>toggleGroup(box));}else input.value=f.value;
 if(f.type==='number'){input.min=g.id==='dstar'?1:0;input.max=g.id==='dstar'?65535:15;input.step=1;}
 if(g.id==='station'&&f.key==='callsign')input.required=true;
 if(f.type==='password'&&f.saved)input.placeholder='Saved — leave blank to keep';
 label.append(input);grid.append(label);}
 box.append(grid);root.append(box);toggleGroup(box);
 }
}
function toggleGroup(box){const enabled=box.querySelector('input[type=checkbox]');if(enabled)for(const input of box.querySelectorAll('input:not([type=checkbox])')){input.disabled=!enabled.checked;input.parentElement.hidden=!enabled.checked;}}
function renderSummary(){const dl=$('summary');dl.replaceChildren();const rows=[['Station',fieldValue('station','callsign')||'Not saved']];for(const g of ['allstar','echolink','brandmeister','tgif','dstar'])rows.push([groupNames[g],fieldValue(g,'enabled')?(schema.workflow.applied?'Applied':'Saved — apply required'):'Off']);const s=schema.workflow.radio;rows.push(['Radio',s?`RX ${s.rx} / TX ${s.tx} MHz; RX tone ${s.rx_ctcss}, TX tone ${s.tx_ctcss}. Acknowledged, not RF verified.`:'Programming incomplete']);for(const [label,value]of rows){const dt=document.createElement('dt');dt.textContent=label;const dd=document.createElement('dd');dd.textContent=value;dl.append(dt,dd);}const list=$('blockers');list.replaceChildren();for(const item of schema.workflow.blockers){const li=document.createElement('li');li.textContent=item;list.append(li);}}
function show(step,focus=true){if(busy||!isAvailable(step))return;if(dirty){message('Save this step before leaving so your changes are kept.');return;}current=step;sessionStorage.setItem('allmode.setup.step',step);
 const steps=$('steps');steps.replaceChildren();schema.workflow.steps.forEach((s,i)=>{const li=document.createElement('li');const b=document.createElement('button');b.type='button';b.textContent=`${i+1}. ${s.title} · ${s.complete?'Saved':s.available?'Pending':'Locked'}`;b.disabled=!s.available||busy;if(step===s.id)b.setAttribute('aria-current','step');b.onclick=()=>show(s.id);li.append(b);steps.append(li);});
 $('onboarding').hidden=!['station','networks'].includes(step);for(const id of ['radio','review','audio'])$(id+'-step').hidden=step!==id;
 $('back').disabled=step==='station'||busy;$('review-link').disabled=!isAvailable('review')||busy;
 if(step==='station'||step==='networks'){$('step-title').textContent=step==='station'?'1. Your station':'2. Choose your networks';$('step-help').textContent=step==='station'?'Start with your callsign. Your network credentials come next.':'Turn on only the networks you plan to use. Disabled networks do not require credentials. Saving a choice does not activate it.';displayFields();}
 const s=schema.workflow.radio;$('radio').textContent=s?`Last acknowledged write: RX ${s.rx} / TX ${s.tx} MHz; RX tone ${s.rx_ctcss}, TX tone ${s.tx_ctcss}. ${schema.workflow.radio_note}`:'No complete programming record yet. A saved draft alone does not complete this step.';
 $('radio-next').disabled=!schema.workflow.radio;$('review-next').disabled=!isAvailable('audio');renderSummary();renderRuntime();$('progress-note').textContent='Service status is checked on the Pi. RF and audio verification require your radio.';
 if(focus)document.querySelector(step==='station'||step==='networks'?'#step-title':`#${step}-step h2`).focus();
}
async function load(){schema=await request('/api/onboarding');const remembered=location.hash.slice(1)||sessionStorage.getItem('allmode.setup.step');show(isAvailable(remembered)?remembered:schema.workflow.next_step,false);}
$('onboarding').addEventListener('input',()=>{dirty=true;});
$('onboarding').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;$('save').disabled=true;try{const values={};for(const g of schema.groups.filter(g=>current==='station'?g.id==='station':g.id!=='station')){values[g.id]={};for(const f of g.fields){const input=e.target.elements.namedItem(g.id+'.'+f.key);values[g.id][f.key]=f.type==='checkbox'?input.checked:f.type==='number'?Number(input.value):input.value;}}const next=current==='station'?'networks':'radio';schema=await request('/api/onboarding',{section:current,values});dirty=false;busy=false;message('Saved privately. No services were started.');show(next);}catch(error){message(error.message);}finally{busy=false;$('save').disabled=false;}};
$('back').onclick=()=>show(order.slice(0,order.indexOf(current)).filter(isAvailable).at(-1));$('review-link').onclick=()=>show('review');$('radio-next').onclick=()=>show('review');$('review-next').onclick=()=>show('audio');$('audio-next').onclick=()=>show('review');
$('refresh-radio').onclick=async()=>{try{schema=await request('/api/onboarding');show('radio');message(schema.workflow.radio?'All four programming commands were acknowledged. Continue to Review and Apply.':'Programming is not complete. Open radio configuration to continue.');}catch(e){message(e.message);}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
load().catch(e=>message(e.message));

function renderRuntime(){$('audio-draft-status').textContent='Showing applied levels.';renderChangeState();renderHealth();const r=schema.workflow.runtime||{};const applied=schema.workflow.applied;const text=!r.available?'System management unavailable.':!r.applied?'No live configuration applied yet.':`${r.active?'Asterisk running':'Maintenance'} · node ${r.node} · AllStar ${r.registration} · radio ${r.radio_enabled?'enabled':'disconnected'}`;$('system-status').textContent=text;$('radio-runtime').textContent=text;$('apply-system').disabled=!r.available;$('test-ambe').disabled=!r.available||!fieldValue('dstar','enabled');$('start-radio').disabled=!applied||!schema.workflow.radio||r.radio_enabled;$('apply-audio').disabled=!r.radio_enabled;$('confirm-audio').disabled=!r.radio_enabled;for(const [id,key]of [['rx-level','rx'],['txa-level','txa'],['txb-level','txb']])$(id).value=r.levels?.[key]??({rx:650,txa:600,txb:500}[key]);$('restore-audio').disabled=!r.levels;}
async function systemAction(action,extra={}){if(busy||dirty){message('Save changes before performing a system action.');return;}busy=true;for(const b of document.querySelectorAll('main button'))b.disabled=true;message('Working on the Pi…');try{const result=await request('/api/system',{action,...extra});schema=await request('/api/onboarding');busy=false;show(isAvailable(current)?current:schema.workflow.next_step);message(result.message||'System operation completed. Live status refreshed.');}catch(e){message(e.message);}finally{busy=false;const text=$('feedback').textContent;show(isAvailable(current)?current:schema.workflow.next_step,false);message(text);}}
$('apply-system').onclick=()=>systemAction('apply');$('maintenance').onclick=()=>systemAction('maintenance');$('test-ambe').onclick=()=>systemAction('test-ambe');
$('start-radio').onclick=()=>{if(!$('rf-ready').checked){message('Confirm the radio settings and RF load first.');return;}systemAction('activate',{confirm:'ACTIVATE'});};
$('apply-audio').onclick=()=>systemAction('audio',{levels:{rx:Number($('rx-level').value),txa:Number($('txa-level').value),txb:Number($('txb-level').value)}});
$('confirm-audio').onclick=()=>{if(!$('audio-checked').checked){message('Complete the physical receive/transmit audio check first.');return;}systemAction('audio-confirm',{checked:true});};
$('refresh-system').onclick=async()=>{try{schema=await request('/api/onboarding');show(current);message('Live status refreshed.');}catch(e){message(e.message);}};

addEventListener('hashchange',()=>{const step=location.hash.slice(1);if(isAvailable(step))show(step);else message('Complete the earlier setup steps to open '+step+'.');});

addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});

function renderChangeState(){ $('change-state').textContent=dirty?'Unsaved changes':schema.workflow.applied?'Saved and applied':'Saved — Apply required';$('cancel-edit').disabled=!dirty; }
function renderHealth(){const h=schema.workflow.runtime?.health||{};const rows={'CPU temperature':h.cpu_celsius==null?'Unavailable':h.cpu_celsius+' °C','Storage':h.storage_free_gb==null?'Unavailable':h.storage_free_gb+' GB free · '+h.storage_used_percent+'% used','Uptime':h.uptime_seconds==null?'Unavailable':Math.floor(h.uptime_seconds/3600)+' h '+Math.floor(h.uptime_seconds%3600/60)+' min','Kernel':h.kernel||'Unavailable'};const root=$('system-health');root.replaceChildren();for(const [key,value]of Object.entries(rows)){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=key;dd.textContent=value;root.append(dt,dd);}}
$('onboarding').addEventListener('input',renderChangeState);
$('cancel-edit').onclick=()=>{dirty=false;show(current);message('Unsaved edits discarded. Saved settings restored.');};
function audioDraft(){ $('audio-draft-status').textContent='Edited levels — press Apply audio levels to use them.'; }
for(const id of ['rx-level','txa-level','txb-level']){const input=$(id);const controls=document.createElement('span');controls.className='level-controls';input.after(controls);for(const [symbol,delta]of [['−',-10],['+',10]]){const button=document.createElement('button');button.type='button';button.textContent=symbol;button.setAttribute('aria-label',(delta<0?'Decrease ':'Increase ')+id+' by 10');button.onclick=()=>{input.value=Math.max(0,Math.min(999,Number(input.value)+delta));audioDraft();};controls.append(button);}input.addEventListener('input',audioDraft);}
$('restore-audio').onclick=()=>{renderRuntime();$('audio-draft-status').textContent='Applied levels restored in the form. No service change.';};
$('baseline-audio').onclick=()=>{for(const [id,value]of [['rx-level',650],['txa-level',600],['txb-level',500]])$(id).value=value;audioDraft();};
