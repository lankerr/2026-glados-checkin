// Display only verified local snapshots. No demo values or success inference.
export function dashboardView(state) {
 const snapshot=state?.observation;
 const validPoints=typeof snapshot?.points==='number'&&Number.isFinite(snapshot.points);
 return {
  account:state?.binding?.label || '未连接',
  enabled:state?.enabled===true,
  task:state?.task?.state || 'NO_TASK',
  points:validPoints?String(snapshot.points):'—',
  checkedAt:typeof snapshot?.checkedAt==='number'&&Number.isFinite(snapshot.checkedAt)?snapshot.checkedAt:null,
  count:Number.isInteger(snapshot?.todayCheckinRecords)&&snapshot.todayCheckinRecords>=0?snapshot.todayCheckinRecords:null,
  day:typeof snapshot?.day==='string'?snapshot.day:'—'
 };
}
export function isDashboardSender(sender,runtime) {
 return sender?.id===runtime.id && sender.url===runtime.getURL('dashboard/index.html')
  && (sender.frameId===undefined||sender.frameId===0);
}
