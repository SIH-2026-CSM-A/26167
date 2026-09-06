import type { Evidence, BBoxPayload, MaskPayload } from '@/types/contracts';
import type {
  GeoJSONFeature,
  GeoJSONFeatureCollection,
  GeoJSONPolygon,
  GeoJSONPosition,
} from '@/types/geojson';

export function bboxToPolygonCoordinates(
  bbox: [number, number, number, number]
): GeoJSONPosition[][] {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  return [
    [
      [minLon, minLat],
      [maxLon, minLat],
      [maxLon, maxLat],
      [minLon, maxLat],
      [minLon, minLat],
    ],
  ];
}

function createBBoxFeature(ev: Evidence): GeoJSONFeature | null {
  const payload = ev.payload as BBoxPayload;
  if (!payload.bbox || payload.bbox.length !== 4) {
    return null;
  }
  const coordinates = bboxToPolygonCoordinates(payload.bbox);
  return {
    type: 'Feature',
    id: ev.id,
    geometry: {
      type: 'Polygon',
      coordinates,
    },
    properties: {
      id: ev.id,
      tool: ev.tool,
      type: ev.type,
      confidence: ev.confidence,
      timing: ev.timing,
      label: payload.label ?? `Evidence ${ev.id}`,
      color: '#0284c7',
    },
  };
}

function createMaskFeature(ev: Evidence): GeoJSONFeature | null {
  const payload = ev.payload as MaskPayload;
  if (!payload.geojson) {
    return null;
  }
  const raw = payload.geojson;
  if ('type' in raw && raw.type === 'Feature') {
    return {
      ...(raw as GeoJSONFeature),
      id: ev.id,
      properties: {
        ...(raw as GeoJSONFeature).properties,
        id: ev.id,
        tool: ev.tool,
        type: ev.type,
        confidence: ev.confidence,
        timing: ev.timing,
        label: payload.label ?? `Evidence ${ev.id}`,
        color: payload.color ?? '#3b82f6',
      },
    };
  }
  return null;
}

export function evidenceToFeatures(evidenceList: Evidence[]): GeoJSONFeature[] {
  const features: GeoJSONFeature[] = [];
  for (const ev of evidenceList) {
    if (ev.type === 'bbox') {
      const f = createBBoxFeature(ev);
      if (f) features.push(f);
    } else if (ev.type === 'mask') {
      const f = createMaskFeature(ev);
      if (f) features.push(f);
    }
  }
  return features;
}

export function buildFeatureCollection(
  features: GeoJSONFeature[]
): GeoJSONFeatureCollection {
  return {
    type: 'FeatureCollection',
    features,
  };
}

export function getFeatureBounds(
  feature: GeoJSONFeature
): [number, number, number, number] | null {
  if (feature.geometry.type !== 'Polygon') {
    return null;
  }
  const poly = feature.geometry as GeoJSONPolygon;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const ring of poly.coordinates) {
    for (const [x, y] of ring) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }

  if (!isFinite(minX)) return null;
  return [minX, minY, maxX, maxY];
}

export function getCollectionBounds(
  features: GeoJSONFeature[]
): [number, number, number, number] | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const f of features) {
    const b = getFeatureBounds(f);
    if (!b) continue;
    if (b[0] < minX) minX = b[0];
    if (b[1] < minY) minY = b[1];
    if (b[2] > maxX) maxX = b[2];
    if (b[3] > maxY) maxY = b[3];
  }

  if (!isFinite(minX)) return null;
  return [minX, minY, maxX, maxY];
}

export function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  }
  return `${seconds.toFixed(2)}s`;
}
