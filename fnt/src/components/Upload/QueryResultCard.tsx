import React, { useState } from 'react';
import type { Answer, Evidence, ExecutionTrace } from '../../types/contracts';
import { downloadEvidenceGeoJson, downloadEvidencePdf } from '../../services/api';

interface QueryResultCardProps {
  answer: Answer;
}

const RAW_ARRAY_PREVIEW_ITEMS = 8;
const RAW_TEXT_MAX_CHARS = 2000;

/** Evidence payloads can carry full-resolution rasters (e.g. 512x512 masks); never print them. */
function truncatedPayloadJson(payload: unknown): string {
  const json = JSON.stringify(
    payload,
    (_key, value: unknown) =>
      Array.isArray(value) && value.length > RAW_ARRAY_PREVIEW_ITEMS
        ? `[array of ${value.length} items omitted]`
        : value,
    2
  );
  return json.length > RAW_TEXT_MAX_CHARS ? `${json.slice(0, RAW_TEXT_MAX_CHARS)}\n… (truncated)` : json;
}

function readNumber(payload: Record<string, unknown>, key: string): number | null {
  const value = payload[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function readText(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

/** Coverage as a percentage: fusion reports a 0-1 water fraction, change detection a percent. */
function coverageLabel(payload: Record<string, unknown>): string | null {
  const waterFraction = readNumber(payload, 'water_fraction');
  if (waterFraction !== null) return `water ${(waterFraction * 100).toFixed(1)}%`;
  const changedPercentage = readNumber(payload, 'changed_percentage');
  if (changedPercentage !== null) return `changed ${changedPercentage.toFixed(1)}%`;
  return null;
}

const EvidenceSummary: React.FC<{ evidence: Evidence }> = ({ evidence }) => {
  const payload =
    evidence.payload && typeof evidence.payload === 'object'
      ? (evidence.payload as Record<string, unknown>)
      : {};
  const description = readText(payload, 'description') ?? readText(payload, 'note');
  const region = readText(payload, 'region') ?? readText(payload, 'relative_position');
  const coverage = coverageLabel(payload);

  return (
    <div className="p-2 rounded bg-slate-950/60 border border-slate-800 text-xs text-slate-300">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-cyan-400">[{evidence.type.toUpperCase()}]</span>
        <span className="text-slate-400">({evidence.tool})</span>
        {coverage && <span className="font-mono text-slate-300">{coverage}</span>}
        {region && (
          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
            {region}
          </span>
        )}
        <span className="ml-auto font-mono text-slate-400">
          {(evidence.confidence * 100).toFixed(0)}%
        </span>
      </div>
      {description && <p className="mt-1">{description}</p>}
      <details className="mt-1.5">
        <summary className="cursor-pointer text-[11px] text-slate-500">Raw evidence data</summary>
        <pre className="mt-1.5 max-h-64 overflow-auto rounded bg-slate-950 border border-slate-800 p-2 text-[10px] leading-relaxed text-slate-500 font-mono">
          {truncatedPayloadJson(evidence.payload)}
        </pre>
      </details>
    </div>
  );
};

/** Collapsible execution trace, shared by the result card and the Upload page's veto alert. */
export const ExecutionTraceToggle: React.FC<{ trace: ExecutionTrace }> = ({ trace }) => {
  const [showTrace, setShowTrace] = useState<boolean>(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setShowTrace(!showTrace)}
        className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 cursor-pointer"
      >
        <span>{showTrace ? 'Hide' : 'Show'} Execution Trace</span>
        <span className="text-slate-500">({trace.steps.length} steps)</span>
      </button>
      {showTrace && (
        <div className="mt-2.5 flex flex-col gap-1 font-mono text-[11px] bg-slate-950 p-3 rounded border border-slate-800">
          {trace.steps.map((step, idx) => (
            <div key={idx} className="flex flex-col gap-0.5 text-slate-400 py-1 border-b border-slate-800/50 last:border-0">
              <div className="flex items-center gap-2">
                <span className="text-slate-600">{idx + 1}.</span>
                <span className="text-cyan-400 font-semibold">{step.module}</span>
                <span className="text-slate-500">→</span>
                <span className="text-amber-300">{step.action}</span>
                {step.confidence !== null && (
                  <span className="text-emerald-400 text-[10px]">({Math.round(step.confidence * 100)}%)</span>
                )}
              </div>
              {step.params && Object.keys(step.params).length > 0 && (
                <div className="text-slate-500 text-[10px] pl-4 truncate">
                  {JSON.stringify(step.params)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
};

export const QueryResultCard: React.FC<QueryResultCardProps> = ({ answer }) => {
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
    <div className="rounded-lg border border-slate-800 bg-slate-900/90 p-5 flex flex-col gap-4 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h3 className="font-semibold text-sm text-slate-100">Pipeline Result</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Confidence:</span>
          <span
            className={`font-mono text-xs px-2 py-0.5 rounded font-bold ${
              answer.confidence >= 0.75
                ? 'bg-emerald-950 border border-emerald-800 text-emerald-300'
                : 'bg-amber-950 border border-amber-800 text-amber-300'
            }`}
          >
            {(answer.confidence * 100).toFixed(0)}%
          </span>
          <button
            type="button"
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
            className="ml-2 rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
          >
            {downloadingPdf ? 'Exporting...' : 'PDF Report'}
          </button>
          <button
            type="button"
            onClick={handleDownloadGeoJson}
            disabled={downloadingGeoJson}
            className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
          >
            {downloadingGeoJson ? 'Exporting...' : 'Export GeoJSON'}
          </button>
        </div>
      </div>

      {answer.abstained && (
        <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-md text-amber-300 text-xs">
          <strong>Pipeline Abstained:</strong> {answer.abstention_reason || 'Confidence threshold unmet.'}
        </div>
      )}

      <div>
        <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Answer</label>
        <p className="mt-1 text-sm text-slate-200 leading-relaxed font-sans">{answer.text}</p>
      </div>

      {answer.evidence && answer.evidence.length > 0 && (
        <div>
          <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Grounded Evidence ({answer.evidence.length})
          </label>
          <div className="mt-1.5 flex flex-col gap-1.5">
            {answer.evidence.map((ev, i) => (
              <EvidenceSummary key={ev.id || i} evidence={ev} />
            ))}
          </div>
        </div>
      )}

      {answer.trace?.steps && answer.trace.steps.length > 0 && (
        <div className="border-t border-slate-800 pt-3">
          <ExecutionTraceToggle trace={answer.trace} />
        </div>
      )}
    </div>
  );
};
