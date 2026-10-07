const profileSections = [["personal", "Personal information", [["employee_id", "Employee ID", "text"], ["last_name", "Last name", "text"], ["first_name", "First name", "text"], ["middle_name", "Middle name", "text"], ["suffix", "Suffix", "text"], ["nickname", "Nickname", "text"], ["current_address", "Current address", "textarea"], ["zip_code", "ZIP code", "text"], ["provincial_address", "Provincial address", "textarea"], ["provincial_zip", "Provincial ZIP code", "text"], ["contact_number", "Contact number", "tel"], ["cellphone", "Cellphone number", "tel"], ["email", "Email address", "email"], ["gender", "Gender", "text"], ["birthplace", "Place of birth", "text"], ["birth_date", "Date of birth", "date"], ["civil_status", "Civil status", "text"], ["citizenship", "Citizenship", "text"], ["religion", "Religion", "text"], ["blood_type", "Blood type", "text"], ["height_cm", "Height (cm)", "number"], ["weight_kg", "Weight (kg)", "number"], ["emergency_name", "Emergency contact name", "text"], ["emergency_relationship", "Relationship", "text"], ["emergency_address", "Emergency contact address", "textarea"], ["emergency_phone", "Emergency contact number", "tel"], ["philhealth", "PhilHealth number", "text"], ["sss", "SSS number", "text"], ["tin", "TIN", "text"], ["pagibig", "Pag-IBIG number", "text"]]], ["education", "Educational background", [["education", "Schools, courses, qualifications, and years attended", "textarea"]]], ["family", "Family background", [["family", "Family members, relationships, and contact details", "textarea"]]], ["employment", "Employment history", [["employment_history", "Previous employers, roles, dates, and reason for leaving", "textarea"]]], ["other", "Other information", [["other_information", "Training, skills, certifications, and other notes", "textarea"]]], ["work", "Work information", [["department", "Department", "text"], ["position", "Position / job title", "text"], ["hire_date", "Date hired", "date"], ["employment_status", "Employment status", "text"], ["shift", "Shift / schedule", "text"], ["supervisor", "Supervisor", "text"], ["work_notes", "Work notes", "textarea"]]]];
if(admin){
  let personId=null,version=0,dirty=false,generatedName='',saving=false,loading=false;
  let imageChanges={},fileReads=0,editorGeneration=0,imageRevision={photo:0,signature:0};
  function profileMessage(text,kind='info'){$('people-message').textContent=text;$('people-message').dataset.kind=kind;}
  function section(key){
    document.querySelectorAll('.profile-tab').forEach(tab=>{
      const active=tab.dataset.section===key;tab.classList.toggle('active',active);
      tab.setAttribute('aria-selected',active);tab.tabIndex=active?0:-1;
    });
    document.querySelectorAll('.profile-panel').forEach(panel=>panel.hidden=panel.id!=='profile-panel-'+key);
  }
  for(const tab of document.querySelectorAll('.profile-tab')){
    tab.addEventListener('click',()=>section(tab.dataset.section));
    tab.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      event.preventDefault();const tabs=[...document.querySelectorAll('.profile-tab')];
      let index=tabs.indexOf(tab);
      index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      section(tabs[index].dataset.section);tabs[index].focus();
    });
  }
  function mayDiscard(){return !dirty||window.confirm('Discard unsaved changes to this 201 file?');}
  function resetEditor(){
    editorGeneration++;
    $('person-form').reset();personId=null;version=0;dirty=false;generatedName='';imageChanges={};
    $('profile-heading').textContent='New 201 file';$('save-person').textContent='Create 201 file';
    profileMessage('');$('profile-barcode-status').textContent='Barcode assignment is handled separately in People & badges.';
    for(const kind of ['photo','signature']){$('preview-'+kind).hidden=true;$('preview-'+kind).removeAttribute('src');}
    section('personal');
  }
  function showEditor(){ $('profile-editor').hidden=false;$('employee-list').hidden=true; }
  function showList(){ $('profile-editor').hidden=true;$('employee-list').hidden=false;history.replaceState(null,'','/admin/201'); }
  $('new-person').addEventListener('click',()=>{if(!saving&&!loading&&mayDiscard()){resetEditor();showEditor();history.replaceState(null,'','/admin/201');$('name').focus();}});
  $('cancel-profile').addEventListener('click',()=>{if(!saving&&!loading&&mayDiscard()){resetEditor();showList();refresh();}});
  $('person-form').addEventListener('input',()=>dirty=true);
  $('person-form').addEventListener('change',()=>dirty=true);
  for(const key of ['first_name','last_name','middle_name','suffix']) $('profile-'+key).addEventListener('input',()=>{
    const full=['first_name','middle_name','last_name','suffix'].map(k=>$('profile-'+k).value.trim()).filter(Boolean).join(' ');
    if(!$('name').value||$('name').value===generatedName){$('name').value=full;generatedName=full;}
  });
  async function readImage(file){
    if(!['image/png','image/jpeg'].includes(file.type)||file.size>1024*1024)throw new Error('Choose a PNG or JPEG image, up to 1 MB.');
    const result=await new Promise((resolve,reject)=>{
      const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('Could not read image.'));
      reader.readAsDataURL(file);
    });
    const image=new Image();image.src=result;
    try{await image.decode();}catch(e){throw new Error('The image could not be opened. Choose a valid PNG or JPEG.');}
    return result;
  }
  for(const kind of ['photo','signature']){
    $('profile-'+kind).addEventListener('change',async()=>{
      const file=$('profile-'+kind).files[0];if(!file)return;
      const generation=editorGeneration,revision=++imageRevision[kind];fileReads++;$('save-person').disabled=true;
      try{const image=await readImage(file);if(generation!==editorGeneration||revision!==imageRevision[kind])return;imageChanges[kind]=image;$('preview-'+kind).src=imageChanges[kind];$('preview-'+kind).hidden=false;dirty=true;profileMessage('');}
      catch(e){profileMessage(e.message,'error');}
      finally{fileReads--;$('profile-'+kind).value='';$('save-person').disabled=saving||fileReads>0;}
    });
    $('remove-'+kind).addEventListener('click',()=>{
      imageRevision[kind]++;imageChanges[kind]=null;$('preview-'+kind).hidden=true;$('preview-'+kind).removeAttribute('src');dirty=true;
    });
  }
  async function openProfile(id){
    if(saving||loading||!mayDiscard())return;
    loading=true;$('global-message').textContent='Opening employee record…';
    try{
      const record=await api('/api/people/'+id);
      resetEditor();showEditor();personId=record.id;version=record.version;
      $('name').value=record.name;
      $('profile-barcode-status').textContent=record.barcode?`Attendance barcode: ${record.barcode}`:'No attendance barcode yet. An admin can assign one from People & badges.';
      $('profile-heading').textContent=record.name+' · 201 file';$('save-person').textContent='Save 201 file';
      for(const [key,,fields] of profileSections)for(const [field] of fields)$('profile-'+field).value=record.profile[field]||'';
      for(const kind of ['photo','signature'])if(record.images[kind]){$('preview-'+kind).src=record.images[kind];$('preview-'+kind).hidden=false;}
      history.replaceState(null,'','/admin/201?person='+record.id);
      $('profile-heading').scrollIntoView({block:'start'});$('global-message').textContent='';
    }catch(e){$('global-message').textContent=e.message;}finally{loading=false;}
  }
  $('directory').addEventListener('click',event=>{
    const button=event.target.closest('[data-profile-id]');if(button)openProfile(button.dataset.profileId);
  });
  const initialPerson=new URLSearchParams(location.search).get('person');
  if(initialPerson&&/^\d+$/.test(initialPerson))openProfile(initialPerson);
  $('person-form').addEventListener('submit',async event=>{
    event.preventDefault();if(saving||loading||fileReads)return;
    const name=$('name').value.trim();
    if(!name){section('personal');$('name').focus();profileMessage('Enter the employee’s full name.','error');return;}
    for(const input of event.currentTarget.querySelectorAll('input:not([type=file]),textarea')){
      if(!input.checkValidity()){
        section(input.closest('.profile-panel').id.replace('profile-panel-',''));input.reportValidity();return;
      }
    }
    const profile={};for(const [key,,fields] of profileSections)for(const [field] of fields)profile[field]=$('profile-'+field).value;
    const row={name,profile,...imageChanges};
    saving=true;$('save-person').disabled=true;
    // Freeze the editor during saves so typed changes cannot be silently discarded.
    const controls=[...$('person-form').querySelectorAll('input,textarea,button')];controls.forEach(c=>c.disabled=true);
    try{
      if(personId){
        const result=await api('/api/people/'+personId,{...row,version});
        version=result.version;imageChanges={};dirty=false;$('profile-heading').textContent=result.name+' · 201 file';
        profileMessage(`Saved 201 file for ${result.name}.`,'success');
      }else{
        const result=await api('/api/employees',row);const person=result.people[0];
        personId=person.id;version=1;imageChanges={};dirty=false;
        $('profile-heading').textContent=person.name+' · 201 file';$('save-person').textContent='Save 201 file';
        $('profile-barcode-status').textContent='No attendance barcode yet. An admin can assign one from People & badges.';
        history.replaceState(null,'','/admin/201?person='+person.id);
        profileMessage(`Created 201 file for ${person.name}. Barcode can be assigned later.`,'success');
      }
      await refresh();
    }catch(e){profileMessage(e.message,'error');}
    finally{saving=false;controls.forEach(c=>c.disabled=false);}
  });
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
}
