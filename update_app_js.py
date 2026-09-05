import re

with open('frontend/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add model ID span to agent message header
text = re.sub(
    r'(EDGEMIND.*?LOCAL AGENTIC REASONING)',
    r'\1<span id="agent-model-${agentMsgId}" style="color:var(--primary);"></span>',
    text
)

# 2. Update model used text after API response
text = re.sub(
    r'(agentMsgEl\.innerHTML = data\.final_output;)',
    r'\1\n      document.getElementById(`agent-model-${agentMsgId}`).innerHTML = ` &middot; MODEL: ${data.model_used || "ollama"}`;',
    text
)

# 3. Add actual citations parsing instead of pushing hardcoded RAG tag
text = re.sub(
    r"if \(s\.tool === 'rag_search'\) \{.*?\}",
    r'''if (s.tool === 'rag_search' && s.tool_data && s.tool_data.citations) {
        s.tool_data.citations.forEach(cit => {
          citations.push({ name: 'RAG Doc: ' + (cit.doc_id || 'Unknown').substring(0,20), sub: cit.text ? cit.text.substring(0, 50) + '...' : 'Context retrieved', tag: 'RAG' });
        });
      }''',
    text,
    flags=re.DOTALL
)

with open('frontend/app.js', 'w', encoding='utf-8') as f:
    f.write(text)
