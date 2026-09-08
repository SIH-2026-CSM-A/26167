import type { Evidence, LayerPayload, MaskPayload } from '@/types/contracts';

const TITILER_BASE_URL = (import.meta.env.VITE_TITILER_URL ?? 'http://localhost:8001').replace(/\/$/, '');
const DEFAULT_RASTER_TILE_SIZE = 256;
const DEFAULT_RASTER_OPACITY = 0.75;
const VECTOR_SOURCE_ID = 'satquery-evidence';
const RASTER_SOURCE_PREFIX = 'satquery-raster-source-';
const RASTER_LAYER_PREFIX = 'satquery-raster-layer-';

export type EvidenceSourceKind = 'vector' | 'raster';

export type EvidenceSourceState = 'idle' | 'loading' | 'ready' | 'error';

export interface EvidenceSourceStatus {
  id: string;
  label: string;
  kind: EvidenceSourceKind;
  state: EvidenceSourceState;
  message?: string;
}

export interface RasterEvidenceOverlay {
  evidenceId: string;
  kind: 'mask' | 'layer';
  label: string;
  sourceId: string;
  layerId: string;
  tiles: string[];
  opacity: number;
  bounds?: [number, number, number, number];
}

export interface RasterSourceSpecification {
  type: 'raster';
  tiles: string[];
  tileSize: number;
  bounds?: [number, number, number, number];
}

export interface RasterLayerSpecification {
  id: string;
  type: 'raster';
  source: string;
  paint: {
    'raster-opacity': number;
  };
}

export type EvidenceBounds = [number, number, number, number];

