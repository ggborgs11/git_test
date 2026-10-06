document.getElementById('login-form').addEventListener('submit',async event=>{
  event.preventDefault();
  const button=event.currentTarget.querySelector('button');button.disabled=true;
  try {
    const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('password').value})});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error);
    location.replace('/admin');
  }catch(e){document.getElementById('login-message').textContent=e.message;}finally{button.disabled=false;}
});
