import React, { useState } from 'react';
import { Activity, ChevronDown, ChevronUp, Cpu } from 'lucide-react';
import type { ExecutionTrace } from '@/types/contracts';
import { formatDuration } from '@/utils/evidenceGeoJson';
import { TraceStepItem } from './TraceStepItem';

export interface ExecutionTracePanelProps {
  trace: ExecutionTrace;
  onSelectEvidence?: (id: string) => void;
}

function calculateTotalDuration(trace: ExecutionTrace): number {
  let total = 0;
  for (const s of trace.steps) {
    if (s.completed_at && s.started_at) {
      total += (new Date(s.completed_at).getTime() - new Date(s.started_at).getTime()) / 1000;
    }
  }
  return total;
}

const TraceHeaderButton: React.FC<{
  trace: ExecutionTrace;
  isExpanded: boolean;
  totalSec: number;
  onToggle: () => void;
}> = ({ trace, isExpanded, totalSec, onToggle }) => (
  <button
    onClick={onToggle}
    className="w-full flex items-center justify-between p-3 bg-slate-900/60 hover:bg-slate-900/90 transition-colors text-left"
  >
    <div className="flex items-center gap-2">
      <Activity className="h-4 w-4 text-cyan-400" />
      <span className="font-semibold text-slate-200">Execution Trace</span>
      <span className="font-mono text-[11px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
        {trace.trace_id}
      </span>
    </div>

    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 text-slate-400 font-mono text-[11px]">
        <Cpu className="h-3.5 w-3.5 text-slate-500" />
        <span>{trace.steps.length} stages</span>
        {totalSec > 0 && <span>· {formatDuration(totalSec)}</span>}
      </div>
      {isExpanded ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
    </div>
  </button>
);

export const ExecutionTracePanel: React.FC<ExecutionTracePanelProps> = ({
  trace,
  onSelectEvidence,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const totalSec = calculateTotalDuration(trace);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 overflow-hidden text-xs">
      <TraceHeaderButton
        trace={trace}
        isExpanded={isExpanded}
        totalSec={totalSec}
        onToggle={() => setIsExpanded(!isExpanded)}
      />

      {isExpanded && (
        <div className="p-4 border-t border-slate-800/80 bg-slate-950/40">
          <div className="mb-3 text-[11px] text-slate-500 font-mono">
            Pipeline trace logged at: {new Date(trace.created_at).toLocaleTimeString()}
          </div>
          <div className="space-y-1">
            {trace.steps.map((step, idx) => (
              <TraceStepItem
                key={`${step.module}-${idx}`}
                step={step}
                index={idx}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutionTracePanel;
