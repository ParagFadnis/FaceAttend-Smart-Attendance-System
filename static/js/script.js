let stream=null,timer=null,busy=false;
const video=document.getElementById("camera"), result=document.getElementById("result");
document.getElementById("start").onclick=startCamera; document.getElementById("stop").onclick=stopCamera;
async function startCamera(){
 try{stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},facingMode:"user"},audio:false});
 video.srcObject=stream; document.getElementById("camstatus").textContent="Camera On"; document.getElementById("msg").style.display="none";
 timer=setInterval(recognize,4000); recognize();}catch(e){result.textContent="Camera permission denied or camera unavailable.";}}
function stopCamera(){if(timer)clearInterval(timer);timer=null;if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;document.getElementById("camstatus").textContent="Camera Off";document.getElementById("msg").style.display="flex";fetch("/api/reset-dwell",{method:"POST"});}
async function recognize(){if(!stream||busy||video.readyState<2)return;busy=true;
 const c=document.createElement("canvas");c.width=video.videoWidth||640;c.height=video.videoHeight||480;c.getContext("2d").drawImage(video,0,0,c.width,c.height);
 try{const r=await fetch("/api/recognize",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({image:c.toDataURL("image/jpeg",.75)})});const d=await r.json();
 if(!d.success){result.textContent=d.error;return} if(!d.recognized){result.innerHTML="<strong>Unknown / No face</strong><small>"+(d.message||"")+"</small>";return}
 const rem=Math.max(0,d.required_seconds-d.dwell_seconds);result.innerHTML=d.marked?`<strong>✓ Attendance marked</strong><span>${esc(d.name)}</span><small>Confidence: ${d.confidence}%</small>`:`<strong>${esc(d.name)}</strong><span>Confidence: ${d.confidence}%</span><small>Keep your face visible for ${rem}s more.</small>`;
 if(d.marked)loadStats();}catch(e){result.textContent="Backend connection error."}finally{busy=false}}
async function loadStats(){const d=await (await fetch("/api/stats")).json();document.getElementById("total").textContent=d.total;document.getElementById("present").textContent=d.present;document.getElementById("absent").textContent=d.absent;document.getElementById("percent").textContent=d.percentage+"%";loadRecent();}
async function loadRecent(){const rows=await (await fetch("/api/attendance")).json();const p=rows.filter(x=>x.Status==="Present").slice(-8).reverse();document.getElementById("recent").innerHTML=p.length?p.map(x=>`<div class="recent"><div><b>${esc(x["Student Name"])}</b><small>${esc(x.Time||"")}</small></div><span class="present">Present</span></div>`).join(""):"<p>No attendance marked yet.</p>";}
function esc(v){return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
loadStats();