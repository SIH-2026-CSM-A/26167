import React from 'react';
import { Plus, Minus, Maximize2, Satellite } from 'lucide-react';

export type BasemapMode = 'satellite' | 'street' | 'dark';

export interface MapControlsProps {
  onFitAll: () => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  basemap: BasemapMode;
  onSelectBasemap: (mode: BasemapMode) => void;
}

const BasemapButtons: React.FC<{
  current: BasemapMode;
  onSelect: (mode: BasemapMode) => void;
}> = ({ current, onSelect }) => (
  <div className="flex items-center gap-1 rounded-lg border border-slate-700 bg-slate-900/90 p-1 shadow-lg backdrop-blur">
    {(['satellite', 'dark', 'street'] as BasemapMode[]).map((mode) => (
      <button
        key={mode}
        onClick={() => onSelect(mode)}
        className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium capitalize transition-colors ${
          current === mode ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
        }`}
      >
        {mode === 'satellite' && <Satellite className="h-3 w-3" />}
        <span>{mode}</span>
      </button>
    ))}
  </div>
);

const ZoomToolbar: React.FC<{
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitAll: () => void;
}> = ({ onZoomIn, onZoomOut, onFitAll }) => (
  <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-900/90 shadow-lg backdrop-blur overflow-hidden">
    <button
      onClick={onZoomIn}
      className="p-2 text-slate-300 hover:bg-slate-800 hover:text-white border-b border-slate-800 transition-colors"
      title="Zoom In"
    >
      <Plus className="h-4 w-4" />
    </button>
    <button
      onClick={onZoomOut}
      className="p-2 text-slate-300 hover:bg-slate-800 hover:text-white border-b border-slate-800 transition-colors"
      title="Zoom Out"
    >
      <Minus className="h-4 w-4" />
    </button>
    <button
      onClick={onFitAll}
      className="p-2 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
      title="Fit All Features"
    >
      <Maximize2 className="h-4 w-4" />
    </button>
  </div>
);

export const MapControls: React.FC<MapControlsProps> = ({
  onFitAll,
  onZoomIn,
  onZoomOut,
  basemap,
  onSelectBasemap,
}) => (
  <div className="absolute top-4 right-4 z-10 flex flex-col gap-2 items-end">
    <BasemapButtons current={basemap} onSelect={onSelectBasemap} />
    <ZoomToolbar onZoomIn={onZoomIn} onZoomOut={onZoomOut} onFitAll={onFitAll} />
    <div className="rounded-md border border-slate-800 bg-slate-950/80 px-2 py-1 font-mono text-[10px] text-slate-400 shadow backdrop-blur">
      CRS: EPSG:4326 (WGS 84)
    </div>
  </div>
);

export default MapControls;
