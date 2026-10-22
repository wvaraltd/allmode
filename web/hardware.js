'use strict';
const $ = id => document.getElementById(id);
const form = $('settings');
let state, reviewed = null;
const settings = () => Object.fromEntries([...form.elements].filter(e => e.name).map(e => [e.name, e.type === 'checkbox' ? e.checked : ['bandwidth','volume','squelch'].includes(e.name) ? Number(e.value) : e.value]));
function invalidate() { reviewed = null; $('program').disabled = true; $('confirm').value = ''; }
function fill(values) { if (!values) throw Error('No saved draft exists.'); for (const [k,v] of Object.entries(values)) { const e = form.elements.namedItem(k); if (e.type === 'checkbox') e.checked = v; else e.value = v; } invalidate(); }
async function api(body) { const response = await fetch('./api/hardware', body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {}); const result = await response.json(); if (!response.ok) throw Error(result.error || 'Request failed'); return result; }
function render(s) { state=s; $('mode').textContent=s.enabled?'Commissioning enabled. Radio services must remain stopped.':'Hardware access disabled; draft and preview only.'; $('limitation').textContent=s.limitation; $('device').textContent=JSON.stringify(s.device || 'Not checked',null,2); $('last').textContent=JSON.stringify(s.last_program || 'No programming record',null,2); $('logs').textContent=s.events.map(e=>`${e.time} ${e.message}`).join('\n'); const selected=$('port').value; $('port').replaceChildren(new Option('Select the SHARI serial port','')); for(const p of s.ports) $('port').add(new Option(`${p.path}${p.accessible?'':' — permission required'}`,p.path)); if(s.ports.some(p=>p.path===selected)) $('port').value=selected; else if(s.ports.length===1) $('port').value=s.ports[0].path; }
async function run(task) { for(const b of document.querySelectorAll('button')) b.disabled=true; try { await task(); } catch(e) { $('feedback').textContent=e.message; try { render(await api()); } catch {} } finally { for(const b of document.querySelectorAll('button')) b.disabled=false; $('program').disabled=!reviewed || !state?.enabled; } }
form.addEventListener('input',invalidate);
$('port').addEventListener('change',invalidate);
$('detect').onclick=()=>run(async()=>render(await api()));
$('preset').onclick=()=>run(async()=>fill(state.preset));
$('draft').onclick=()=>run(async()=>fill(state.draft));
$('save').onclick=()=>run(async()=>{render(await api({action:'save',settings:settings()}));$('feedback').textContent='Draft saved. Radio unchanged.';});
form.onsubmit=e=>{e.preventDefault();run(async()=>{const s=settings();const result=await api({action:'preview',settings:s});$('preview').textContent=JSON.stringify(result,null,2);reviewed=JSON.stringify(s);$('feedback').textContent='Review the settings and commands before programming.';});};
$('probe').onclick=()=>run(async()=>{render(await api({action:'probe',port:$('port').value,safe:$('safe').checked}));$('feedback').textContent='Connection check finished; see device status.';});
$('program').onclick=()=>run(async()=>{const s=settings();if(JSON.stringify(s)!==reviewed)throw Error('Validate and review the current settings first.');const body={action:'program',settings:s,port:$('port').value,safe:$('safe').checked,confirm:$('confirm').value};invalidate();render(await api(body));$('feedback').textContent='All writes acknowledged. RF behavior and persistence still need hardware testing.';});
run(async()=>{const s=await api();for(const k of ['rx_ctcss','tx_ctcss']) for(const tone of s.tones)form.elements.namedItem(k).add(new Option(tone==='0'?'Off':tone,tone));render(s);fill(s.draft || s.preset);});
