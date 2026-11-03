let attendanceReport=null,attendanceRequest=0;
function attendanceQuery(){
  const params=new URLSearchParams();
  const period=$('records-period').value;
  if(period==='range'){
    params.set('start_date',$('records-start').value);
    params.set('end_date',$('records-end').value);
  }else{
    const value=$(period==='month'?'records-month':'date').value;
    params.set(period==='month'?'month':'date',value||'');
  }
  const department=$('records-department').value;
  if(department)params.set('department',department.slice(2));
  if($('records-person').value)params.set('person',$('records-person').value);
  params.set('sort',$('records-sort').value);
  return params;
}
function populateAttendanceFilters(data){
  const department=$('records-department').value;
  const departments=[...data.departments];
  if(department&&!departments.includes(department.slice(2)))departments.push(department.slice(2));
  $('records-department').innerHTML='<option value="">All departments</option>'+departments.map(d=>`<option value="${esc('d:'+d)}">${esc(d||'No department assigned')}</option>`).join('');
  $('records-department').value=department;
  const selected=$('records-person').value;
  const people=data.people.filter(p=>!department||p.department===department.slice(2));
  $('records-person').innerHTML='<option value="">All employees</option>'+people.map(p=>`<option value="${p.id}">${esc(p.sort_name)}${p.barcode?' · '+esc(p.barcode):''}</option>`).join('');
  $('records-person').value=people.some(p=>String(p.id)===selected)?selected:'';
}
function renderAttendance(data){
  populateAttendanceFilters(data);
  const monthly=data.mode==='month'&&data.employee;
  $('monthly-summary').hidden=!monthly;
  $('export-log').hidden=!monthly;
  if(monthly){
    $('monthly-heading').textContent=`${data.employee.sort_name} · ${data.period} · ${data.employee.department||'No department assigned'}`;
    $('monthly-body').innerHTML=data.days.map(day=>`<tr><td>${esc(day.date)}</td><td>${day.first_in?time(day.first_in):'—'}</td><td>${day.last_out?time(day.last_out):'—'}</td><td>${day.scans||'No scans'}</td></tr>`).join('');
  }
  $('records-body').innerHTML=data.records.map(r=>`<tr><td>${esc(r.date)}</td><td>${esc(r.name)}</td><td>${esc(r.department||'Not assigned')}</td><td>${esc(r.barcode||'—')}</td><td><span class="badge ${r.action==='out'?'out':''}">Time ${r.action==='in'?'In':'Out'}</span></td><td>${time(r.timestamp)}</td></tr>`).join('');
  $('records-empty').hidden=data.records.length>0;
  $('records-status').textContent=`${data.records.length} scan${data.records.length===1?'':'s'} · ${data.period}${data.employee?' · '+data.employee.sort_name:''}`;
  $('timezone').textContent=`Times shown in ${zone}. Departments use existing employee data.`;
  const params=attendanceQuery();
  $('export-log').href='/api/attendance/export?'+params.toString();
  if(monthly)params.set('format','summary');
  $('export').href='/api/attendance/export?'+params.toString();
  $('export').textContent=monthly?'Export monthly CSV ↓':'Export CSV ↓';
  $('export').download=monthly?'attendance-'+data.period+'-employee-'+data.employee.id+'.csv':'attendance-'+data.period+'.csv';
}
async function refreshAttendance(){
  const request=++attendanceRequest;
  $('records-status').textContent='Loading attendance…';
  // Disable exports until their filters and rows match the latest request.
  for(const id of ['export','export-log']){$(id).removeAttribute('href');$(id).setAttribute('aria-disabled','true');}
  try{
    const data=await api('/api/attendance?'+attendanceQuery().toString());
    if(request!==attendanceRequest)return;
    attendanceReport=data;zone=data.timezone;
    for(const id of ['records-start','records-end'])if(!$(id).value)$(id).value=data.today;
    if(!$('date').value)$('date').value=data.today;
    if(!$('records-month').value)$('records-month').value=data.today.slice(0,7);
    renderAttendance(data);
    for(const id of ['export','export-log'])$(id).removeAttribute('aria-disabled');
  }catch(e){if(request===attendanceRequest){$('records-status').textContent='Could not load attendance: '+e.message;}}
}
if(admin){
  const today=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  for(const id of ['records-start','records-end'])if(!$(id).value)$(id).value=today;
  function setPeriod(){
    const monthly=$('records-period').value==='month';
    $('day-filter').hidden=$('records-period').value!=='day';$('month-filter').hidden=!monthly;
    $('range-filter').hidden=$('records-period').value!=='range';
  }
  $('records-period').addEventListener('change',()=>{setPeriod();refreshAttendance();});
  $('records-department').addEventListener('change',()=>{
    if(attendanceReport)populateAttendanceFilters(attendanceReport);
    refreshAttendance();
  });
  $('records-person').addEventListener('change',()=>{
    refreshAttendance();
  });
  for(const id of ['date','records-month','records-start','records-end','records-sort'])$(id).addEventListener('change',refreshAttendance);
}
