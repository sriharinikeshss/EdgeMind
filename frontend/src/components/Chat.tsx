/**
 * Chat component — Phase 3 (M6).
 *
 * Adds an "Agent Mode" toggle:
 *   - OFF → calls POST /api/tasks (direct single-shot, Phase 1/2)
 *   - ON  → calls POST /api/agent  (Planner→Executor→Validator loop, Phase 3)
 *           and renders the AgentTrace component below the response.
 */
import { useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AgentTrace, type StepResult, type AgentEvent } from './AgentTrace';
import './Chat.css';

const MAX_IMAGE_BYTES = 8 * 1024 * 1024; // ~8MB client-side guard

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
  trace?: AgentTraceData;
  imageDataUrl?: string;
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function Chat() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [attachedImage, setAttachedImage] = useState<{ base64: string; dataUrl: string; filename: string } | null>(null);
  const [attachError, setAttachError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;

    if (file.size > MAX_IMAGE_BYTES) {
      setAttachError(`"${file.name}" is too large (max 8MB).`);
      return;
    }
    setAttachError(null);

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const base64 = dataUrl.split(',')[1] ?? '';
      setAttachedImage({ base64, dataUrl, filename: file.name });
    };
    reader.readAsDataURL(file);
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    // An attached image only makes sense through the agent loop (Direct
    // Mode's /api/tasks endpoint has no concept of images), so attaching a
    // file implicitly routes this send through /api/agent regardless of
    // the Agent Mode toggle's current value.
    const useAgent = agentMode || !!attachedImage;

    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: input,
      imageDataUrl: attachedImage?.dataUrl,
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      if (useAgent) {
        // Phase 3: full agent loop (Phase 5: optional attached image)
        const response = await fetch(`${API_URL}/api/agent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          body: JSON.stringify({
            prompt: userMessage.text,
            image_base64: attachedImage?.base64,
            filename: attachedImage?.filename,
          }),
        });
        const data = await response.json();

        const agentMessage: Message = {
          id: data.task_id,
          sender: 'agent',
          text: data.final_output || '[No output]',
          trace: {
            steps: data.steps ?? [],
            events: data.events ?? [],
            status: data.status,
            validationPassed: data.validation_passed,
          },
        };
        setMessages(prev => [...prev, agentMessage]);
      } else {
        // Phase 1/2: direct single-shot
        const response = await fetch(`${API_URL}/api/tasks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          body: JSON.stringify({ prompt: userMessage.text }),
        });
        const data = await response.json();

        const agentMessage: Message = {
          id: data.task_id,
          sender: 'agent',
          text: data.response,
          model_used: data.model_used,
          latency_ms: data.latency_ms,
        };
        setMessages(prev => [...prev, agentMessage]);
      }
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [
        ...prev,
        { id: Date.now().toString(), sender: 'agent', text: 'Error: Could not connect to API.' },
      ]);
    } finally {
      setIsLoading(false);
      setAttachedImage(null);
    }
  };

  return (
    <div className="chat-container">
      {/* Agent Mode toggle */}
      <div className="chat-mode-bar">
        <label className="mode-toggle">
          <input
            type="checkbox"
            checked={agentMode}
            onChange={e => setAgentMode(e.target.checked)}
          />
          <span className={`mode-label ${agentMode ? 'agent' : 'direct'}`}>
            {agentMode ? '🤖 Agent Mode (Planner → Executor → Validator)' : '⚡ Direct Mode'}
          </span>
        </label>
      </div>

      <div className="chat-history">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            {msg.imageDataUrl && (
              <img className="message-thumbnail" src={msg.imageDataUrl} alt="Attached" />
            )}
            <div className="message-content">{msg.text}</div>
            {msg.model_used && (
              <div className={`model-badge ${msg.model_used.includes('coder') ? 'coder' : 'reasoning'}`}>
                🤖 {msg.model_used}
                {msg.latency_ms !== undefined && (
                  <span className="latency"> · {Math.round(msg.latency_ms)}ms</span>
                )}
              </div>
            )}
            {msg.trace && (
              <AgentTrace
                steps={msg.trace.steps}
                events={msg.trace.events}
                status={msg.trace.status}
                validationPassed={msg.trace.validationPassed}
              />
            )}
          </div>
        ))}
        {isLoading && (
          <div className="message agent">
            <div className="message-content thinking">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </div>
          </div>
        )}
      </div>
      {(attachedImage || attachError) && (
        <div className="attach-bar">
          {attachedImage && (
            <span className="attach-chip">
              <img className="attach-thumbnail" src={attachedImage.dataUrl} alt={attachedImage.filename} />
              {attachedImage.filename}
              <button
                type="button"
                className="attach-chip-remove"
                onClick={() => setAttachedImage(null)}
                aria-label="Remove attached image"
              >
                ✕
              </button>
            </span>
          )}
          {attachError && <span className="attach-error">{attachError}</span>}
        </div>
      )}
      <div className="chat-input-area">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          className="attach-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isLoading}
          title="Attach a scanned document or image"
        >
          📎
        </button>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder={agentMode ? 'Give the agent a multi-step task (Shift+Enter for newline)…' : 'Ask EdgeMind…'}
          rows={3}
        />
        <button onClick={sendMessage} disabled={isLoading}>Send</button>
      </div>
    </div>
  );
}
