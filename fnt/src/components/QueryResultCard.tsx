import React, { useState } from 'react';
import {
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Layers,
  Activity,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  Cpu,
} from 'lucide-react';
import type { Answer, Evidence, TraceStep } from '@/services/types';

export interface QueryResultCardProps {
  answer: Answer;
  onReset?: () => void;
}

export const QueryResultCard: React.FC<QueryResultCardProps> = ({ answer, onReset }) => {
  const [showTrace, setShowTrace] = useState(false);
  const [expandedPayloads, setExpandedPayloads] = useState<Record<string, boolean>>({});

  const togglePayload = (id: string) => {
    setExpandedPayloads((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const confidencePercent = (answer.confidence * 100).toFixed(1);

  return (
    <article
      className="mt-8 rounded-xl border border-cyan-500/30 bg-slate-900/90 shadow-2xl shadow-cyan-950/20 overflow-hidden"
      aria-labelledby="backend-answer-heading"
    >
      {/* Response Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/80 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 id="backend-answer-heading" className="text-base font-semibold text-white">
              SatQuery AI Inference Result
            </h2>
            <p className="text-xs text-slate-400 font-mono">
              Trace ID: {answer.trace.trace_id.slice(0, 8)}...
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Abstention or Grounded Badge */}
          {answer.abstained ? (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-950/60 border border-amber-500/40 px-3 py-1 text-xs font-semibold text-amber-300">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
              <span>Abstained</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-950/60 border border-emerald-500/40 px-3 py-1 text-xs font-semibold text-emerald-300">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Verified & Grounded</span>
            </span>
          )}

          {/* Confidence Metric */}
          <div className="flex items-center gap-2 rounded-md bg-slate-900 border border-slate-800 px-3 py-1 text-xs text-slate-300">
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
            <span>Confidence:</span>
            <span className="font-mono font-bold text-cyan-300">{confidencePercent}%</span>
          </div>

          {onReset && (
            <button
              type="button"
              onClick={onReset}
              className="rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1 text-xs font-medium text-slate-200 border border-slate-700 transition-colors"
            >
              New Query
            </button>
          )}
        </div>
      </div>

      {/* Abstention Warning Banner if Abstained */}
      {answer.abstained && answer.abstention_reason && (
        <div
          role="alert"
          className="border-b border-amber-500/30 bg-amber-950/40 px-6 py-3 text-xs text-amber-200 flex items-start gap-2.5"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
          <div>
            <span className="font-semibold">Pipeline Abstention Triggered:</span>{' '}
            <span>{answer.abstention_reason}</span>
          </div>
        </div>
      )}

      <div className="p-6 space-y-6">
        {/* Synthesized Answer Text */}
        <section>
          <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
            Synthesized Answer
          </h3>
          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
            <p className="text-sm font-medium leading-relaxed text-slate-100 whitespace-pre-wrap">
              {answer.text}
            </p>
          </div>
        </section>

        {/* Cited Evidence Items */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyan-400" />
              <h3 className="text-xs font-mono uppercase tracking-wider text-slate-400">
                Grounded Evidence Items ({answer.evidence.length})
              </h3>
            </div>
          </div>

          {answer.evidence.length === 0 ? (
            <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-center text-xs text-slate-400">
              No evidence items produced by the inference tools.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {answer.evidence.map((item: Evidence) => {
                const isExpanded = !!expandedPayloads[item.id];
                return (
                  <div
                    key={item.id}
                    className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 text-xs text-slate-300"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <FileCheck2 className="h-4 w-4 text-cyan-400 shrink-0" />
                        <span className="font-semibold text-white">{item.tool}</span>
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-mono text-cyan-300 border border-slate-700">
                          {item.type}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {(item.timing * 1000).toFixed(1)}ms
                        </span>
                      </div>
                    </div>

                    <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/80 pt-2">
                      <span>Confidence: {(item.confidence * 100).toFixed(1)}%</span>
                      <button
                        type="button"
                        onClick={() => togglePayload(item.id)}
                        className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
                      >
                        <span>{isExpanded ? 'Hide Payload' : 'View Payload'}</span>
                        {isExpanded ? (
                          <ChevronUp className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </button>
                    </div>

                    {isExpanded && (
                      <div className="mt-2.5 rounded bg-slate-900 p-2 border border-slate-800 overflow-x-auto">
                        <pre className="text-[10px] font-mono text-slate-300">
                          {JSON.stringify(item.payload, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Auditable Execution Trace Collapsible */}
        <section className="border-t border-slate-800 pt-4">
          <button
            type="button"
            onClick={() => setShowTrace((prev) => !prev)}
            className="flex w-full items-center justify-between rounded-lg bg-slate-950/60 px-4 py-2.5 text-xs font-semibold text-slate-300 border border-slate-800 hover:text-white transition-colors"
            aria-expanded={showTrace}
          >
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-cyan-400" />
              <span>Auditable Pipeline Execution Trace ({answer.trace.steps.length} Steps)</span>
            </div>
            {showTrace ? (
              <ChevronUp className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronDown className="h-4 w-4 text-slate-400" />
            )}
          </button>

          {showTrace && (
            <div className="mt-3 space-y-2 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
              <div className="mb-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                <span>Trace: {answer.trace.trace_id}</span>
                <span>Initiated: {new Date(answer.trace.created_at).toLocaleTimeString()}</span>
              </div>
              <ol className="space-y-2 border-l border-slate-800 pl-4 ml-2">
                {answer.trace.steps.map((step: TraceStep, idx: number) => (
                  <li key={idx} className="relative text-xs">
                    <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-cyan-400" />
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-white capitalize">{step.module}</span>
                      <span className="font-mono text-slate-400 text-[11px]">({step.action})</span>
                      {step.confidence !== null && (
                        <span className="text-[10px] text-cyan-400">
                          conf: {(step.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    {Object.keys(step.params).length > 0 && (
                      <p className="mt-0.5 text-[11px] font-mono text-slate-400">
                        params: {JSON.stringify(step.params)}
                      </p>
                    )}
                    {step.evidence_ids.length > 0 && (
                      <p className="mt-0.5 text-[10px] font-mono text-slate-500">
                        evidence_ids: {step.evidence_ids.join(', ')}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      </div>
    </article>
  );
};
