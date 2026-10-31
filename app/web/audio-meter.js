(()=>{'use strict';
try{const style=localStorage.getItem('ara.meterStyle');document.documentElement.dataset.meterStyle=['analog','vintage','led','digital'].includes(style)?style:'analog';}catch{document.documentElement.dataset.meterStyle='analog';}
let busy=false,host=null,held={rx:-96,tx:-96},expires={rx:0,tx:0},lastSequence=-1,lastDelivery=0;
function mount(){
 const form=document.getElementById('audio-form');
 const dash=document.getElementById('dashboard-audio-meters');
 const rig=document.getElementById('rig-meter-host');
 const target=rig||(form?form.parentElement:dash);
 if(!target)return null;
 let box=document.getElementById('live-audio-meters');
 if(box)return box;
 box=document.createElement('section');box.id='live-audio-meters';box.className='panel';
 box.classList.add('audio-console');
 box.innerHTML='<div class="audio-console-heading"><h2>RADIO AUDIO</h2><span class="audio-live-badge">LIVE LEVELS</span></div><div class="audio-meter-pair">'+['rx','tx'].map(k=>'<div class="audio-channel"><div class="audio-channel-heading"><span class="audio-channel-id">'+k.toUpperCase()+'</span><span>'+(k==='rx'?'RADIO → NETWORK':'NETWORK → RADIO')+'</span><strong id="meter-number-'+k+'">—</strong></div><div class="audio-led-track" id="meter-'+k+'" role="meter" aria-label="'+k.toUpperCase()+' audio RMS level" aria-valuemin="-60" aria-valuemax="0" aria-valuenow="-60">'+Array.from({length:30},()=>'<i></i>').join('')+'</div><div class="audio-scale"><span>−60</span><span>−48</span><span>−36</span><span>−24</span><span>−12</span><span>0 dBFS</span></div><p id="meter-text-'+k+'" class="audio-reading">Waiting for audio…</p></div>').join('')+'</div><div class="audio-console-footer"><span id="meter-state" role="status"></span>'+(dash?'<a href="/settings#audio">Audio settings & test →</a>':'<span>RF deviation · Not calibrated</span>')+'</div>'+(dash?'':'<details class="audio-meter-help"><summary>About these readings</summary><p>RMS audio and a two-second peak hold at the SimpleUSB audio path. CLIPPING indicates digital full scale; radio hardware can distort before this point. These are audio readings, not measured RF deviation. Calibration needs a known RX reference and an external TX deviation measurement.</p></details>');
 const gauge="<div class=\"rig-shared-meter\"><div class=\"rig-meter-mode\" id=\"rig-meter-mode\">AUDIO · IDLE</div><svg class=\"rig-gauge\" viewBox=\"0 0 300 170\" aria-hidden=\"true\"><path d=\"M 50.40707856478956,97.49999999999999 A 115 115 0 0 1 196.77471395371703,49.9422723711009\" fill=\"none\" stroke=\"#63b78b\" stroke-width=\"5\"/><path d=\"M 196.77471395371703,49.9422723711009 A 115 115 0 0 1 235.46165492990033,78.0499802687313\" fill=\"none\" stroke=\"#efba59\" stroke-width=\"5\"/><path d=\"M 235.46165492990033,78.0499802687313 A 115 115 0 0 1 249.59292143521043,97.49999999999999\" fill=\"none\" stroke=\"#e76d62\" stroke-width=\"5\"/><line x1=\"56.46925639128064\" y1=\"100.99999999999999\" x2=\"66.86156123669389\" y2=\"106.99999999999999\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"60.463942164055496\" y1=\"94.60716642515935\" x2=\"65.43816759938575\" y2=\"97.96232384598383\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"64.89483861047403\" y1=\"88.5085606648289\" x2=\"69.62290313211436\" y2=\"92.20252951678285\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"69.74035884844142\" y1=\"82.73389451324331\" x2=\"74.19922780130578\" y2=\"86.74867815139646\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"74.97689599042829\" y1=\"77.31130156342567\" x2=\"79.14484621318228\" y2=\"81.62734036545758\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"80.57893815385376\" y1=\"72.26720014315038\" x2=\"88.29238947009223\" y2=\"81.45973346057811\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"86.51919275241289\" y1=\"67.62616460750567\" x2=\"90.04590426616774\" y2=\"72.48026657375536\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"92.76871946281386\" y1=\"63.410805615106\" x2=\"95.94823504821309\" y2=\"68.49909419204455\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"99.2970712191238\" y1=\"59.64165997123588\" x2=\"102.11390059583914\" y2=\"64.93934552838945\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"106.07244254781358\" y1=\"56.3370905745991\" x2=\"108.51286240626838\" y2=\"61.81836332045471\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"113.06182452082777\" y1=\"53.513196955121884\" x2=\"117.1660662407358\" y2=\"64.78950840455279\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"120.2311655717641\" y1=\"51.18373683866156\" x2=\"121.88498970666609\" y2=\"56.95130701429147\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"127.54553739168199\" y1=\"49.360059120748986\" x2=\"128.79300753658856\" y2=\"55.22894472515182\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"134.96930509631292\" y1=\"48.0510485759104\" x2=\"135.8043437020733\" y2=\"53.992656988359826\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"142.46630083563446\" y1=\"47.26308257193898\" x2=\"142.8848396780992\" y2=\"53.24846687349793\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"150\" y1=\"47\" x2=\"150\" y2=\"59\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"157.53369916436554\" y1=\"47.26308257193898\" x2=\"157.1151603219008\" y2=\"53.24846687349793\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"165.03069490368708\" y1=\"48.0510485759104\" x2=\"164.1956562979267\" y2=\"53.992656988359826\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"172.454462608318\" y1=\"49.360059120748986\" x2=\"171.20699246341144\" y2=\"55.22894472515182\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"179.76883442823592\" y1=\"51.18373683866156\" x2=\"178.1150102933339\" y2=\"56.95130701429147\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"186.93817547917223\" y1=\"53.513196955121884\" x2=\"182.8339337592642\" y2=\"64.78950840455279\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"193.92755745218642\" y1=\"56.3370905745991\" x2=\"191.48713759373163\" y2=\"61.81836332045471\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"200.70292878087622\" y1=\"59.64165997123588\" x2=\"197.88609940416086\" y2=\"64.93934552838945\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"207.23128053718614\" y1=\"63.410805615106\" x2=\"204.0517649517869\" y2=\"68.49909419204455\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"213.4808072475871\" y1=\"67.62616460750567\" x2=\"209.95409573383228\" y2=\"72.48026657375536\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"219.42106184614624\" y1=\"72.26720014315038\" x2=\"211.70761052990775\" y2=\"81.45973346057811\" stroke=\"#f5ce86\" stroke-width=\"2\"/><line x1=\"225.0231040095717\" y1=\"77.31130156342567\" x2=\"220.8551537868177\" y2=\"81.62734036545758\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"230.25964115155858\" y1=\"82.73389451324331\" x2=\"225.80077219869423\" y2=\"86.74867815139646\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"235.10516138952596\" y1=\"88.5085606648289\" x2=\"230.37709686788565\" y2=\"92.20252951678285\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"239.53605783594452\" y1=\"94.60716642515935\" x2=\"234.56183240061426\" y2=\"97.96232384598383\" stroke=\"#f5ce86\" stroke-width=\"1\"/><line x1=\"243.53074360871938\" y1=\"100.99999999999999\" x2=\"233.1384387633061\" y2=\"106.99999999999999\" stroke=\"#f5ce86\" stroke-width=\"2\"/><text x=\"33.95259589288523\" y=\"91.99999999999999\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-60</text><text x=\"63.866460302003745\" y=\"56.35004462205694\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-50</text><text x=\"104.1693007943604\" y=\"33.081188814688275\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-40</text><text x=\"150\" y=\"25\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-30</text><text x=\"195.8306992056396\" y=\"33.081188814688275\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-20</text><text x=\"236.13353969799624\" y=\"56.35004462205694\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">-10</text><text x=\"266.04740410711474\" y=\"91.99999999999999\" text-anchor=\"middle\" fill=\"#f5ce86\" font-family=\"monospace\" font-size=\"15\">0</text><text x=\"150\" y=\"111\" text-anchor=\"middle\" fill=\"#a9a49a\" font-family=\"monospace\" font-size=\"12\" letter-spacing=\"2\">AUDIO dBFS</text><g transform=\"translate(150 155)\"><line id=\"rig-peak\" x1=\"0\" y1=\"-120\" x2=\"0\" y2=\"-128\" stroke=\"#fff0b9\" stroke-width=\"3\" opacity=\"0\"/><line id=\"rig-needle\" class=\"needle\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"-109\" stroke=\"#ffffff\" stroke-width=\"2.4\" transform=\"rotate(-60)\"/></g><circle cx=\"150\" cy=\"155\" r=\"7\" fill=\"#bdc0bf\"/><circle cx=\"150\" cy=\"155\" r=\"3\" fill=\"#444a4b\"/></svg><div id=\"rig-meter-value\" role=\"meter\" aria-label=\"Active audio level\" aria-valuemin=\"-60\" aria-valuemax=\"0\" aria-valuenow=\"-60\">—</div></div>";
 box.querySelector('.audio-meter-pair').insertAdjacentHTML('beforebegin',gauge);
 box.querySelector('#rig-meter-value').insertAdjacentHTML('beforebegin','<div class="rig-led-meter" aria-hidden="true"><svg viewBox="0 0 300 50"><defs><linearGradient id="shared-led-colors"><stop offset="0%" stop-color="#65d9aa"/><stop offset="75%" stop-color="#65d9aa"/><stop offset="85%" stop-color="#edcb65"/><stop offset="100%" stop-color="#ef6d77"/></linearGradient><pattern id="shared-led-gaps" width="10" height="36" patternUnits="userSpaceOnUse"><rect x="8" width="2" height="36" fill="#08121c"/></pattern><clipPath id="shared-led-clip"><rect id="rig-led-fill" width="0" height="36"/></clipPath></defs><rect width="300" height="36" fill="#253642"/><rect width="300" height="36" fill="url(#shared-led-colors)" clip-path="url(#shared-led-clip)"/><rect width="300" height="36" fill="url(#shared-led-gaps)"/><g fill="#9eb8c9" font-family="monospace" font-size="9"><text x="0" y="49">−60</text><text x="95" y="49">−40</text><text x="195" y="49">−20</text><text x="290" y="49">0</text></g></svg></div>');
 if(form&&!rig)target.insertBefore(box,form);else target.append(box);
 held={rx:-96,tx:-96};expires={rx:0,tx:0};return box;
}
function updateSharedMeter(box,s){
 const valid=k=>s.active&&s[k]?.available&&Number.isFinite(s[k].rms_db)&&s[k].age_ms<350;
 const tx=valid('tx')&&s.tx.rms_db>-60,rx=valid('rx')&&s.rx.rms_db>-60;
 const side=tx?'tx':rx?'rx':null;
 const available=valid('rx')||valid('tx');
 const level=side?Math.max(-60,Math.min(0,s[side].rms_db)):-60;
 const clipping=side&&s[side].clipping;
 const peak=box.querySelector('#rig-peak');
 peak.setAttribute('opacity',side&&Number.isFinite(s[side].peak_db)?'1':'0');
 if(side&&Number.isFinite(s[side].peak_db))peak.setAttribute('transform','rotate('+(-60+(Math.max(-60,Math.min(0,s[side].peak_db))+60)*2)+')');
 box.querySelector('#rig-led-fill').setAttribute('width',String((level+60)*5));
 box.querySelector('#rig-meter-value').setAttribute('data-clipping',clipping?'true':'false');
 box.querySelector('#rig-needle').setAttribute('transform','rotate('+(-60+(level+60)*2)+')');
 box.querySelector('#rig-needle').setAttribute('opacity',available?'1':'.15');
 box.querySelector('#rig-needle').setAttribute('stroke',clipping?'#ff6268':'#e2eef6');
 box.querySelector('#rig-meter-mode').textContent=side?(side.toUpperCase()+' AUDIO'+(clipping?' · CLIP':tx&&rx?' · RX+TX':'')):available?'AUDIO · IDLE':'UNAVAILABLE';
 const readout=box.querySelector('#rig-meter-value');
 readout.textContent=side?s[side].rms_db.toFixed(1)+' dBFS':available?'−∞ dBFS':'—';
 readout.setAttribute('aria-valuenow',String(level));readout.setAttribute('aria-label',side?side.toUpperCase()+' audio level':'Audio level');
}
async function update(){
 if(busy||document.hidden)return;
 host=mount();if(!host)return;
 busy=true;const box=host,requested=performance.now();
 const controller=new AbortController(),deadline=setTimeout(()=>controller.abort(),1000);
 try{
  const r=await fetch('/api/audio-meter',{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('Audio meters unavailable');const s=await r.json();
  if(!box.isConnected)return;
  const received=performance.now(),changed=s.sequence!==lastSequence,timely=received-requested<350;
  if(changed&&timely){lastSequence=s.sequence;lastDelivery=received;}
  const current=timely&&received-lastDelivery<350;
  updateSharedMeter(box,{...s,active:s.active&&current});
  box.querySelector('#meter-state').textContent=s.active&&current&&(s.rx?.available||s.tx?.available)?'Live · listening only':s.error||(s.active?'Waiting for fresh audio':'Audio meters unavailable');
  for(const k of ['rx','tx']){
   const v=s[k],fresh=s.active&&current&&v?.available&&Number.isFinite(v.rms_db)&&Number.isFinite(v.peak_db)&&v.age_ms<350,now=performance.now();
   if(!fresh){held[k]=-96;expires[k]=0;}else if((changed&&v.peak_db>held[k])||now>expires[k]){held[k]=v.peak_db;expires[k]=now+2000;}
   const level=fresh?Math.max(-60,v.rms_db):-60,track=box.querySelector('#meter-'+k);
   track.setAttribute('aria-valuenow',level.toFixed(1));
   const lit=Math.max(0,Math.ceil((level+60)/2)),peak=fresh&&held[k]>-60?Math.min(29,Math.floor((held[k]+60)/2)):-1;
   track.querySelectorAll('i').forEach((led,i)=>{led.classList.toggle('lit',i<lit);led.classList.toggle('peak',i===peak);});
   box.querySelector('#meter-number-'+k).textContent=fresh?(v.rms_db<=-96?'−∞':v.rms_db.toFixed(1)):'—';
   const text=box.querySelector('#meter-text-'+k);
   text.textContent=fresh?'RMS '+v.rms_db.toFixed(1)+' dBFS · Peak '+held[k].toFixed(1)+' dBFS'+(v.clipping?' · CLIPPING':''):(s.active?'Idle · no recent audio':'Unavailable');
   text.classList.toggle('audio-clipping',!!(fresh&&v.clipping));
  }
 }catch(e){if(box.isConnected){updateSharedMeter(box,{active:false});box.querySelector('#meter-state').textContent=(e.name==='AbortError'?'Meter update timed out':e.message);for(const k of ['rx','tx']){box.querySelector('#meter-'+k).setAttribute('aria-valuenow','-60');box.querySelector('#meter-'+k).querySelectorAll('i').forEach(led=>led.classList.remove('lit','peak'));box.querySelector('#meter-number-'+k).textContent='—';box.querySelector('#meter-text-'+k).textContent='Unavailable';}}}
 finally{clearTimeout(deadline);busy=false;}
}
// Independent freshness watchdog: a slow HTTP response must not leave old bars live.
setInterval(()=>{
 if(!host?.isConnected)return;
 if(document.hidden||performance.now()-lastDelivery>=350){
  updateSharedMeter(host,{active:false});
  host.querySelector('#meter-state').textContent='Waiting for fresh audio';
  for(const k of ['rx','tx']){
   host.querySelector('#meter-'+k).setAttribute('aria-valuenow','-60');
   host.querySelector('#meter-'+k).querySelectorAll('i').forEach(led=>led.classList.remove('lit','peak'));
   host.querySelector('#meter-number-'+k).textContent='-';
   host.querySelector('#meter-text-'+k).textContent='No fresh audio';
   host.querySelector('#meter-text-'+k).classList.remove('audio-clipping');
  }
 }
},100);
setInterval(update,100);update();
})();
