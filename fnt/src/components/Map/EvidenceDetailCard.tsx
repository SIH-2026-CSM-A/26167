import React from 'react';
import { X, Layers, Clock, ShieldCheck, MapPin } from 'lucide-react';
import type { Evidence, BBoxPayload } from '@/types/contracts';
import { formatDuration } from '@/utils/evidenceGeoJson';

export interface EvidenceDetailCardProps {
  evidence: Evidence | null;
  onClose: () => void;
}

const EvidenceMetrics: React.FC<{ evidence: Evidence }> = ({ evidence }) => {
  const bboxPayload = evidence.type === 'bbox' ? (evidence.payload as BBoxPayload) : null;
  const bboxCoords = bboxPayload?.bbox ? bboxPayload.bbox.map((c) => c.toFixed(4)).join(', ') : null;

  return (
    <div className="mt-3 space-y-2 text-xs">
      <div className="flex justify-between items-center text-slate-300">
        <span className="text-slate-400">Tool:</span>
        <span className="font-mono bg-slate-800 px-2 py-0.5 rounded text-cyan-300">{evidence.tool}</span>
      </div>
      <div className="flex justify-between items-center text-slate-300">
        <span className="text-slate-400">Type:</span>
        <span className="capitalize text-slate-200">{evidence.type}</span>
      </div>
      <div className="flex justify-between items-center text-slate-300">
        <span className="text-slate-400">Confidence:</span>
        <span className="flex items-center gap-1 font-semibold text-emerald-400">
          <ShieldCheck className="h-3.5 w-3.5" />
          {(evidence.confidence * 100).toFixed(1)}%
        </span>
      </div>
      <div className="flex justify-between items-center text-slate-300">
        <span className="text-slate-400">Timing:</span>
        <span className="flex items-center gap-1 font-mono text-slate-300">
          <Clock className="h-3 w-3 text-slate-400" />
          {formatDuration(evidence.timing)}
        </span>
      </div>
      {bboxCoords && (
        <div className="pt-2 border-t border-slate-800/80">
          <div className="flex items-center gap-1 text-slate-400 mb-1">
            <MapPin className="h-3 w-3 text-cyan-400" />
            <span>Bounding Coordinates (WGS84):</span>
          </div>
          <div className="font-mono text-[11px] bg-slate-950/80 p-1.5 rounded text-cyan-200 break-all">
            [{bboxCoords}]
          </div>
        </div>
      )}
    </div>
  );
};

export const EvidenceDetailCard: React.FC<EvidenceDetailCardProps> = ({ evidence, onClose }) => {
  if (!evidence) return null;

  return (
    <div className="absolute top-4 left-4 z-10 w-80 rounded-xl border border-cyan-500/40 bg-slate-900/95 p-4 shadow-2xl shadow-cyan-950/60 backdrop-blur-md">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded bg-cyan-500/20 text-cyan-400">
            <Layers className="h-3.5 w-3.5" />
          </span>
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-cyan-400">
            Evidence [{evidence.id}]
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          title="Close details"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <EvidenceMetrics evidence={evidence} />
    </div>
  );
};

export default EvidenceDetailCard;
