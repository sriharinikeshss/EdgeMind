import re

with open('frontend/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

sovereignty_code = """
// ---------------- SOVEREIGNTY STATUS ----------------
async function fetchSovereignty() {
  try {
    const res = await fetch(`${API}/sovereignty/report`, { headers: getHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    
    const sovTitle = document.getElementById('sov-title');
    const sovScore = document.getElementById('sov-score');
    const sovMsg = document.getElementById('sov-msg');
    const sovSub = document.querySelector('.sov-details .sov-sub');
    
    if (data.sovereign) {
      sovTitle.innerHTML = 'Local &amp; protected';
      sovTitle.nextElementSibling.setAttribute('stroke', 'var(--success)');
      sovScore.textContent = '100';
      sovMsg.textContent = 'No egress detected';
      sovSub.textContent = 'Air-gapped verification passed';
    } else {
      sovTitle.innerHTML = 'External egress detected';
      sovTitle.nextElementSibling.setAttribute('stroke', 'var(--danger)');
      sovScore.textContent = '65';
      
      const egressStr = data.egress_check && !data.egress_check.egress_blocked ? 'Internet reachable. ' : '';
      const flags = (data.network_monitor && data.network_monitor.flagged_external_connections && data.network_monitor.flagged_external_connections.length > 0) ? `${data.network_monitor.flagged_external_connections.length} external connections.` : '';
      
      sovMsg.textContent = egressStr + flags || 'Network anomaly detected';
      sovMsg.style.color = 'var(--danger)';
      sovSub.textContent = 'Warning: Not strictly air-gapped';
    }
  } catch (err) {
    console.error("Sovereignty fetch failed", err);
  }
}
"""

if "fetchSovereignty" not in text:
    text += "\n" + sovereignty_code

# Inject call to fetchSovereignty() on login
text = re.sub(
    r"(loadDocuments\(\);\n)",
    r"\1      fetchSovereignty();\n",
    text
)

with open('frontend/app.js', 'w', encoding='utf-8') as f:
    f.write(text)
