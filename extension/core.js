export const ORIGIN = 'https://glados.cloud';
export const SLOTS = ['09:30', '12:30', '20:30'];
const DAY = 86400000;
export function beijingDay(ms = Date.now()) { return new Date(ms + 8 * 3600000).toISOString().slice(0, 10); }
export function nextSlot(slot, ms = Date.now()) {
  if (!/^\d\d:\d\d$/.test(slot)) throw new Error('invalid slot');
  const [h,m]=slot.split(':').map(Number);
  if(h>23||m>59)throw new Error('invalid slot');
  const dayStart=Math.floor((ms+8*3600000)/DAY)*DAY-8*3600000;
  const at=dayStart+h*3600000+m*60000;
  return at>ms?at:at+DAY;
}
export function accountFromStatus(body) {
  const email=body?.code===0 && typeof body?.data?.email==='string' ? body.data.email.trim().toLowerCase():'';
  if(!/^[^\s@]+@[^\s@]+$/.test(email)||email.length>254)throw new Error('identity_unconfirmed');
  return {identity:email,label:email[0]+'***@'+email.split('@')[1]};
}
export function ledgerObservation(body, ms=Date.now()) {
  if(!body || !['number','string'].includes(typeof body.points) || String(body.points).trim()==='' || !Number.isFinite(Number(body.points)))throw new Error('ledger_unconfirmed');
  if(body.code!==undefined && body.code!==0)throw new Error('ledger_unconfirmed');
  const history=Array.isArray(body.history)?body.history:Array.isArray(body.list)?body.list:null;
  if(!history)throw new Error('ledger_unconfirmed');
  // Exact business whitelist only. No text/amount inference, no compensation/refund/exchange.
  let todayCheckinRecords=0;
  for(const e of history.slice(0,10)){
    if(!e||String(e.business).trim().toLowerCase()!=='checkin')continue;
    const time=Number(e.time),change=Number(e.change);
    if(!Number.isFinite(time)||time<=0||time>ms+300000||!Number.isFinite(change)||change<=0)continue;
    if(beijingDay(time)===beijingDay(ms))todayCheckinRecords++;
  }
  return {points:Number(body.points),todayCheckinRecords,checkedAt:ms,day:beijingDay(ms),scope:'first_10_returned_records'};
}
export const INFLIGHT = new Set(['PREPARING','PAGE_OPEN','SUBMITTING']);
export const BLOCKING = new Set([...INFLIGHT,'UNKNOWN','NEEDS_USER']);
export function blankState(){return {version:2,enabled:false,binding:null,task:null,observation:null};}
export function loadState(raw){
  if(raw?.version!==2)return blankState();
  return {...blankState(),...raw,enabled:raw.enabled===true};
}
export function validContentSender(sender,task){
  if(!task||sender?.tab?.id!==task.tabId||sender.frameId!==0||typeof sender.documentId!=='string')return false;
  try {const u=new URL(sender.url);return u.origin===ORIGIN && u.pathname==='/console/checkin' && u.hash==='#glados-task='+task.id && (!task.documentId||sender.documentId===task.documentId);}catch{return false;}
}
