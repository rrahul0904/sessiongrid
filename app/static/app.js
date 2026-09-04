const state={profiles:[],sessions:[],overview:null};
const $=s=>document.querySelector(s);
const toast=m=>{const t=$("#toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),1800)};
async function api(path,options={}){const r=await fetch(path,{headers:{"Content-Type":"application/json"},...options});if(!r.ok){let d={};try{d=await r.json()}catch{}throw new Error(d.detail||("Request failed: "+r.status))}return r.status===204?null:r.json()}
function activeSession(profileId){return state.sessions.find(s=>s.profile_id===profileId&&s.status==="running")}
function card(p){const s=activeSession(p.id);const running=!!s;const statusClass=p.status==="error"?"error":running?"":"offline";return `
<article class="card" data-profile="${p.id}">
 <div class="card-head"><div><b>${escapeHtml(p.name)}</b><small>${escapeHtml(p.platform)} · ${escapeHtml(p.owner)}</small></div><span class="status ${statusClass}">${running?"● ONLINE":p.status==="error"?"ERROR":"READY"}</span></div>
 <div class="screen">${running?`<img src="/api/profiles/${p.id}/frame?ts=${Date.now()}" alt="${escapeHtml(p.name)}"><div class="screen-overlay" data-pointer="${p.id}"></div>`:`<div class="placeholder"><strong>${escapeHtml(p.platform)}</strong>Persistent workspace is offline</div>`}</div>
 <div class="actions">${running?`<button data-stop="${p.id}">Stop</button><button data-shot="${p.id}">Refresh frame</button><button data-text="${p.id}">Type</button>`:`<button data-start="${p.id}">Start session</button>`}</div>
</article>`}
function escapeHtml(v=""){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]))}
function render(){
 const o=state.overview||{profiles:0,active_sessions:0,audit_events:0,screenshots:0};
 $("#metrics").innerHTML=[
  ["Profiles",o.profiles,"persistent workspaces"],
  ["Active",o.active_sessions,"runtime sessions"],
  ["Screenshots",o.screenshots,"evidence frames"],
  ["Audit events",o.audit_events,"recorded actions"]
 ].map(x=>`<div class="metric"><span>${x[0]}</span><strong>${x[1]}</strong><small>${x[2]}</small></div>`).join("");
 const cards=state.profiles.map(card).join("");
 $("#session-grid").innerHTML=cards||'<div class="panel">No profiles yet.</div>';
 $("#screen-wall").innerHTML=cards||'<div class="panel">No profiles yet.</div>';
 $("#profile-table").innerHTML=state.profiles.map(p=>`<div class="row"><div><b>${escapeHtml(p.name)}</b><small>${escapeHtml(p.platform)}</small></div><span>${escapeHtml(p.owner)}</span><span class="chip">${escapeHtml(p.locale)}</span><span>${escapeHtml(p.network_label)}</span><span>${escapeHtml(p.status)}</span></div>`).join("");
 wireCards();
}
function wireCards(){
 document.querySelectorAll("[data-start]").forEach(b=>b.onclick=()=>action(async()=>{await api(`/api/profiles/${b.dataset.start}/start`,{method:"POST"});toast("Session started")}));
 document.querySelectorAll("[data-stop]").forEach(b=>b.onclick=()=>action(async()=>{await api(`/api/profiles/${b.dataset.stop}/stop`,{method:"POST"});toast("Session stopped")}));
 document.querySelectorAll("[data-shot]").forEach(b=>b.onclick=()=>{const c=b.closest(".card");const img=c.querySelector("img");if(img)img.src=`/api/profiles/${b.dataset.shot}/frame?ts=${Date.now()}`});
 document.querySelectorAll("[data-text]").forEach(b=>b.onclick=async()=>{const text=prompt("Text to send to the active page");if(text!==null)await action(()=>api(`/api/profiles/${b.dataset.text}/input/text`,{method:"POST",body:JSON.stringify({text})}))});
 document.querySelectorAll("[data-pointer]").forEach(el=>el.onclick=async e=>{const rect=el.getBoundingClientRect();const x=(e.clientX-rect.left)*(430/rect.width);const y=(e.clientY-rect.top)*(820/rect.height);await action(()=>api(`/api/profiles/${el.dataset.pointer}/input/pointer`,{method:"POST",body:JSON.stringify({x,y})}),false)});
}
async function load(){
 try{
  const [health,overview,profiles,sessions,audit]=await Promise.all([api("/api/health"),api("/api/overview"),api("/api/profiles"),api("/api/sessions"),api("/api/audit")]);
  $("#health-label").textContent=health.status==="ok"?"Control plane online":"Degraded";
  state.overview=overview;state.profiles=profiles;state.sessions=sessions;render();
  $("#audit-list").innerHTML=audit.map(e=>`<div class="audit-row"><small>${new Date(e.created_at).toLocaleString()}</small><div><b>${escapeHtml(e.action)}</b><small>${escapeHtml(e.detail||"")}</small></div><span>${escapeHtml(e.resource_type)} #${escapeHtml(e.resource_id)}</span></div>`).join("")||"No audit events.";
 }catch(e){$("#health-label").textContent="Unavailable";toast(e.message)}
}
async function action(fn,reload=true){try{await fn();if(reload)await load()}catch(e){toast(e.message)}}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>{document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));b.classList.add("active");$("#"+b.dataset.view).classList.add("active");$("#page-title").textContent={dashboard:"Operations overview",screens:"Screen wall",profiles:"Profile inventory",automation:"Automation",audit:"Audit trail"}[b.dataset.view]});
$("#refresh").onclick=load;
$("#new-profile").onclick=()=>$("#profile-dialog").showModal();
$("#close-dialog").onclick=$("#cancel-dialog").onclick=()=>$("#profile-dialog").close();
$("#profile-form").onsubmit=async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget).entries());await action(()=>api("/api/profiles",{method:"POST",body:JSON.stringify(data)}));$("#profile-dialog").close();e.currentTarget.reset();toast("Profile created")};
load();
setInterval(()=>{document.querySelectorAll(".card img").forEach(img=>{const p=img.closest(".card").dataset.profile;img.src=`/api/profiles/${p}/frame?ts=${Date.now()}`})},5000);
