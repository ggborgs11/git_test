const $ = id => document.getElementById(id);
let action = 'in', state = {people: [], events: []}, todayEvents = [], busy = false, zone = 'Asia/Manila';
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials = name => name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
const time = timestamp => new Date(timestamp).toLocaleTimeString('en-PH',{timeZone:zone,hour:'2-digit',minute:'2-digit',second:'2-digit'});
async function api(path, body) {
  const response = await fetch(path, body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}
function directory() {
  const query = $('search').value.trim().toLowerCase();
  const people = state.people.filter(p=>p.name.toLowerCase().includes(query)||p.barcode.includes(query));
  $('directory').innerHTML = people.length ? people.map(p=>`<div class="person"><span class="avatar">${esc(initials(p.name))}</span><div class="details"><b>${esc(p.name)}</b><small>${esc(p.barcode)}</small></div><span class="badge ${p.status==='out'?'out':''}">${p.status==='in'?'In':'Out'}</span></div>`).join('') : '<p class="empty">No people found. Add a person or import your team.</p>';
}
function render() {
  $('total').textContent = state.people.length;
  $('inside').textContent = state.people.filter(p=>p.status==='in').length;
  $('scans').textContent = todayEvents.length;
  $('recent').innerHTML = todayEvents.length ? todayEvents.slice(0,8).map(e=>`<div class="activity"><span class="avatar">${esc(initials(e.name))}</span><div class="details"><b>${esc(e.name)}</b><small>Barcode ${esc(e.barcode)}</small></div><span class="badge ${e.action==='out'?'out':''}">Time ${e.action==='in'?'In':'Out'}</span><time>${time(e.timestamp)}</time></div>`).join('') : '<p class="empty">A fresh start.<br>Today’s scans will appear here.</p>';
  $('records-body').innerHTML = state.events.map(e=>`<tr><td>${esc(e.name)}</td><td>${esc(e.barcode)}</td><td><span class="badge ${e.action==='out'?'out':''}">Time ${e.action==='in'?'In':'Out'}</span></td><td>${time(e.timestamp)}</td></tr>`).join('');
  $('records-empty').hidden = state.events.length > 0;
  $('export').href = '/api/export?date='+encodeURIComponent($('date').value);
  $('timezone').textContent = `Times shown in ${zone}. Export the selected day for Excel.`;
  directory();
}
async function refresh() {
  try {
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
for(const mode of ['in','out']) $(mode).addEventListener('click',()=>{
  action=mode;
  for(const id of ['in','out']) {$(id).classList.toggle('selected',id===mode);$(id).setAttribute('aria-pressed',id===mode);}
  $('scan-submit').textContent=`Record Time ${mode==='in'?'In':'Out'} →`;
  $('barcode').focus();
});
$('scan-form').addEventListener('submit',async event=>{
  event.preventDefault();
  if(busy) return;
  const barcode=$('barcode').value.trim();
  if(!barcode) return;
  busy=true;
  $('scan-submit').disabled=true;
  try {
    const result=await api('/api/scan',{barcode,action});
    $('scan-message').className='success';
    $('scan-message').textContent=`✓ ${result.name} · Time ${result.action==='in'?'In':'Out'} · ${time(result.timestamp)}`;
    $('barcode').value='';
    await refresh();
  } catch(e) {
    $('scan-message').className='error';
    $('scan-message').textContent=e.message;
    $('barcode').select();
  } finally {busy=false;$('scan-submit').disabled=false;$('barcode').focus();}
});
$('person-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const button=event.currentTarget.querySelector('button');button.disabled=true;
  try {
    const result=await api('/api/people',{people:[{name:$('name').value,barcode:$('new-barcode').value}]});
    $('people-message').textContent=`Added ${result.people[0].name}. Barcode: ${result.people[0].barcode}`;
    $('person-form').reset();await refresh();
  }catch(e){$('people-message').textContent=e.message;}finally{button.disabled=false;}
});
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
$('import').addEventListener('change',async()=>{
  const file=$('import').files[0];if(!file)return;
  $('import').disabled=true;
  try {
    if(file.size>200000)throw new Error('Use a CSV smaller than 200 KB.');
    const people=parseCSV(await file.text());
    const result=await api('/api/people',{people});
    $('people-message').textContent=`Imported ${result.people.length} people. Badges are ready to print.`;
    await refresh();
  }catch(e){$('people-message').textContent=e.message;}finally{$('import').disabled=false;$('import').value='';}
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
$('print').addEventListener('click',()=>{
  const query=$('search').value.trim().toLowerCase();
  const people=state.people.filter(p=>p.name.toLowerCase().includes(query)||p.barcode.includes(query));
  if(!people.length){$('people-message').textContent='Add people before printing badges.';return;}
  $('badges').innerHTML=people.map(p=>`<article class="print-badge"><small>CLOCKWORK · ATTENDANCE</small><h3>${esc(p.name)}</h3>${barcodeSVG(p.barcode)}<p>${esc(p.barcode)}</p></article>`).join('');
  window.print();
});
$('search').addEventListener('input',directory);
$('date').addEventListener('change',refresh);
function clock(){ $('clock').textContent=new Date().toLocaleString('en-PH',{timeZone:zone,month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
clock();setInterval(clock,1000);refresh();setInterval(refresh,10000);$('barcode').focus();
