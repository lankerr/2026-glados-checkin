// Local-first MV3 coordinator. No cookie API, CAPTCHA manipulation, redemption, or network response interception.
import {createEngine} from './engine.js';
import {ORIGIN,loadState} from './core.js';
import {isDashboardSender} from './dashboard/view-model.js';
import {selectExtensionAPI,restrictPersistentStorage} from './platform.js';
const extensionAPI=selectExtensionAPI();
const STATE_KEY='gladosStateV2';
async function getJSON(path){
  const response=await fetch(ORIGIN+path,{method:'GET',credentials:'include',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!response.ok||!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('read_failed');
  return response.json();
}
const engine=createEngine({
  read:async()=> (await extensionAPI.storage.local.get(STATE_KEY))[STATE_KEY],
  write:s=>extensionAPI.storage.local.set({[STATE_KEY]:s}),
  clear:()=>extensionAPI.storage.local.clear(),
  restrictStorage:()=>restrictPersistentStorage(extensionAPI),
  status:()=>getJSON('/api/user/status'),points:()=>getJSON('/api/user/points'),
  hash:async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))).map(b=>b.toString(16).padStart(2,'0')).join(''),
  now:()=>Date.now(),uuid:()=>crypto.randomUUID(),
  openTab:url=>extensionAPI.tabs.create({url,active:false}),
  alarm:(name,when)=>extensionAPI.alarms.create(name,{when}),
  clearAlarms:async()=>{for(const alarm of await extensionAPI.alarms.getAll())if(alarm.name.startsWith('slot-')||alarm.name.startsWith('watch-'))await extensionAPI.alarms.clear(alarm.name);}
});
const POPUP_TYPES=new Set(['get-state','connect','enable','pause','forget','review-task','manual-run','open-site']);
extensionAPI.runtime.onMessage.addListener((msg,sender,respond)=>{
  if(sender.id!==extensionAPI.runtime.id||!msg||typeof msg.type!=='string')return false;
  // Strictly read the saved local record; do not initialize engine, rebuild alarms,
  // inspect site sessions, or accept execution commands from the options page.
  if(msg.type==='dashboard-state'){
    if(!isDashboardSender(sender,extensionAPI.runtime))return false;
    extensionAPI.storage.local.get(STATE_KEY).then(
      saved=>respond({ok:true,data:loadState(saved[STATE_KEY])}),
      ()=>respond({ok:false,error:'snapshot_unavailable'})
    );
    return true;
  }
  let job;
  if(POPUP_TYPES.has(msg.type)){
    if(sender.url!==extensionAPI.runtime.getURL('popup.html')||sender.tab)return false;
    if(msg.type==='get-state')job=engine.getState();
    else if(msg.type==='connect')job=engine.connect();
    else if(msg.type==='enable')job=engine.enable(msg.consent);
    else if(msg.type==='pause')job=engine.pause();
    else if(msg.type==='forget')job=engine.forget();
    else if(msg.type==='review-task')job=engine.reviewTask(msg.consent);
    else if(msg.type==='manual-run')job=engine.run('manual',msg.consent);
    else job=extensionAPI.tabs.create({url:ORIGIN+'/console/checkin',active:true}).then(()=>({opened:true}));
  }else if(['task-ready','authorize-submit','needs-user','observe-after-submit'].includes(msg.type)){
    job=engine.content(msg.type,msg,sender);
  }else return false;
  job.then(data=>respond({ok:true,data}),()=>respond({ok:false,error:'operation_not_completed'}));
  return true;
});
// Installation/update never opens a page or signs in. Legacy implicit scheduling migrates to disabled.
extensionAPI.runtime.onInstalled.addListener(()=>engine.initialize().catch(()=>{}));
extensionAPI.runtime.onStartup.addListener(()=>engine.initialize().catch(()=>{}));
extensionAPI.alarms.onAlarm.addListener(a=>engine.alarm(a.name).catch(()=>{}));
extensionAPI.tabs.onRemoved.addListener(id=>engine.tabClosed(id).catch(()=>{}));
// Engine entry points recover interrupted tasks on demand.
// A read-only dashboard wake must not initialize execution or rebuild alarms.
