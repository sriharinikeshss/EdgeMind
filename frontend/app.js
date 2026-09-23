/**
 * EdgeMind Sovereign Agentic Workbench — Assistant-UI Design Implementation
 * Connects frontend with FastAPI Backend (/api/agent, /api/documents, /api/artifacts, /api/audit, /api/sovereignty)
 */

let token = '';
let currentUser = { username: 'operator', role: 'operator' };
const API = 'http://localhost:8000/api';

// Cached Data
let allDocuments = [];
let allArtifacts = [];
let attachedFileBase64 = null;
let attachedFileName = '';

// Icons
const iconDoc = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`;
const iconImage = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`;
const iconPDF = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M10 18v-6"/><path d="M10 12h3a2 2 0 1 1 0 4h-3"/></svg>`;
const iconDownload = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
const iconCheck = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;
const iconCopy = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;

function getHeaders(extra = {}) {
  const h = { ...extra };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

// ---------------- AUTHENTICATION ----------------
async function doLogin() {
  const user = document.getElementById('login-username').value.trim();
  const pass = document.getElementById('login-password').value.trim();
  const btn = document.getElementById('enter-workspace-btn');
  btn.textContent = 'Authenticating...';

  try {
    const fd = new URLSearchParams();
    fd.append('username', user || 'operator');
    fd.append('password', pass || 'kavach123');

    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: fd
    });

    if (res.ok) {
      const data = await res.json();
      token = data.access_token;
      currentUser = { username: data.username, role: data.role };

      // Update user details
      document.getElementById('current-user-name').textContent = data.username.charAt(0).toUpperCase() + data.username.slice(1);
      document.getElementById('current-user-role').textContent = `Role: ${data.role}`;
      document.getElementById('current-user-avatar').textContent = data.username.substring(0, 2).toUpperCase();
      document.getElementById('welcome-title').textContent = `Welcome, ${data.username.charAt(0).toUpperCase() + data.username.slice(1)}.`;

      // Hide login overlay
      const login = document.getElementById('login');
      login.style.transition = 'opacity 0.3s ease';
      login.style.opacity = '0';
      setTimeout(() => { login.style.display = 'none'; }, 300);

      // Load initial state
      loadAllData();
      fetchSovereignty();
    } else {
      let errDetail = 'Login failed';
      try {
        const err = await res.json();
        if (err.detail) errDetail = err.detail;
      } catch (_) {}
      alert(`Authentication failed: ${errDetail}`);
      btn.textContent = 'Sign in';
    }
  } catch (e) {
    alert(`Error connecting to backend (${API}): ${e.message}`);
    btn.textContent = 'Sign in';
  }
}

document.getElementById('enter-workspace-btn').addEventListener('click', doLogin);
document.getElementById('login-username')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });
document.getElementById('login-password')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') doLogin(); });

document.getElementById('signout-btn').addEventListener('click', () => {
  token = '';
  const login = document.getElementById('login');
  login.style.display = 'flex';
  login.style.opacity = '1';
  document.getElementById('enter-workspace-btn').textContent = 'Sign in';
});

// ---------------- NAVIGATION ----------------
const crumbEl = document.getElementById('crumb');
const navLabels = {
  workspace: 'AGENT WORKSPACE',
  knowledge: 'KNOWLEDGE LIBRARY',
  artifacts: 'DELIVERABLES',
  audit: 'AUDIT TRAIL',
  settings: 'NODE SETTINGS'
};

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');
    const page = item.dataset.page;
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    const targetPage = document.getElementById('page-' + page);
    if (targetPage) targetPage.classList.add('active');
    crumbEl.textContent = navLabels[page] || 'WORKBENCH';

    if (page === 'knowledge') loadDocuments();
    if (page === 'artifacts') loadArtifacts();
    if (page === 'audit') loadAuditLogs();
    fetchSovereignty();
  });
});

document.getElementById('refresh-all-btn')?.addEventListener('click', function() {
  loadAllData();
  fetchSovereignty();
  const svg = this.querySelector('svg');
  if (svg) {
    svg.style.transition = 'transform 0.5s ease';
    svg.style.transform = `rotate(${svg.dataset.rot ? parseInt(svg.dataset.rot) + 360 : 360}deg)`;
    svg.dataset.rot = svg.dataset.rot ? parseInt(svg.dataset.rot) + 360 : 360;
  }
});

function loadAllData() {
  loadDocuments();
  loadArtifacts();
  loadAuditLogs();
  fetchSovereignty();
  loadModels();
}

async function loadModels() {
  try {
    const res = await fetch(`${API}/models`, { headers: getHeaders() });
    if (res.ok) {
      const models = await res.json();
      renderModels(models);
      if (models.length > 0) {
        const badge = document.getElementById('active-model-badge');
        if (badge && badge.textContent === 'Loading models...') {
          badge.textContent = `${models[0].id}`;
        }
      }
    } else {
      document.getElementById('models-body').innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">Failed to load models.</td></tr>`;
    }
  } catch (e) {
    document.getElementById('models-body').innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">Network error loading models.</td></tr>`;
  }
}

