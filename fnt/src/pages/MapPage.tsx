import React, { useState } from 'react';
import { Layers, ShieldCheck, Filter, Clock } from 'lucide-react';
import { useSatQuery } from '@/hooks/useSatQuery';
import { MapHero } from '@/components/Map/MapHero';
import { formatDuration } from '@/utils/evidenceGeoJson';
import type { Evidence, EvidenceType } from '@/types/contracts';

const EvidenceCardItem: React.FC<{
  ev: Evidence;
  isSelected: boolean;
  onSelect: (id: string | null) => void;
}> = ({ ev, isSelected, onSelect }) => (
  <button
    onClick={() => onSelect(isSelected ? null : ev.id)}
    className="w-full rounded-lg border p-3 text-left text-xs transition-all"
    style={
      isSelected
        ? { borderColor: 'var(--accent)', background: 'var(--accent-dim)', color: 'var(--text-hi)' }
        : { borderColor: 'var(--line)', background: 'var(--bg-2)', color: 'var(--text-mid)' }
    }
  >
    <div className="flex items-center justify-between">
      <span className="font-bold" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
        [{ev.id}]
      </span>
      <span
        className="rounded px-1.5 py-0.5 text-[10px] uppercase"
        style={{ background: 'var(--bg-1)', color: 'var(--text-low)' }}
      >
        {ev.type}
      </span>
    </div>
    <div className="mt-2 flex items-center justify-between text-[11px]" style={{ color: 'var(--text-low)' }}>
      <span>Tool: {ev.tool}</span>
      <span className="flex items-center gap-1" style={{ color: '#8fc79e', fontFamily: 'var(--font-mono)' }}>
        <ShieldCheck className="h-3 w-3" />
        {(ev.confidence * 100).toFixed(0)}%
      </span>
    </div>
    <div
      className="mt-1 flex items-center gap-1 text-[10px]"
      style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
    >
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
      <div className="flex h-48 flex-col items-center justify-center p-4 text-center">
        <Layers className="mb-2 h-8 w-8" style={{ color: 'var(--text-low)' }} />
        <p className="text-xs" style={{ color: 'var(--text-low)' }}>
          {totalCount === 0
            ? 'No spatial evidence generated yet. Submit a query in Chat or upload imagery to display grounded features.'
            : 'No features match the selected filter.'}
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1">
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
  <div
    className="lg:col-span-4 xl:col-span-3 flex flex-col h-[660px] rounded-xl p-4"
    style={{ background: 'var(--bg-1)', border: '1px solid var(--line)' }}
  >
    <div className="flex items-center justify-between pb-3" style={{ borderBottom: '1px solid var(--line)' }}>
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4" style={{ color: 'var(--accent)' }} />
        <span
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          Evidence Features
        </span>
      </div>
      <select
        value={filterType}
        onChange={(e) => onFilterChange(e.target.value as EvidenceType | 'all')}
        className="rounded px-2 py-1 text-xs outline-none"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-mid)' }}
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
  const {
    evidenceList,
    selectedEvidenceId,
    hoveredEvidenceId,
    selectEvidence,
    hoverEvidence,
  } = useSatQuery();
  const [filterType, setFilterType] = useState<EvidenceType | 'all'>('all');

  const filteredEvidence = evidenceList.filter((e) => filterType === 'all' || e.type === filterType);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl" style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }}>
            Spatial Evidence &amp; Map View
          </h1>
          <p className="mt-1 text-xs sm:text-sm" style={{ color: 'var(--text-low)' }}>
            Interactive MapLibre satellite viewport with vector masks, bounding boxes, and audit metadata.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs"
            style={{ border: '1px solid var(--line)', background: 'var(--bg-1)', color: 'var(--text-mid)' }}
          >
            <Layers className="h-4 w-4" style={{ color: 'var(--accent)' }} />
            <span>Active Layers: {evidenceList.length}</span>
          </div>
          <div
            className="rounded-md px-3 py-1.5 text-xs"
            style={{
              border: '1px solid var(--line)',
              background: 'var(--bg-1)',
              color: 'var(--text-low)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            CRS: EPSG:4326
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="relative h-[660px] overflow-hidden rounded-xl lg:col-span-8 xl:col-span-9">
          <MapHero
            edgeLabel="SPATIAL FEED"
            evidenceList={evidenceList}
            selectedEvidenceId={selectedEvidenceId}
            hoveredEvidenceId={hoveredEvidenceId}
            onSelectEvidence={selectEvidence}
            onHoverEvidence={hoverEvidence}
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
