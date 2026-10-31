const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/app/web/operator.js','utf8');
const code=source.slice(source.indexOf('function cpuHealthTile('),source.indexOf('function dashboard('));
const context={esc:v=>String(v)};vm.createContext(context);vm.runInContext(code,context);
for(const [c,f] of [[0,'32.0'],[50,'122.0'],[100,'212.0']]){
 const html=context.cpuHealthTile({cpu_celsius:c,cpu_usage_percent:25,kernel:'test'});
 assert(html.includes(f+' °F'));assert(html.includes('CPU usage: 25.0%'));
 assert.equal((html.match(/class="metric"/g)||[]).length,1);
 assert(html.indexOf('CPU usage:')>html.indexOf('</strong>'));
}
const missing=context.cpuHealthTile({cpu_celsius:null,cpu_usage_percent:null});
assert(missing.includes('<strong>Unavailable</strong>'));assert(missing.includes('CPU usage: Unavailable'));
assert(!missing.includes('0.0%'));assert(context.cpuHealthTile({cpu_usage_percent:0}).includes('CPU usage: 0.0%'));
assert(source.includes('${cpuHealthTile(h)}'));
console.log('PASS: Fahrenheit conversion, CPU usage below temperature in one shared tile, unavailable and measured-zero states');
