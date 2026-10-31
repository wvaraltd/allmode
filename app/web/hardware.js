'use strict';
const $ = id => document.getElementById(id);
const form = $('settings');
let state, reviewed = null;
const settings = () => Object.fromEntries([...form.elements].filter(e => e.name).map(e => [e.name, e.type === 'checkbox' ? e.checked : ['bandwidth','volume','squelch'].includes(e.name) ? Number(e.value) : e.value]));
function invalidate() { reviewed = null; $('program').disabled = true; $('confirm').value = ''; }
function fill(values) { if (!values) throw Error('No saved draft exists.'); for (const [k,v] of Object.entries(values)) { const e = form.elements.namedItem(k); if (e.type === 'checkbox') e.checked = v; else e.value = v; } invalidate(); }
async function api(body) { const response = await fetch('./api/hardware', body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {}); const result = await response.json(); if(response.status===401){location.href="/login";throw Error("Session expired.");} if (!response.ok) throw Error(result.error || 'Request failed'); return result; }
function render(s) { state=s; $('port-help').textContent=s.uart_reboot_required===true?'The installer changed GPIO serial settings during this boot. Reboot the Pi, reopen this page, then select Refresh ports. Your saved draft is retained.':s.uart_reboot_required===null?'UART reboot status could not be checked. If you have not rebooted since installation, reboot before testing the GPIO connection. Otherwise select Refresh ports.':s.ports.length?'Select the connected SHARI port, then test the connection.':'No serial ports detected. For a GPIO SHARI, enable serial hardware, disable serial login, and reboot the Pi. For USB serial, check the cable and connection.'; $('mode').textContent=s.enabled?'Commissioning enabled. Radio services must remain stopped.':'Hardware access disabled; draft and preview only.'; $('limitation').textContent=s.limitation; $('device').textContent=JSON.stringify(s.device || 'Not checked',null,2); $('last').textContent=JSON.stringify(s.last_program || 'No programming record',null,2); $('logs').textContent=s.events.map(e=>`${e.time} ${e.message}`).join('\n'); const selected=$('port').value; $('port').replaceChildren(new Option(s.ports.length?'Select the SHARI serial port':'No serial ports detected','')); for(const p of s.ports) $('port').add(new Option(`${p.path}${p.accessible?'':' — permission required'}`,p.path)); if(s.ports.some(p=>p.path===selected)) $('port').value=selected; else if(s.ports.length===1) $('port').value=s.ports[0].path; }
async function run(task) { for(const b of document.querySelectorAll('button')) b.disabled=true; try { await task(); } catch(e) { $('feedback').textContent=e.message; try { render(await api()); } catch {} } finally { for(const b of document.querySelectorAll('button')) b.disabled=false; $('probe').disabled=!state?.enabled || !state?.ports?.length || state?.uart_reboot_required===true; $('program').disabled=!reviewed || !state?.enabled || !$('port').value || state?.uart_reboot_required===true;if($('setup-radio-continue'))$('setup-radio-continue').disabled=programmingRecordResult(state?.last_program)[0]!=='success'; } }
form.addEventListener('input',invalidate);
$('port').addEventListener('change',invalidate);
$('detect').onclick=()=>run(async()=>render(await api()));
$('preset').onclick=()=>run(async()=>fill(state.preset));
$('draft').onclick=()=>run(async()=>fill(state.draft));
$('save').onclick=()=>run(async()=>{render(await api({action:'save',settings:settings()}));$('feedback').textContent='Draft saved. Radio unchanged.';});
form.onsubmit=e=>{e.preventDefault();run(async()=>{const s=settings();const result=await api({action:'preview',settings:s});$('preview').textContent=JSON.stringify(result,null,2);reviewed=JSON.stringify(s);$('feedback').textContent='Review the settings and commands before programming.';});};
$('probe').onclick=()=>run(async()=>{render(await api({action:'probe',port:$('port').value,safe:$('safe').checked}));$('feedback').textContent='Connection check finished; see device status.';});
$('program').onclick=()=>run(async()=>{const s=settings();if(JSON.stringify(s)!==reviewed)throw Error('Validate and review the current settings first.');const body={action:'program',settings:s,port:$('port').value,safe:$('safe').checked,confirm:$('confirm').value};invalidate();render(await api(body));if(window.parent!==window)window.parent.postMessage('allmode-radio-programmed',location.origin);$('feedback').textContent='All writes acknowledged. RF behavior and persistence still need hardware testing.';});
run(async()=>{const s=await api();for(const k of ['rx_ctcss','tx_ctcss']) for(const tone of s.tones)form.elements.namedItem(k).add(new Option(tone==='0'?'Off':tone,tone));render(s);fill(s.draft || s.preset);});

