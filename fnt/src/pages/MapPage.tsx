import React, { useState } from 'react';
import { Layers, ShieldCheck, Filter, Clock } from 'lucide-react';
import { useSatQuery } from '@/hooks/useSatQuery';
import { EvidenceMap } from '@/components/Map/EvidenceMap';
import { formatDuration } from '@/utils/evidenceGeoJson';
import type { Evidence, EvidenceType } from '@/types/contracts';

const EvidenceCardItem: React.FC<{
  ev: Evidence;
  isSelected: boolean;
  onSelect: (id: string | null) => void;
}> = ({ ev, isSelected, onSelect }) => (
  <button
    onClick={() => onSelect(isSelected ? null : ev.id)}
    className={`w-full text-left p-3 rounded-lg border transition-all text-xs ${
      isSelected
        ? 'border-cyan-500 bg-cyan-950/50 shadow-md shadow-cyan-950/40'
        : 'border-slate-800 bg-slate-900/80 hover:border-slate-700 hover:bg-slate-800/60 text-slate-300'
    }`}
  >
    <div className="flex items-center justify-between">
      <span className="font-mono font-bold text-cyan-400">[{ev.id}]</span>
      <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
        {ev.type}
      </span>
    </div>
    <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
      <span>Tool: {ev.tool}</span>
      <span className="flex items-center gap-1 text-emerald-400 font-mono">
        <ShieldCheck className="h-3 w-3" />
        {(ev.confidence * 100).toFixed(0)}%
      </span>
    </div>
    <div className="mt-1 flex items-center gap-1 text-[10px] text-slate-500 font-mono">
      <Clock className="h-3 w-3" />
      <span>Inference: {formatDuration(ev.timing)}</span>
    </div>
  </button>
);

const EvidenceListSection: React.FC<{
  items: Evidence[];
  totalCount: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}> = ({ items, totalCount, selectedId, onSelect }) => {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-center p-4">
        <Layers className="h-8 w-8 text-slate-600 mb-2" />
        <p className="text-xs text-slate-400">
          {totalCount === 0
            ? 'No spatial evidence generated yet. Submit a query in Chat or upload imagery to display grounded features.'
            : 'No features match the selected filter.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto mt-3 space-y-2 pr-1">
      {items.map((ev) => (
        <EvidenceCardItem key={ev.id} ev={ev} isSelected={selectedId === ev.id} onSelect={onSelect} />
      ))}
    </div>
  );
};

const MapSidebar: React.FC<{
  filterType: EvidenceType | 'all';
  onFilterChange: (t: EvidenceType | 'all') => void;
  filteredItems: Evidence[];
  totalCount: number;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}> = ({ filterType, onFilterChange, filteredItems, totalCount, selectedId, onSelect }) => (
  <div className="lg:col-span-4 xl:col-span-3 flex flex-col h-[660px] rounded-xl border border-slate-800 bg-slate-900/40 p-4">
    <div className="flex items-center justify-between pb-3 border-b border-slate-800">
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-cyan-400" />
        <span className="text-sm font-semibold text-white">Evidence Features</span>
      </div>
      <select
        value={filterType}
        onChange={(e) => onFilterChange(e.target.value as EvidenceType | 'all')}
        className="rounded bg-slate-800 border border-slate-700 px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
      >
        <option value="all">All Types</option>
        <option value="bbox">Bounding Boxes</option>
        <option value="mask">Segmentation Masks</option>
        <option value="stats">Statistical Layers</option>
      </select>
    </div>
    <EvidenceListSection
      items={filteredItems}
      totalCount={totalCount}
      selectedId={selectedId}
      onSelect={onSelect}
    />
  </div>
);

export const MapPage: React.FC = () => {
  const { evidenceList, selectedEvidenceId, selectEvidence } = useSatQuery();
  const [filterType, setFilterType] = useState<EvidenceType | 'all'>('all');

  const filteredEvidence = evidenceList.filter((e) => filterType === 'all' || e.type === filterType);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">Spatial Evidence & Map View</h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-400">
            Interactive MapLibre satellite viewport with vector masks, bounding boxes, and audit metadata.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
            <Layers className="h-4 w-4 text-cyan-400" />
            <span>Active Layers: {evidenceList.length}</span>
          </div>
          <div className="rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-400 font-mono">
            CRS: EPSG:4326
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8 xl:col-span-9 h-[660px]">
          <EvidenceMap
            evidenceList={evidenceList}
            selectedEvidenceId={selectedEvidenceId}
            onSelectEvidence={selectEvidence}
            className="h-full w-full"
          />
        </div>
        <MapSidebar
          filterType={filterType}
          onFilterChange={setFilterType}
          filteredItems={filteredEvidence}
          totalCount={evidenceList.length}
          selectedId={selectedEvidenceId}
          onSelect={selectEvidence}
        />
      </div>
    </main>
  );
};

export default MapPage;
