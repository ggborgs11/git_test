const admin = location.pathname === '/admin' || location.pathname === '/admin/';
const $ = id => document.getElementById(id);
const selectedEmployees=new Set();
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
  $('directory').innerHTML=people.length?people.map(p=>`<div class="person"><span class="avatar">${esc(initials(p.name))}</span><div class="details"><b>${esc(p.name)}</b><small>${p.barcode?esc(p.barcode):'No barcode assigned'}</small></div>${p.barcode?`<span class="badge ${p.status==='out'?'out':''}">${p.status==='in'?'In':'Out'}</span>`:`<button type="button" class="profile-open" data-assign-id="${p.id}">Assign barcode</button>`}<button type="button" class="secondary" data-delete-id="${p.id}">Delete</button></div>`).join(''):'<p class="empty">No employees found. Add an employee or import a CSV.</p>';
}

function allEmployees(){
  const query=$('employees-search').value.trim().toLowerCase();
  const people=state.people.filter(p=>p.name.toLowerCase().includes(query)||String(p.barcode||'').includes(query))
    .sort((a,b)=>a.name.localeCompare(b.name)||a.id-b.id);
  $('employees-count').textContent=`${people.length} of ${state.people.length} employees`;
  for(const id of selectedEmployees)if(!state.people.some(p=>p.id===id))selectedEmployees.delete(id);
  $('employees-selected').textContent=`${selectedEmployees.size} selected`;
  if(!$('bulk-department-form').dataset.saving)$('bulk-department-save').disabled=selectedEmployees.size===0;
  $('employees-list').innerHTML=people.length?people.map(p=>`<div class="person"><input class="employee-select" type="checkbox" data-select-id="${p.id}" aria-label="Select ${esc(p.name)}" ${selectedEmployees.has(p.id)?'checked':''}><div class="details"><b>${esc(p.name)}</b><small>${esc(p.department||'No department assigned')} · ${p.barcode?'Barcode '+esc(p.barcode):'No barcode assigned'}</small></div><button type="button" class="secondary" data-edit-id="${p.id}">Edit</button><button type="button" class="secondary" data-delete-id="${p.id}" aria-label="Delete ${esc(p.name)}">Delete</button></div>`).join(''):'<p class="empty">No employees found.</p>';
}

function render() {
  $('total').textContent = admin ? state.people.length : state.total;
  $('inside').textContent = admin ? state.people.filter(p=>p.status==='in').length : state.inside;
  $('scans').textContent = admin ? todayEvents.length : state.scans;
  $('recent').innerHTML = todayEvents.length ? todayEvents.slice(0,8).map(e=>`<div class="activity"><span class="avatar">${esc(initials(e.name))}</span><div class="details"><b>${esc(e.name)}</b><small>Barcode ${esc(e.barcode)}</small></div><span class="badge ${e.action==='out'?'out':''}">Time ${e.action==='in'?'In':'Out'}</span><time>${time(e.timestamp)}</time></div>`).join('') : '<p class="empty">A fresh start.<br>Today’s scans will appear here.</p>';
  if(!admin) return;
  directory();
  allEmployees();
}
async function refresh() {
  try {
    if(!admin) {
      state=await api('/api/desk');zone=state.timezone;todayEvents=state.events;
      render();$('connection').textContent='Connected';$('global-message').textContent='';return;
    }
    state=await api('/api/state');zone=state.timezone;todayEvents=state.events;
    const employees=await api('/api/employees');
    const details=new Map(employees.people.map(p=>[p.id,p]));
    state.people=state.people.map(p=>({...p,department:details.get(p.id)?.department||''}));
    for(const id of ['records-start','records-end'])if(!$(id).value)$(id).value=state.today;
    if(!$('date').value)$('date').value=state.today;
    if(!$('records-month').value)$('records-month').value=state.today.slice(0,7);
    render();
    $('connection').textContent='Connected';
    $('global-message').textContent='';
    if(!$('records').hidden&&typeof refreshAttendance==='function')await refreshAttendance();
  } catch(e) {
    $('connection').textContent='Offline';
    $('global-message').textContent='Cannot refresh records: '+e.message;
  }
}
for (const tab of document.querySelectorAll('.tab')) tab.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t===tab));
  document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==tab.dataset.view);
  if(tab.dataset.view==='desk') $('barcode').focus();
  if(tab.dataset.view==='records'&&typeof refreshAttendance==='function')refreshAttendance();
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
if(admin) $('employees-search').addEventListener('input',allEmployees);

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
  $('directory').addEventListener('employee-deleted',()=>{assignmentId=null;});
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

if(admin){
  let addingEmployee=false;
  $('add-employee-form').addEventListener('submit',async event=>{
    event.preventDefault();
    if(addingEmployee)return;
    const last=$('employee-last-name').value.trim();
    const first=$('employee-first-name').value.trim();
    if(!last||!first){$('add-employee-message').textContent='Enter both Last name and First name.';return;}
    addingEmployee=true;$('add-employee-save').disabled=true;
    $('add-employee-message').textContent='Adding employee…';
    try{
      const result=await api('/api/employees',{
        name:`${last}, ${first}`,
        profile:{last_name:last,first_name:first,department:$('employee-department').value.trim()}
      });
      $('add-employee-form').reset();
      $('search').value='';
      $('add-employee-message').textContent=`Added ${result.people[0].name}. Choose Assign barcode in the directory to enable scanning.`;
      await refresh();
    }catch(e){$('add-employee-message').textContent=e.message;}
    finally{addingEmployee=false;$('add-employee-save').disabled=false;}
  });
}

