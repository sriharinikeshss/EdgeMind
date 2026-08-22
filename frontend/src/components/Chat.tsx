/**
 * Chat component — Phase 1 (M6).
 *
 * Sends user messages to POST /api/tasks with a JWT Bearer token.
 * Displays the model badge and response latency for each agent reply.
 */
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Chat.css';

interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  model_used?: string;
  latency_ms?: number;
}

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export function Chat() {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage: Message = { id: Date.now().toString(), sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
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
      <div className="chat-history">
        {messages.map(msg => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            <div className="message-content">{msg.text}</div>
            {msg.model_used && (
              <div className="model-badge">
                🤖 {msg.model_used}
                {msg.latency_ms !== undefined && (
                  <span className="latency"> · {Math.round(msg.latency_ms)}ms</span>
                )}
              </div>
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
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="Ask EdgeMind…"
        />
        <button onClick={sendMessage} disabled={isLoading}>Send</button>
      </div>
    </div>
  );
}

