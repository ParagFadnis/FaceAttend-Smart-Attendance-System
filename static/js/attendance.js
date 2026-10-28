let rows=[];
async function load(){rows=await (await fetch("/api/attendance")).json();render()}
function render(){const q=document.getElementById("search").value.toLowerCase(),f=document.getElementById("filter").value;
 const data=rows.filter(x=>x["Student Name"].toLowerCase().includes(q)&&(!f||x.Status===f));
 document.getElementById("table").innerHTML=data.map(x=>`<tr><td><b>${esc(x["Student Name"])}</b></td><td><span class="status ${x.Status.toLowerCase()}">${esc(x.Status)}</span></td><td>${esc(x.Time||"-")}</td><td>${esc(x.Date||"-")}</td><td>${esc(x["Confidence %"]||"-")}</td><td><button onclick="toggle('${js(x["Student Name"])}','${x.Status==="Present"?"Absent":"Present"}')">Mark ${x.Status==="Present"?"Absent":"Present"}</button></td></tr>`).join("")}
async function toggle(name,status){const r=await fetch("/api/manual-attendance",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,status})});const d=await r.json();if(!d.success)alert(d.message||"Update failed");await load()}
document.getElementById("search").oninput=render;document.getElementById("filter").onchange=render;
function esc(v){return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}function js(v){return String(v).replaceAll("\\","\\\\").replaceAll("'","\\'")}load();