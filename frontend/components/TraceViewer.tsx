'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Clock, Wrench, Bot, AlertCircle } from 'lucide-react';
import type { RequestTrace, AgentSpanTrace, ToolCallTrace } from '@/lib/api';

function DurationBadge({ ms }: { ms: number }) {
  const text = ms < 1000 ? `${Math.round(ms)}ms` : `${(ms / 1000).toFixed(2)}s`;
  return (
    <span
      className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-mono"
      style={{ background: 'var(--surface-secondary)', color: 'var(--muted)' }}
    >
      <Clock size={9} />
      {text}
    </span>
  );
}

function JsonBlock({ data, label }: { data: unknown; label: string }) {
  const [open, setOpen] = useState(false);
  if (data === null || data === undefined) return null;

  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  if (!text || text === '{}' || text === '[]' || text === 'null') return null;

  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[11px] font-mono transition-colors hover:opacity-80"
        style={{ color: 'var(--muted)' }}
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        {label}
      </button>
      {open && (
        <pre
          className="mt-1 p-2 rounded text-[11px] overflow-x-auto max-h-48 overflow-y-auto font-mono"
          style={{ background: 'var(--code-block-bg)', color: 'var(--code-block-text)' }}
        >
          {text}
        </pre>
      )}
    </div>
  );
}

function ToolCallRow({ tc }: { tc: ToolCallTrace }) {
  const hasError = !!tc.error;
  return (
    <div
      className="rounded-lg p-2 ml-4 mt-1"
      style={{
        background: 'var(--surface-secondary)',
        borderLeft: `2px solid ${hasError ? 'var(--error, #ef4444)' : 'var(--accent)'}`,
      }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <Wrench size={11} style={{ color: hasError ? 'var(--error, #ef4444)' : 'var(--accent)' }} />
        <span className="text-xs font-semibold font-mono" style={{ color: 'var(--foreground)' }}>
          {tc.tool_name}
        </span>
        <DurationBadge ms={tc.duration_ms} />
        {hasError && (
          <span className="flex items-center gap-0.5 text-[10px]" style={{ color: 'var(--error, #ef4444)' }}>
            <AlertCircle size={10} />
            error
          </span>
        )}
      </div>
      <JsonBlock data={tc.args} label="args" />
      {hasError ? (
        <div className="mt-1 text-[11px] font-mono" style={{ color: 'var(--error, #ef4444)' }}>
          {tc.error}
        </div>
      ) : (
        <JsonBlock data={tc.result} label="result" />
      )}
    </div>
  );
}

function AgentSpanBlock({ span, depth = 0 }: { span: AgentSpanTrace; depth?: number }) {
  const [open, setOpen] = useState(true);
  const totalTools = span.tool_calls.length;
  const totalChildren = span.child_spans.length;

  return (
    <div className={depth > 0 ? 'ml-4 mt-2' : 'mt-2'}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left transition-colors hover:opacity-80"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <Bot size={13} style={{ color: 'var(--accent)' }} />
        <span className="text-xs font-semibold" style={{ color: 'var(--foreground)' }}>
          {span.agent_name}
        </span>
        <DurationBadge ms={span.duration_ms} />
        {totalTools > 0 && (
          <span className="text-[10px]" style={{ color: 'var(--muted)' }}>
            {totalTools} tool{totalTools !== 1 ? 's' : ''}
          </span>
        )}
      </button>

      {open && (
        <div className="mt-1">
          {span.tool_calls.map((tc, i) => (
            <ToolCallRow key={`${tc.tool_name}-${i}`} tc={tc} />
          ))}
          {span.child_spans.map((child, i) => (
            <AgentSpanBlock key={`${child.agent_name}-${i}`} span={child} depth={depth + 1} />
          ))}
          {totalTools === 0 && totalChildren === 0 && (
            <div className="ml-4 text-[11px] italic" style={{ color: 'var(--muted)' }}>
              No tool calls
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TraceViewer({ trace }: { trace: RequestTrace }) {
  const [open, setOpen] = useState(false);

  function countTools(spans: AgentSpanTrace[]): number {
    return spans.reduce(
      (sum, s) => sum + s.tool_calls.length + countTools(s.child_spans), 0
    );
  }
  const totalTools = countTools(trace.agent_spans);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md transition-colors hover:opacity-80"
        style={{
          background: 'var(--surface-secondary)',
          color: 'var(--muted)',
          border: '1px solid var(--border)',
        }}
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        <Wrench size={11} />
        Trace
        <DurationBadge ms={trace.duration_ms} />
        {totalTools > 0 && (
          <span className="text-[10px]">
            ({totalTools} tool call{totalTools !== 1 ? 's' : ''})
          </span>
        )}
      </button>

      {open && (
        <div
          className="mt-1 p-3 rounded-lg"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
          }}
        >
          <div className="flex items-center gap-2 mb-2 text-[10px] font-mono" style={{ color: 'var(--muted)' }}>
            <span>trace: {trace.trace_id.slice(0, 8)}...</span>
            <DurationBadge ms={trace.duration_ms} />
          </div>
          {trace.agent_spans.map((span, i) => (
            <AgentSpanBlock key={`${span.agent_name}-${i}`} span={span} />
          ))}
          {trace.agent_spans.length === 0 && (
            <div className="text-[11px] italic" style={{ color: 'var(--muted)' }}>
              No agent spans recorded
            </div>
          )}
        </div>
      )}
    </div>
  );
}
