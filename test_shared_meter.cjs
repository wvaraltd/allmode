const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/app/web/audio-meter.js','utf8');
const e={};const box={querySelector:k=>e[k]??=( {attrs:{},setAttribute(k,v){this.attrs[k]=v;},textContent:''})};
const c={};vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function updateSharedMeter('),source.indexOf('async function update()')),c);
const v=(db,peak=db,clipping=false)=>({available:true,age_ms:0,rms_db:db,peak_db:peak,clipping});
for(const [s,label,value] of [
 [{active:true,rx:v(-96),tx:v(-96)},'AUDIO · IDLE','−∞ dBFS'],
 [{active:true,rx:v(-24,-12),tx:v(-96)},'RX AUDIO','-24.0 dBFS'],
 [{active:true,rx:v(-96),tx:v(-12,-6)},'TX AUDIO','-12.0 dBFS'],
 [{active:true,rx:v(-96),tx:v(0,0,true)},'TX AUDIO · CLIP','0.0 dBFS'],
 [{active:false,rx:v(-24)},'UNAVAILABLE','—'],
 [{active:true,rx:{...v(-24),age_ms:350}},'UNAVAILABLE','—'],
 [{active:true,rx:{...v(-24),rms_db:NaN}},'UNAVAILABLE','—']]){
 c.updateSharedMeter(box,s);assert.equal(e['#rig-meter-mode'].textContent,label);assert.equal(e['#rig-meter-value'].textContent,value);
 if(value==='—')assert.equal(e['#rig-peak'].attrs.opacity,'0');
}
c.updateSharedMeter(box,{active:true,rx:v(-24,-12)});assert.equal(e['#rig-peak'].attrs.transform,'rotate(36)');
c.updateSharedMeter(box,{active:true,rx:v(-30,-30)});assert.equal(e['#rig-peak'].attrs.transform,'rotate(0)');
assert(source.includes('setInterval(update,100)'));assert(!/mock|fixture|previewState/.test(source));
console.log('PASS independent shared gauge: idle/RX/TX/clip/unavailable/stale/NaN, fresh current peak without hold, dBFS labels');
