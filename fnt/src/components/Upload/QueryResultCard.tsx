import React, { useState } from 'react';
import type { Answer } from '../../types/contracts';

interface QueryResultCardProps {
  answer: Answer;
}

export const QueryResultCard: React.FC<QueryResultCardProps> = ({ answer }) => {
  const [showTrace, setShowTrace] = useState<boolean>(false);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/90 p-5 flex flex-col gap-4 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="font-semibold text-sm text-slate-100">Pipeline Result</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Confidence:</span>
          <span
            className={`font-mono text-xs px-2 py-0.5 rounded font-bold ${
              answer.confidence >= 0.75
                ? 'bg-emerald-950 border border-emerald-800 text-emerald-300'
                : 'bg-amber-950 border border-amber-800 text-amber-300'
            }`}
          >
            {(answer.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {answer.abstained && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-md text-amber-300 text-xs">
          <strong>Pipeline Abstained:</strong> {answer.abstention_reason || 'Confidence threshold unmet.'}
        </div>
      )}

      <div>
        <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Answer</label>
        <p className="mt-1 text-sm text-slate-200 leading-relaxed font-sans">{answer.text}</p>
      </div>

      {answer.evidence && answer.evidence.length > 0 && (
        <div>
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Grounded Evidence ({answer.evidence.length})
          </label>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {answer.evidence.map((ev, i) => {
              const desc =
                ev.payload && typeof ev.payload === 'object' && 'description' in ev.payload
                  ? String((ev.payload as Record<string, unknown>).description)
                  : JSON.stringify(ev.payload);
              return (
                <div key={ev.id || i} className="p-2 rounded bg-slate-950/60 border border-slate-800 text-xs text-slate-300">
                  <span className="font-mono text-cyan-400 mr-2">[{ev.type.toUpperCase()}]</span>
                  <span className="text-slate-400 mr-2">({ev.tool})</span>
                  <span>{desc}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {answer.trace?.steps && answer.trace.steps.length > 0 && (
        <div className="border-t border-slate-800 pt-3">
          <button
            type="button"
            onClick={() => setShowTrace(!showTrace)}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 cursor-pointer"
          >
            <span>{showTrace ? '? Hide' : '? Show'} Execution Trace</span>
            <span className="text-slate-500">({answer.trace.steps.length} steps)</span>
          </button>
          {showTrace && (
            <div className="mt-2.5 flex flex-col gap-1 font-mono text-[11px] bg-slate-950 p-3 rounded border border-slate-800">
              {answer.trace.steps.map((step, idx) => (
                <div key={idx} className="flex flex-col gap-0.5 text-slate-400 py-1 border-b border-slate-800/50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-600">{idx + 1}.</span>
                    <span className="text-cyan-400 font-semibold">{step.module}</span>
                    <span className="text-slate-500">?</span>
                    <span className="text-amber-300">{step.action}</span>
                    {step.confidence !== null && (
                      <span className="text-emerald-400 text-[10px]">({Math.round(step.confidence * 100)}%)</span>
                    )}
                  </div>
                  {step.params && Object.keys(step.params).length > 0 && (
                    <div className="text-slate-500 text-[10px] pl-4 truncate">
                      {JSON.stringify(step.params)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
