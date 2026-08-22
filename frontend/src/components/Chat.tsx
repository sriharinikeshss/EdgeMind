/**
 * Chat component - Phase 5. Emoji as Unicode escapes to avoid Windows encoding corruption.
 */
import { useState, useRef, type ChangeEvent } from 'react';
import { useAuth } from '../context/AuthContext';
import { AgentTrace, type StepResult, type AgentEvent } from './AgentTrace';
import { VisualEvidence, type MultimodalResult } from './VisualEvidence';
import './Chat.css';

interface AgentTraceData {
  steps: StepResult[];
  events: AgentEvent[];
  status: string;
  validationPassed: boolean;
}

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  model_used?: string;
  latency_ms?: number;
  image_preview?: string;
  multimodal_result?: MultimodalResult;
  trace?: AgentTraceData;
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// Unicode escape constants - immune to Windows filesystem encoding issues
const ROBOT  = '\u{1F916}'; // robot
const BOLT   = '\u26A1';    // lightning
const EYE    = '\u{1F441}\uFE0F'; // eye
const CAMERA = '\u{1F4F7}'; // camera
const ARROW  = '\u2192';    // right arrow
const ELLIP  = '\u2026';    // ellipsis
const CROSS  = '\u2715';    // cross mark
const MIDDOT = '\u00B7';    // middle dot

export function Chat() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getHeaders = (): Record<string, string> => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  };

  const handleImageUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => setAttachedImage(ev.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  const removeAttachedImage = () => {
    setAttachedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const sendMessage = async () => {
    if (!input.trim() && !attachedImage) return;
    const currentImage = attachedImage;
    const userMsg: Message = {
      id: Date.now().toString(), sender: 'user',
      text: input || (currentImage ? 'Analyze uploaded image/document' : ''),
      image_preview: currentImage || undefined,
    };
    setMessages(prev => [...prev, userMsg]);
    setInput(''); setAttachedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setIsLoading(true);
    try {
      if (currentImage) {
        const visionResp = await fetch(`${API_URL}/api/vision/multimodal`, {
          method: 'POST', headers: getHeaders(),
          body: JSON.stringify({ image_base64: currentImage, task_type: 'auto' }),
        });
        const visionData: MultimodalResult = await visionResp.json();
        const prompt = `${userMsg.text}\n\n${(visionData as any).grounding_prompt || ''}`;
        const resp = await fetch(`${API_URL}/api/tasks`, { method: 'POST', headers: getHeaders(), body: JSON.stringify({ prompt }) });
        const data = await resp.json();
        setMessages(prev => [...prev, { id: data.task_id || Date.now().toString(), sender: 'agent', text: data.response, model_used: data.model_used || 'qwen2.5:1.5b', latency_ms: data.latency_ms, multimodal_result: visionData, image_preview: currentImage }]);
      } else if (agentMode) {
        const resp = await fetch(`${API_URL}/api/agent`, { method: 'POST', headers: getHeaders(), body: JSON.stringify({ prompt: userMsg.text }) });
        const data = await resp.json();
        setMessages(prev => [...prev, { id: data.task_id, sender: 'agent', text: data.final_output || '[No output]', trace: { steps: data.steps ?? [], events: data.events ?? [], status: data.status, validationPassed: data.validation_passed } }]);
      } else {
        const resp = await fetch(`${API_URL}/api/tasks`, { method: 'POST', headers: getHeaders(), body: JSON.stringify({ prompt: userMsg.text }) });
        const data = await resp.json();
        setMessages(prev => [...prev, { id: data.task_id, sender: 'agent', text: data.response, model_used: data.model_used, latency_ms: data.latency_ms }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'agent', text: 'Error: Could not connect to API.' }]);
    } finally { setIsLoading(false); }
  };

  return (
    <div className="chat-container">
      <div className="chat-mode-bar">
        <label className="mode-toggle">
          <input type="checkbox" checked={agentMode} onChange={e => setAgentMode(e.target.checked)} />
          <span className={`mode-label ${agentMode ? 'agent' : 'direct'}`}>
            {agentMode ? `${ROBOT} Agent Mode (Planner ${ARROW} Executor ${ARROW} Validator)` : `${BOLT} Direct Mode`}
          </span>
        </label>
        <span className="multimodal-indicator">{EYE} Multimodal OCR/P&ID Enabled</span>
      </div>
      <div className="chat-history">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            {msg.image_preview && <div className="chat-image-attachment"><img src={msg.image_preview} alt="Attached" /></div>}
            <div className="message-content">{msg.text}</div>
            {msg.model_used && (
              <div className={`model-badge ${msg.model_used.includes('coder') ? 'coder' : 'reasoning'}`}>
                {ROBOT} {msg.model_used}
                {msg.latency_ms !== undefined && <span className="latency"> {MIDDOT} {Math.round(msg.latency_ms)}ms</span>}
              </div>
            )}
            {msg.multimodal_result && <VisualEvidence imageSrc={msg.image_preview} result={msg.multimodal_result} />}
            {msg.trace && <AgentTrace steps={msg.trace.steps} events={msg.trace.events} status={msg.trace.status} validationPassed={msg.trace.validationPassed} />}
          </div>
        ))}
        {isLoading && <div className="message agent"><div className="message-content thinking"><span className="dot" /><span className="dot" /><span className="dot" /></div></div>}
      </div>
      {attachedImage && (
        <div className="attachment-bar">
          <div className="attachment-preview"><img src={attachedImage} alt="Thumb" /><span>Image attached</span></div>
          <button className="remove-attachment-btn" onClick={removeAttachedImage}>{CROSS}</button>
        </div>
      )}
      <div className="chat-input-area">
        <input type="file" ref={fileInputRef} onChange={handleImageUpload} accept="image/*,application/pdf" style={{ display: 'none' }} />
        <button type="button" className="attach-btn" onClick={() => fileInputRef.current?.click()} title="Attach Document or P&ID">{CAMERA}</button>
        <textarea value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          placeholder={attachedImage ? 'Ask about this document...' : agentMode ? `Give the agent a task (Shift+Enter for newline)${ELLIP}` : `Ask EdgeMind${ELLIP}`}
          rows={2} />
        <button onClick={sendMessage} disabled={isLoading || (!input.trim() && !attachedImage)}>Send</button>
      </div>
    </div>
  );
}
