const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const elements={};const get=id=>elements[id]??={value:'',textContent:'',dataset:{},listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}};
let fail=false,payload;
const context={admin:true,$:get,selectedEmployees:new Set(),state:{people:[{id:1,name:'Ana',barcode:'001'},{id:2,name:'Bob'}]},allEmployees(){},refresh:async()=>{},api:async(path,body)=>{assert.equal(path,'/api/employees/department');payload=body;if(fail)throw Error('Failed');return {updated:body.people.length,department:body.department};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/bulk.js','utf8'),context);
(async()=>{
  get('employees-search').value='001';get('employees-select-visible').listeners.click();
  assert.deepEqual([...context.selectedEmployees],[1]);
  get('bulk-department').value='Production';fail=true;
  await get('bulk-department-form').listeners.submit({preventDefault(){}});
  assert.equal(context.selectedEmployees.size,1);assert.equal(get('bulk-department-message').textContent,'Failed');
  fail=false;await get('bulk-department-form').listeners.submit({preventDefault(){}});
  assert.deepEqual([...payload.people],[1]);assert.equal(payload.department,'Production');assert.equal(context.selectedEmployees.size,0);
  get('employees-search').value='';get('employees-select-visible').listeners.click();assert.equal(context.selectedEmployees.size,2);
  get('employees-clear-selection').listeners.click();assert.equal(context.selectedEmployees.size,0);
  console.log('Bulk department UI: filtered selection, failure/retry, save and clear passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
