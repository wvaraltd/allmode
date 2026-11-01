// Browser verification was NOT RUN successfully in the cloud sandbox: Chromium local sockets were blocked.
// Run in a browser-capable environment with Playwright and CHROMIUM_PATH if needed.
// Isolated browser verification. Every API is mocked; no station or RF is contacted.
const {chromium}=require('playwright'),assert=require('assert'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  let snapshot={revision:1,favorites:[{id:'stable-a',mode:'AllStar',target:'2000',note:'Club',slot:'7',enabled:false},{id:'stable-b',mode:'DMR',target:'91',network:'TGIF',note:'World',slot:null,enabled:false}],rf:{available:true,reason:'Fixture: local RF configuration verified.'}};
  let reject=false;
  await page.addInitScript(()=>{localStorage.setItem('ara.favorites',JSON.stringify([{mode:'DMR',target:'91',note:'World'},{mode:'AllStar',target:'3000'}]));});
  await page.route('http://allmode.test/**',async route=>{
   const u=new URL(route.request().url()),method=route.request().method();
   if(u.pathname.startsWith('/api/')){
    let data={};
    if(u.pathname==='/api/onboarding')data={complete:true,groups:[],workflow:{runtime:{node:'1999',available:true,health:{}}}};
    else if(u.pathname==='/api/status')data={modes:['AllStar','DMR'],dmr_network:'TGIF',events:[]};
    else if(u.pathname==='/api/favorites'){
     if(method==='POST'){const body=route.request().postDataJSON();writes.push(body);if(reject)return route.fulfill({status:409,json:{error:'Favorites changed in another browser.'}});assert.equal(body.revision,snapshot.revision);snapshot={...snapshot,revision:snapshot.revision+1,favorites:body.favorites.map((f,i)=>({...f,id:f.id||'new-'+i}))};}
     data=snapshot;
    }else if(u.pathname==='/api/favorites/import'){
     const body=route.request().postDataJSON();writes.push(body);for(const f of body.favorites)if(!snapshot.favorites.some(x=>x.mode===f.mode&&x.target===f.target&&x.network===f.network))snapshot.favorites.push({...f,id:'import-'+snapshot.favorites.length,slot:null,enabled:false});snapshot.revision++;data=snapshot;
    }
    return route.fulfill({json:data});
   }
   const file=u.pathname==='/connections'?'operator.html':u.pathname.slice(1);const filename=path.join(__dirname,'app/web',file);
   if(!fs.existsSync(filename))return route.fulfill({status:404,body:''});
   return route.fulfill({body:fs.readFileSync(filename),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
  });
  await page.goto('http://allmode.test/connections');await page.locator('#favorite-memory-form').waitFor();
  assert.equal(writes.length,0);assert.equal(await page.locator('#favorites .favorite').count(),2);
  assert.equal(await page.locator('[data-memory-id="stable-a"] output').textContent(),'*57');
  await page.locator('[data-memory-id="stable-a"] [name=slot]').fill('01');assert.equal(await page.locator('[data-memory-id="stable-a"] output').textContent(),'—');assert.equal(writes.length,0);
  await page.locator('[data-memory-id="stable-a"] [name=slot]').fill('8');await page.locator('[data-memory-id="stable-a"] [name=enabled]').check();assert.equal(writes.length,0);
  await page.locator('#favorite-memory-form button').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('Dial plan saved'));
  assert.equal(writes[0].favorites[0].id,'stable-a');assert.equal(writes[0].favorites[0].slot,'8');assert(writes[0].favorites[0].enabled);
  reject=true;await page.locator('[data-memory-id="stable-b"] [name=slot]').fill('9');await page.locator('#favorite-memory-form button').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('Reload station favorites'));
  assert.equal(await page.locator('[data-memory-id="stable-b"] [name=slot]').inputValue(),'9');assert.equal(snapshot.favorites[1].slot,null);
  reject=false;await page.locator('#favorites-reload').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent==='Station favorites reloaded.');assert.equal(await page.locator('[data-memory-id="stable-b"] [name=slot]').inputValue(),'');
  await page.locator('.favorite-import summary').click();await page.locator('#favorite-import-form button').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('Choose a DMR network'));
  const before=writes.length;await page.locator('[data-import-network="0"]').selectOption('TGIF');await page.locator('#favorite-import-form button').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('Selected favorites imported'));
  assert.equal(writes.length,before+1);assert.equal(snapshot.favorites.length,3);assert.equal(snapshot.favorites[1].note,'World');assert.equal(snapshot.favorites[2].enabled,false);assert.equal(JSON.parse(await page.evaluate(()=>localStorage.getItem('ara.favorites'))).length,2);
  await page.locator('[data-remove="1"]').click();await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('Other RF slots are unchanged'));
  assert.equal(snapshot.favorites[0].slot,'8');assert.equal(snapshot.favorites[0].id,'stable-a');
  await page.setViewportSize({width:390,height:844});assert(await page.locator('#favorite-memory-form').isVisible());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await page.screenshot({path:'/tmp/allmode-favorite-memory-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS: real Chromium mocked API; explicit save, no automatic RF/import, leading-zero preview, stable IDs/slots, stale edit retention/reload, DMR import review/dedup/backup, deletion, mobile overflow; no RF.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
