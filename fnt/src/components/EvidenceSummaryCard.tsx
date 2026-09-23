import React from 'react';
import { MapPin } from 'lucide-react';
import type { BBoxPayload, Evidence, LayerPayload, MaskPayload, StatsPayload } from '@/types/contracts';

export interface EvidenceSummaryCardProps {
  evidence: Evidence;
  /** Present only when this evidence can be located on a map (bbox/mask/layer with real
   * geometry) — omit to hide the "View on map" action entirely. */
  onViewOnMap?: (id: string) => void;
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

function readString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === 'string' && value.length > 0 ? value : null;
}

/** Plain-language grounding line — what a human needs, not the JSON blob it's derived from. */
function GroundingSummary({ evidence }: { evidence: Evidence }): React.ReactElement | null {
  const payload = evidence.payload as Record<string, unknown>;

  if (evidence.type === 'text') {
    const filename = readString(payload, 'source_filename');
    const modelId = readString(payload, 'model_id');
    if (!filename && !modelId) return null;
    return (
      <p className="text-xs" style={{ color: 'var(--text-mid)' }}>
        {filename ? (
          <>
            Grounded to <span style={{ color: 'var(--accent)' }}>{filename}</span>
          </>
        ) : (
          'Grounded evidence'
        )}
        {modelId && <span style={{ color: 'var(--text-low)' }}> · {modelId}</span>}
      </p>
    );
  }

  if (evidence.type === 'bbox') {
    const bboxPayload = payload as BBoxPayload;
    return (
      <p className="text-xs" style={{ color: 'var(--text-mid)' }}>
        {bboxPayload.label ?? 'Bounding region'}
        {bboxPayload.description && (
          <span style={{ color: 'var(--text-low)' }}> — {bboxPayload.description}</span>
        )}
      </p>
    );
  }

  if (evidence.type === 'mask' || evidence.type === 'layer') {
    const label = readString(payload, 'label');
    return (
      <p className="text-xs" style={{ color: 'var(--text-mid)' }}>
        {label ?? `Spatial ${evidence.type} layer`}
      </p>
    );
  }

  if (evidence.type === 'stats') {
    const stats = payload as StatsPayload;
    const metricEntries = stats.metrics ? Object.entries(stats.metrics) : [];
    if (metricEntries.length === 0) return null;
    return (
      <p className="text-xs" style={{ color: 'var(--text-mid)' }}>
        {metricEntries.map(([k, v]) => `${k}: ${v}`).join(' · ')}
      </p>
    );
  }

  return null;
}

function hasMapGeometry(evidence: Evidence): boolean {
  if (evidence.type === 'bbox') return Array.isArray((evidence.payload as BBoxPayload).bbox);
  if (evidence.type === 'mask') return Boolean((evidence.payload as MaskPayload).geojson ?? (evidence.payload as MaskPayload).bounds);
  if (evidence.type === 'layer') return Boolean((evidence.payload as LayerPayload).bounds);
  return false;
}

export const EvidenceSummaryCard: React.FC<EvidenceSummaryCardProps> = ({ evidence, onViewOnMap }) => (
  <div className="rounded-lg p-3 text-xs" style={{ background: 'var(--bg-2)', border: '1px solid var(--line)' }}>
    <div className="flex flex-wrap items-center gap-2">
      <span
        className="rounded px-1.5 py-0.5 text-[10px] uppercase"
        style={{ background: 'var(--bg-1)', border: '1px solid var(--line)', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
      >
        {evidence.type}
      </span>
      <span style={{ color: 'var(--text-low)' }}>{evidence.tool}</span>
      <span className="ml-auto" style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}>
        {(evidence.confidence * 100).toFixed(0)}%
      </span>
    </div>

    <div className="mt-1.5">
      <GroundingSummary evidence={evidence} />
    </div>

    {onViewOnMap && hasMapGeometry(evidence) && (
      <button
        type="button"
        onClick={() => onViewOnMap(evidence.id)}
        className="mt-2 flex items-center gap-1 text-[11px] font-medium"
        style={{ color: 'var(--accent)' }}
      >
        <MapPin className="h-3 w-3" />
        View on map
      </button>
    )}

    <details className="mt-2">
      <summary className="cursor-pointer text-[11px]" style={{ color: 'var(--text-low)' }}>
        Raw evidence data
      </summary>
      <pre
        className="mt-1.5 overflow-x-auto rounded p-2 text-[10px] leading-relaxed"
        style={{ background: 'var(--bg-1)', border: '1px solid var(--line)', color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
      >
        {truncatedPayloadJson(evidence.payload)}
      </pre>
    </details>
  </div>
);

export default EvidenceSummaryCard;
