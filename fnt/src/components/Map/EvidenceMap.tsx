import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Map as MapLibreMap,
  type GeoJSONSource,
  type StyleSpecification,
  type LngLatBoundsLike,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Evidence } from '@/types/contracts';
import {
  evidenceToFeatures,
  buildFeatureCollection,
  getFeatureBounds,
  getCollectionBounds,
} from '@/utils/evidenceGeoJson';
import { MapControls, BasemapMode } from './MapControls';
import { EvidenceDetailCard } from './EvidenceDetailCard';

export interface EvidenceMapProps {
  evidenceList: Evidence[];
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string | null) => void;
  className?: string;
}

const BASEMAP_TILES: Record<BasemapMode, { tiles: string[]; attribution: string }> = {
  satellite: {
    tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
    attribution: '© Esri, Maxar, Earthstar Geographics',
  },
  dark: {
    tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],
    attribution: '© CARTO, © OpenStreetMap contributors',
  },
  street: {
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    attribution: '© OpenStreetMap contributors',
  },
};

function createMapStyle(mode: BasemapMode): StyleSpecification {
  const config = BASEMAP_TILES[mode];
  return {
    version: 8,
    sources: {
      'basemap-tiles': {
        type: 'raster',
        tiles: config.tiles,
        tileSize: 256,
        attribution: config.attribution,
      },
    },
    layers: [
      { id: 'basemap-layer', type: 'raster', source: 'basemap-tiles', minzoom: 0, maxzoom: 20 },
    ],
  };
}

function addEvidenceLayers(map: MapLibreMap, onSelect: (id: string) => void): void {
  if (map.getSource('satquery-evidence')) return;
  map.addSource('satquery-evidence', { type: 'geojson', data: buildFeatureCollection([]) });

  map.addLayer({
    id: 'evidence-mask-fill',
    type: 'fill',
    source: 'satquery-evidence',
    paint: { 'fill-color': ['coalesce', ['get', 'color'], '#0284c7'], 'fill-opacity': 0.35 },
  });

  map.addLayer({
    id: 'evidence-boundary-line',
    type: 'line',
    source: 'satquery-evidence',
    paint: { 'line-color': ['coalesce', ['get', 'color'], '#38bdf8'], 'line-width': 2.5 },
  });

  map.addLayer({
    id: 'evidence-selected-halo',
    type: 'line',
    source: 'satquery-evidence',
    filter: ['==', ['get', 'id'], ''],
    paint: { 'line-color': '#22d3ee', 'line-width': 6, 'line-opacity': 0.9, 'line-blur': 2 },
  });

  map.on('click', 'evidence-mask-fill', (e) => {
    const id = e.features?.[0]?.properties?.id as string | undefined;
    if (id) onSelect(id);
  });
}

function useEvidenceSource(
  map: MapLibreMap | null,
  isLoaded: boolean,
  evidenceList: Evidence[],
  selectedId: string | null
): void {
  useEffect(() => {
    if (!map || !isLoaded) return;
    const source = map.getSource('satquery-evidence') as GeoJSONSource | undefined;
    if (!source) return;

    const features = evidenceToFeatures(evidenceList);
    source.setData(buildFeatureCollection(features));

    if (features.length > 0 && !selectedId) {
      const bounds = getCollectionBounds(features);
      if (bounds) {
        map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]] as LngLatBoundsLike, {
          padding: 60,
          maxZoom: 16,
          duration: 1200,
        });
      }
    }
  }, [map, isLoaded, evidenceList, selectedId]);
}

function useFeatureHighlight(
  map: MapLibreMap | null,
  isLoaded: boolean,
  selectedId: string | null,
  evidenceList: Evidence[]
): void {
  useEffect(() => {
    if (!map || !isLoaded) return;
    if (map.getLayer('evidence-selected-halo')) {
      map.setFilter('evidence-selected-halo', ['==', ['get', 'id'], selectedId ?? '']);
    }
    if (!selectedId) return;

    const features = evidenceToFeatures(evidenceList);
    const target = features.find((f) => String(f.properties.id) === selectedId);
    if (!target) return;

    const bounds = getFeatureBounds(target);
    if (bounds) {
      map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]] as LngLatBoundsLike, {
        padding: 80,
        maxZoom: 16,
        duration: 1200,
        essential: true,
      });
    }
  }, [map, isLoaded, selectedId, evidenceList]);
}

function useMapInstance(
  containerRef: React.RefObject<HTMLDivElement>,
  onSelect: (id: string | null) => void
): { mapRef: React.MutableRefObject<MapLibreMap | null>; isLoaded: boolean } {
  const mapRef = useRef<MapLibreMap | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: createMapStyle('satellite'),
      center: [78.9629, 20.5937],
      zoom: 4,
    });
    map.on('load', () => {
      addEvidenceLayers(map, (id) => onSelect(id));
      setIsLoaded(true);
    });
    mapRef.current = map;
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [containerRef, onSelect]);

  return { mapRef, isLoaded };
}

function useMapActions(
  map: MapLibreMap | null,
  evidenceList: Evidence[],
  onSelect: (id: string | null) => void,
  setBasemap: (m: BasemapMode) => void
) {
  const handleBasemapChange = useCallback((mode: BasemapMode) => {
    setBasemap(mode);
    if (!map) return;
    map.setStyle(createMapStyle(mode));
    map.once('style.load', () => {
      addEvidenceLayers(map, (id) => onSelect(id));
      const source = map.getSource('satquery-evidence') as GeoJSONSource | undefined;
      if (source) source.setData(buildFeatureCollection(evidenceToFeatures(evidenceList)));
    });
  }, [map, evidenceList, onSelect, setBasemap]);

  const handleFitAll = useCallback(() => {
    if (!map) return;
    const bounds = getCollectionBounds(evidenceToFeatures(evidenceList));
    if (bounds) {
      map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]] as LngLatBoundsLike, {
        padding: 60,
        maxZoom: 16,
        duration: 1000,
      });
    }
  }, [map, evidenceList]);

  return { handleBasemapChange, handleFitAll };
}

export const EvidenceMap: React.FC<EvidenceMapProps> = ({
  evidenceList,
  selectedEvidenceId,
  onSelectEvidence,
  className = 'h-[560px] w-full',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [basemap, setBasemap] = useState<BasemapMode>('satellite');
  const { mapRef, isLoaded } = useMapInstance(containerRef, onSelectEvidence);
  const { handleBasemapChange, handleFitAll } = useMapActions(
    mapRef.current,
    evidenceList,
    onSelectEvidence,
    setBasemap
  );

  const selectedEvidence = evidenceList.find((e) => e.id === selectedEvidenceId) ?? null;
  useEvidenceSource(mapRef.current, isLoaded, evidenceList, selectedEvidenceId);
  useFeatureHighlight(mapRef.current, isLoaded, selectedEvidenceId, evidenceList);

  return (
    <div className={`relative overflow-hidden rounded-xl border border-slate-800 bg-slate-950 ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      <EvidenceDetailCard evidence={selectedEvidence} onClose={() => onSelectEvidence(null)} />
      <MapControls
        onFitAll={handleFitAll}
        onZoomIn={() => mapRef.current?.zoomIn()}
        onZoomOut={() => mapRef.current?.zoomOut()}
        basemap={basemap}
        onSelectBasemap={handleBasemapChange}
      />
    </div>
  );
};

export default EvidenceMap;
