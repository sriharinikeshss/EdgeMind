/**
 * Chat component — Phase 5 (M6).
 *
 * Adds:
 *   - Agent Mode toggle (Phase 3)
 *   - Image & Scanned Document / P&ID upload flow (Phase 5)
 *   - Interactive Visual Evidence rendering with Bounding Boxes & Confidence Badges (Phase 5)
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

export function Chat() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getHeaders = (): Record<string, string> => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  };

  const handleImageUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (uploadEvent) => {
        setAttachedImage(uploadEvent.target?.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const removeAttachedImage = () => {
    setAttachedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendMessage = async () => {
    if (!input.trim() && !attachedImage) return;

    const currentImage = attachedImage;
    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: input || (currentImage ? 'Analyze uploaded image/document' : ''),
      image_preview: currentImage || undefined,
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setAttachedImage(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setIsLoading(true);

    try {
      if (currentImage) {
        // Phase 5 Multimodal Analysis pipeline
        const visionResp = await fetch(`${API_URL}/api/vision/multimodal`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({
            image_base64: currentImage,
            task_type: 'auto',
          }),
        });
        const visionData: MultimodalResult = await visionResp.json();

        // Feed extracted visual data into reasoning agent / LLM
        const promptWithGrounding = `${userMessage.text}\n\n${(visionData as any).grounding_prompt || ''}`;
        const response = await fetch(`${API_URL}/api/tasks`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({ prompt: promptWithGrounding }),
        });
        const data = await response.json();

        const agentMessage: Message = {
          id: data.task_id || Date.now().toString(),
          sender: 'agent',
          text: data.response,
          model_used: data.model_used || 'qwen2.5:1.5b',
          latency_ms: data.latency_ms,
          multimodal_result: visionData,
          image_preview: currentImage,
        };
        setMessages(prev => [...prev, agentMessage]);
      } else if (agentMode) {
        // Phase 3: full agent loop
        const response = await fetch(`${API_URL}/api/agent`, {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({ prompt: userMessage.text }),
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
          headers: getHeaders(),
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
    }
  };

  return (
    <div className="chat-container">
      {/* Mode bar */}
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
        <span className="multimodal-indicator">👁️ Multimodal OCR/P&ID Enabled</span>
      </div>

      <div className="chat-history">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            {msg.image_preview && (
              <div className="chat-image-attachment">
                <img src={msg.image_preview} alt="Attached input" />
              </div>
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
            {msg.multimodal_result && (
              <VisualEvidence
                imageSrc={msg.image_preview}
                result={msg.multimodal_result}
              />
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

      {/* Attachment Preview bar */}
      {attachedImage && (
        <div className="attachment-bar">
          <div className="attachment-preview">
            <img src={attachedImage} alt="Attachment thumbnail" />
            <span>Image attached (Document / P&ID)</span>
          </div>
          <button className="remove-attachment-btn" onClick={removeAttachedImage}>✕</button>
        </div>
      )}

      <div className="chat-input-area">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleImageUpload}
          accept="image/*,application/pdf"
          style={{ display: 'none' }}
        />
        <button
          type="button"
          className="attach-btn"
          onClick={() => fileInputRef.current?.click()}
          title="Attach Scanned Document or P&ID Schematic"
        >
          📷
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
          placeholder={
            attachedImage
              ? 'Ask a question about this document/diagram...'
              : agentMode
              ? 'Give the agent a multi-step task (Shift+Enter for newline)…'
              : 'Ask EdgeMind…'
          }
          rows={2}
        />
        <button onClick={sendMessage} disabled={isLoading || (!input.trim() && !attachedImage)}>
          Send
        </button>
      </div>
    </div>
  );
}
