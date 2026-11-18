import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {dashboardView,isDashboardSender} from '../dashboard/view-model.js';
test('empty dashboard never invents account points or completion',()=>{const v=dashboardView();assert.equal(v.account,'未连接');assert.equal(v.points,'—');assert.equal(v.task,'NO_TASK');assert.equal(v.enabled,false);assert.equal(v.count,null)});
test('dashboard reflects snapshot without inferring success',()=>{const v=dashboardView({binding:{label:'x***@example.test'},enabled:true,task:{state:'UNKNOWN'},observation:{points:0,checkedAt:100,day:'2026-11-18',todayCheckinRecords:0}});assert.equal(v.points,'0');assert.equal(v.task,'UNKNOWN');assert.equal(v.count,0)});
test('invalid numeric snapshots stay empty',()=>{assert.equal(dashboardView({observation:{points:NaN}}).points,'—');assert.equal(dashboardView({observation:{points:'26'}}).points,'—')});
test('dashboard sender requires exact extension page and top frame',()=>{const runtime={id:'ours',getURL:p=>'chrome-extension://ours/'+p};const s={id:'ours',url:runtime.getURL('dashboard/index.html'),frameId:0};assert.ok(isDashboardSender(s,runtime));for(const patch of [{id:'other'},{url:'https://glados.cloud/'},{url:s.url+'?x=1'},{frameId:1}])assert.equal(isDashboardSender({...s,...patch},runtime),false)});
test('dashboard has only read-only message and no network or storage APIs',()=>{const app=fs.readFileSync(new URL('../dashboard/app.js',import.meta.url),'utf8');assert.deepEqual([...app.matchAll(/type:'([^']+)'/g)].map(x=>x[1]),['dashboard-state']);assert.doesNotMatch(app,/fetch\(|\.storage\.|manual-run|authorize-submit/);});
test('actual dashboard message handler only reads local snapshot, without engine initialization',async()=>{
 let handler,reads=0,alarms=0,writes=0;const noop={addListener(){}};
 globalThis.chrome={runtime:{id:'ours',getURL:p=>'chrome-extension://ours/'+p,onMessage:{addListener:f=>{handler=f}},onInstalled:noop,onStartup:noop},storage:{local:{get:async()=>{reads++;return {}},set:async()=>{writes++},setAccessLevel:async()=>{writes++}}},alarms:{onAlarm:noop,getAll:async()=>{alarms++;return []}},tabs:{onRemoved:noop}};
 await import('../background.js?dashboard-test');
 assert.equal(reads,0);assert.equal(writes,0);assert.equal(alarms,0);
 const sender={id:'ours',url:'chrome-extension://ours/dashboard/index.html',frameId:0};
 const result=await new Promise(resolve=>assert.equal(handler({type:'dashboard-state'},sender,resolve),true));
 assert.equal(result.ok,true);assert.equal(result.data.enabled,false);assert.equal(reads,1);assert.equal(writes,0);assert.equal(alarms,0);
 assert.equal(handler({type:'manual-run',consent:true},sender,()=>{}),false);
 assert.equal(handler({type:'dashboard-state'},{...sender,url:'https://evil.test'},()=>{}),false);
 delete globalThis.chrome;
});
test('dashboard submitting wording does not claim permission delivery or scheduler health',()=>{
 const app=fs.readFileSync(new URL('../dashboard/app.js',import.meta.url),'utf8');
 const html=fs.readFileSync(new URL('../dashboard/index.html',import.meta.url),'utf8');
 assert.match(app,/SUBMITTING:'提交阶段，结果未确认（可能尚未点击）'/);
 assert.doesNotMatch(app,/已发出一次提交许可/);
 assert.match(html,/已保存的自动化设置/);
 assert.match(html,/不代表调度当前健康或仍在运行/);
 assert.match(html,/已保存的最近任务/);
});
