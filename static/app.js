const admin = location.pathname === '/admin' || location.pathname === '/admin/';
const $ = id => document.getElementById(id);
let state = {people: [], events: []}, todayEvents = [], busy = false, zone = 'Asia/Manila';
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials = name => name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
const time = timestamp => new Date(timestamp).toLocaleTimeString('en-PH',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit'});
async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if(response.status===401 && admin && path !== '/api/scan') location.replace('/admin');
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function directory() {
  const query=$('search').value.trim().toLowerCase();
  const people=state.people.filter(p=>p.name.toLowerCase().includes(query)||String(p.barcode||'').includes(query));
  $('directory').innerHTML=people.length?people.map(p=>`<div class="person"><span class="avatar">${esc(initials(p.name))}</span><div class="details"><b>${esc(p.name)}</b><small>${p.barcode?esc(p.barcode):'No barcode assigned'}</small></div><a class="profile-open" href="/admin/201?person=${p.id}">Edit 201 file</a>${p.barcode?`<span class="badge ${p.status==='out'?'out':''}">${p.status==='in'?'In':'Out'}</span>`:`<button type="button" class="profile-open" data-assign-id="${p.id}">Assign barcode</button>`}</div>`).join(''):'<p class="empty">No employees found. Create a 201 file first.</p>';
}

function render() {
  $('total').textContent = admin ? state.people.length : state.total;
  $('inside').textContent = admin ? state.people.filter(p=>p.status==='in').length : state.inside;
  $('scans').textContent = admin ? todayEvents.length : state.scans;
  $('recent').innerHTML = todayEvents.length ? todayEvents.slice(0,8).map(e=>`<div class="activity"><span class="avatar">${esc(initials(e.name))}</span><div class="details"><b>${esc(e.name)}</b><small>Barcode ${esc(e.barcode)}</small></div><span class="badge ${e.action==='out'?'out':''}">Time ${e.action==='in'?'In':'Out'}</span><time>${time(e.timestamp)}</time></div>`).join('') : '<p class="empty">A fresh start.<br>Today’s scans will appear here.</p>';
  if(!admin) return;
  $('records-body').innerHTML = state.events.map(e=>`<tr><td>${esc(e.name)}</td><td>${esc(e.barcode)}</td><td><span class="badge ${e.action==='out'?'out':''}">Time ${e.action==='in'?'In':'Out'}</span></td><td>${time(e.timestamp)}</td></tr>`).join('');
  $('records-empty').hidden = state.events.length > 0;
  $('export').href = '/api/export?date='+encodeURIComponent($('date').value);
  $('timezone').textContent = `Times shown in ${zone}. Export the selected day for Excel.`;
  directory();
}
async function refresh() {
  try {
    if(!admin) {
      state=await api('/api/desk');zone=state.timezone;todayEvents=state.events;
      render();$('connection').textContent='Connected';$('global-message').textContent='';return;
    }
    const selected = $('date').value;
    state = await api('/api/state'+(selected?'?date='+encodeURIComponent(selected):''));
    zone = state.timezone;
    if (!selected) $('date').value = state.today;
    todayEvents = $('date').value===state.today ? state.events : (await api('/api/state')).events;
    render();
    $('connection').textContent='Connected';
    $('global-message').textContent='';
  } catch(e) {
    $('connection').textContent='Offline';
    $('global-message').textContent='Cannot refresh records: '+e.message;
  }
}
for (const tab of document.querySelectorAll('.tab')) tab.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===tab));
  document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==tab.dataset.view);
  if(tab.dataset.view==='desk') $('barcode').focus();
});
const pendingScans=[];
function focusScanner(){if(!$('desk').hidden) $('barcode').focus();}
$('scan-form').addEventListener('submit',event=>{
  event.preventDefault();
  const barcode=$('barcode').value.trim();
  if(!barcode) return;
  $('barcode').value='';
  focusScanner();
  pendingScans.push(barcode);
  processScans();
});
async function processScans(){
  if(busy) return;
  busy=true;$('scan-form').setAttribute('aria-busy','true');
  while(pendingScans.length){
    const barcode=pendingScans.shift();
    try {
      const result=await api('/api/scan',{barcode});
      $('scan-message').className=result.duplicate?'duplicate':'success';
      const label=result.action==='in'?'Time In':'Time Out';
      $('scan-message').innerHTML=result.duplicate
        ? `<strong class="scan-duplicate">Duplicate scan ignored</strong><span class="scan-person">${esc(result.name)} · Still ${result.action==='in'?'In':'Out'}</span><span class="scan-result-time">Scan again after ${result.retry_after} seconds.</span>`
        : `<strong class="scan-action">${label}</strong><span class="scan-person">${esc(result.name)}</span><time class="scan-result-time">${time(result.timestamp)}</time>`;
      await refresh();
    } catch(e) {
      $('scan-message').className='error';
      $('scan-message').textContent=e.message;
    }
  }
  busy=false;$('scan-form').setAttribute('aria-busy','false');
  // Do not steal focus from admin forms or discard a barcode already being typed.
  if(!admin) focusScanner();
}
window.addEventListener('focus',()=>{if(!admin) focusScanner();});
if(!admin){
  $('barcode').addEventListener('blur',()=>requestAnimationFrame(focusScanner));
  document.addEventListener('pointerdown',event=>{
    if(!event.target.closest('a,button,input')) focusScanner();
  });
}
// RFC 4180-style quoted fields, including commas, escaped quotes, and newlines.
function parseCSV(text) {
  text=text.replace(/^\uFEFF/,'');
  let rows=[],row=[],field='',quoted=false;
  for(let i=0;i<text.length;i++) {
    const c=text[i];
    if(c==='"') {if(quoted&&text[i+1]==='"'){field+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){row.push(field);field='';}
    else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(field);if(row.some(v=>v.trim()))rows.push(row);row=[];field='';}
    else field+=c;
  }
  if(quoted)throw new Error('CSV has an unclosed quotation mark.');
  row.push(field);if(row.some(v=>v.trim()))rows.push(row);
  if(!rows.length)throw new Error('CSV is empty.');
  const headers=rows.shift().map(h=>h.trim().toLowerCase()),name=headers.indexOf('name'),barcode=headers.indexOf('barcode');
  if(name<0)throw new Error('CSV must include a name column.');
  return rows.map(r=>({name:r[name]||'',barcode:barcode<0?'':r[barcode]||''}));
}
if(admin) $('import').addEventListener('change',async()=>{
  const file=$('import').files[0];if(!file)return;
  $('import').disabled=true;
  try {
    if(file.size>200000)throw new Error('Use a CSV smaller than 200 KB.');
    const people=parseCSV(await file.text());
    const result=await api('/api/people',{people});
    $('import-message').textContent=`Imported ${result.people.length} people. Badges are ready to print.`;
    await refresh();
  }catch(e){$('import-message').textContent=e.message;}finally{$('import').disabled=false;$('import').value='';}
});
// Code 39: n = narrow, w = wide; each character has nine alternating bars/spaces.
const patterns={'0':'nnnwwnwnn','1':'wnnwnnnnw','2':'nnwwnnnnw','3':'wnwwnnnnn','4':'nnnwwnnnw','5':'wnnwwnnnn','6':'nnwwwnnnn','7':'nnnwnnwnw','8':'wnnwnnwnn','9':'nnwwnnwnn','*':'nwnnwnwnn'};
function barcodeSVG(value) {
  let x=12,bars='';
  for(const c of '*'+value+'*') {
    patterns[c].split('').forEach((width,index)=>{const w=width==='w'?3:1;if(index%2===0)bars+=`<rect x="${x}" y="0" width="${w}" height="50"/>`;x+=w;});x+=1;
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${x+12} 50" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Barcode ${esc(value)}">${bars}</svg>`;
}
if(admin) $('print').addEventListener('click',()=>{
  const query=$('search').value.trim().toLowerCase();
  const people=state.people.filter(p=>p.barcode&&(p.name.toLowerCase().includes(query)||p.barcode.includes(query)));
  if(!people.length){$('assignment-message').textContent='No assigned barcodes to print for this search.';return;}
  $('badges').innerHTML=people.map(p=>`<article class="print-badge"><small>Cavite Nagano Seiko Inc. · ATTENDANCE</small><h3>${esc(p.name)}</h3>${barcodeSVG(p.barcode)}<p>${esc(p.barcode)}</p></article>`).join('');
  window.print();
});
if(admin) $('search').addEventListener('input',directory);
if(admin) $('date').addEventListener('change',refresh);
if(admin) $('logout').addEventListener('click',async()=>{
  try {await api('/api/logout',{});location.replace('/');}
  catch(e){$('global-message').textContent='Could not log out: '+e.message;}
});
function clock(){
  const now=new Date();
  $('clock').textContent=now.toLocaleTimeString('en-PH',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit'});
  $('clock-date').textContent=now.toLocaleDateString('en-PH',{timeZone:zone,weekday:'long',month:'long',day:'numeric',year:'numeric'});
}
clock();setInterval(clock,1000);refresh();setInterval(refresh,10000);
if(admin&&location.hash==='#people')document.querySelector('[data-view=people]').click();else focusScanner();

if(admin){
  let assignmentId=null,assigning=false;
  $('directory').addEventListener('click',event=>{
    const button=event.target.closest('[data-assign-id]');if(!button||assigning)return;
    const person=state.people.find(p=>p.id===Number(button.dataset.assignId));if(!person)return;
    assignmentId=person.id;$('assign-name').value=person.name;$('assign-barcode').value='';
    $('assign-save').disabled=false;$('assign-generate').disabled=false;$('assignment-message').textContent='';
    $('assign-name').scrollIntoView({block:'center'});$('assign-barcode').focus();
  });
  async function saveBarcode(generate){
    if(assigning||assignmentId===null)return;
    const barcode=$('assign-barcode').value.trim();
    if(!generate&&!barcode){$('assignment-message').textContent='Enter a barcode or choose Generate & assign barcode.';return;}
    assigning=true;$('assign-save').disabled=true;$('assign-generate').disabled=true;
    try{
      const result=await api('/api/people/'+assignmentId+'/barcode',generate?{}:{barcode});
      $('assignment-message').textContent=`Assigned ${result.barcode} to ${result.name}. Ready for scanning and badge printing.`;
      assignmentId=null;$('barcode-form').reset();await refresh();
    }catch(e){$('assignment-message').textContent=e.message;}
    finally{assigning=false;$('assign-save').disabled=assignmentId===null;$('assign-generate').disabled=assignmentId===null;}
  }
  $('barcode-form').addEventListener('submit',event=>{event.preventDefault();saveBarcode(false);});
  $('assign-generate').addEventListener('click',()=>saveBarcode(true));
}
