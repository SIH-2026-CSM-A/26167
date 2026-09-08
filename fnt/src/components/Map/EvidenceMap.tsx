import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
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
  isOutsideViewport,
  normalizeBoundsForFit,
} from '@/utils/evidenceGeoJson';
import {
  buildRasterLayerSpecification,
  buildRasterSourceSpecification,
  createRasterSourceStatus,
  createVectorSourceStatus,
  evidenceToRasterOverlays,
  loadRasterBounds,
  getRasterOverlayBounds,
  type EvidenceSourceStatus,
  type RasterEvidenceOverlay,
} from '@/utils/evidenceRaster';
import { MapControls, BasemapMode } from './MapControls';
import { EvidenceDetailCard } from './EvidenceDetailCard';

export interface EvidenceMapProps {
  evidenceList: Evidence[];
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string | null) => void;
  hoveredEvidenceId?: string | null;
  onHoverEvidence?: (id: string | null) => void;
  className?: string;
}

const BASEMAP_TILES: Record<BasemapMode, { tiles: string[]; attribution: string }> = {
  satellite: { tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], attribution: '© Esri, Maxar, Earthstar Geographics' },
  dark: { tiles: ['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'], attribution: '© CARTO, © OpenStreetMap contributors' },
  street: { tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'], attribution: '© OpenStreetMap contributors' },
};

function createMapStyle(mode: BasemapMode): StyleSpecification {
  const config = BASEMAP_TILES[mode];
  return {
    version: 8,
    sources: {
      'basemap-tiles': { type: 'raster', tiles: config.tiles, tileSize: 256, attribution: config.attribution },
    },
    layers: [{ id: 'basemap-layer', type: 'raster', source: 'basemap-tiles', minzoom: 0, maxzoom: 20 }],
  };
}

function addEvidenceLayers(
  map: MapLibreMap,
  onSelect: (id: string) => void,
  onHover?: (id: string | null) => void
): void {
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
    id: 'evidence-hover-halo',
    type: 'line',
    source: 'satquery-evidence',
    filter: ['==', ['get', 'id'], ''],
    paint: { 'line-color': '#f59e0b', 'line-width': 5.5, 'line-opacity': 0.95, 'line-blur': 1 },
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

  if (onHover) {
    map.on('mouseenter', 'evidence-mask-fill', (e) => {
      const canvas = map.getCanvas?.();
      if (canvas?.style) canvas.style.cursor = 'pointer';
      const id = e.features?.[0]?.properties?.id as string | undefined;
      if (id) onHover(id);
    });
    map.on('mouseleave', 'evidence-mask-fill', () => {
      const canvas = map.getCanvas?.();
      if (canvas?.style) canvas.style.cursor = '';
      onHover(null);
    });
  }
}

function syncRasterLayers(map: MapLibreMap, overlays: RasterEvidenceOverlay[]): void {
  for (const overlay of overlays) {
    if (!map.getSource(overlay.sourceId)) {
      map.addSource(overlay.sourceId, buildRasterSourceSpecification(overlay));
    }
    if (!map.getLayer(overlay.layerId)) {
      map.addLayer(buildRasterLayerSpecification(overlay), 'evidence-mask-fill');
    }
  }
}