if(new URLSearchParams(location.search).get('embedded')==='1'){
 for(const el of document.querySelectorAll('header,nav'))el.hidden=true;
 for(const link of document.querySelectorAll('a'))link.target='_top';
}
for(const link of document.querySelectorAll('a[href="/setup"]'))link.href='/setup?step=radio';

if(new URLSearchParams(location.search).get('embedded')==='1'){const report=()=>window.parent.postMessage({type:'allmode-radio-height',height:document.body.getBoundingClientRect().height},location.origin);new ResizeObserver(report).observe(document.body);report();}

if(new URLSearchParams(location.search).get('return')==='setup'&&window.parent===window){
 document.querySelector('h1').textContent='Setup: program your radio';
 const stop=document.createElement('button');stop.type='button';stop.className='secondary';stop.textContent='Stop radio services for programming';
 document.querySelector('#identify').append(stop);
 stop.onclick=()=>run(async()=>{const response=await fetch('/api/system',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'maintenance'})});const result=await response.json();if(!response.ok)throw Error(result.error||'Could not stop radio services.');$('feedback').textContent='Radio services stopped. Review your settings before programming.';});
 const nav=document.createElement('div');nav.className='actions';const back=document.createElement('button');back.className='secondary';back.textContent='Back to network setup';back.onclick=()=>{sessionStorage.setItem('ara.setupStepName','dstar');location.href='/setup';};
 const next=document.createElement('button');next.textContent='Continue to review & apply';next.disabled=true;next.id='setup-radio-continue';
 next.onclick=async()=>{try{const response=await fetch('/api/onboarding');const result=await response.json();if(!response.ok)throw Error(result.error||'Could not check programming.');if(!result.workflow?.radio)throw Error('Complete radio programming before continuing.');sessionStorage.setItem('ara.setupStepName','review');location.href='/setup';}catch(e){$('feedback').textContent=e.message;}};
 nav.append(back,next);document.querySelector('main').append(nav);
 const renderRadioState=render;render=function(s){renderRadioState(s);next.disabled=s.last_program?.state!=='acknowledged-not-verified'||s.last_program?.acknowledged?.length!==4;};
 for(const a of document.querySelectorAll('a[href="/setup?step=radio"]'))a.hidden=true;
}

