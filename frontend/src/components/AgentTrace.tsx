/**
 * AgentTrace — Phase 3 (M6).
 *
 * Displays the live agent execution trace: step-by-step plan, status icons,
 * and expand/collapse output for each step.
 * Driven by the `events` array returned in the POST /api/agent response.
 */
import { useState } from 'react';
import './AgentTrace.css';

export interface StepResult {
  step_id: string | null;
  action: string | null;
  success: boolean;
  output: string | null;
  error: string | null;
  tool: string | null;
}

export interface AgentEvent {
  type: string;
  [key: string]: unknown;
}

interface AgentTraceProps {
  steps: StepResult[];
  events: AgentEvent[];
  status: 'COMPLETED' | 'FAILED' | 'RUNNING' | string;
  validationPassed: boolean;
}

const STATUS_ICON: Record<string, string> = {
  COMPLETED: '✅',
  FAILED: '❌',
  RUNNING: '⏳',
  RETRYING: '🔄',
  VALIDATING: '🔍',
};

const TOOL_ICON: Record<string, string> = {
  execute_python: '🐍',
  rag_search: '📚',
  direct_llm: '🤖',
  direct_llm_fallback: '🤖',
  run_ocr: '👁️',
  analyze_scanned_document: '👁️',
  analyze_engineering_drawing: '🏗️',
};

export function AgentTrace({ steps, events, status, validationPassed }: AgentTraceProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (id: string) =>
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }));

  const overallIcon = STATUS_ICON[status] ?? '❓';

  return (
    <div className="agent-trace">
      <div className="trace-header">
        <span className="trace-title">Agent Execution Trace</span>
        <span className={`trace-status ${status.toLowerCase()}`}>
          {overallIcon} {status}
          {status === 'COMPLETED' && (
            <span className={`validation-badge ${validationPassed ? 'pass' : 'fail'}`}>
              {validationPassed ? ' · Validated ✅' : ' · Validation ❌'}
            </span>
          )}
        </span>
      </div>

      {steps.length === 0 && (
        <div className="trace-empty">No steps executed yet.</div>
      )}

      <ol className="trace-steps">
        {steps.map((step, idx) => {
          const key = step.step_id ?? `step-${idx}`;
          const icon = step.success ? '✅' : '❌';
          const toolIcon = TOOL_ICON[step.tool ?? ''] ?? '🔧';
          const isExpanded = !!expanded[key];

          return (
            <li
              key={key}
              className={`trace-step ${step.success ? 'success' : 'failed'}`}
            >
              <div
                className="step-header"
                onClick={() => toggle(key)}
                role="button"
                tabIndex={0}
                onKeyDown={e => e.key === 'Enter' && toggle(key)}
              >
                <span className="step-icon">{icon}</span>
                <span className="step-id">{step.step_id ?? `#${idx + 1}`}</span>
                <span className="step-tool">{toolIcon} {step.tool ?? 'unknown'}</span>
                <span className="step-action">{step.action}</span>
                <span className="step-toggle">{isExpanded ? '▲' : '▼'}</span>
              </div>
              {isExpanded && (
                <div className="step-body">
                  {step.success && step.output && (
                    <pre className="step-output">{step.output}</pre>
                  )}
                  {!step.success && step.error && (
                    <pre className="step-error">Error: {step.error}</pre>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {events.length > 0 && (
        <details className="trace-events">
          <summary>Raw events ({events.length})</summary>
          <pre className="events-json">{JSON.stringify(events, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