if(admin){
  let editingEmployee=null,savingEmployee=false,editRequest=0;
  $('employees-list').addEventListener('click',async event=>{
    const button=event.target.closest('[data-edit-id]');
    if(!button||savingEmployee)return;
    const request=++editRequest;
    $('employee-edit-form').hidden=false;
    editingEmployee=null;$('employee-edit-save').disabled=true;
    $('employee-edit-message').textContent='Loading employee…';
    try{
      const person=await api('/api/people/'+Number(button.dataset.editId));
      if(request!==editRequest)return;
      editingEmployee=person;
      $('edit-name').value=person.name;
      $('edit-department').value=person.profile.department||'';
      $('employee-edit-message').textContent='';
      $('employee-edit-save').disabled=false;
      $('employee-edit-form').scrollIntoView({block:'center'});$('edit-name').focus();
    }catch(e){if(request===editRequest)$('employee-edit-message').textContent=e.message;}
  });
  $('employee-edit-cancel').addEventListener('click',()=>{
    if(savingEmployee)return;
    ++editRequest;editingEmployee=null;$('employee-edit-form').hidden=true;
  });
  $('employee-edit-form').addEventListener('submit',async event=>{
    event.preventDefault();if(!editingEmployee||savingEmployee)return;
    const name=$('edit-name').value.trim();
    if(!name){$('employee-edit-message').textContent='Enter an employee name.';return;}
    const profile={...editingEmployee.profile,department:$('edit-department').value.trim()};
    if(name!==editingEmployee.name){
      const comma=name.indexOf(',');
      profile.last_name=comma>=0?name.slice(0,comma).trim():'';
      profile.first_name=comma>=0?name.slice(comma+1).trim():'';
    }
    savingEmployee=true;$('employee-edit-save').disabled=true;$('employee-edit-cancel').disabled=true;
    try{
      await api('/api/people/'+editingEmployee.id,{name,profile,version:editingEmployee.version});
      $('employees-message').textContent=`Saved ${name}.`;
      $('employee-edit-form').hidden=true;editingEmployee=null;
      await refresh();
    }catch(e){$('employee-edit-message').textContent=e.message;}
    finally{savingEmployee=false;$('employee-edit-save').disabled=false;$('employee-edit-cancel').disabled=false;}
  });
}

if(admin){
  let deletingEmployee=false,pendingDeletion=null,deleteMessage=null,deleteTrigger=null;
  function closeDeletion(){
    if(deletingEmployee)return;
    $('delete-overlay').hidden=true;
    pendingDeletion=null;
    if(deleteTrigger&&deleteTrigger.isConnected)deleteTrigger.focus();
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-delete-id]');
    if(!button||deletingEmployee||!$('delete-overlay').hidden)return;
    const person=state.people.find(p=>p.id===Number(button.dataset.deleteId));
    if(!person)return;
    pendingDeletion=person;deleteTrigger=button;
    deleteMessage=button.closest('#employees-list')?$('employees-message'):$('assignment-message');
    $('delete-description').textContent=`Permanently delete ${person.name}? This removes their employee details, barcode, images, and all attendance records. This cannot be undone.`;
    $('delete-error').textContent='';
    $('delete-overlay').hidden=false;
    $('delete-cancel').focus();
  });
  $('delete-cancel').addEventListener('click',closeDeletion);
  $('delete-overlay').addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();closeDeletion();}
    if(event.key==='Tab'){
      event.preventDefault();
      const next=document.activeElement===$('delete-cancel')?$('delete-confirm'):$('delete-cancel');
      if(!next.disabled)next.focus();
    }
  });
  $('delete-confirm').addEventListener('click',async()=>{
    if(!pendingDeletion||deletingEmployee)return;
    const person=pendingDeletion;
    deletingEmployee=true;
    $('delete-confirm').disabled=true;$('delete-cancel').disabled=true;
    $('delete-confirm').textContent='Deleting…';$('delete-error').textContent='';
    try{
      await api('/api/people/'+person.id+'/delete',{confirm:true});
      state.people=state.people.filter(p=>p.id!==person.id);
      state.events=state.events.filter(e=>e.person_id!==person.id);
      deleteMessage.textContent=`Deleted ${person.name} and their attendance records.`;
      $('directory').dispatchEvent(new Event('employee-deleted'));
      $('assign-name').value='';$('assign-barcode').value='';
      $('assign-save').disabled=true;$('assign-generate').disabled=true;
      directory();allEmployees();
      $('delete-overlay').hidden=true;pendingDeletion=null;
      const search=deleteMessage===$('employees-message')?$('employees-search'):$('search');
      search.focus();
      await refresh();
    }catch(e){$('delete-error').textContent='Could not delete employee: '+(e.message==='Not found'?'Update app.py from GitHub and restart the Python server, then reload this page.':e.message);}
    finally{
      deletingEmployee=false;
      $('delete-confirm').disabled=false;$('delete-cancel').disabled=false;
      $('delete-confirm').textContent='Delete permanently';
    }
  });
}
