import React from 'react';
import { Layers, AlertCircle, HelpCircle, CheckCircle2 } from 'lucide-react';
import type { InputConfiguration } from '@/services/types';

export interface UploadSidebarProps {
  config: InputConfiguration;
}

export const UploadSidebar: React.FC<UploadSidebarProps> = ({ config }) => {
  return (
    <aside className="space-y-5">
      {/* Active Modality Info */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-white">
          <Layers className="h-4 w-4 text-cyan-400" />
          <span>Modalities Supported</span>
        </div>
        <ul className="mt-4 space-y-2.5 text-xs text-slate-300">
          <li
            className={`flex items-center justify-between p-2 rounded-lg border transition-colors ${
              config === 'single'
                ? 'border-cyan-500/40 bg-cyan-950/20'
                : 'border-slate-800/80 bg-slate-950/30'
            }`}
          >
            <div className="flex items-center gap-2">
              {config === 'single' && (
                <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
              )}
              <span>Single Image Analysis</span>
            </div>
            <span className="font-mono text-cyan-400">Optical / SAR</span>
          </li>
          <li
            className={`flex items-center justify-between p-2 rounded-lg border transition-colors ${
              config === 'cross-modal'
                ? 'border-cyan-500/40 bg-cyan-950/20'
                : 'border-slate-800/80 bg-slate-950/30'
            }`}
          >
            <div className="flex items-center gap-2">
              {config === 'cross-modal' && (
                <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
              )}
              <span>Cross-Modal Pair</span>
            </div>
            <span className="font-mono text-cyan-400">Optical + SAR</span>
          </li>
          <li
            className={`flex items-center justify-between p-2 rounded-lg border transition-colors ${
              config === 'bi-temporal'
                ? 'border-cyan-500/40 bg-cyan-950/20'
                : 'border-slate-800/80 bg-slate-950/30'
            }`}
          >
            <div className="flex items-center gap-2">
              {config === 'bi-temporal' && (
                <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
              )}
              <span>Bi-Temporal Pair</span>
            </div>
            <span className="font-mono text-cyan-400">T1 / T2</span>
          </li>
        </ul>
      </div>

      {/* Problem Statement Ingestion File Format Rules */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-amber-300">
          <AlertCircle className="h-4 w-4 text-amber-400" />
          <span>Ingestion Format Rules</span>
        </div>
        <div className="mt-3 space-y-2 text-xs text-slate-400 leading-relaxed">
          <p>
            <span className="font-semibold text-slate-200">Geospatial Imagery:</span> Accepted
            as GeoTIFF / TIFF (<span className="font-mono text-cyan-400">.tif, .tiff</span>)
            preserving coordinate reference systems (CRS) and geospatial bounds.
          </p>
          <p>
            <span className="font-semibold text-slate-200">Public Benchmarks:</span> Accepted
            as PNG / JPEG (<span className="font-mono text-cyan-400">.png, .jpg, .jpeg</span>)
            only for prescribed public benchmark datasets (BigEarthNet.txt, VRSBench).
          </p>
        </div>
      </div>

      {/* Pipeline Trace & Verification Notice */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-300">
          <HelpCircle className="h-4 w-4 text-cyan-400" />
          <span>Backend Pipeline Details</span>
        </div>
        <p className="mt-2 text-xs text-slate-400 leading-relaxed">
          Submissions stream to <span className="font-mono text-slate-300">POST /query</span>.
          The pipeline executes in order:{' '}
          <span className="font-mono text-cyan-400">
            Ingestion → Router → Model Tools → Verification → Evidence
          </span>
          . Unsupported numeric/spatial claims are stripped with explicit abstention per F15/F16.
        </p>
      </div>
    </aside>
  );
};