/** Read WGS84 bounds from the existing TiTiler COG bounds endpoint. */
export async function loadRasterBounds(overlay: RasterEvidenceOverlay, signal: AbortSignal): Promise<EvidenceBounds | undefined> {
  if (overlay.bounds) return overlay.bounds;
  const url = new URL(overlay.tiles[0], window.location.href);
  const tilePath = '/cog/tiles/';
  const index = url.pathname.indexOf(tilePath);
  if (index < 0 || !url.searchParams.has('url')) return undefined;
  url.pathname = `${url.pathname.slice(0, index)}/cog/bounds`;
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Raster bounds failed (${response.status})`);
  const data = await response.json();
  const bounds = normalizeBounds(data.bounds);
  if (!bounds) throw new Error('Raster bounds are invalid');
  return bounds;
}

/** Normalize an evidence identifier into a MapLibre-safe source or layer suffix. */
function sanitizeMapId(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return normalized || 'evidence';
}

/** Detect an XYZ-style template that MapLibre can request directly. */
function isXyzTemplateUrl(value: string): boolean {
  return value.includes('{z}') && value.includes('{x}') && value.includes('{y}');
}

/** Convert a raw COG URL into the repo's TiTiler XYZ template convention. */
function buildTitilerTileTemplate(cogUrl: string): string {
  const queryString = new URLSearchParams({ url: cogUrl }).toString();
  return `${TITILER_BASE_URL}/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?${queryString}`;
}

/** Resolve an evidence raster URL into a MapLibre-ready XYZ template. */
export function resolveRasterTileUrl(rawUrl: string | undefined): string | null {
  if (typeof rawUrl !== 'string') {
    return null;
  }

  const trimmed = rawUrl.trim();
  if (!trimmed) {
    return null;
  }

  if (isXyzTemplateUrl(trimmed)) {
    return trimmed;
  }

  return buildTitilerTileTemplate(trimmed);
}

/** Clamp an opacity value into MapLibre's supported 0..1 range. */
function clampOpacity(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }

  return Math.min(Math.max(value, 0), 1);
}

/** Validate a 4-number bounds tuple before sending it to MapLibre. */
function normalizeBounds(bounds: unknown): [number, number, number, number] | undefined {
  if (
    !Array.isArray(bounds) ||
    bounds.length !== 4 ||
    !bounds.every((coordinate) => typeof coordinate === 'number' && Number.isFinite(coordinate))
  ) {
    return undefined;
  }

  return bounds as [number, number, number, number];
}

/** Build a stable MapLibre source ID for one raster evidence record. */
function buildRasterSourceId(evidenceId: string, kind: RasterEvidenceOverlay['kind']): string {
  return `${RASTER_SOURCE_PREFIX}${sanitizeMapId(evidenceId)}-${kind}`;
}

/** Build a stable MapLibre layer ID for one raster evidence record. */
function buildRasterLayerId(evidenceId: string, kind: RasterEvidenceOverlay['kind']): string {
  return `${RASTER_LAYER_PREFIX}${sanitizeMapId(evidenceId)}-${kind}`;
}

/** Build the MapLibre raster source specification for one evidence overlay. */
export function buildRasterSourceSpecification(overlay: RasterEvidenceOverlay): RasterSourceSpecification {
  const source: RasterSourceSpecification = {
    type: 'raster',
    tiles: overlay.tiles,
    tileSize: DEFAULT_RASTER_TILE_SIZE,
  };

  if (overlay.bounds) {
    source.bounds = overlay.bounds;
  }

  return source;
}

/** Build the MapLibre raster layer specification for one evidence overlay. */
export function buildRasterLayerSpecification(overlay: RasterEvidenceOverlay): RasterLayerSpecification {
  return {
    id: overlay.layerId,
    type: 'raster',
    source: overlay.sourceId,
    paint: {
      'raster-opacity': overlay.opacity,
    },
  };
}

/** Build one raster overlay definition from a mask evidence payload. */
function buildMaskOverlay(evidence: Evidence): RasterEvidenceOverlay | null {
  const payload = (evidence.payload ?? {}) as MaskPayload;
  const tileUrl = resolveRasterTileUrl(payload.raster_url);
  if (!tileUrl) {
    return null;
  }

  return {
    evidenceId: evidence.id,
    kind: 'mask',
    label: payload.label ?? `Evidence ${evidence.id}`,
    sourceId: buildRasterSourceId(evidence.id, 'mask'),
    layerId: buildRasterLayerId(evidence.id, 'mask'),
    tiles: [tileUrl],
    opacity: clampOpacity(payload.opacity, DEFAULT_RASTER_OPACITY),
    bounds: normalizeBounds(payload.bounds),
  };
}

/** Build one raster overlay definition from a layer evidence payload. */
function buildLayerOverlay(evidence: Evidence): RasterEvidenceOverlay | null {
  const payload = (evidence.payload ?? {}) as LayerPayload;
  const tileUrl = resolveRasterTileUrl(payload.tile_url);
  if (!tileUrl) {
    return null;
  }

  return {
    evidenceId: evidence.id,
    kind: 'layer',
    label: payload.label ?? `Evidence ${evidence.id}`,
    sourceId: buildRasterSourceId(evidence.id, 'layer'),
    layerId: buildRasterLayerId(evidence.id, 'layer'),
    tiles: [tileUrl],
    opacity: clampOpacity(payload.opacity, DEFAULT_RASTER_OPACITY),
    bounds: normalizeBounds(payload.bounds),
  };
}

/** Collect every raster evidence overlay that the map should render. */
export function evidenceToRasterOverlays(evidenceList: Evidence[]): RasterEvidenceOverlay[] {
  const overlays: RasterEvidenceOverlay[] = [];

  for (const evidence of evidenceList) {
    if ((evidence.payload as MaskPayload | undefined)?.raster_url) {
      const overlay = buildMaskOverlay(evidence);
      if (overlay) {
        overlays.push(overlay);
      }
    }

    if ((evidence.payload as LayerPayload | undefined)?.tile_url) {
      const overlay = buildLayerOverlay(evidence);
      if (overlay) {
        overlays.push(overlay);
      }
    }
  }

  return overlays;
}

/** Create the canonical source status entry for the GeoJSON evidence source. */
export function createVectorSourceStatus(
  featureCount: number,
  state: EvidenceSourceState = featureCount > 0 ? 'ready' : 'idle',
  message?: string
): EvidenceSourceStatus {
  return {
    id: VECTOR_SOURCE_ID,
    label: 'GeoJSON evidence',
    kind: 'vector',
    state,
    message,
  };
}

/** Create a loading status entry for one raster overlay. */
export function createRasterSourceStatus(
  overlay: RasterEvidenceOverlay,
  state: EvidenceSourceState,
  message?: string
): EvidenceSourceStatus {
  return {
    id: overlay.sourceId,
    label: overlay.label,
    kind: 'raster',
    state,
    message,
  };
}

/** Return the canonical GeoJSON source ID used by the evidence map. */
export function getVectorEvidenceSourceId(): string {
  return VECTOR_SOURCE_ID;
}

/** Combine the bounds of raster overlays into one map-fitting extent. */
export function getRasterOverlayBounds(
  overlays: RasterEvidenceOverlay[]
): EvidenceBounds | null {
  if (!Array.isArray(overlays) || overlays.length === 0) {
    return null;
  }

  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  for (const overlay of overlays) {
    if (!overlay.bounds) {
      continue;
    }

    const [overlayMinLon, overlayMinLat, overlayMaxLon, overlayMaxLat] = overlay.bounds;
    if (overlayMinLon < minLon) minLon = overlayMinLon;
    if (overlayMinLat < minLat) minLat = overlayMinLat;
    if (overlayMaxLon > maxLon) maxLon = overlayMaxLon;
    if (overlayMaxLat > maxLat) maxLat = overlayMaxLat;
  }

  if (
    !Number.isFinite(minLon) ||
    !Number.isFinite(minLat) ||
    !Number.isFinite(maxLon) ||
    !Number.isFinite(maxLat)
  ) {
    return null;
  }

  return [minLon, minLat, maxLon, maxLat];
}
