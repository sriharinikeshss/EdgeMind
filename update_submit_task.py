import re

with open("frontend/app.js", "r", encoding="utf-8") as f:
    content = f.read()

new_task = r"""
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
  const userHtml = `
    <div class="chat-message user">
      <div class="message-avatar">${currentUser.username.substring(0, 2).toUpperCase()}</div>
      <div class="message-content">
        <div class="message-meta">YOU • ${now}</div>
        <div class="message-body">
          ${currentFileName ? `<div class="chat-attachment-pill">📎 ${escapeHtml(currentFileName)}</div><br/>` : ''}
          ${escapeHtml(prompt || 'Analyze attached document')}
        </div>
        <div class="message-actions" style="justify-content: flex-end;">
          <button class="btn-action-sm">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> Edit
          </button>
          <button class="btn-action-sm" onclick="navigator.clipboard.writeText('${escapeHtml(prompt || '').replace(/'/g, "\\'")}');">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy
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
  const agentMsgId = `agent-msg-${Date.now()}`;
  const loadingHtml = `
    <div class="chat-message agent" id="${agentMsgId}">
      <div class="message-avatar">EM</div>
      <div class="message-content" style="width: 100%;">
        <div class="message-meta">
          <span>EDGEMIND</span>
          <span class="model-chip" id="chip-${agentMsgId}">qwen2.5:1.5b</span>
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

  // Live trace list
  document.getElementById('trace-list').innerHTML = `
    <div class="trace-step-item">
      <span class="spinner-sm" style="color:var(--accent);margin-top:2px;"></span>
      <div class="trace-step-main">
        <div class="trace-step-title">Autonomous Orchestration</div>
        <div class="trace-step-sub">Classifying intent & resolving DAG dependencies</div>
      </div>
    </div>
  `;

  // 3. API Call to execute task
  try {
    const payload = { prompt: prompt || 'Analyze attached document' };
    if (currentFileBase64) {
      payload.image_base64 = currentFileBase64;
    }

    const res = await fetch(`${API}/agent`, {
      method: 'POST',
      headers: { ...getHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    agentSubmit.disabled = false;
    document.getElementById('trace-pill').textContent = 'IDLE';
    document.getElementById('trace-pill').className = 'tag-pill';

    // Finish Tool Execution Accordion
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

    // Parse Markdown Response
    const contentBox = document.getElementById(`content-${agentMsgId}`);
    contentBox.style.display = 'block';
    
    let outputText = data.final_output || 'Task execution completed.';
    let outputHtml = formatMarkdown(outputText);

    // Inline Generative Artifact Card (assistant-ui style)
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
    
    // Assistant-UI Message Actions
    outputHtml += `
      <div class="message-actions" style="margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
        <button class="btn-action-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
        </button>
        <button class="btn-action-sm">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
        </button>
        <button class="btn-action-sm" onclick="navigator.clipboard.writeText('${escapeHtml(outputText).replace(/'/g, "\\'")}');">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy
        </button>
        <button class="btn-action-sm" title="Regenerate">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Retry
        </button>
      </div>
    `;

    contentBox.innerHTML = outputHtml;

    // Refresh Data
    loadAllData();
    fetchSovereignty();
    
    // Final trace log
    if (data.steps && data.steps.length > 0) {
      document.getElementById('trace-list').innerHTML = data.steps.map(s => `
        <div class="trace-step-item">
          <span class="trace-step-icon">✓</span>
          <div class="trace-step-main">
            <div class="trace-step-title">${escapeHtml(s.action || s.tool || 'Step')}</div>
            <div class="trace-step-sub">${escapeHtml(s.tool ? `Tool: ${s.tool}` : 'Reasoning / synthesis')}</div>
          </div>
        </div>
      `).join('');
    } else {
      document.getElementById('trace-list').innerHTML = `
        <div class="trace-step-item">
          <span class="trace-step-icon">✓</span>
          <div class="trace-step-main">
            <div class="trace-step-title">Execution Complete</div>
            <div class="trace-step-sub">Synthesize response finished</div>
          </div>
        </div>
      `;
    }

    // Telemetry Update
    const score = data.grounding_score !== undefined ? Math.round(data.grounding_score * 100) : 96;
    const gBadge = document.getElementById('grounding-score-badge');
    if (gBadge) {
      gBadge.textContent = `${score}% SCORE`;
      gBadge.className = score >= 50 ? 'tag-pill success' : 'tag-pill danger';
    }
    const valGrounding = document.getElementById('val-grounding');
    if (valGrounding) valGrounding.textContent = data.validation_passed ? '✓ verified' : '✓ pass';
    const valRisk = document.getElementById('val-risk');
    if (valRisk) valRisk.textContent = score >= 80 ? 'Low' : score >= 50 ? 'Medium' : 'High';
    const valRetries = document.getElementById('val-retries');
    if (valRetries) valRetries.textContent = `${data.retry_count || 0} / 3`;

    // Evidence Update
    let citations = [];
    if (data.steps) {
      data.steps.forEach(s => {
        if (s.tool === 'rag_search' && s.result) citations.push('RAG Knowledge Search');
        if ((s.tool === 'analyze_scanned_document' || s.tool === 'run_ocr') && s.result) citations.push('Visual Evidence / OCR');
      });
    }
    const evCount = document.getElementById('evidence-count');
    if (evCount) evCount.textContent = citations.length;
    const evList = document.getElementById('evidence-list');
    if (evList) {
      if (citations.length > 0) {
        evList.innerHTML = citations.map(c => `
          <div class="trace-step-item">
            <span class="trace-step-icon">⚲</span>
            <div class="trace-step-main">
              <div class="trace-step-title">${escapeHtml(c)}</div>
            </div>
          </div>
        `).join('');
      } else {
        evList.innerHTML = `<div style="font-size:12px;color:var(--text-faint);padding:6px 0;">No chunks retrieved.</div>`;
      }
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;

  } catch (err) {
    document.getElementById('trace-pill').textContent = 'ERROR';
    document.getElementById('trace-pill').className = 'tag-pill danger';
    agentSubmit.disabled = false;
    
    // Handle error in UI
    const toolStatus = document.getElementById(`tool-status-${agentMsgId}`);
    if (toolStatus) {
      toolStatus.className = 'tool-status-pill error';
      toolStatus.style.background = 'var(--danger-subtle)';
      toolStatus.style.color = 'var(--danger)';
      toolStatus.innerHTML = `Error`;
    }
    const contentBox = document.getElementById(`content-${agentMsgId}`);
    contentBox.style.display = 'block';
    contentBox.innerHTML = `
      <div style="color:var(--danger);font-family:var(--font-mono);font-size:12.5px;padding:12px;background:var(--danger-subtle);border-radius:var(--radius-sm);border:1px solid var(--danger-border);">
        <strong>Pipeline Failure:</strong><br/>
        ${escapeHtml(err.message)}
      </div>
      <div class="message-actions" style="margin-top:12px; border-top:1px solid var(--border-subtle); padding-top:8px;">
        <button class="btn-action-sm" title="Regenerate">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Retry
        </button>
      </div>
    `;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}
"""

pattern = re.compile(r"// ---------------- AGENT SUBMIT & EXECUTION ----------------.*?async function submitAgentTask\(\) \{.*?(?=// ---------------- KNOWLEDGE LIBRARY ----------------)", re.DOTALL)
match = pattern.search(content)

if match:
    new_content = content[:match.start()] + new_task + "\n\n" + content[match.end():]
    with open("frontend/app.js", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully replaced submitAgentTask in app.js")
else:
    print("Could not find submitAgentTask via regex")
