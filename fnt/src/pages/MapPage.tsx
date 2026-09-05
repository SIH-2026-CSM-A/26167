import React from 'react';
import { Compass, Maximize2, Layers } from 'lucide-react';

export const MapPage: React.FC = () => {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Spatial Evidence & Map View
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Geospatial tile overlays, bounding boxes, and change masks rendered over base maps.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-400">
            CRS: EPSG:4326 / WGS 84
          </span>
        </div>
      </div>

      <div className="relative h-[560px] w-full overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 flex flex-col items-center justify-center text-center p-8">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-950/80 text-cyan-400 border border-cyan-500/30 mb-4 shadow-lg shadow-cyan-950/50">
          <Compass className="h-8 w-8" />
        </div>
        <h2 className="text-lg font-semibold text-white">MapLibre GL Viewport Container</h2>
        <p className="mt-2 max-w-md text-xs text-slate-400 leading-relaxed">
          This container shell will host the MapLibre GL JS map engine, TiTiler raster tile
          endpoints, and vector bounding box overlays in ticket LIKI-002.
        </p>

        <div className="absolute top-4 right-4 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 bg-slate-800/80 text-slate-300">
            <Layers className="h-4 w-4" />
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-700 bg-slate-800/80 text-slate-300">
            <Maximize2 className="h-4 w-4" />
          </div>
        </div>

        <div className="absolute bottom-4 left-4 text-xs font-mono text-slate-500">
          MapLibre Shell Ready · Viewport Scaled
        </div>
      </div>
    </main>
  );
};