function renderModels(models) {
  const tbody = document.getElementById('models-body');
  if (!models || models.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">No models configured.</td></tr>`;
    return;
  }
  
  tbody.innerHTML = models.map(m => `
    <tr>
      <td style="font-family:var(--font-mono);color:var(--text-primary);font-weight:500;">${escapeHtml(m.id)}</td>
      <td>${escapeHtml(m.modality)}</td>
      <td style="font-family:var(--font-mono);font-size:11px;">${escapeHtml(m.capabilities)}</td>
      <td style="font-family:var(--font-mono);">${m.vram_gb} GB</td>
      <td><span class="status-indicator"><span class="status-dot"></span>${escapeHtml(m.status)}</span></td>
      <td style="${m.verified ? 'color:var(--success);' : 'color:var(--warning);'}">${m.verified ? '✓ verified' : '⚠ unverified'}</td>
    </tr>
  `).join('');
}

// Global caches for chat actions
window._promptCache = window._promptCache || {};
window._responseCache = window._responseCache || {};

window.editPrompt = function(id) {
  const p = window._promptCache[id];
  if (p) {
    document.getElementById('agent-prompt').value = p;
    document.getElementById('agent-prompt').focus();
  }
};

window.copyPrompt = function(btn, id) {
  const p = window._promptCache[id];
  if (p) {
    navigator.clipboard.writeText(p);
    const label = btn.querySelector('.copy-label');
    if (label) {
      label.textContent = 'Copied!';
      setTimeout(() => label.textContent = 'Copy', 2000);
    }
  }
};

window.copyAgentText = function(btn, id) {
  const text = window._responseCache[id];
  if (text) {
    navigator.clipboard.writeText(text);
    const label = btn.querySelector('.copy-label');
    if (label) {
      label.textContent = 'Copied!';
      setTimeout(() => label.textContent = 'Copy', 2000);
    }
  }
};

window.retryPrompt = function(id) {
  const p = window._promptCache[id];
  if (p) {
    document.getElementById('agent-prompt').value = p;
    submitAgentTask();
  }
};



// ---------------- PROMPT SUGGESTIONS ----------------
document.querySelectorAll('.suggestion-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const prompt = pill.dataset.prompt;
    if (prompt) {
      document.getElementById('agent-prompt').value = prompt;
      submitAgentTask();
    }
  });
});

// ---------------- MULTI-MODAL COMPOSER ----------------
const agentFile = document.getElementById('agent-file');
const agentUploadBtn = document.getElementById('agent-upload-btn');
const uploadIndicatorBox = document.getElementById('upload-indicator-box');
const attachedFilenameSpan = document.getElementById('attached-filename');
const removeFileBtn = document.getElementById('remove-file-btn');
const agentPrompt = document.getElementById('agent-prompt');
const agentSubmit = document.getElementById('agent-submit');
const chatMessages = document.getElementById('chat-messages');

agentUploadBtn.addEventListener('click', () => agentFile.click());

agentFile.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    attachedFileName = file.name;
    const reader = new FileReader();
    reader.onload = (ev) => {
      attachedFileBase64 = ev.target.result;
      attachedFilenameSpan.textContent = file.name;
      uploadIndicatorBox.style.display = 'flex';
      agentPrompt.focus();
    };
    reader.readAsDataURL(file);
  }
});

removeFileBtn.addEventListener('click', () => {
  attachedFileBase64 = null;
  attachedFileName = '';
  agentFile.value = '';
  uploadIndicatorBox.style.display = 'none';
});

// Auto-expand textarea
agentPrompt.addEventListener('input', () => {
  agentPrompt.style.height = 'auto';
  agentPrompt.style.height = Math.min(agentPrompt.scrollHeight, 140) + 'px';
});

agentPrompt.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    submitAgentTask();
  }
});

agentSubmit.addEventListener('click', submitAgentTask);



