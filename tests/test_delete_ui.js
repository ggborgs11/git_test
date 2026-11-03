// Run with node tests/test_delete_ui.js. Exercise the real deletion event handlers.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/app.js','utf8');
function fixture(){
  const elements={};
  const get=id=>elements[id]??=( {hidden:true,disabled:false,textContent:'',value:'',listeners:{},focus(){},addEventListener(type,fn){this.listeners[type]=fn;},dispatchEvent(){}} );
  const clicks={};let calls=0,fail=false;
  const context={admin:true,state:{people:[{id:7,name:'Dela Cruz, Ana'},{id:8,name:'Keep'}],events:[]},$:get,
    document:{addEventListener:(type,fn)=>clicks[type]=fn},Event:class{},
    api:async(path,body)=>{calls++;assert.equal(path,'/api/people/7/delete');assert.equal(body.confirm,true);if(fail)throw Error('Not found');},
    directory(){},allEmployees(){},refresh:async()=>{}};
  vm.createContext(context);vm.runInContext(source.slice(source.indexOf('if(admin){\n  let deletingEmployee=false')),context);
  const button={dataset:{deleteId:'7'},isConnected:true,focus(){},closest:selector=>selector==='#employees-list'?{}:null};
  return {context,get,open:()=>clicks.click({target:{closest:()=>button}}),calls:()=>calls,setFailure:value=>fail=value};
}
(async()=>{
  const f=fixture();f.open();assert.equal(f.get('delete-overlay').hidden,false);
  assert(f.get('delete-description').textContent.includes('Dela Cruz, Ana'));
  assert.equal(f.calls(),0);
  f.get('delete-cancel').listeners.click();assert.equal(f.get('delete-overlay').hidden,true);assert.equal(f.calls(),0);
  f.open();f.setFailure(true);await f.get('delete-confirm').listeners.click();
  assert.equal(f.get('delete-overlay').hidden,false);assert(f.get('delete-error').textContent.includes('restart'));
  assert.equal(f.get('delete-confirm').disabled,false);assert.equal(f.context.state.people.length,2);
  f.setFailure(false);await f.get('delete-confirm').listeners.click();
  assert.equal(f.get('delete-overlay').hidden,true);assert.equal(f.context.state.people.length,1);
  assert.equal(f.context.state.people[0].id,8);assert(f.get('employees-message').textContent.includes('Deleted'));
  console.log('Delete UI: confirm, cancel, failure, retry, and removal passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
