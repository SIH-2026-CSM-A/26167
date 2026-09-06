import React, { useState } from 'react';
import { ChevronRight, ChevronDown, CheckCircle, Clock, Link as LinkIcon } from 'lucide-react';
import type { TraceStep } from '@/types/contracts';
import { formatDuration } from '@/utils/evidenceGeoJson';

export interface TraceStepItemProps {
  step: TraceStep;
  index: number;
  onSelectEvidence?: (id: string) => void;
}

const StepParamsViewer: React.FC<{ params: Record<string, unknown> }> = ({ params }) => {
  const [isOpen, setIsOpen] = useState(false);
  const count = Object.keys(params).length;
  if (count === 0) return null;

  return (
    <div className="mt-2 pt-1 border-t border-slate-800/60">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span>Parameters ({count})</span>
      </button>
      {isOpen && (
        <pre className="mt-1.5 p-2 rounded bg-slate-950 font-mono text-[10px] text-slate-300 overflow-x-auto border border-slate-800/80">
          {JSON.stringify(params, null, 2)}
        </pre>
      )}
    </div>
  );
};

const StepHeaderRow: React.FC<{
  module: string;
  action: string;
  confidence: number | null;
  durationSec: number | null;
}> = ({ module, action, confidence, durationSec }) => (
  <div className="flex items-center justify-between flex-wrap gap-2">
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs font-semibold text-cyan-300">{module}</span>
      <span className="text-slate-500 text-xs">/</span>
      <span className="text-xs font-medium text-slate-200">{action}</span>
    </div>
    <div className="flex items-center gap-3 text-[11px] text-slate-400">
      {confidence !== null && (
        <span className="flex items-center gap-1 text-emerald-400 font-mono">
          <CheckCircle className="h-3 w-3" />
          {(confidence * 100).toFixed(0)}%
        </span>
      )}
      {durationSec !== null && (
        <span className="flex items-center gap-1 font-mono text-slate-400">
          <Clock className="h-3 w-3" />
          {formatDuration(durationSec)}
        </span>
      )}
    </div>
  </div>
);

export const TraceStepItem: React.FC<TraceStepItemProps> = ({ step, index, onSelectEvidence }) => {
  const durationSec = step.completed_at
    ? (new Date(step.completed_at).getTime() - new Date(step.started_at).getTime()) / 1000
    : null;

  return (
    <div className="relative pl-6 pb-4 border-l border-slate-800 last:border-l-0 last:pb-0">
      <div className="absolute -left-2 top-0 flex h-4 w-4 items-center justify-center rounded-full bg-slate-900 border border-cyan-500/60 text-cyan-400 text-[10px]">
        {index + 1}
      </div>

      <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-2.5 hover:border-slate-700 transition-colors">
        <StepHeaderRow
          module={step.module}
          action={step.action}
          confidence={step.confidence}
          durationSec={durationSec}
        />

        {step.evidence_ids.length > 0 && (
          <div className="mt-2 flex items-center gap-1.5 flex-wrap">
            <span className="flex items-center gap-1 text-[11px] text-slate-500">
              <LinkIcon className="h-3 w-3" />
              Evidence:
            </span>
            {step.evidence_ids.map((id) => (
              <button
                key={id}
                onClick={() => onSelectEvidence?.(id)}
                className="rounded bg-cyan-950/80 border border-cyan-500/30 px-1.5 py-0.5 font-mono text-[10px] text-cyan-300 hover:bg-cyan-900/60 hover:border-cyan-400 transition-colors"
                title={`Highlight evidence ${id} on map`}
              >
                [{id}]
              </button>
            ))}
          </div>
        )}

        <StepParamsViewer params={step.params} />
      </div>
    </div>
  );
};

export default TraceStepItem;