function useEvidenceSource(
  map: MapLibreMap | null,
  isLoaded: boolean,
  evidenceList: Evidence[],
  selectedId: string | null
): RasterEvidenceOverlay[] {
  const overlays = useMemo(() => evidenceToRasterOverlays(evidenceList), [evidenceList]);
  useEffect(() => {
    if (!map || !isLoaded) return;
    const source = map.getSource('satquery-evidence') as GeoJSONSource | undefined;
    if (!source) return;

    const features = evidenceToFeatures(evidenceList);
    source.setData(buildFeatureCollection(features));

    if (features.length > 0 && !selectedId && map.fitBounds) {
      const bounds = getCollectionBounds(features);
      if (bounds) {
        const fitBox = normalizeBoundsForFit(bounds);
        map.fitBounds([[fitBox[0], fitBox[1]], [fitBox[2], fitBox[3]]] as LngLatBoundsLike, {
          padding: 60,
          maxZoom: 16,
          duration: 1200,
        });
      }
    }
  }, [map, isLoaded, evidenceList, selectedId, overlays]);
  useEffect(() => {
    if (!map || !isLoaded || overlays.length === 0) return;
    const controller = new AbortController();
    let resolved: RasterEvidenceOverlay[] = [];
    const restore = () => syncRasterLayers(map, resolved);
    map.on('style.load', restore);
    void Promise.all(overlays.map(async (overlay) => {
      try {
        return { ...overlay, bounds: await loadRasterBounds(overlay, controller.signal) };
      } catch (error) {
        if (!controller.signal.aborted) map.fire('error', {
          sourceId: overlay.sourceId,
          error: error instanceof Error ? error : new Error('Raster metadata failed'),
        });
        return null;
      }
    })).then((items) => {
      if (controller.signal.aborted) return;
      resolved = items.filter((item) => item !== null);
      restore();
      const selected = resolved.filter((overlay) => overlay.evidenceId === selectedId);
      const bounds = getRasterOverlayBounds(selected.length ? selected : resolved);
      if (bounds) map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], {
        padding: 60, maxZoom: 16, duration: 1200,
      });
    });
    return () => {
      controller.abort();
      map.off('style.load', restore);
      for (const overlay of resolved) {
        if (map.getLayer(overlay.layerId)) map.removeLayer(overlay.layerId);
        if (map.getSource(overlay.sourceId)) map.removeSource(overlay.sourceId);
      }
    };
  }, [map, isLoaded, overlays, selectedId]);
  return overlays;
}

function useEvidenceStatuses(
  map: MapLibreMap | null,
  isLoaded: boolean,
  overlays: RasterEvidenceOverlay[],
  featureCount: number
): EvidenceSourceStatus[] {
  const [statuses, setStatuses] = useState<EvidenceSourceStatus[]>([]);

  useEffect(() => {
    if (!map || !isLoaded) return;
    setStatuses([
      createVectorSourceStatus(featureCount),
      ...overlays.map((overlay) => createRasterSourceStatus(overlay, 'loading')),
    ]);

    const listeners = overlays.map((overlay) => {
      const handleData = (event: Parameters<Parameters<MapLibreMap['on']>[1]>[0]) => {
        if (!('sourceId' in event) || event.sourceId !== overlay.sourceId || !('isSourceLoaded' in event) || !event.isSourceLoaded) return;
        setStatuses((current) => current.map((status) => status.id === overlay.sourceId
          ? createRasterSourceStatus(overlay, 'ready')
          : status));
      };
      const handleError = (event: Parameters<Parameters<MapLibreMap['on']>[1]>[0]) => {
        if (!('sourceId' in event) || event.sourceId !== overlay.sourceId) return;
        setStatuses((current) => current.map((status) => status.id === overlay.sourceId
          ? createRasterSourceStatus(overlay, 'error', 'Raster source failed to load')
          : status));
      };
      map.on('data', handleData);
      map.on('error', handleError);
      return { handleData, handleError };
    });
    return () => {
      listeners.forEach(({ handleData, handleError }) => {
        map.off('data', handleData);
        map.off('error', handleError);
      });
    };
  }, [map, isLoaded, overlays, featureCount]);

  return statuses;
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
    if (bounds && map.fitBounds) {
      let shouldFit = true;
      try {
        const vp = map.getBounds?.();
        if (vp) {
          const vpBounds: [number, number, number, number] = [vp.getWest(), vp.getSouth(), vp.getEast(), vp.getNorth()];
          shouldFit = isOutsideViewport(bounds, vpBounds);
        }
      } catch {
        shouldFit = true;
      }

      if (shouldFit) {
        const fitBox = normalizeBoundsForFit(bounds);
        map.fitBounds([[fitBox[0], fitBox[1]], [fitBox[2], fitBox[3]]] as LngLatBoundsLike, {
          padding: 80,
          maxZoom: 16,
          duration: 1200,
          essential: true,
        });
      }
    }
  }, [map, isLoaded, selectedId, evidenceList]);
}

