import React from 'react';
import { ShieldCheck, AlertTriangle } from 'lucide-react';

export interface ConfidenceBadgeProps {
  confidence: number;
  abstained?: boolean;
  abstentionReason?: string | null;
  className?: string;
}

export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
  confidence,
  abstained = false,
  abstentionReason,
  className = '',
}) => {
  if (abstained) {
    return (
      <div
        className={`inline-flex items-center gap-1.5 rounded-full border border-rose-500/40 bg-rose-950/40 px-2.5 py-1 text-xs font-medium text-rose-300 ${className}`}
        title={abstentionReason ?? 'Pipeline abstained due to insufficient evidence'}
      >
        <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
        <span>Abstained</span>
        {abstentionReason && (
          <span className="max-w-[200px] truncate text-[11px] text-rose-400/80">
            · {abstentionReason}
          </span>
        )}
      </div>
    );
  }

  const percent = Math.round(confidence * 100);
  const colorClass =
    percent >= 80
      ? 'border-emerald-500/40 bg-emerald-950/40 text-emerald-300'
      : percent >= 50
      ? 'border-amber-500/40 bg-amber-950/40 text-amber-300'
      : 'border-rose-500/40 bg-rose-950/40 text-rose-300';

  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${colorClass} ${className}`}
    >
      <ShieldCheck className="h-3.5 w-3.5" />
      <span>Confidence: {percent}%</span>
    </div>
  );
};

export default ConfidenceBadge;
