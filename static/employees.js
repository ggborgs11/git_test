const admin=true;
const $=id=>document.getElementById(id);
const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let employeeRows=[];
async function api(path,body){
  const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
  const data=await response.json();
  if(response.status===401){location.replace('/admin/201'+location.search);throw new Error('Admin login required.');}
  if(!response.ok)throw new Error(data.error||'Request failed');
  return data;
}
function directory(){
  const query=$('search').value.trim().toLowerCase();
  const rows=employeeRows.filter(p=>[p.name,p.employee_id,p.barcode].some(value=>String(value||'').toLowerCase().includes(query)));
  $('directory').innerHTML=rows.length?rows.map(p=>`<button type="button" class="employee-row" data-profile-id="${p.id}"><span class="employee-row-details"><b>${esc(p.name)}</b><small>Employee ID: ${esc(p.employee_id||'Not set')} · ${p.barcode?'Barcode: '+esc(p.barcode):'Barcode not assigned'}</small></span><span class="employee-row-edit">Edit 201 file →</span></button>`).join(''):'<p class="empty">No employees found. Choose New 201 file to add an employee.</p>';
}
async function refresh(){
  try{employeeRows=(await api('/api/employees')).people;directory();}
  catch(e){$('global-message').textContent='Could not load employees: '+e.message;}
}
$('search').addEventListener('input',directory);
refresh();setInterval(refresh,10000);
