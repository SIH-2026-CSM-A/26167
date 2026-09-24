import React, { useEffect, useState } from 'react';
import { getHistory } from '@/services/history';
import { ConfidenceBadge } from '@/components/Chat/ConfidenceBadge';
import { useSatQuery } from '@/hooks/useSatQuery';
import type { Answer, QueryHistoryItem } from '@/types/contracts';

export interface HistoryPanelProps {
  /** Re-fetches whenever this value changes — pass the latest completed Answer reference. */
  refreshKey?: unknown;
}

function formatModality(modality: string): string {
  if (modality === 'fusion') return 'Fusion';
  if (modality === 'sar') return 'SAR';
  if (modality === 'optical') return 'Optical';
  return modality;
}

/** A history row only ever persisted query_text/answer_text/confidence/modality (see
 * app/contracts/history.py) — evidence and trace were never stored, so a replayed turn
 * renders with none rather than inventing data that was never fetched. */
function historyItemToAnswer(item: QueryHistoryItem): Answer {
  return {
    text: item.answer_text,
    evidence: [],
    trace: { trace_id: `history-${item.id}`, steps: [], created_at: item.created_at },
    confidence: item.confidence,
    abstained: false,
    abstention_reason: null,
  };
}

export const HistoryPanel: React.FC<HistoryPanelProps> = ({ refreshKey }) => {
  const [items, setItems] = useState<QueryHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { loadAnswer } = useSatQuery();

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getHistory()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load history.');
          setItems([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="flex flex-col">
      <div
        className="px-4 pb-2 pt-4 text-[10px] font-medium uppercase tracking-widest"
        style={{ color: 'var(--text-low)' }}
      >
        History
      </div>

      {items === null && (
        <div className="px-4 py-3 text-xs" style={{ color: 'var(--text-low)' }}>
          Loading history…
        </div>
      )}

      {error && (
        <div className="px-4 py-3 text-xs" style={{ color: 'var(--danger)' }}>
          {error}
        </div>
      )}

      {items !== null && items.length === 0 && !error && (
        <div className="px-4 py-3 text-xs" style={{ color: 'var(--text-low)' }}>
          No queries yet.
        </div>
      )}

      {items !== null &&
        items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => loadAnswer(historyItemToAnswer(item), item.query_text)}
            className="w-full px-4 py-2.5 text-left text-[12.5px] transition-colors hover:opacity-80"
            style={{ borderBottom: '1px solid var(--line-soft)', color: 'var(--text-mid)' }}
            title="View this past turn"
          >
            <div className="line-clamp-2">{item.query_text}</div>
            <div
              className="mt-1 flex items-center gap-2 text-[10.5px]"
              style={{ color: 'var(--text-low)' }}
            >
              <span>{formatModality(item.modality)}</span>
              <ConfidenceBadge confidence={item.confidence} className="text-[10px] py-0.5 px-2" />
            </div>
          </button>
        ))}
    </div>
  );
};

export default HistoryPanel;
