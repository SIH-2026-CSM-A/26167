import type { Evidence, BBoxPayload, MaskPayload } from '@/types/contracts';
import type {
  GeoJSONFeature,
  GeoJSONFeatureCollection,
  GeoJSONGeometry,
  GeoJSONMultiPolygon,
  GeoJSONPoint,
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

function featureFromGeoJSON(
  raw: GeoJSONFeature | GeoJSONFeatureCollection | GeoJSONGeometry,
  ev: Evidence,
  defaultColor: string,
  label?: string,
  description?: string
): GeoJSONFeature | null {
  if (!raw || typeof raw !== 'object' || !('type' in raw)) {
    return null;
  }

  if (raw.type === 'Feature') {
    const feat = raw as GeoJSONFeature;
    return {
      ...feat,
      id: ev.id,
      properties: {
        ...(feat.properties ?? {}),
        id: ev.id,
        tool: ev.tool,
        type: ev.type,
        confidence: ev.confidence,
        timing: ev.timing,
        label: label ?? (feat.properties?.label as string) ?? `Evidence ${ev.id}`,
        description: description ?? (feat.properties?.description as string),
        color: (feat.properties?.color as string) ?? defaultColor,
      },
    };
  }

  if (raw.type === 'FeatureCollection') {
    const coll = raw as GeoJSONFeatureCollection;
    const first = coll.features?.[0];
    if (!first) return null;
    return {
      ...first,
      id: ev.id,
      properties: {
        ...(first.properties ?? {}),
        id: ev.id,
        tool: ev.tool,
        type: ev.type,
        confidence: ev.confidence,
        timing: ev.timing,
        label: label ?? (first.properties?.label as string) ?? `Evidence ${ev.id}`,
        description: description ?? (first.properties?.description as string),
        color: (first.properties?.color as string) ?? defaultColor,
      },
    };
  }

  if ('coordinates' in raw) {
    return {
      type: 'Feature',
      id: ev.id,
      geometry: raw as GeoJSONGeometry,
      properties: {
        id: ev.id,
        tool: ev.tool,
        type: ev.type,
        confidence: ev.confidence,
        timing: ev.timing,
        label: label ?? `Evidence ${ev.id}`,
        description,
        color: defaultColor,
      },
    };
  }

  return null;
}

function createBBoxFeature(ev: Evidence): GeoJSONFeature | null {
  const payload = (ev.payload ?? {}) as BBoxPayload;
  if (
    Array.isArray(payload.bbox) &&
    payload.bbox.length === 4 &&
    payload.bbox.every((n) => typeof n === 'number' && isFinite(n))
  ) {
    const coordinates = bboxToPolygonCoordinates(payload.bbox as [number, number, number, number]);
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
        description: payload.description,
        color: (payload.color as string) ?? '#0284c7',
      },
    };
  }

  if (payload.geojson) {
    return featureFromGeoJSON(
      payload.geojson as GeoJSONFeature | GeoJSONFeatureCollection | GeoJSONGeometry,
      ev,
      (payload.color as string) ?? '#0284c7',
      payload.label,
      payload.description
    );
  }

  return null;
}

function createMaskFeature(ev: Evidence): GeoJSONFeature | null {
  const payload = (ev.payload ?? {}) as MaskPayload;
  if (payload.geojson) {
    return featureFromGeoJSON(
      payload.geojson,
      ev,
      payload.color ?? '#3b82f6',
      payload.label
    );
  }

  if (
    Array.isArray(payload.bounds) &&
    payload.bounds.length === 4 &&
    payload.bounds.every((n) => typeof n === 'number' && isFinite(n))
  ) {
    const coordinates = bboxToPolygonCoordinates(payload.bounds as [number, number, number, number]);
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
        color: payload.color ?? '#3b82f6',
      },
    };
  }

  return null;
}

export function evidenceToFeatures(evidenceList: Evidence[]): GeoJSONFeature[] {
  const features: GeoJSONFeature[] = [];
  for (const ev of evidenceList) {
    const payload = (ev.payload ?? {}) as Record<string, unknown>;
    const hasBbox = Array.isArray(payload.bbox) && payload.bbox.length === 4;
    const hasBounds = Array.isArray(payload.bounds) && payload.bounds.length === 4;

    if (ev.type === 'bbox' || hasBbox) {
      const f = createBBoxFeature(ev);
      if (f) features.push(f);
    } else if (ev.type === 'mask' || hasBounds || payload.geojson) {
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
  if (!feature || !feature.geometry) {
    return null;
  }

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  const update = (x: unknown, y: unknown) => {
    if (typeof x === 'number' && typeof y === 'number' && isFinite(x) && isFinite(y)) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  };

  const geom = feature.geometry;
  if (geom.type === 'Polygon') {
    const poly = geom as GeoJSONPolygon;
    if (Array.isArray(poly.coordinates)) {
      for (const ring of poly.coordinates) {
        if (Array.isArray(ring)) {
          for (const pt of ring) {
            if (Array.isArray(pt) && pt.length >= 2) {
              update(pt[0], pt[1]);
            }
          }
        }
      }
    }
  } else if (geom.type === 'MultiPolygon') {
    const multi = geom as GeoJSONMultiPolygon;
    if (Array.isArray(multi.coordinates)) {
      for (const poly of multi.coordinates) {
        if (Array.isArray(poly)) {
          for (const ring of poly) {
            if (Array.isArray(ring)) {
              for (const pt of ring) {
                if (Array.isArray(pt) && pt.length >= 2) {
                  update(pt[0], pt[1]);
                }
              }
            }
          }
        }
      }
    }
  } else if (geom.type === 'Point') {
    const pt = (geom as GeoJSONPoint).coordinates;
    if (Array.isArray(pt) && pt.length >= 2) {
      update(pt[0], pt[1]);
    }
  }

  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) {
    return null;
  }
  return [minX, minY, maxX, maxY];
}

export function getCollectionBounds(
  features: GeoJSONFeature[]
): [number, number, number, number] | null {
  if (!Array.isArray(features) || features.length === 0) return null;

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

  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) {
    return null;
  }
  return [minX, minY, maxX, maxY];
}

export function isOutsideViewport(
  featureBounds: [number, number, number, number],
  viewportBounds: [number, number, number, number]
): boolean {
  const [fMinX, fMinY, fMaxX, fMaxY] = featureBounds;
  const [vMinX, vMinY, vMaxX, vMaxY] = viewportBounds;
  return fMinX < vMinX || fMinY < vMinY || fMaxX > vMaxX || fMaxY > vMaxY;
}

export function normalizeBoundsForFit(
  bounds: [number, number, number, number],
  epsilon = 0.001
): [number, number, number, number] {
  let [minLon, minLat, maxLon, maxLat] = bounds;
  if (minLon === maxLon) {
    minLon -= epsilon;
    maxLon += epsilon;
  }
  if (minLat === maxLat) {
    minLat -= epsilon;
    maxLat += epsilon;
  }
  return [minLon, minLat, maxLon, maxLat];
}

export function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  }
  return `${seconds.toFixed(2)}s`;
}
