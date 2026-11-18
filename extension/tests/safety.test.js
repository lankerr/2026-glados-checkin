import test from 'node:test';
import assert from 'node:assert/strict';
import {createEngine} from '../engine.js';
import {beijingDay,nextSlot,ledgerObservation,validContentSender} from '../core.js';
function fixture(){
 let state,seq=0;
 const calls={tabs:[],alarms:[],status:0}, now=Date.parse('2026-11-16T17:00:00Z');
 const io={read:async()=>structuredClone(state),write:async s=>{state=structuredClone(s)},clear:async()=>{state=undefined},
 restrictStorage:async()=>{},status:async()=>{calls.status++;return {code:0,data:{email:'a@example.test'}}},
 points:async()=>({points:2,history:[]}),hash:async s=>'hash:'+s,now:()=>now,uuid:()=>String(++seq),
 openTab:async url=>{calls.tabs.push({url,state:structuredClone(state)});return {id:17}},
 alarm:async(name,when)=>calls.alarms.push({name,when}),clearAlarms:async()=>{calls.alarms=[]}};
 const engine=createEngine(io);return {io,calls,engine,state:()=>state,now};
}
async function prepared(f){await f.engine.connect();await f.engine.run('manual',true);const t=f.state().task;return {id:'extension',tab:{id:17},frameId:0,documentId:'doc',url:'https://glados.cloud/console/checkin#glados-task='+t.id}}
test('default installation is paused and performs no account reads or tabs',async()=>{const f=fixture();await f.engine.initialize();assert.equal(f.state().enabled,false);assert.equal(f.calls.status,0);assert.equal(f.calls.tabs.length,0);assert.equal(f.calls.alarms.length,0)});
test('explicit consent required',async()=>{const f=fixture();await f.engine.connect();await assert.rejects(f.engine.run('manual'));await assert.rejects(f.engine.enable());assert.equal(f.calls.tabs.length,0)});
test('concurrent runs open one owned tab after durable PREPARING',async()=>{const f=fixture();await f.engine.connect();await Promise.all([f.engine.run('manual',true),f.engine.run('manual',true)]);assert.equal(f.calls.tabs.length,1);assert.equal(f.calls.tabs[0].state.task.state,'PREPARING')});
test('submit grant follows durable SUBMITTING and duplicate grant is denied',async()=>{const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);assert.equal((await f.engine.content('authorize-submit',msg,sender)).allowed,true);assert.equal(f.state().task.state,'SUBMITTING');assert.equal((await f.engine.content('authorize-submit',msg,sender)).allowed,false)});
test('worker restart retains uncertain task and never repeats',async()=>{const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);await f.engine.content('authorize-submit',msg,sender);const restarted=createEngine(f.io);await restarted.initialize();assert.equal(f.state().task.state,'UNKNOWN');await restarted.run('manual',true);assert.equal(f.calls.tabs.length,1)});
test('rejects wrong frame, tab, document, URL, task',async()=>{const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);for(const change of [{frameId:1},{tab:{id:18}},{documentId:'other'},{url:'https://evil.test/'}])await assert.rejects(f.engine.content('authorize-submit',msg,{...sender,...change}));await assert.rejects(f.engine.content('authorize-submit',{taskId:'wrong'},sender));assert.equal(f.state().task.state,'PAGE_OPEN')});
test('identity change stops submission',async()=>{const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);f.io.status=async()=>({code:0,data:{email:'b@example.test'}});assert.equal((await f.engine.content('authorize-submit',msg,sender)).allowed,false);assert.equal(f.state().task.state,'NEEDS_USER')});
test('compensation is not checkin; exact checkin observation is not attribution',async()=>{const f=fixture();assert.equal(ledgerObservation({points:2,history:[{business:'compensation',time:f.now,change:2}]},f.now).todayCheckinRecords,0);f.io.points=async()=>({points:2,history:[{business:'checkin',time:f.now,change:2}]});await f.engine.connect();await f.engine.run('manual',true);assert.equal(f.state().task.state,'OBSERVED');assert.equal(f.state().task.detail,'ledger_not_request_attribution');assert.equal(f.calls.tabs.length,0)});
test('pending account read cancelled by forget cannot resurrect storage or open tab',async()=>{const f=fixture();await f.engine.connect();let release,entered;const started=new Promise(r=>entered=r);f.io.status=()=>{entered();return new Promise(r=>release=r)};const run=f.engine.run('manual',true);await started;const forgotten=f.engine.forget();release({code:0,data:{email:'a@example.test'}});await Promise.all([run,forgotten]);assert.equal(f.state(),undefined);assert.equal(f.calls.tabs.length,0)});
test('pending submit authorization paused before response gives no permission',async()=>{const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);let release,entered;const started=new Promise(r=>entered=r);f.io.status=()=>{entered();return new Promise(r=>release=r)};const grant=f.engine.content('authorize-submit',msg,sender);await started;const paused=f.engine.pause();release({code:0,data:{email:'a@example.test'}});assert.equal((await grant).allowed,false);await paused;assert.equal(f.state().task.state,'NEEDS_USER')});
test('Beijing date and future slots independent of host timezone',()=>{const ms=Date.parse('2026-11-16T17:00:00Z');for(const tz of ['UTC','Asia/Shanghai','America/Los_Angeles']){process.env.TZ=tz;assert.equal(beijingDay(ms),'2026-11-17');assert.equal(new Date(nextSlot('09:30',ms)).toISOString(),'2026-11-17T01:30:00.000Z')}});
test('closed unrelated tabs do not change task and no tabs ever auto-closed',async()=>{const f=fixture();await prepared(f);await f.engine.tabClosed(99);assert.equal(f.state().task.state,'PAGE_OPEN');await f.engine.tabClosed(17);assert.equal(f.state().task.state,'NEEDS_USER')});
test('manifest resources and popup locale keys exist in both retained locales',async()=>{
 const fs=await import('node:fs/promises');
 const root=new URL('../',import.meta.url), manifest=JSON.parse(await fs.readFile(new URL('manifest.json',root)));
 assert.equal(manifest.default_locale,'zh_CN');assert.equal(manifest.background.type,'module');
 assert.deepEqual([...manifest.permissions].sort(),['alarms','storage']);
 const html=await fs.readFile(new URL('popup.html',root),'utf8');
 for(const language of ['en','zh_CN']){
  const locale=JSON.parse(await fs.readFile(new URL('_locales/'+language+'/messages.json',root)));
  for(const [,key] of html.matchAll(/data-i18n="([^"]+)"/g))assert.ok(locale[key]?.message,key);
 }
 for(const asset of Object.values(manifest.icons))await fs.access(new URL(asset,root));
});
test('pause during durable SUBMITTING write prevents delivery of click grant',async()=>{
 const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};
 await f.engine.content('task-ready',msg,sender);
 const write=f.io.write;let release,entered;const started=new Promise(r=>entered=r);
 f.io.write=async s=>{if(s.task?.state==='SUBMITTING'){entered();await new Promise(r=>release=r);}await write(s)};
 const grant=f.engine.content('authorize-submit',msg,sender);await started;
 const pause=f.engine.pause();release();assert.equal((await grant).allowed,false);await pause;
 assert.equal(f.state().enabled,false);assert.equal(f.state().task.state,'UNKNOWN');
});
test('unknown observation stays paused; code1 does not count as successful result',async()=>{
 const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};
 await f.engine.content('task-ready',msg,sender);await f.engine.content('authorize-submit',msg,sender);
 f.io.points=async()=>({code:1,points:2,history:[{business:'checkin',time:f.now,change:2}]});
 await f.engine.content('observe-after-submit',{...msg,success:true,code:0},sender);
 assert.equal(f.state().task.state,'UNKNOWN');assert.equal(f.state().enabled,false);
});
test('pause cancels queued manual run before it captures a new epoch',async()=>{
 const f=fixture();await f.engine.connect();const run=f.engine.run('manual',true),pause=f.engine.pause();await Promise.all([run,pause]);assert.equal(f.calls.tabs.length,0);
});
test('pause cancels queued submit before it captures a new epoch',async()=>{
 const f=fixture(),sender=await prepared(f),msg={taskId:f.state().task.id};await f.engine.content('task-ready',msg,sender);
 const grant=f.engine.content('authorize-submit',msg,sender),pause=f.engine.pause();
 assert.equal((await grant).allowed,false);await pause;assert.equal(f.state().task.state,'NEEDS_USER');
});
