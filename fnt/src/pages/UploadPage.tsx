import React from 'react';
import { UploadCloud, Layers, AlertCircle } from 'lucide-react';

export const UploadPage: React.FC = () => {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Remote Sensing Data Ingestion
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload single, bi-temporal, or cross-modal (optical + SAR) satellite imagery.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center hover:border-cyan-500/50 transition-colors">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-cyan-950/60 text-cyan-400 border border-cyan-500/20">
            <UploadCloud className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-base font-semibold text-white">
            Drag & drop GeoTIFF / TIFF files
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Supports Optical (Sentinel-2, Cartosat) and SAR (Sentinel-1, RISAT-1) modalities
          </p>
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-cyan-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 transition-colors"
            >
              Select Imagery Files
            </button>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Layers className="h-4 w-4 text-cyan-400" />
              <span>Modalities Supported</span>
            </div>
            <ul className="mt-3 space-y-2 text-xs text-slate-300">
              <li className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Optical Imagery</span>
                <span className="font-mono text-cyan-400">RGB / NIR</span>
              </li>
              <li className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>SAR Imagery</span>
                <span className="font-mono text-cyan-400">VV / VH (dB)</span>
              </li>
              <li className="flex items-center justify-between py-1">
                <span>Bi-temporal Pair</span>
                <span className="font-mono text-cyan-400">T1 / T2</span>
              </li>
            </ul>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-300">
              <AlertCircle className="h-4 w-4 text-amber-400" />
              <span>Ingestion Notice</span>
            </div>
            <p className="mt-2 text-xs text-slate-400 leading-relaxed">
              Files are checked for spatial alignment, projection CRS, and band order prior to
              forwarding to the inference pipeline.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
};
