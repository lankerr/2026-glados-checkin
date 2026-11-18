import {dashboardView} from './view-model.js';
const $=id=>document.getElementById(id);
const labels={NO_TASK:'没有任务',PREPARING:'准备页面',PAGE_OPEN:'等待页面',SUBMITTING:'提交阶段，结果未确认（可能尚未点击）',OBSERVED:'观察到签到记录，不归因本次',UNKNOWN:'结果未知，请核查',NEEDS_USER:'需要人工处理'};
async function refresh(){
 $('refresh').disabled=true;
 try{
  const api=globalThis.browser??globalThis.chrome;
  const response=await api.runtime.sendMessage({type:'dashboard-state'});
  if(!response?.ok)throw Error('unavailable');
  const v=dashboardView(response.data);
  $('account').textContent=v.account;$('enabled').textContent=v.enabled?'已启用':'暂停';
  $('task').textContent=v.task;$('task-label').textContent=labels[v.task]||'未识别的状态，请核查';
  $('points').textContent=v.points;$('day').textContent=v.day;$('count').textContent=v.count===null?'—':String(v.count);
  $('checked-at').textContent=v.checkedAt===null?'尚无有效快照':new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium',timeStyle:'medium',hour12:false}).format(v.checkedAt)+' 北京时间';
  $('updated').textContent='已读取本地记录，没有访问官网';
 }catch{
  for(const id of ['account','enabled','task','points','day','count','checked-at'])$(id).textContent='—';
  $('task-label').textContent='尚未读取';
  $('updated').textContent='无法读取。请从已加载的扩展设置页打开；未进行联网或签到。';
 }finally{$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);refresh();