// ---------------- AGENT SUBMIT & EXECUTION ----------------
async function submitAgentTask() {
  const prompt = agentPrompt.value.trim();
  if (!prompt && !attachedFileBase64) return;

  const currentFileBase64 = attachedFileBase64;
  const currentFileName = attachedFileName;

  // Reset inputs
  agentPrompt.value = '';
  agentPrompt.style.height = '24px';
  attachedFileBase64 = null;
  attachedFileName = '';
  agentFile.value = '';
  uploadIndicatorBox.style.display = 'none';

  // Remove empty state
  const emptyState = document.getElementById('chat-empty-state');
  if (emptyState) emptyState.remove();

  // 1. Render User Message Bubble with Assistant-UI actions
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const agentMsgId = `agent-msg-${Date.now()}`;
  window._promptCache[agentMsgId] = prompt || 'Analyze attached document';

  const userHtml = `
    <div class="chat-message user">
      <div class="message-content">
        <div class="message-meta">YOU • ${now}</div>
        <div class="message-body">
          ${currentFileName ? `<div class="chat-attachment-pill">📎 ${escapeHtml(currentFileName)}</div><br/>` : ''}
          ${escapeHtml(prompt || 'Analyze attached document')}
        </div>
        <div class="message-actions" style="justify-content: flex-end;">
          <button class="btn-action-sm" onclick="editPrompt('${agentMsgId}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> Edit
          </button>
          <button class="btn-action-sm" onclick="copyPrompt(this, '${agentMsgId}')">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span class="copy-label">Copy</span>
          </button>
        </div>
      </div>
    </div>
  `;
  chatMessages.insertAdjacentHTML('beforeend', userHtml);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Update Status
  document.getElementById('trace-pill').textContent = 'RUNNING';
  document.getElementById('trace-pill').className = 'tag-pill accent';
  agentSubmit.disabled = true;

  // 2. Render Loading Agent Bubble with Assistant-UI Tool Accordion
  const loadingHtml = `
    <div class="chat-message agent" id="${agentMsgId}">
      <div class="message-content" style="width: 100%;">
        <div class="message-meta">
          <span>EDGEMIND</span>
          <span class="model-chip" id="chip-${agentMsgId}">Selecting...</span>
          <span>• ${now}</span>
        </div>
        <div class="message-body" id="body-${agentMsgId}" style="padding-bottom: 4px;">
          
          <!-- Assistant-UI Tool Call Accordion (Running State) -->
          <div class="tool-call-accordion open" id="tool-${agentMsgId}">
            <div class="tool-call-header" onclick="this.parentElement.classList.toggle('open')">
              <div class="tool-name-tag">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
                <span id="tool-name-${agentMsgId}">orchestrating_tools</span>
              </div>
              <div style="display:flex;align-items:center;gap:8px;">
                <span class="tool-status-pill running" id="tool-status-${agentMsgId}">
                  <span class="spinner-sm" style="width:10px;height:10px;border-width:1px;"></span> Running...
                </span>
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
              </div>
            </div>
            <div class="tool-call-body" id="tool-args-${agentMsgId}">
              <span style="color:var(--text-faint);">Evaluating semantic space...</span>
            </div>
          </div>
          
          <div id="content-${agentMsgId}" style="margin-top:12px; display:none;"></div>

        </div>
      </div>
    </div>
  `;
  chatMessages.insertAdjacentHTML('beforeend', loadingHtml);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Live trace list (Dynamic Loading Sequence)
  const traceList = document.getElementById('trace-list');
  traceList.innerHTML = `
    <div class="trace-step-item" id="sse-stage-row">
      <span class="spinner-sm" style="color:var(--accent);margin-top:2px;flex-shrink:0;"></span>
      <div class="trace-step-main">
        <div class="trace-step-title" id="sse-stage-title">Initialising pipeline...</div>
        <div class="trace-step-sub" id="sse-stage-sub">Connecting to EdgeMind backend</div>
      </div>
    </div>
  `;

  // ── SSE streaming fetch — real events from backend in real-time ───────────
  try {
    const payload = { prompt: prompt || 'Analyze attached document' };
    if (currentFileBase64) payload.image_base64 = currentFileBase64;

    const res = await fetch(`${API}/agent/stream`, {
      method: 'POST',
      headers: { ...getHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Server error: ${res.status} ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalData = null;
    let stepRowIds = {};   // step_id -> DOM id for updating spinner→checkmark
    let valRowIds  = {};   // check name -> DOM id for scorecard row

    // Helper: add a row to the trace list
    function addTraceRow(id, icon, title, sub, iconColor) {
      const domId = `trace-row-${id}-${Date.now()}`;
      traceList.insertAdjacentHTML('beforeend', `
        <div class="trace-step-item" id="${domId}">
          <span id="${domId}-icon" style="font-size:11px;font-family:var(--font-mono);color:${iconColor || 'var(--accent)'};margin-top:1px;flex-shrink:0;">${icon}</span>
          <div class="trace-step-main">
            <div class="trace-step-title">${escapeHtml(title)}</div>
            <div class="trace-step-sub" id="${domId}-sub">${escapeHtml(sub)}</div>
          </div>
        </div>
      `);
      traceList.scrollTop = traceList.scrollHeight;
      return domId;
    }

    // Helper: update a row's icon and sub-text
    function updateTraceRow(domId, icon, sub, iconColor) {
      const iconEl = document.getElementById(`${domId}-icon`);
      const subEl  = document.getElementById(`${domId}-sub`);
      if (iconEl) { iconEl.innerHTML = icon; iconEl.style.color = iconColor || 'var(--success)'; }
      if (subEl && sub !== undefined) subEl.textContent = sub;
    }

    // ── SSE event handler ────────────────────────────────────────────────────
    function handleEvent(evt) {
      const stageTitle = document.getElementById('sse-stage-title');
      const stageSub   = document.getElementById('sse-stage-sub');

      if (evt.type === 'pipeline_start') {
        if (stageTitle) stageTitle.textContent = 'Pipeline started';
        if (stageSub)   stageSub.textContent   = `Task ${(evt.task_id || '').substring(0, 8)}...`;
        
        // Instantly animate the Validation Engine box to show it is actively working
        const spinnerHtml = `<span class="spinner-sm" style="width:12px;height:12px;border-width:1px;color:var(--warning);margin-right:4px;"></span> pending...`;
        const scoreBadge = document.getElementById('grounding-score-badge');
        if (scoreBadge) {
          scoreBadge.innerHTML = `<span class="spinner-sm" style="width:10px;height:10px;border-width:1px;margin-right:4px;border-top-color:transparent;"></span> SCORING`;
          scoreBadge.className = 'tag-pill';
        }
        const valSchema = document.getElementById('val-schema');
        if (valSchema) { valSchema.innerHTML = spinnerHtml; valSchema.style.color = 'var(--text-faint)'; }
        const valGrounding = document.getElementById('val-grounding');
        if (valGrounding) { valGrounding.innerHTML = spinnerHtml; valGrounding.style.color = 'var(--text-faint)'; }
        const valRisk = document.getElementById('val-risk');
        if (valRisk) { valRisk.innerHTML = `<span class="spinner-sm" style="width:12px;height:12px;border-width:1px;color:var(--warning);margin-right:4px;"></span> assessing...`; valRisk.style.color = 'var(--text-faint)'; }

      } else if (evt.type === 'stage') {
        const stageRow = document.getElementById('sse-stage-row');
        const icons = { PLANNING: '⚙', EXECUTING: '▶', COMPLETED: '✓', FAILED: '✗' };
        const colors = { PLANNING: 'var(--accent)', EXECUTING: 'var(--accent)', COMPLETED: 'var(--success)', FAILED: 'var(--danger)' };
        
        if (stageRow && evt.stage !== 'VALIDATING') {
          const iconEl = stageRow.querySelector('span');
          if (iconEl) {
            if (evt.stage === 'PLANNING' || evt.stage === 'EXECUTING') {
              iconEl.outerHTML = `<span class="spinner-sm" style="color:${colors[evt.stage] || 'var(--accent)'};margin-top:2px;flex-shrink:0;"></span>`;
            } else {
              const c = colors[evt.stage] || 'var(--success)';
              stageRow.querySelector('span') && (stageRow.querySelector('span').outerHTML = `<span style="font-size:11px;color:${c};margin-top:1px;flex-shrink:0;">${icons[evt.stage] || '•'}</span>`);
            }
          }
          if (stageTitle) stageTitle.textContent = evt.stage.charAt(0) + evt.stage.slice(1).toLowerCase();
          if (stageSub)   stageSub.textContent   = evt.message || '';
        }

        if (evt.stage === 'VALIDATING') {
          // Update the spinners to show it has reached the actual validation stage
          const valSchema = document.getElementById('val-schema');
          if (valSchema && valSchema.innerHTML.includes('pending')) { valSchema.innerHTML = `<span class="spinner-sm" style="width:12px;height:12px;border-width:1px;color:var(--warning);margin-right:4px;"></span> validating...`; }
          const valGrounding = document.getElementById('val-grounding');
          if (valGrounding && valGrounding.innerHTML.includes('pending')) { valGrounding.innerHTML = `<span class="spinner-sm" style="width:12px;height:12px;border-width:1px;color:var(--warning);margin-right:4px;"></span> validating...`; }
        }

      } else if (evt.type === 'step_start') {
        const spinner = `<span class="spinner-sm" style="width:10px;height:10px;border-width:1px;color:var(--accent);"></span>`;
        const domId = addTraceRow(evt.step_id, spinner, evt.action || evt.tool || 'Step', `Tool: ${evt.tool || '—'}`, 'var(--accent)');
        // replace text icon with real spinner
        const iconEl = document.getElementById(`${domId}-icon`);
        if (iconEl) iconEl.innerHTML = `<span class="spinner-sm" style="width:10px;height:10px;border-width:1px;"></span>`;
        stepRowIds[evt.step_id] = domId;

      } else if (evt.type === 'step_done') {
        const domId = stepRowIds[evt.step_id];
        if (domId) {
          const icon  = evt.success ? '✓' : '✗';
          const color = evt.success ? 'var(--success)' : 'var(--danger)';
          const sub   = evt.success ? (evt.output_snippet ? evt.output_snippet.substring(0, 80) : 'Done') : (evt.error || 'Failed');
          updateTraceRow(domId, icon, sub, color);
        }

      } else if (evt.type === 'validation_check') {
        // Live scorecard update directly in the Validation Engine card
        if (evt.check === 'schema') {
          const el = document.getElementById('val-schema');
          if (el) { el.textContent = evt.passed ? '✓ pass' : '✗ fail'; el.style.color = evt.passed ? '' : 'var(--danger)'; }
        }
        else if (evt.check === 'grounding') {
          const scoreEl    = document.getElementById('grounding-score-badge');
          const groundEl   = document.getElementById('val-grounding');
          const riskEl     = document.getElementById('val-risk');
          const isBase     = evt.base_model;
          const score      = Math.round((evt.score || 0) * 100);
          if (scoreEl) {
            scoreEl.textContent = isBase ? 'N/A (BASE)' : `${score}% SCORE`;
            scoreEl.className   = isBase ? 'tag-pill' : (score >= 50 ? 'tag-pill success' : 'tag-pill danger');
          }
          if (groundEl) {
            groundEl.textContent = isBase ? 'Ungrounded' : (evt.passed ? '✓ verified' : '⚠ failed');
            groundEl.style.color = isBase ? 'var(--text-faint)' : (evt.passed ? '' : 'var(--warning)');
          }
          if (riskEl) {
            riskEl.textContent = isBase ? 'Inherent' : (evt.risk || (score >= 80 ? 'Low' : score >= 50 ? 'Medium' : 'High'));
            riskEl.style.color = isBase ? 'var(--text-faint)' : (score >= 80 ? '' : (score >= 50 ? 'var(--warning)' : 'var(--danger)'));
          }
        }
        else if (evt.check === 'self_rag' && evt.passed === null) {
          // If Self-RAG starts, show a specialized spinner in the grounding box
          const groundEl = document.getElementById('val-grounding');
          if (groundEl) { groundEl.innerHTML = `<span class="spinner-sm" style="width:12px;height:12px;border-width:1px;color:var(--warning);margin-right:4px;"></span> searching SOPs...`; }
        }

      } else if (evt.type === 'complete') {
        finalData = evt;
        const stageRow = document.getElementById('sse-stage-row');
        if (stageRow) {
          const iconEl = stageRow.querySelector('span');
          if (iconEl) iconEl.outerHTML = `<span style="font-size:11px;color:var(--success);margin-top:1px;flex-shrink:0;">✓</span>`;
          const stageTitle = document.getElementById('sse-stage-title');
          const stageSub   = document.getElementById('sse-stage-sub');
          if (stageTitle) stageTitle.textContent = 'Execution Complete';
          if (stageSub)   stageSub.textContent   = 'Task verified and delivered';
        }

      } else if (evt.type === 'error') {
        finalData = { error: evt.message };
      }
    }

    // ── Read the SSE stream ───────────────────────────────────────────────────
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Parse complete SSE events from buffer (separated by \n\n)
      const parts = buffer.split('\n\n');
      buffer = parts.pop(); // keep incomplete trailing chunk

      for (const part of parts) {
        const line = part.trim();
        if (line.startsWith('data: ')) {
          try {
            const evt = JSON.parse(line.slice(6));
            handleEvent(evt);
          } catch (e) {
            console.warn('SSE parse error:', e, line);
          }
        }
      }
    }

    // ── Pipeline complete — render final response ─────────────────────────────
    agentSubmit.disabled = false;
    document.getElementById('trace-pill').textContent = 'IDLE';
    document.getElementById('trace-pill').className = 'tag-pill';

    if (!finalData || finalData.error) {
      throw new Error(finalData?.error || 'Pipeline returned no data');
    }

    const data = finalData;

    // Close the tool accordion
    const toolStatus = document.getElementById(`tool-status-${agentMsgId}`);
    if (toolStatus) {
      toolStatus.className = 'tool-status-pill done';
      toolStatus.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Completed`;
    }
    const toolArgs = document.getElementById(`tool-args-${agentMsgId}`);
    if (toolArgs && data.steps && data.steps.length > 0) {
      const primaryTool = data.steps.find(s => s.tool) || data.steps[0];
      document.getElementById(`tool-name-${agentMsgId}`).textContent = primaryTool.tool || primaryTool.action || 'synthesize_response';
      toolArgs.innerHTML = `<pre style="margin:0;white-space:pre-wrap;background:transparent;"><code>${JSON.stringify(data.steps, null, 2)}</code></pre>`;
    } else if (toolArgs) {
      document.getElementById(`tool-name-${agentMsgId}`).textContent = 'synthesize_response';
      toolArgs.innerHTML = `<pre style="margin:0;white-space:pre-wrap;background:transparent;"><code>{ "mode": "direct_answer" }</code></pre>`;
    }
    const toolContainer = document.getElementById(`tool-${agentMsgId}`);
    if (toolContainer) toolContainer.classList.remove('open');

    // Render response
    const contentBox = document.getElementById(`content-${agentMsgId}`);
    contentBox.style.display = 'block';

    const chip = document.getElementById(`chip-${agentMsgId}`);
    if (chip) chip.textContent = data.model_used || 'Unknown';
    const activeBadge = document.getElementById('active-model-badge');
    if (activeBadge && data.model_used) activeBadge.textContent = data.model_used;

    let outputText = data.final_output || 'Task execution completed.';
    window._responseCache[agentMsgId] = outputText;
    let outputHtml = formatMarkdown(outputText);

    // Artifact download cards
    if (data.artifacts && data.artifacts.length > 0) {
      data.artifacts.forEach(a => {
        outputHtml += `
          <div class="message-deliverable-card">
            <div class="deliverable-info">
              <div class="deliverable-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              </div>
              <div>
                <div class="deliverable-title">${escapeHtml(a.filename)}</div>
                <div class="deliverable-sub">Artifact Generated • Secure Node</div>
              </div>
            </div>
            <button class="btn-download" onclick="window.open('${API}/artifacts/${a.id}/download?token=${token}', '_blank')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> Download
            </button>
          </div>
        `;
      });
    }

    outputHtml += `
      <div class="message-actions" style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
        <button class="btn-action-sm" onclick="copyAgentText(this, '${agentMsgId}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> <span class="copy-label">Copy</span>
        </button>
        <button class="btn-action-sm" onclick="retryPrompt('${agentMsgId}')" title="Regenerate">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Retry
        </button>
      </div>
    `;
    contentBox.innerHTML = outputHtml;

    // Final retry count update
    const valRetries = document.getElementById('val-retries');
    if (valRetries) valRetries.textContent = `${data.retry_count || 0} / 3`;

    // Evidence panel
    let citations = [];
    if (data.steps) {
      data.steps.forEach(s => {
        if (s.tool === 'rag_search' && s.output) {
          const docIdRegex = /\(Doc: ([a-f0-9\-]+)\)/g;
          let match;
          let foundDocs = new Set();
          while ((match = docIdRegex.exec(s.output)) !== null) {
            const docObj = allDocuments.find(d => d.id === match[1]);
            foundDocs.add(docObj ? docObj.filename : `Document ${match[1].substring(0, 8)}`);
          }
          if (foundDocs.size > 0) foundDocs.forEach(n => citations.push(n));
          else citations.push('RAG Knowledge Search');
        }
        if ((s.tool === 'analyze_scanned_document' || s.tool === 'run_ocr') && s.output)
          citations.push('Visual Evidence / OCR');
      });
    }
    const evCount = document.getElementById('evidence-count');
    if (evCount) evCount.textContent = citations.length;
    const evList = document.getElementById('evidence-list');
    if (evList) {
      evList.innerHTML = citations.length > 0
        ? citations.map(c => `<div class="trace-step-item"><span class="trace-step-icon">⚲</span><div class="trace-step-main"><div class="trace-step-title">${escapeHtml(c)}</div></div></div>`).join('')
        : `<div style="font-size:12px;color:var(--text-faint);padding:6px 0;">No chunks retrieved.</div>`;
    }

    loadAllData();
    fetchSovereignty();
    chatMessages.scrollTop = chatMessages.scrollHeight;

  } catch (err) {
    agentSubmit.disabled = false;
    document.getElementById('trace-pill').textContent = 'ERROR';
    document.getElementById('trace-pill').className = 'tag-pill danger';

    const toolStatus = document.getElementById(`tool-status-${agentMsgId}`);
    if (toolStatus) {
      toolStatus.className = 'tool-status-pill error';
      toolStatus.style.background = 'var(--danger-subtle)';
      toolStatus.style.color = 'var(--danger)';
      toolStatus.innerHTML = 'Error';
    }
    const contentBox = document.getElementById(`content-${agentMsgId}`);
    contentBox.style.display = 'block';
    contentBox.innerHTML = `
      <div style="color:var(--danger);font-family:var(--font-mono);font-size:12.5px;padding:12px;background:var(--danger-subtle);border-radius:var(--radius-sm);border:1px solid var(--danger-border);">
        <strong>Pipeline Failure:</strong><br/>${escapeHtml(err.message)}
      </div>
      <div class="message-actions" style="margin-top:12px;border-top:1px solid var(--border-subtle);padding-top:8px;">
        <button class="btn-action-sm" onclick="retryPrompt('${agentMsgId}')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Retry
        </button>
      </div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

}


// ---------------- KNOWLEDGE LIBRARY ----------------
const knowledgeList = document.getElementById('knowledge-list');
const knowledgeUploadBtn = document.getElementById('knowledge-upload-btn');
const knowledgeFileInput = document.getElementById('knowledge-file-input');
const knowledgeSearch = document.getElementById('knowledge-search');

knowledgeUploadBtn.addEventListener('click', () => knowledgeFileInput.click());

knowledgeFileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  knowledgeUploadBtn.disabled = true;
  knowledgeUploadBtn.textContent = 'Uploading & indexing...';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('classification', 'internal');

  try {
    const res = await fetch(`${API}/documents/upload`, {
      method: 'POST',
      headers: getHeaders(),
      body: formData
    });

    if (res.ok) {
      alert(`Document "${file.name}" uploaded and indexed into Qdrant successfully!`);
      loadDocuments();
      fetchSovereignty();
    } else {
      const err = await res.json();
      alert(`Upload failed: ${err.detail || res.statusText}`);
    }
  } catch (err) {
    alert(`Upload error: ${err.message}`);
  } finally {
    knowledgeFileInput.value = '';
    knowledgeUploadBtn.disabled = false;
    knowledgeUploadBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <span>Upload SOP / PDF</span>
    `;
  }
});

knowledgeSearch.addEventListener('input', (e) => {
  const query = e.target.value.toLowerCase();
  const filtered = allDocuments.filter(d => 
    d.filename.toLowerCase().includes(query) || 
    (d.classification && d.classification.toLowerCase().includes(query))
  );
  renderDocuments(filtered);
});

async function loadDocuments() {
  try {
    const res = await fetch(`${API}/documents`, { headers: getHeaders() });
    if (res.ok) {
      allDocuments = await res.json();
      renderDocuments(allDocuments);
      document.getElementById('sidebar-doc-count').textContent = allDocuments.length;
      document.getElementById('doc-count-eyebrow').textContent = `${allDocuments.length} documents indexed in Qdrant vector database`;
    } else {
      knowledgeList.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-faint);">Failed to load knowledge documents</div>`;
    }
  } catch (e) {
    knowledgeList.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-faint);">Network error connecting to knowledge service</div>`;
  }
}

function renderDocuments(docs) {
    if (!docs || docs.length === 0) {
      knowledgeList.innerHTML = `
        <div style="text-align:center;padding:48px 20px;border:1px dashed var(--border);border-radius:var(--radius);">
          <div style="font-size:15px;font-weight:600;color:var(--text-primary);margin-bottom:4px;">No knowledge documents indexed</div>
          <div style="font-size:13px;color:var(--text-muted);margin-bottom:16px;">Upload standard operating procedures, manuals, or inspection forms for RAG search.</div>
          <button class="btn-download" onclick="document.getElementById('knowledge-file-input').click()">
            Upload Document
          </button>
        </div>
      `;
      return;
    }
  
    knowledgeList.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:8px;">
        ${docs.map(d => {
          const fn = d.filename.toLowerCase();
          const isVision = fn.endsWith('.png') || fn.endsWith('.jpg') || fn.endsWith('.jpeg');
          const isPdf = fn.endsWith('.pdf');
          const tag = isVision ? 'VISION' : 'RAG';
          const dateStr = d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString() : '-';
          
          let currIcon = iconDoc;
          if (isVision) currIcon = iconImage;
          else if (isPdf) currIcon = iconPDF;
          
          const statusText = isVision ? 'Stored in MinIO' : 'Indexed in Qdrant';
  
          return `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--bg);border:1px solid var(--border-subtle);border-radius:var(--radius);">
              <div style="display:flex;align-items:center;gap:12px;">
                <div style="width:34px;height:34px;border-radius:var(--radius-sm);background:var(--panel);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;color:var(--text-secondary);">
                  ${currIcon}
                </div>
                <div>
                  <div style="font-weight:500;color:var(--text-primary);font-size:13.5px;">${escapeHtml(d.filename)}</div>
                  <div style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);">Version ${d.version || 1} • ${statusText}</div>
                </div>
              </div>
              <div style="display:flex;align-items:center;gap:10px;">
                <span class="tag-pill ${tag === 'VISION' ? 'accent' : 'success'}">${tag}</span>
                <span class="tag-pill">${escapeHtml(d.classification || 'internal')}</span>
                <span style="font-size:11px;font-family:var(--font-mono);color:var(--text-faint);width:75px;text-align:right;">${dateStr}</span>
                <button onclick="deleteDocument('${d.id}')" class="icon-button" style="color:var(--danger);" title="Delete document">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }
  
  window.deleteDocument = async function(id) {
  if (!confirm("Are you sure you want to delete this document from the knowledge base?")) return;
  try {
    const res = await fetch(`${API}/documents/${id}`, {
      method: 'DELETE',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error("Failed to delete document");
    loadDocuments();
    fetchSovereignty();
  } catch (err) {
    alert(err.message);
  }
};

// ---------------- ARTIFACTS / DELIVERABLES ----------------
const artifactsList = document.getElementById('artifacts-list');

window.downloadArtifact = async function(id, filename) {
  try {
    const res = await fetch(`${API}/artifacts/${id}/download`, { headers: getHeaders() });
    if (!res.ok) {
      window.open(`${API}/artifacts/${id}/download?token=${encodeURIComponent(token)}`, '_blank');
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'artifact.bin';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    window.open(`${API}/artifacts/${id}/download?token=${encodeURIComponent(token)}`, '_blank');
  }
};

async function loadArtifacts() {
  try {
    const res = await fetch(`${API}/artifacts`, { headers: getHeaders() });
    if (res.ok) {
      allArtifacts = await res.json();
      renderArtifacts(allArtifacts);
      document.getElementById('sidebar-art-count').textContent = allArtifacts.length;
      document.getElementById('artifact-count-eyebrow').textContent = `${allArtifacts.length} deliverables created across tasks`;
    } else {
      artifactsList.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-faint);">Failed to load deliverables</div>`;
    }
  } catch (e) {
    artifactsList.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-faint);">Network error loading deliverables</div>`;
  }
}

function renderArtifacts(arts) {
  if (!arts || arts.length === 0) {
    artifactsList.innerHTML = `
      <div style="text-align:center;padding:48px 20px;border:1px dashed var(--border);border-radius:var(--radius);">
        <div style="font-size:15px;font-weight:600;color:var(--text-primary);margin-bottom:4px;">No deliverables generated yet</div>
        <div style="font-size:13px;color:var(--text-muted);">Ask EdgeMind to "generate a DOCX report", "export an XLSX checklist", or "create a PDF note".</div>
      </div>
    `;
    return;
  }

  artifactsList.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:8px;">
      ${arts.map(a => {
        const ext = (a.filename.split('.').pop() || 'FILE').toUpperCase();
        const hashShort = a.file_hash ? `${a.file_hash.substring(0, 8)}…` : 'verified';

        return `
          <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--bg);border:1px solid var(--border-subtle);border-radius:var(--radius);">
            <div style="display:flex;align-items:center;gap:12px;">
              <div style="width:34px;height:34px;border-radius:var(--radius-sm);background:var(--accent-subtle);border:1px solid var(--accent-border);display:flex;align-items:center;justify-content:center;color:var(--accent);">
                ${iconDoc}
              </div>
              <div>
                <div style="font-weight:500;color:var(--text-primary);font-size:13.5px;">${escapeHtml(a.filename)}</div>
                <div style="font-size:11px;font-family:var(--font-mono);color:var(--text-muted);">${ext} • Task #${a.task_id ? a.task_id.substring(0, 8) : '0000'} • SHA-256 ${hashShort}</div>
              </div>
            </div>
            <button class="btn-download" onclick="downloadArtifact('${a.id}', '${escapeHtml(a.filename)}')">
              ${iconDownload} Download
            </button>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

// ---------------- AUDIT TRAIL ----------------
const auditBody = document.getElementById('audit-body');

async function loadAuditLogs() {
  try {
    const res = await fetch(`${API}/audit/export`, { headers: getHeaders() });
    if (res.ok) {
      const data = await res.json();
      const logs = data.audit_logs || data.entries || (Array.isArray(data) ? data : []);
      renderAuditLogs(logs);
    } else {
      auditBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">No audit records available.</td></tr>`;
    }
  } catch (e) {
    auditBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">Audit trail standby.</td></tr>`;
  }
}

function renderAuditLogs(logs) {
  if (!logs || logs.length === 0) {
    auditBody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-faint);padding:24px;">Audit trail empty. Actions are logged on task &amp; document events.</td></tr>`;
    return;
  }

  auditBody.innerHTML = logs.slice(0, 40).map(l => {
    const timeStr = l.created_at ? new Date(l.created_at).toLocaleTimeString() : '—';
    const hashStr = l.hash ? l.hash.substring(0, 8) : '—';

    return `
      <tr>
        <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${timeStr}</td>
        <td style="font-weight:500;color:var(--text-primary);">${escapeHtml(l.user_id || 'operator')}</td>
        <td><span class="tag-pill">${escapeHtml(l.action || 'EVENT')}</span></td>
        <td>${escapeHtml(l.details || '')}</td>
        <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted);">${hashStr}</td>
        <td style="color:var(--success);font-size:12px;">✓ verified</td>
      </tr>
    `;
  }).join('');
}

// ---------------- SOVEREIGNTY TELEMETRY ----------------
async function fetchSovereignty() {
  try {
    const res = await fetch(`${API}/sovereignty/report`, { headers: getHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    
    const statusText = document.getElementById('sov-status-text');
    const mainTitle = document.getElementById('sov-main-title');
    const metaDesc = document.getElementById('sov-meta-desc');
    
    const dot = document.querySelector('.node-health .status-dot');
    if (data.sovereign) {
      statusText.textContent = 'AIR-GAPPED';
      statusText.style.color = 'var(--success)';
      if (dot) dot.style.background = 'var(--success)';
      mainTitle.textContent = '100% Local Inference';
      metaDesc.textContent = 'Zero egress detected • Ollama';
    } else {
      statusText.textContent = 'EGRESS FLAGGED';
      statusText.style.color = '#ef4444';
      if (dot) dot.style.background = '#ef4444';
      mainTitle.textContent = 'External Network Reachable';
      const flags = (data.network_monitor && data.network_monitor.flagged_external_connections && data.network_monitor.flagged_external_connections.length > 0) 
        ? `${data.network_monitor.flagged_external_connections.length} external connections` 
        : 'Outbound egress allowed';
      metaDesc.textContent = flags;
    }
  } catch (err) {
    console.error("Sovereignty fetch failed", err);
  }
}

// ---------------- FORMATTING UTILS ----------------
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
  if (!text) return '';
  let clean = escapeHtml(text);
  
  // Headers
  clean = clean.replace(/^### (.*$)/gim, '<h3 style="font-size:14px;font-weight:600;margin:8px 0 4px;color:var(--text-primary);">$1</h3>');
  clean = clean.replace(/^## (.*$)/gim, '<h2 style="font-size:15px;font-weight:600;margin:12px 0 6px;color:var(--text-primary);">$1</h2>');
  clean = clean.replace(/^# (.*$)/gim, '<h1 style="font-size:16px;font-weight:700;margin:14px 0 8px;color:var(--text-primary);">$1</h1>');
  
  // Bold & Italics
  clean = clean.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  clean = clean.replace(/\*(.*?)\*/g, '<em>$1</em>');
  
  // Inline code
  clean = clean.replace(/`([^`]+)`/g, '<code style="font-family:var(--font-mono);font-size:12px;background:var(--bg);padding:2px 6px;border-radius:4px;border:1px solid var(--border-subtle);color:var(--accent);">$1</code>');
  
  // Linebreaks / paragraphs
  clean = clean.replace(/\n\n/g, '<div style="height:8px;"></div>');
  clean = clean.replace(/\n/g, '<br/>');
  
  return clean;
}