// Suggestions populate the form only; programming still requires explicit review.
function frequencyAssessment(value,band){
 if(!/^\d{3}(?:\.\d{1,4})?$/.test(value))return {ok:false,text:'Enter MHz with up to four decimal places.'};
 const n=Number(value),low=band==='UHF'?430:144,high=band==='UHF'?449.995:148;
 if(n<low||n>high)return {ok:false,text:`Use ${low.toFixed(3)}–${high.toFixed(3)} MHz.`};
 if(band==='UHF'&&n>=435&&n<=438)return {ok:false,text:'Blocked satellite range'};
 if(Math.abs(n*400-Math.round(n*400))>0.000001)return {ok:false,text:'Use a 2.5 kHz frequency step.'};
 return {ok:true,warn:band==='UHF'&&n>=447,text:band==='UHF'&&n>=447?'OK — This frequency could interfere with a local repeater.':'OK'};
}
function updateFrequencyStatus(){
 for(const key of ['rx','tx']){const input=form.elements.namedItem(key),status=$('frequency-status-'+key);if(!status)continue;const result=frequencyAssessment(input.value,form.elements.namedItem('band').value);status.textContent=input.value?result.text:'Enter a frequency or choose a suggestion.';status.className='frequency-status '+(!input.value?'':!result.ok?'error':result.warn?'warning':'ok');input.setCustomValidity(result.ok?'':result.text);}
}
const frequencyChoices=[
 ...['438.4500','438.5500','438.6750','445.9250','445.9750','446.0250','446.0750','446.1250'].map(f=>({group:'Simplex',rx:f,tx:f})),
 ...[['433.4500','438.4500'],['433.5500','438.5500'],['433.6750','438.6750']].map(([rx,tx])=>({group:'Duplex',rx,tx}))
];
const suggestions=document.createElement('section');suggestions.className='frequency-suggestions';
const heading=document.createElement('h3');heading.textContent='Suggested frequencies';suggestions.append(heading);
const hint=document.createElement('p');hint.className='hint';hint.textContent='Optional; custom frequencies are allowed. Selecting a suggestion fills RX/TX and selects wide FM. Review and program separately.';suggestions.append(hint);
for(const group of ['Simplex','Duplex']){const title=document.createElement('h4');title.textContent=group;suggestions.append(title);const row=document.createElement('div');row.className='frequency-choice-row';for(const choice of frequencyChoices.filter(c=>c.group===group)){const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=group==='Simplex'?Number(choice.tx).toFixed(3)+' MHz':`RX ${Number(choice.rx).toFixed(3)} / TX ${Number(choice.tx).toFixed(3)}`;button.onclick=()=>{form.elements.namedItem('band').value='UHF';form.elements.namedItem('rx').value=choice.rx;form.elements.namedItem('tx').value=choice.tx;form.elements.namedItem('bandwidth').value='1';invalidate();updateFrequencyStatus();$('feedback').textContent='Suggestion selected. Radio unchanged; review the settings before programming.';};row.append(button);}suggestions.append(row);}
const duplexHint=document.createElement('p');duplexHint.className='hint';duplexHint.textContent='RX and TX are from the hotspot’s perspective. Duplex pairs require suitable hardware; selecting a pair does not enable simultaneous transmit and receive.';suggestions.append(duplexHint);
form.before(suggestions);
for(const key of ['rx','tx']){const input=form.elements.namedItem(key),status=document.createElement('span');status.id='frequency-status-'+key;status.setAttribute('role','status');input.after(status);input.setAttribute('aria-describedby',status.id);}
form.addEventListener('input',updateFrequencyStatus);form.addEventListener('change',updateFrequencyStatus);
const originalFill=fill;fill=function(values){originalFill(values);updateFrequencyStatus();};
updateFrequencyStatus();
// Keep the last programming outcome visible beside the programming controls.
const programResult = document.createElement('p');
programResult.id = 'program-result';
programResult.setAttribute('role', 'status');
programResult.setAttribute('aria-live', 'polite');
$('program').closest('.row').after(programResult);
let programAttemptActive = false;
function showProgramResult(kind, detail) {
  programResult.className = 'program-result ' + kind;
  programResult.textContent = detail;
}
function programmingRecordResult(record) {
  if (!record) return ['pending', 'Not programmed — no programming record.'];
  const success = record.state === 'acknowledged-not-verified' && JSON.stringify(record.acknowledged) === JSON.stringify(['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL']);
  const when = record.time ? ' (' + record.time + ')' : '';
  return success
    ? ['success', 'Success — radio acknowledged all programming commands' + when + '. RF audio still needs checking.']
    : ['failure', 'Fail — programming did not complete' + when + '. Review and program again.'];
}
const renderBeforeProgramResult = render;
render = function(s) {
  renderBeforeProgramResult(s);
  if (!programAttemptActive) showProgramResult(...programmingRecordResult(s.last_program));
};
$('program').onclick = () => run(async () => {
  programAttemptActive = true;
  showProgramResult('pending', 'Programming…');
  try {
    const s = settings();
    if (JSON.stringify(s) !== reviewed) throw Error('Review the current settings first.');
    const body = {action:'program', settings:s, port:$('port').value, safe:$('safe').checked, confirm:$('confirm').value};
    invalidate();
    const result = await api(body);
    render(result);
    const outcome = programmingRecordResult(result.last_program);
    showProgramResult(...outcome);
    if (outcome[0] !== 'success') throw Error('Radio did not acknowledge all programming commands.');
    if (window.parent !== window) window.parent.postMessage('allmode-radio-programmed', location.origin);
  } catch (e) {
    showProgramResult('failure', 'Fail — ' + e.message + ' Programming success is not confirmed.');
  } finally {
    programAttemptActive = false;
  }
});

