const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'app/web/operator.js'),'utf8');
const hw=fs.readFileSync(path.join(__dirname,'app/web/hardware.js'),'utf8');
const resultCode=hw.slice(hw.indexOf('function programmingRecordResult('),hw.indexOf('const renderBeforeProgramResult'));
const ctx={};vm.createContext(ctx);vm.runInContext(resultCode,ctx);
const acknowledged=['AT+DMOSETGROUP','AT+DMOSETVOLUME','AT+SETFILTER','AT+SETTAIL'];
assert.equal(ctx.programmingRecordResult({state:'acknowledged-not-verified',acknowledged})[0],'success');
for(const record of [null,{}, {state:'incomplete',acknowledged},{state:'acknowledged-not-verified',acknowledged:['wrong','wrong','wrong','wrong']},{state:'acknowledged-not-verified',acknowledged:acknowledged.slice(0,3)}])assert.notEqual(ctx.programmingRecordResult(record)[0],'success');
const nodes=Object.fromEntries(['content','activate-radio','confirm-audio','audio-check','audio-feedback','audio-finish','audio-skip','wizard-next','rf-check'].map(k=>[k,{}]));
let renders=0;
const ui={$:id=>nodes[id],runtime:{audio_verified:true,radio_enabled:true},schema:{workflow:{radio:{},applied:true}},panel:()=>'',bindLiveAudio:()=>{},wizardNav:()=>{},wizardSteps:['audio','finish'],wizard:0,formDirty:true,renderWizard:()=>renders++};
vm.createContext(ui);vm.runInContext(source.slice(source.indexOf('function audioPage('),source.indexOf('async function applyWizardNext(')),ui);
ui.audioPage(true);nodes['audio-finish'].onclick();assert.equal(ui.wizard,1);assert.equal(ui.formDirty,false);assert.equal(renders,1);
// Exercise actual apply handler with confirmed, rejected, and unconfirmed saves.
const applyCode=source.slice(source.indexOf('async function applyWizardNext('),source.indexOf('function wizardNav('));
async function checkApply(mode){
 const buttons={'wizard-next':{},'wizard-back':{}};let calls=0,rendered=0;
 const c={$:id=>buttons[id],action:async fn=>fn(),message:()=>{},api:async()=>{calls++;if(mode==='reject')throw Error('offline');},loadSchema:async()=>{},schema:{workflow:{applied:mode==='ok'}},wizard:0,wizardSteps:['review','audio'],renderWizard:()=>rendered++};
 vm.createContext(c);vm.runInContext(applyCode,c);
 if(mode==='ok')await c.applyWizardNext();else await assert.rejects(c.applyWizardNext());
 assert.equal(calls,1);assert.equal(c.wizard,mode==='ok'?1:0);assert.equal(rendered,mode==='ok'?1:0);assert.equal(buttons['wizard-next'].disabled,false);assert.equal(buttons['wizard-back'].disabled,false);
}
(async()=>{for(const mode of ['ok','reject','unconfirmed'])await checkApply(mode);console.log('PASS: programming acknowledgement integrity, audio finish navigation, and apply success/failure/unconfirmed flow.');})().catch(e=>{console.error(e);process.exitCode=1;});
