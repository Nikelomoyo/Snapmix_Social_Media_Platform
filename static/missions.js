// Missions stay useful without JS: all participation and discussion use real forms.
document.querySelectorAll('[data-mission-react]').forEach(button=>button.addEventListener('click',async()=>{
  button.disabled=true;
  try{
    const response=await fetch(button.dataset.missionReact,{method:'POST',headers:{'X-CSRFToken':document.querySelector('#csrf input').value,'Accept':'application/json'}});
    if(!response.ok)throw Error(response.status===429?'A little too fast. Try again in a minute.':'Could not save your reaction. Please try again.');
    const data=await response.json();
    button.setAttribute('aria-pressed',String(data.active));
    button.querySelector('span').textContent=data.count;
  }catch(error){toast(error.message)}finally{button.disabled=false}
}));

const missionLive=document.querySelector('#mission-live');
if(missionLive){
  const notice=document.querySelector('#mission-refresh'),refresh=document.querySelector('#mission-refresh-button');
  const initial=JSON.parse(document.querySelector('#mission-initial-state').textContent);
  let stopped=false,busy=false;
  function changed(){notice.hidden=false}
  refresh.addEventListener('click',()=>{
    const draft=document.querySelector('#mission-discussion textarea');
    if(draft?.value.trim()&&!confirm('Refreshing will clear your unsent reply. Refresh anyway?'))return;
    location.reload();
  });
  function countdown(){
    if(missionLive.dataset.closed==='true')return;
    const remaining=new Date(missionLive.dataset.ends).getTime()-Date.now();
    const label=missionLive.querySelector('.mission-countdown');
    if(remaining<=0){label.textContent='Finished';changed();return}
    const minutes=Math.ceil(remaining/60000),hours=Math.floor(minutes/60),days=Math.floor(hours/24);
    label.textContent=days?`${days}d ${hours%24}h`:hours?`${hours}h ${minutes%60}m`:`${minutes}m`;
  }
  async function check(){
    if(stopped||busy||document.visibilityState!=='visible')return;
    busy=true;
    try{
      const response=await fetch(missionLive.dataset.updates,{headers:{Accept:'application/json'}});
      if(response.redirected||response.status===404||response.status===403){stopped=true;return}
      if(!response.ok)return;
      const latest=await response.json();
      if(Object.keys(initial).some(key=>initial[key]!==latest[key]))changed();
    }catch{/* Keep the existing collection usable through a connection interruption. */}
    finally{busy=false}
  }
  countdown();
  const timer=setInterval(()=>{countdown();check()},15000);
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'){countdown();check()}});
  window.addEventListener('pagehide',()=>{stopped=true;clearInterval(timer)});
}
