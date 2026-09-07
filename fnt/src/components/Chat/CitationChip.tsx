import React from 'react';
import { Layers, CheckCircle2 } from 'lucide-react';
import type { Evidence } from '@/types/contracts';

export interface CitationChipProps {
  evidenceId: string;
  evidence?: Evidence;
  isSelected?: boolean;
  isHovered?: boolean;
  onClick: (id: string) => void;
  onHover?: (id: string | null) => void;
}

export const CitationChip: React.FC<CitationChipProps> = ({
  evidenceId,
  evidence,
  isSelected = false,
  isHovered = false,
  onClick,
  onHover,
}) => {
  const confidencePercent = evidence ? Math.round(evidence.confidence * 100) : null;
  const toolName = evidence?.tool ?? 'evidence';

  return (
    <button
      type="button"
      onClick={() => onClick(evidenceId)}
      onMouseEnter={() => onHover?.(evidenceId)}
      onMouseLeave={() => onHover?.(null)}
      onFocus={() => onHover?.(evidenceId)}
      onBlur={() => onHover?.(null)}
      data-testid={`citation-chip-${evidenceId}`}
      className={`inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-full font-mono text-xs transition-all ${
        isHovered
          ? 'bg-amber-500 text-slate-950 font-semibold shadow-md shadow-amber-500/40 ring-2 ring-amber-300'
          : isSelected
          ? 'bg-cyan-500 text-slate-950 font-bold shadow-md shadow-cyan-500/40 ring-2 ring-cyan-300'
          : 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-900/80 hover:border-cyan-400'
      }`}
      title={
        evidence
          ? `Grounded by ${toolName} (${confidencePercent}%) - Click to view on map`
          : `Evidence [${evidenceId}] - Click to view on map`
      }
    >
      <Layers className="h-3 w-3" />
      <span>[{evidenceId}]</span>
      {confidencePercent !== null && (
        <span className="flex items-center text-[10px] opacity-90">
          <CheckCircle2 className="h-2.5 w-2.5 mr-0.5" />
          {confidencePercent}%
        </span>
      )}
    </button>
  );
};

export default CitationChip;