function useHoverHighlight(map: MapLibreMap | null, isLoaded: boolean, hoveredId: string | null): void {
  useEffect(() => {
    if (!map || !isLoaded) return;
    if (map.getLayer?.('evidence-hover-halo')) {
      map.setFilter('evidence-hover-halo', ['==', ['get', 'id'], hoveredId ?? '']);
    }
  }, [map, isLoaded, hoveredId]);
}

function useMapInstance(
  containerRef: React.RefObject<HTMLDivElement>,
  onSelect: (id: string | null) => void,
  onHover?: (id: string | null) => void
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
      addEvidenceLayers(map, (id) => onSelect(id), onHover);
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
  }, [containerRef, onSelect, onHover]);

  return { mapRef, isLoaded };
}

function useMapActions(
  map: MapLibreMap | null,
  evidenceList: Evidence[],
  onSelect: (id: string | null) => void,
  setBasemap: (m: BasemapMode) => void,
  onHover?: (id: string | null) => void
) {
  const handleBasemapChange = useCallback((mode: BasemapMode) => {
    setBasemap(mode);
    if (!map) return;
    map.setStyle(createMapStyle(mode));
    map.once('style.load', () => {
      addEvidenceLayers(map, (id) => onSelect(id), onHover);
      const source = map.getSource('satquery-evidence') as GeoJSONSource | undefined;
      if (source) source.setData(buildFeatureCollection(evidenceToFeatures(evidenceList)));
    });
  }, [map, evidenceList, onSelect, setBasemap, onHover]);

  const handleFitAll = useCallback(() => {
    if (!map || !map.fitBounds) return;
    const bounds = getCollectionBounds(evidenceToFeatures(evidenceList));
    if (bounds) {
      const fitBox = normalizeBoundsForFit(bounds);
      map.fitBounds([[fitBox[0], fitBox[1]], [fitBox[2], fitBox[3]]] as LngLatBoundsLike, {
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
  hoveredEvidenceId = null,
  onHoverEvidence,
  className = 'h-[560px] w-full',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [basemap, setBasemap] = useState<BasemapMode>('satellite');
  const { mapRef, isLoaded } = useMapInstance(containerRef, onSelectEvidence, onHoverEvidence);
  const { handleBasemapChange, handleFitAll } = useMapActions(
    mapRef.current,
    evidenceList,
    onSelectEvidence,
    setBasemap,
    onHoverEvidence
  );

  const selectedEvidence = evidenceList.find((e) => e.id === selectedEvidenceId) ?? null;
  const rasterOverlays = useEvidenceSource(mapRef.current, isLoaded, evidenceList, selectedEvidenceId);
  const sourceStatuses = useEvidenceStatuses(mapRef.current, isLoaded, rasterOverlays, evidenceToFeatures(evidenceList).length);
  useFeatureHighlight(mapRef.current, isLoaded, selectedEvidenceId, evidenceList);
  useHoverHighlight(mapRef.current, isLoaded, hoveredEvidenceId);

  return (
    <div className={`relative overflow-hidden rounded-xl border border-slate-800 bg-slate-950 ${className}`}>
      <div ref={containerRef} className="h-full w-full" />
      {sourceStatuses.length > 0 && (
        <div className="absolute left-3 top-3 z-10 max-w-xs rounded-lg border border-slate-700/80 bg-slate-950/90 px-3 py-2 text-xs text-slate-200 shadow-lg">
          <div className="mb-1 font-semibold text-slate-100">Evidence layers</div>
          {sourceStatuses.map((status) => (
            <div key={status.id} className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${status.state === 'error' ? 'bg-rose-400' : status.state === 'ready' ? 'bg-emerald-400' : status.state === 'loading' ? 'bg-amber-400' : 'bg-slate-500'}`} />
              <span className="truncate">{status.label}: {status.state}</span>
              {status.state === 'error' && <span className="text-rose-300">failed</span>}
            </div>
          ))}
        </div>
      )}
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
