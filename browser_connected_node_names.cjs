// Fixture-only Chromium UI acceptance. All requests are intercepted; no station or RF.
const {chromium}=require('playwright'),assert=require('assert'),fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  for(const layout of ['1','2','3'])for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:1000}}),errors=[],writes=[],lookups=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(layout=>localStorage.setItem('ara.layout',layout),layout);
   let favorite='Club <img src=x onerror="window.pwned=1"> & Friends',connected=true,target='516228';
   const runtime={node:'1999',available:true,radio_enabled:false,health:{cpu_celsius:44,cpu_usage_percent:3},levels:{rx:650,txa:600,txb:500}};
   await page.route('**/*',async route=>{
    const u=new URL(route.request().url());
    assert.equal(u.hostname,'allmode.test','unexpected external request');
    if(route.request().method()!=='GET')writes.push(u.pathname);
    if(u.pathname.startsWith('/api/')){
     let data={};
     if(u.pathname==='/api/onboarding')data={complete:true,groups:[],workflow:{runtime,radio:{rx:'145.5000',tx:'145.5000',rx_ctcss:'100.0',tx_ctcss:'100.0'}}};
     else if(u.pathname==='/api/system')data=runtime;
     else if(u.pathname==='/api/status')data={connected,mode:'AllStar',target,active_connections:connected?[{mode:'AllStar',target}]:[],modes:['AllStar'],events:[]};
     else if(u.pathname==='/api/favorites')data={revision:1,favorites:favorite?[{id:'fixture',mode:'AllStar',target:'516228',note:favorite,enabled:false}]:[],rf:{available:false}};
     else if(u.pathname==='/api/node-names'){lookups.push(u.search);data={rows:[{target,name:'K1TEST <script>window.pwned=2</script> · Town'}],expires_in:60};}
     else if(u.pathname==='/api/current-speaker')data={active:true,identity:'Via node '+target,mode:'AllStar',state:'active',expires_in_ms:1500};
     return route.fulfill({json:data});
    }
    const file=u.pathname==='/'||u.pathname==='/connections'?'operator.html':u.pathname.slice(1),filename=path.join(__dirname,'app/web',file);
    if(!fs.existsSync(filename))return route.fulfill({status:404,body:''});
    return route.fulfill({body:fs.readFileSync(filename),contentType:file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':'text/html'});
   });
   await page.goto('http://allmode.test/');
   const label=layout==='3'?'#rig-connected-destination':'.banner .connected-node-name';
   const number=layout==='3'?'#rig-connected-nodes':'.banner .connected-node-number';
   await page.waitForFunction(({label,text})=>document.querySelector(label)?.textContent===text,{label,text:favorite});
   assert.equal(await page.locator(number).textContent(),'Node 516228');assert.equal(lookups.length,0);
   assert.equal(await page.evaluate(()=>window.pwned),undefined);assert.equal(await page.locator('#content img,#content script').count(),0);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'horizontal overflow '+layout+'/'+width);
   const meter=layout==='3'?'#rig-meter-host':'#dashboard-audio-meters';
   await page.waitForFunction(meter=>document.querySelector(meter)?.childElementCount>0,meter);
   await page.evaluate(meter=>window.keptMeter=document.querySelector(meter),meter);
   await page.evaluate(()=>dashboard());
   assert(await page.evaluate(meter=>window.keptMeter===document.querySelector(meter),meter),'meter root replaced');
   favorite='';await page.evaluate(async()=>{await loadStationFavorites();dashboard();});
   await page.waitForFunction(label=>document.querySelector(label)?.textContent.startsWith('K1TEST'),label);
   assert.equal(await page.locator(number).textContent(),'Node 516228');assert.equal(lookups.length,1);
   assert.equal(await page.locator('#content script').count(),0);assert.equal(await page.evaluate(()=>window.pwned),undefined);
   if(layout==='3'){
    await page.waitForFunction(()=>document.querySelector('#rig-current-speaker')?.textContent==='Via node 516228');
    assert.equal(await page.locator('#rig-rx-tone').textContent(),'PL 100.0 Hz');
    assert.equal(await page.locator('#rig-frequency-tx').textContent(),'145.5000');
   }
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'remote label overflow');
   await page.screenshot({path:path.join(__dirname,'..',`qa-layout-${layout}-${width}.png`),fullPage:true});
   connected=false;await page.evaluate(()=>pollStation());
   if(layout==='3'){assert.equal(await page.locator(label).textContent(),'Not connected');assert.equal(await page.locator(number).textContent(),'');}
   else assert.equal(await page.locator('.banner .connected-node-name').count(),0);
   assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);await page.close();
   console.log(`PASS layout ${layout}, width ${width}: saved/public name, separate node, no XSS/overflow/mutations, retained meter, disconnect`);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
