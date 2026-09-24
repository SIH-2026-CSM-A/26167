import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Answer, ExecutionTrace } from '../../types/contracts';
import { downloadEvidenceGeoJson, downloadEvidencePdf } from '../../services/api';
import { EvidenceSummaryCard } from '@/components/EvidenceSummaryCard';
import { TraceStepItem } from '@/components/Trace/TraceStepItem';
import { useSatQuery } from '@/hooks/useSatQuery';

interface QueryResultCardProps {
  answer: Answer;
}

/** Show/Hide list of TraceStepItems, shared by the result card and the Upload page's veto alert. */
export const ExecutionTraceToggle: React.FC<{ trace: ExecutionTrace }> = ({ trace }) => {
  const [showTrace, setShowTrace] = useState<boolean>(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setShowTrace(!showTrace)}
        className="flex cursor-pointer items-center gap-1 text-xs"
        style={{ color: 'var(--accent)' }}
      >
        <span>{showTrace ? 'Hide' : 'Show'} Execution Trace</span>
        <span style={{ color: 'var(--text-low)' }}>({trace.steps.length} steps)</span>
      </button>
      {showTrace && (
        <div className="mt-2.5 flex flex-col gap-1">
          {trace.steps.map((step, idx) => (
            <TraceStepItem key={`${step.module}-${idx}`} step={step} index={idx} />
          ))}
        </div>
      )}
    </>
  );
};

export const QueryResultCard: React.FC<QueryResultCardProps> = ({ answer }) => {
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);
  const [downloadingGeoJson, setDownloadingGeoJson] = useState<boolean>(false);
  const { loadAnswer } = useSatQuery();
  const navigate = useNavigate();

  const handleDownloadPdf = async () => {
    try {
      setDownloadingPdf(true);
      await downloadEvidencePdf(answer);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleDownloadGeoJson = async () => {
    try {
      setDownloadingGeoJson(true);
      await downloadEvidenceGeoJson(answer);
    } catch (err) {
      console.error('GeoJSON export failed:', err);
    } finally {
      setDownloadingGeoJson(false);
    }
  };

  // Upload has no map panel of its own — "View on map" hands this result to the shared
  // chat/query context and opens Chat, whose map hero already fits to all of its bounds.
  const handleViewOnMap = () => {
    loadAnswer(answer);
    navigate('/chat');
  };

  return (
    <div
      className="flex flex-col gap-4 rounded-lg p-5 shadow-lg"
      style={{ background: 'var(--bg-1)', border: '1px solid var(--line)' }}
    >
      <div className="flex items-center justify-between pb-3" style={{ borderBottom: '1px solid var(--line)' }}>
        <h3 className="text-sm" style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }}>
          Pipeline Result
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-low)' }}>Confidence:</span>
          <span
            className="rounded px-2 py-0.5 text-xs font-bold"
            style={
              answer.confidence >= 0.75
                ? { background: 'var(--success-dim)', border: '1px solid var(--success)', color: 'var(--success)' }
                : { background: 'rgba(199,123,58,0.16)', border: '1px solid var(--thermal)', color: '#e3a66c' }
            }
          >
            {(answer.confidence * 100).toFixed(0)}%
          </span>
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="ml-2 rounded px-2.5 py-1 text-xs font-medium transition disabled:opacity-50"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-mid)' }}
          >
            {downloadingPdf ? 'Exporting...' : 'PDF Report'}
          </button>
          <button
            type="button"
            onClick={handleDownloadGeoJson}
            disabled={downloadingGeoJson}
            className="rounded px-2.5 py-1 text-xs font-medium transition disabled:opacity-50"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-mid)' }}
          >
            {downloadingGeoJson ? 'Exporting...' : 'Export GeoJSON'}
          </button>
        </div>
      </div>

      {answer.abstained && (
        <div
          className="rounded-md p-3 text-xs"
          style={{ background: 'rgba(199,123,58,0.16)', border: '1px solid var(--thermal)', color: '#e3a66c' }}
        >
          <strong>Pipeline Abstained:</strong> {answer.abstention_reason || 'Confidence threshold unmet.'}
        </div>
      )}

      <div>
        <label
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          Answer
        </label>
        <p className="mt-1 text-sm leading-relaxed" style={{ color: 'var(--text-hi)' }}>{answer.text}</p>
      </div>

      {answer.evidence && answer.evidence.length > 0 && (
        <div>
          <label
            className="text-[11px] font-medium uppercase tracking-widest"
            style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
          >
            Grounded Evidence ({answer.evidence.length})
          </label>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {answer.evidence.map((ev) => (
              <EvidenceSummaryCard key={ev.id} evidence={ev} onViewOnMap={handleViewOnMap} />
            ))}
          </div>
        </div>
      )}

      {answer.trace?.steps && answer.trace.steps.length > 0 && (
        <div className="pt-3" style={{ borderTop: '1px solid var(--line)' }}>
          <ExecutionTraceToggle trace={answer.trace} />
        </div>
      )}
    </div>
  );
};
