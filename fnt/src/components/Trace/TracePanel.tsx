import React, { useState } from 'react';
import type { Answer } from '@/types/contracts';
import { TraceStepItem } from './TraceStepItem';
import { downloadEvidencePdf } from '@/services/api';

export interface TracePanelProps {
  answer: Answer | null;
  onSelectEvidence?: (id: string) => void;
  /** console-v2: the PDF action lives inline under the relevant chat turn instead;
   * the rail's copy of this panel hides its own button to avoid a duplicate CTA. */
  showDownload?: boolean;
}

export const TracePanel: React.FC<TracePanelProps> = ({ answer, onSelectEvidence, showDownload = true }) => {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    if (!answer || isDownloading) return;
    setIsDownloading(true);
    try {
      await downloadEvidencePdf(answer);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div
        className="px-4 pb-2 pt-4 text-[10px] font-medium uppercase tracking-widest"
        style={{ color: 'var(--text-low)' }}
      >
        Agent trace
      </div>

      <div className="flex-1 overflow-y-auto px-4">
        {answer === null ? (
          <p className="text-xs" style={{ color: 'var(--text-low)' }}>
            Run a query to see the execution trace here.
          </p>
        ) : (
          <div className="space-y-1">
            {answer.trace.steps.map((step, idx) => (
              <TraceStepItem
                key={`${step.module}-${idx}`}
                step={step}
                index={idx}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        )}
      </div>

      {showDownload && (
        <button
          type="button"
          onClick={() => {
            void handleDownload();
          }}
          disabled={answer === null || isDownloading}
          className="m-4 rounded-lg py-2.5 text-center text-[12.5px] font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            background: 'var(--accent-dim)',
            border: '1px solid var(--accent)',
            color: 'var(--accent)',
          }}
        >
          {isDownloading ? 'Generating PDF…' : 'Download evidence-backed PDF report'}
        </button>
      )}
    </div>
  );
};

export default TracePanel;
