import {ORIGIN,SLOTS,beijingDay,nextSlot,accountFromStatus,ledgerObservation,blankState,loadState,INFLIGHT,BLOCKING,validContentSender} from './core.js';
export function createEngine(io){
  let chain=Promise.resolve(),epoch=0,ready=false;
  const serial=fn=>{const job=chain.then(fn);chain=job.catch(()=>{});return job;};
  const read=async()=>loadState(await io.read());
  const save=s=>io.write(s);
  const account=async()=>{const a=accountFromStatus(await io.status());return {key:await io.hash(a.identity),label:a.label};};
  const observation=async expected=>{
    const before=await account();if(before.key!==expected)throw new Error('identity_changed');
    const result=ledgerObservation(await io.points(),io.now());
    const after=await account();if(after.key!==expected)throw new Error('identity_changed');
    return result;
  };
  async function alarms(s){
    await io.clearAlarms();
    if(s.enabled)for(const slot of SLOTS)await io.alarm('slot-'+slot,nextSlot(slot,io.now()));
    if(s.task && INFLIGHT.has(s.task.state))await io.alarm('watch-'+s.task.id,s.task.deadline);
  }
  async function init(){
    if(ready)return;
    await io.restrictStorage();
    const s=await read();
    // An interrupted operation is never resumed by repeating its side effect.
    if(s.task&&INFLIGHT.has(s.task.state)){
      s.task={...s.task,state:s.task.state==='SUBMITTING'?'UNKNOWN':'NEEDS_USER',detail:'worker_interrupted'};
      s.enabled=false;
    }
    await save(s);await alarms(s);ready=true;
  }
  async function markFailure(s,error,submitted=false){
    if(s.task)s.task={...s.task,state:submitted?'UNKNOWN':'NEEDS_USER',detail:error==='identity_changed'?'identity_changed':'check_failed'};
    s.enabled=false;await save(s);await alarms(s);return s;
  }
  async function start(reason,explicit,e){
    await init();if(e!==epoch)return read();let s=await read();
    if(!s.binding)throw new Error('connect_first');
    if(reason!=='manual'&&!s.enabled)return s;
    if(reason==='manual'&&explicit!==true)throw new Error('consent_required');
    if(s.task && BLOCKING.has(s.task.state))return s;
    if(s.task?.state==='OBSERVED'&&s.task.day===beijingDay(io.now()))return s;
    try{
      const a=await account();if(e!==epoch)return read();
      if(a.key!==s.binding.key)return markFailure(s,'identity_changed');
      const obs=await observation(s.binding.key);if(e!==epoch)return read();
      s.observation=obs;
      if(obs.todayCheckinRecords>0){s.task={id:io.uuid(),accountKey:a.key,day:beijingDay(io.now()),state:'OBSERVED',detail:'ledger_not_request_attribution'};await save(s);return s;}
      s.task={id:io.uuid(),accountKey:a.key,day:beijingDay(io.now()),state:'PREPARING',reason,tabId:null,documentId:null,deadline:io.now()+180000};
      await save(s);if(e!==epoch)return read();
      // One persisted task precedes opening exactly one owned page.
      const tab=await io.openTab(ORIGIN+'/console/checkin#glados-task='+s.task.id);
      s.task.tabId=tab.id;
      if(e!==epoch){s.task.state='NEEDS_USER';s.task.detail='cancelled';s.enabled=false;await save(s);return s;}
      s.task.state='PAGE_OPEN';await save(s);await alarms(s);return s;
    }catch(error){if(e!==epoch)return read();return markFailure(s,error.message);}
  }
  async function content(type,msg,sender,e){
    await init();if(e!==epoch)return {allowed:false,accepted:false};let s=await read(),task=s.task;
    if(!validContentSender(sender,task)||msg.taskId!==task.id)throw new Error('unowned_message');
    if(type==='task-ready'){
      if(task.state!=='PAGE_OPEN')return {allowed:false};
      task.documentId=sender.documentId;await save(s);return {allowed:true,taskId:task.id};
    }
    if(type==='authorize-submit'){
      if(task.state!=='PAGE_OPEN'||task.documentId!==sender.documentId)return {allowed:false};
      try{
        const a=await account();if(e!==epoch)return {allowed:false};
        if(a.key!==task.accountKey){await markFailure(s,'identity_changed');return {allowed:false};}
        const obs=await observation(task.accountKey);if(e!==epoch)return {allowed:false};
        s.observation=obs;
        if(obs.todayCheckinRecords>0){task.state='OBSERVED';task.detail='ledger_not_request_attribution';await save(s);return {allowed:false};}
        // Crash after this write but before click => UNKNOWN, not retry.
        task.state='SUBMITTING';task.deadline=io.now()+90000;await save(s);
        if(e!==epoch)return {allowed:false};
        await alarms(s);if(e!==epoch)return {allowed:false};
        return {allowed:true,taskId:task.id};
      }catch(error){if(e===epoch)await markFailure(s,error.message);return {allowed:false};}
    }
    if(type==='needs-user'){
      if(!INFLIGHT.has(task.state))return {accepted:false};
      task.state=task.state==='SUBMITTING'?'UNKNOWN':'NEEDS_USER';task.detail='page_requires_attention';s.enabled=false;await save(s);await alarms(s);return {accepted:true};
    }
    if(type==='observe-after-submit'){
      if(task.state!=='SUBMITTING')return {accepted:false};
      try{
        const obs=await observation(task.accountKey);if(e!==epoch)return {accepted:false};
        s.observation=obs;task.state=obs.todayCheckinRecords>0?'OBSERVED':'UNKNOWN';task.detail='ledger_not_request_attribution';
        if(task.state==='UNKNOWN')s.enabled=false;
        await save(s);await alarms(s);return {accepted:true};
      }catch(error){if(e===epoch)await markFailure(s,error.message,true);return {accepted:false};}
    }
    throw new Error('unknown_message');
  }
  return {
    initialize:()=>serial(init),
    getState:()=>serial(async()=>{await init();return read();}),
    connect:()=>{const e=epoch;return serial(async()=>{await init();if(e!==epoch)return read();const a=await account();if(e!==epoch)return read();const s=await read();if(s.task&&BLOCKING.has(s.task.state))throw new Error('review_task_first');s.binding=a;s.observation=null;s.enabled=false;s.task=null;await save(s);await alarms(s);return s;});},
    enable:consent=>{const e=epoch;return serial(async()=>{await init();if(e!==epoch)return read();if(consent!==true)throw new Error('consent_required');const s=await read();if(!s.binding)throw new Error('connect_first');if(s.task&&BLOCKING.has(s.task.state))throw new Error('review_task_first');const a=await account();if(e!==epoch)return read();if(a.key!==s.binding.key)throw new Error('identity_changed');s.enabled=true;await save(s);await alarms(s);return s;});},
    pause:()=>{++epoch;return serial(async()=>{await init();const s=await read();s.enabled=false;if(s.task&&INFLIGHT.has(s.task.state)){s.task.state=s.task.state==='SUBMITTING'?'UNKNOWN':'NEEDS_USER';s.task.detail='paused';}await save(s);await alarms(s);return s;});},
    forget:()=>{++epoch;return serial(async()=>{await init();await io.clearAlarms();await io.clear();return blankState();});},
    reviewTask:consent=>serial(async()=>{await init();if(consent!==true)throw new Error('consent_required');const s=await read();s.enabled=false;s.task=null;await save(s);await alarms(s);return s;}),
    run:(reason,explicit)=>{const e=epoch;return serial(()=>start(reason,explicit,e));},
    content:(type,msg,sender)=>{const e=epoch;return serial(()=>content(type,msg,sender,e));},
    alarm:name=>{const e=epoch;return serial(async()=>{await init();if(e!==epoch)return read();const s=await read();if(name.startsWith('watch-')){if(s.task&&name==='watch-'+s.task.id&&INFLIGHT.has(s.task.state)&&io.now()>=s.task.deadline){s.task.state=s.task.state==='SUBMITTING'?'UNKNOWN':'NEEDS_USER';s.task.detail='timeout';s.enabled=false;await save(s);await alarms(s);}return s;}if(SLOTS.some(slot=>name==='slot-'+slot)){await start('alarm',false,e);await alarms(await read());}return read();});},
    tabClosed:tabId=>serial(async()=>{await init();const s=await read();if(s.task?.tabId===tabId&&INFLIGHT.has(s.task.state)){s.task.state=s.task.state==='SUBMITTING'?'UNKNOWN':'NEEDS_USER';s.task.detail='page_closed';s.enabled=false;await save(s);await alarms(s);}return s;})
  };
}
