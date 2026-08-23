let token = '';
const API = 'http://localhost:8000/api';

// ---------------- LOGIN ----------------
document.getElementById('enter-workspace-btn').addEventListener('click', async () => {
  const user = document.getElementById('login-username').value;
  const pass = document.getElementById('login-password').value;
  const btn = document.getElementById('enter-workspace-btn');
  btn.textContent = 'Authenticating...';
  try {
    const fd = new URLSearchParams();
    fd.append('username', user);
    fd.append('password', pass);
    const res = await fetch(`${API}/auth/token`, { method: 'POST', body: fd });
    if(res.ok) {
      const data = await res.json();
      token = data.access_token;
      const login = document.getElementById('login');
      login.style.transition = 'opacity .35s ease';
      login.style.opacity = '0';
      setTimeout(()=>{ login.style.display = 'none'; }, 350);
    } else {
      alert('Login failed');
      btn.textContent = 'Enter workspace';
    }
  } catch(e) {
    alert('Error connecting to backend');
    btn.textContent = 'Enter workspace';
  }
});

// ---------------- NAV ----------------
const crumbEl = document.getElementById('crumb');
const labels = { workspace:'AGENT WORKSPACE', knowledge:'KNOWLEDGE LIBRARY', artifacts:'ARTIFACTS', audit:'AUDIT TRAIL', settings:'NODE SETTINGS' };
document.querySelectorAll('.nav-item').forEach(item=>{
  item.addEventListener('click', ()=>{
    document.querySelectorAll('.nav-item').forEach(i=>i.classList.remove('active'));
    item.classList.add('active');
    const page = item.dataset.page;
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.getElementById('page-'+page).classList.add('active');
    crumbEl.textContent = labels[page];
  });
});

// ---------------- Node settings tabs ----------------
document.querySelectorAll('.tab-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
    document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
  });
});

// ---------------- AGENT INTERACTION ----------------
let attachedFileBase64 = null;

document.getElementById('agent-upload-btn').addEventListener('click', () => {
  document.getElementById('agent-file').click();
});

document.getElementById('agent-file').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if(file) {
    const reader = new FileReader();
    reader.onload = (ev) => {
      attachedFileBase64 = ev.target.result;
      document.getElementById('upload-indicator').style.display = 'block';
      document.getElementById('upload-indicator').textContent = file.name;
    };
    reader.readAsDataURL(file);
  }
});

document.getElementById('agent-submit').addEventListener('click', async () => {
  const prompt = document.getElementById('agent-prompt').value;
  if(!prompt && !attachedFileBase64) return;
  
  document.getElementById('current-task-prompt').textContent = prompt || 'Analyze attached document';
  document.getElementById('current-task-title').textContent = 'Processing task...';
  document.getElementById('trace-list').innerHTML = `<div style="padding:10px;color:#8b958c;">Agent running...</div>`;
  document.getElementById('agent-prompt').value = '';
  document.getElementById('upload-indicator').style.display = 'none';
  
  const payload = { prompt: prompt || 'Analyze attached document' };
  if (attachedFileBase64) {
    payload.image_base64 = attachedFileBase64;
    attachedFileBase64 = null;
    document.getElementById('agent-file').value = '';
  }
  
  try {
    const res = await fetch(`${API}/agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    if(data.steps) {
      document.getElementById('trace-list').innerHTML = data.steps.map(s => `
        <div class="row-item">
          <div class="row-icon" style="color:#7fd9a8;border-color:#7fd9a8;">✓</div>
          <div class="row-main"><div class="row-title">${s.action}</div><div class="row-sub">${s.tool || 'llm'}</div></div>
          <div class="row-right" style="font-family:monospace;font-size:10.5px;color:#8b958c;">DONE</div>
        </div>
      `).join('');
      document.getElementById('current-task-title').textContent = data.final_output || 'Task Completed';
    } else {
      document.getElementById('current-task-title').textContent = 'Task finished (no output)';
    }
  } catch(e) {
    document.getElementById('current-task-title').textContent = 'Error processing task';
    document.getElementById('trace-list').innerHTML = `<div style="padding:10px;color:#e0655a;">Failed to connect to agent API.</div>`;
  }
});

// UI defaults (keep icons)
const iconDoc = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`;
const iconDownload = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 3v13m0 0-4-4m4 4 4-4M5 21h14"/></svg>`;
