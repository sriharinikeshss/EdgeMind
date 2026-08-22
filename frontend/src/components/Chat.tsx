/**
 * Chat component — Phase 3 (M6).
 *
 * Adds an "Agent Mode" toggle:
 *   - OFF → calls POST /api/tasks (direct single-shot, Phase 1/2)
 *   - ON  → calls POST /api/agent  (Planner→Executor→Validator loop, Phase 3)
 *           and renders the AgentTrace component below the response.
 */
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { AgentTrace, type StepResult, type AgentEvent } from './AgentTrace';
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
  trace?: AgentTraceData;
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function Chat() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [agentMode, setAgentMode] = useState(false);

  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { id: Date.now().toString(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      if (agentMode) {
        // Phase 3: full agent loop
        const response = await fetch(`${API_URL}/api/agent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
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
      <div className="chat-input-area">
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
