import React, { useState } from 'react';
import type { Answer } from '../../types/contracts';
import { downloadEvidenceGeoJson, downloadEvidencePdf } from '../../services/api';

interface QueryResultCardProps {
  answer: Answer;
}

export const QueryResultCard: React.FC<QueryResultCardProps> = ({ answer }) => {
  const [showTrace, setShowTrace] = useState<boolean>(false);
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);
  const [downloadingGeoJson, setDownloadingGeoJson] = useState<boolean>(false);

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
                ? { background: 'rgba(74,124,89,0.18)', border: '1px solid var(--ndvi)', color: '#8fc79e' }
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
            {answer.evidence.map((ev, i) => {
              const desc =
                ev.payload && typeof ev.payload === 'object' && 'description' in ev.payload
                  ? String((ev.payload as Record<string, unknown>).description)
                  : JSON.stringify(ev.payload);
              return (
                <div
                  key={ev.id || i}
                  className="rounded p-2 text-xs"
                  style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-mid)' }}
                >
                  <span className="mr-2" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                    [{ev.type.toUpperCase()}]
                  </span>
                  <span className="mr-2" style={{ color: 'var(--text-low)' }}>({ev.tool})</span>
                  <span>{desc}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {answer.trace?.steps && answer.trace.steps.length > 0 && (
        <div className="pt-3" style={{ borderTop: '1px solid var(--line)' }}>
          <button
            type="button"
            onClick={() => setShowTrace(!showTrace)}
            className="flex cursor-pointer items-center gap-1 text-xs"
            style={{ color: 'var(--accent)' }}
          >
            <span>{showTrace ? 'Hide' : 'Show'} Execution Trace</span>
            <span style={{ color: 'var(--text-low)' }}>({answer.trace.steps.length} steps)</span>
          </button>
          {showTrace && (
            <div
              className="mt-2.5 flex flex-col gap-1 rounded p-3 text-[11px]"
              style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', fontFamily: 'var(--font-mono)' }}
            >
              {answer.trace.steps.map((step, idx) => (
                <div
                  key={idx}
                  className="flex flex-col gap-0.5 py-1 last:border-0"
                  style={{ color: 'var(--text-low)', borderBottom: '1px solid var(--line-soft)' }}
                >
                  <div className="flex items-center gap-2">
                    <span>{idx + 1}.</span>
                    <span className="font-semibold" style={{ color: 'var(--accent)' }}>{step.module}</span>
                    <span>→</span>
                    <span style={{ color: '#e3a66c' }}>{step.action}</span>
                    {step.confidence !== null && (
                      <span className="text-[10px]" style={{ color: '#8fc79e' }}>
                        ({Math.round(step.confidence * 100)}%)
                      </span>
                    )}
                  </div>
                  {step.params && Object.keys(step.params).length > 0 && (
                    <div className="truncate pl-4 text-[10px]">{JSON.stringify(step.params)}</div>
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
