// Isolated-world page executor. Never hooks page fetch/XHR or handles CAPTCHA tokens.
(async()=>{
  const match=location.hash.match(/^#glados-task=([a-f0-9-]{36})$/);
  if(!match||location.origin!=='https://glados.cloud'||location.pathname!=='/console/checkin'||window.top!==window)return;
  const taskId=match[1];
  const send=async type=>{
    try {const r=await chrome.runtime.sendMessage({type,taskId});return r?.ok?r.data:null;}catch{return null;}
  };
  const ready=await send('task-ready');if(!ready?.allowed)return;
  const visible=el=>el.getClientRects().length>0 && getComputedStyle(el).visibility!=='hidden';
  const started=Date.now();
  while(Date.now()-started<60000){
    // A visible official challenge is handed to the user, never clicked or solved by this executor.
    if([...document.querySelectorAll('iframe')].some(el=>visible(el)&&/challenges\.cloudflare\.com/i.test(el.src))){await send('needs-user');return;}
    const buttons=[...document.querySelectorAll('button')].filter(b=>visible(b)&&!b.disabled&&/^check\s*in$/i.test((b.textContent||b.getAttribute('aria-label')||'').trim()));
    if(buttons.length===1){
      const permission=await send('authorize-submit');if(!permission?.allowed)return;
      // User navigation or a new interactive challenge after authorisation must not lead to a blind click.
      if(location.hash!=='#glados-task='+taskId||!buttons[0].isConnected||buttons[0].disabled||!visible(buttons[0])||[...document.querySelectorAll('iframe')].some(el=>visible(el)&&/challenges\.cloudflare\.com/i.test(el.src))){await send('needs-user');return;}
      buttons[0].click();
      await new Promise(resolve=>setTimeout(resolve,4000));
      await send('observe-after-submit');
      return; // Never click a second time. Worker watchdog handles termination/lost messages.
    }
    await new Promise(resolve=>setTimeout(resolve,500));
  }
  await send('needs-user');
})();
