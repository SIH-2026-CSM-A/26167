import React, { useEffect, useState } from 'react';
import { getHistory } from '@/services/history';
import { ConfidenceBadge } from '@/components/Chat/ConfidenceBadge';
import type { QueryHistoryItem } from '@/types/contracts';

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

export const HistoryPanel: React.FC<HistoryPanelProps> = ({ refreshKey }) => {
  const [items, setItems] = useState<QueryHistoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
          <div
            key={item.id}
            className="px-4 py-2.5 text-[12.5px]"
            style={{ borderBottom: '1px solid var(--line-soft)', color: 'var(--text-mid)' }}
          >
            <div className="line-clamp-2">{item.query_text}</div>
            <div
              className="mt-1 flex items-center gap-2 text-[10.5px]"
              style={{ color: 'var(--text-low)' }}
            >
              <span>{formatModality(item.modality)}</span>
              <ConfidenceBadge confidence={item.confidence} className="text-[10px] py-0.5 px-2" />
            </div>
          </div>
        ))}
    </div>
  );
};

export default HistoryPanel;
