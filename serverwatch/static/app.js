const api = (path, options) => fetch(path, options).then(async response => {
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
});
const esc = value => String(value ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const when = value => value ? new Date(value).toLocaleString() : "—";

function drawChart(samples) {
  const canvas = document.querySelector('#chart'), ctx = canvas.getContext('2d');
  const w=canvas.width, h=canvas.height, pad=36; ctx.clearRect(0,0,w,h);
  ctx.strokeStyle='#22374a'; ctx.lineWidth=1;
  for(let p=0;p<=100;p+=25){const y=h-pad-(p/100)*(h-pad*1.5);ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-12,y);ctx.stroke();ctx.fillStyle='#71899e';ctx.fillText(`${p}%`,4,y+4)}
  if(samples.length<2) return;
  [['cpu_percent','#61b8ff'],['memory_percent','#3ddc97'],['disk_percent','#ffbd59']].forEach(([key,color])=>{
    ctx.beginPath(); ctx.strokeStyle=color; ctx.lineWidth=2;
    samples.forEach((s,i)=>{const x=pad+i*(w-pad-12)/(samples.length-1),y=h-pad-(s[key]/100)*(h-pad*1.5);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.stroke();
  });
}

async function refresh(){
  try {
    const [status, metrics, incidents, notifications] = await Promise.all([api('api/status'),api('api/metrics?hours=24'),api('api/incidents'),api('api/notifications')]);
    const overall = document.querySelector('#overall');
    const bad = status.health.some(x=>x.status==='unhealthy'), unknown=status.health.some(x=>x.status==='unknown');
    const state = status.stale?'stale':bad?'unhealthy':unknown?'unknown':'healthy'; overall.className=`badge ${state}`; overall.textContent=status.stale?'Data stale':bad?'Attention':'Healthy';
    document.querySelector('#observed').textContent=status.metric?`Observed ${when(status.metric.observed_at)}${status.stale?' · stale':''}`:'No samples';
    const values=status.metric||{}; const labels=[['CPU','cpu_percent','cpu'],['Memory','memory_percent','memory'],['Disk','disk_percent','disk']];
    document.querySelector('#resource-cards').innerHTML=labels.map(([label,key,t])=>`<div class="card"><span>${label}</span><strong>${values[key]===undefined?'—':Number(values[key]).toFixed(1)+'%'}</strong><span>Alert at ${status.thresholds[t]}%</span></div>`).join('');
    document.querySelector('#health').innerHTML=status.health.map(x=>`<div class="health-item"><p><strong>${esc(x.name)}</strong><br><span class="detail">${esc(x.detail)}</span></p><span class="status ${x.status}">${x.status}</span></div>`).join('')||'<p>No health samples.</p>';
    document.querySelector('#incidents').innerHTML=incidents.map(x=>`<tr><td><span class="status ${x.status==='open'?'unhealthy':'healthy'}">${esc(x.status)}</span></td><td>${esc(x.title)}<br><span class="detail">${esc(x.condition)}</span></td><td>${esc(x.measured_value)}</td><td>${when(x.opened_at)}</td><td>${x.resolved_at?when(x.resolved_at):x.acknowledged_at?'Acknowledged':'Open'}</td></tr>`).join('')||'<tr><td colspan="5">No incidents.</td></tr>';
    document.querySelector('#notification-state').textContent=status.notifications_configured?'SMTP notification channel configured.':'SMTP notification channel is not configured; attempts are recorded as skipped.';
    document.querySelector('#notifications').innerHTML=notifications.map(x=>`<tr><td>${when(x.attempted_at)}</td><td>${x.attempt_number}</td><td><span class="status ${x.status==='sent'?'healthy':x.status==='failed'?'unhealthy':'unknown'}">${esc(x.status)}</span></td><td>${esc(x.detail)}</td></tr>`).join('')||'<tr><td colspan="4">No delivery attempts.</td></tr>';
    drawChart(metrics);
  } catch(error){const overall=document.querySelector('#overall');overall.className='badge unknown';overall.textContent='Unavailable';console.error(error)}
}
document.querySelector('#test-notification').addEventListener('click',async event=>{event.currentTarget.disabled=true;try{await api('api/notifications/test',{method:'POST'});alert('Test notification sent.')}catch(error){alert(`Notification failed: ${error.message}`)}finally{event.currentTarget.disabled=false;refresh()}});
refresh(); setInterval(refresh,30000);

