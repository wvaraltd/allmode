(() => {
 const login=location.pathname==='/login';
 try{document.documentElement.dataset.theme=localStorage.getItem('allmode.theme')||'night';}catch{}
 document.body.classList.add(login?'station-login':'station-ui');
 if(login)return;
 const bar=document.createElement('div');bar.className='station-bar';
 bar.innerHTML='<a class="station-brand" href="/">ALL<span>MODE</span></a><div class="station-status" aria-label="Station status"><span id="station-node">Node · checking</span><span id="station-network">AllStar · checking</span><span id="station-radio">Radio · checking</span></div><button type="button" id="station-theme">Day theme</button><form method="post" action="/logout"><button type="submit">Sign out</button></form>';
 const rail=document.createElement('nav');rail.className='station-rail';rail.setAttribute('aria-label','Station navigation');
 const items=[['OPERATE'],['Dashboard','/'],['Destinations','/#destinations'],['Activity','/#activity'],['CONFIGURE'],['Guided setup','/setup'],['Station identity','/setup#station'],['Network accounts','/setup#networks'],['Frequency & tones','/hardware'],['Audio levels','/setup#audio'],['SYSTEM'],['Review & apply','/setup#review'],['Radio logs','/hardware#status']];
 for(const [title,url] of items){const el=document.createElement(url?'a':'small');el.textContent=title;if(url){el.href=url;if(location.pathname+location.hash===url)el.setAttribute('aria-current','page');}rail.append(el);}
 document.body.prepend(bar,rail);
 const theme=bar.querySelector('#station-theme');
 function themeLabel(){theme.textContent=document.documentElement.dataset.theme==='day'?'Night theme':'Day theme';}
 theme.onclick=()=>{const value=document.documentElement.dataset.theme==='day'?'night':'day';document.documentElement.dataset.theme=value;try{localStorage.setItem('allmode.theme',value);}catch{}themeLabel();};themeLabel();
 addEventListener('hashchange',()=>{rail.querySelectorAll('a').forEach(a=>a.setAttribute('aria-current',a.pathname+a.hash===location.pathname+location.hash?'page':'false'));});
 async function status(){try{const response=await fetch('/api/system');if(!response.ok)throw Error();const s=await response.json();const values=[['station-node',s.node?'Node '+s.node:'Node not applied',!!s.node],['station-network',s.available?'AllStar · '+(s.registered?'registered':'not registered'):'Service unavailable',s.registered],['station-radio',s.available?'Radio · '+(s.radio_enabled?'enabled':'stopped'):'Radio · unknown',s.radio_enabled]];for(const [id,text,good]of values){const e=document.getElementById(id);e.textContent=text;e.dataset.good=!!good;}}catch{for(const id of ['station-node','station-network','station-radio']){const e=document.getElementById(id);e.textContent=id==='station-node'?'Status unavailable':'—';e.dataset.good=false;}}}
 status();setInterval(status,10000);
})();
