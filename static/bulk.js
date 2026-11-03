if(admin){
  let savingDepartment=false;
  $('employees-list').addEventListener('change',event=>{
    const box=event.target.closest('[data-select-id]');if(!box||savingDepartment)return;
    const id=Number(box.dataset.selectId);
    if(box.checked)selectedEmployees.add(id);else selectedEmployees.delete(id);
    allEmployees();
  });
  $('employees-select-visible').addEventListener('click',()=>{
    if(savingDepartment)return;
    const query=$('employees-search').value.trim().toLowerCase();
    for(const person of state.people){
      if(person.name.toLowerCase().includes(query)||String(person.barcode||'').includes(query))selectedEmployees.add(person.id);
    }
    allEmployees();
  });
  $('employees-clear-selection').addEventListener('click',()=>{
    if(savingDepartment)return;selectedEmployees.clear();allEmployees();
  });
  $('bulk-department-form').addEventListener('submit',async event=>{
    event.preventDefault();if(savingDepartment)return;
    const people=[...selectedEmployees],department=$('bulk-department').value.trim();
    if(!people.length||!department){$('bulk-department-message').textContent='Select employees and enter a department.';return;}
    savingDepartment=true;$('bulk-department-form').dataset.saving='true';
    $('bulk-department-save').disabled=true;
    $('bulk-department-message').textContent=`Updating ${people.length} employees…`;
    try{
      const result=await api('/api/employees/department',{people,department});
      for(const id of people)selectedEmployees.delete(id);
      $('bulk-department-message').textContent=`Updated ${result.updated} employees to ${result.department}.`;
      await refresh();
    }catch(e){$('bulk-department-message').textContent=e.message;}
    finally{savingDepartment=false;delete $('bulk-department-form').dataset.saving;allEmployees();}
  });
}
