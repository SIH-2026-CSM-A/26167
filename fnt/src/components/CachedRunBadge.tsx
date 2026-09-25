import React from 'react';
import type { CachedRunInfo } from '@/types/contracts';

interface CachedRunBadgeProps {
  cachedRun: CachedRunInfo;
  onRunLive?: () => void;
}

const FALLBACK_REASONS: Record<string, string> = {
  INFERENCE_UNAVAILABLE: 'the live model service was unavailable',
  INFERENCE_QUOTA: 'the live model service is over its GPU quota',
};

/** Visible marker that an answer is a replay of a recorded real run, not computed just now. */
export const CachedRunBadge: React.FC<CachedRunBadgeProps> = ({ cachedRun, onRunLive }) => {
  const recorded = new Date(cachedRun.recorded_at);
  const recordedLabel = Number.isNaN(recorded.getTime())
    ? cachedRun.recorded_at
    : recorded.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  const fallback = FALLBACK_REASONS[cachedRun.reason];

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-2 rounded-lg px-3 py-2 text-xs"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--thermal)', color: 'var(--text-mid)' }}
    >
      <span
        className="rounded px-1.5 py-0.5 font-semibold uppercase tracking-wider"
        style={{ border: '1px solid var(--thermal)', color: '#e3a66c', fontFamily: 'var(--font-mono)' }}
      >
        Cached demo run
      </span>
      <span>Recorded {recordedLabel}</span>
      {fallback && <span>· shown because {fallback}</span>}
      {cachedRun.identity_mismatch && (
        <span style={{ color: 'var(--danger)' }}>· recorded with different model weights than the current ones</span>
      )}
      {onRunLive && (
        <button
          type="button"
          onClick={onRunLive}
          className="ml-auto rounded px-2.5 py-1 font-medium"
          style={{ background: 'var(--accent)', color: 'var(--bg-0)' }}
        >
          Run live
        </button>
      )}
    </div>
  );
};
