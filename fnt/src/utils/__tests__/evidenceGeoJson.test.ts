import { describe, expect, it } from 'vitest';
import type { Evidence } from '@/types/contracts';
import type { GeoJSONFeature, GeoJSONPolygon } from '@/types/geojson';
import {
  bboxToPolygonCoordinates,
  evidenceToFeatures,
  buildFeatureCollection,
  getFeatureBounds,
  getCollectionBounds,
  isOutsideViewport,
  normalizeBoundsForFit,
  formatDuration,
} from '../evidenceGeoJson';

describe('evidenceGeoJson', () => {
  describe('bboxToPolygonCoordinates', () => {
    it('converts [minLon, minLat, maxLon, maxLat] to a closed 5-point GeoJSON Polygon rectangle', () => {
      const bbox: [number, number, number, number] = [77.1, 28.5, 77.3, 28.7];
      const coords = bboxToPolygonCoordinates(bbox);

      expect(coords).toHaveLength(1);
      expect(coords[0]).toEqual([
        [77.1, 28.5],
        [77.3, 28.5],
        [77.3, 28.7],
        [77.1, 28.7],
        [77.1, 28.5],
      ]);
    });
  });

  describe('evidenceToFeatures', () => {
    it('converts BBOX evidence with [minLon, minLat, maxLon, maxLat] into GeoJSON Polygon feature', () => {
      const bboxEvidence: Evidence = {
        id: 'ev-bbox-1',
        tool: 'grounding_detector',
        type: 'bbox',
        payload: {
          bbox: [72.8, 18.9, 73.0, 19.1],
          label: 'Industrial Complex',
          description: 'Detected industrial facility',
        },
        confidence: 0.94,
        timing: 0.45,
      };

      const features = evidenceToFeatures([bboxEvidence]);
      expect(features).toHaveLength(1);

      const feature = features[0];
      expect(feature.id).toBe('ev-bbox-1');
      expect(feature.geometry.type).toBe('Polygon');
      expect((feature.geometry as GeoJSONPolygon).coordinates).toEqual([
        [
          [72.8, 18.9],
          [73.0, 18.9],
          [73.0, 19.1],
          [72.8, 19.1],
          [72.8, 18.9],
        ],
      ]);
      expect(feature.properties.id).toBe('ev-bbox-1');
      expect(feature.properties.tool).toBe('grounding_detector');
      expect(feature.properties.type).toBe('bbox');
      expect(feature.properties.label).toBe('Industrial Complex');
      expect(feature.properties.confidence).toBe(0.94);
      expect(feature.properties.color).toBe('#0284c7');
    });

    it('supports payload containing bbox even if evidence type is generic', () => {
      const genericEvidence: Evidence = {
        id: 'ev-auto-bbox',
        tool: 'sar_detector',
        type: 'text',
        payload: {
          bbox: [80.0, 13.0, 80.2, 13.2],
          label: 'Port Berth Area',
        },
        confidence: 0.88,
        timing: 0.32,
      };

      const features = evidenceToFeatures([genericEvidence]);
      expect(features).toHaveLength(1);
      expect(features[0].id).toBe('ev-auto-bbox');
      expect(features[0].geometry.type).toBe('Polygon');
    });

    it('supports BBOX evidence with geojson payload (Feature)', () => {
      const geojsonEvidence: Evidence = {
        id: 'ev-geojson-feat',
        tool: 'segmenter',
        type: 'bbox',
        payload: {
          geojson: {
            type: 'Feature',
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [77.0, 28.0],
                  [77.5, 28.0],
                  [77.5, 28.5],
                  [77.0, 28.5],
                  [77.0, 28.0],
                ],
              ],
            },
            properties: { custom: 'value' },
          },
          label: 'Feature BBOX',
        },
        confidence: 0.91,
        timing: 0.5,
      };

      const features = evidenceToFeatures([geojsonEvidence]);
      expect(features).toHaveLength(1);
      expect(features[0].id).toBe('ev-geojson-feat');
      expect(features[0].properties.label).toBe('Feature BBOX');
      expect(features[0].geometry.type).toBe('Polygon');
    });

    it('supports BBOX evidence with geojson payload (FeatureCollection)', () => {
      const geojsonColEvidence: Evidence = {
        id: 'ev-geojson-col',
        tool: 'segmenter',
        type: 'bbox',
        payload: {
          geojson: {
            type: 'FeatureCollection',
            features: [
              {
                type: 'Feature',
                geometry: {
                  type: 'Polygon',
                  coordinates: [
                    [
                      [75.0, 25.0],
                      [75.2, 25.0],
                      [75.2, 25.2],
                      [75.0, 25.2],
                      [75.0, 25.0],
                    ],
                  ],
                },
                properties: {},
              },
            ],
          },
        },
        confidence: 0.85,
        timing: 0.2,
      };

      const features = evidenceToFeatures([geojsonColEvidence]);
      expect(features).toHaveLength(1);
      expect(features[0].id).toBe('ev-geojson-col');
    });

    it('supports BBOX evidence with raw Geometry in geojson payload', () => {
      const geojsonGeomEvidence: Evidence = {
        id: 'ev-geojson-geom',
        tool: 'detector',
        type: 'bbox',
        payload: {
          geojson: {
            type: 'Polygon',
            coordinates: [
              [
                [76.0, 26.0],
                [76.1, 26.0],
                [76.1, 26.1],
                [76.0, 26.1],
                [76.0, 26.0],
              ],
            ],
          } as unknown as GeoJSONFeature,
        },
        confidence: 0.82,
        timing: 0.15,
      };

      const features = evidenceToFeatures([geojsonGeomEvidence]);
      expect(features).toHaveLength(1);
      expect(features[0].id).toBe('ev-geojson-geom');
      expect(features[0].geometry.type).toBe('Polygon');
    });

    it('ignores items with invalid or missing bounding data', () => {
      const invalidEvidence: Evidence = {
        id: 'ev-invalid',
        tool: 'text_agent',
        type: 'bbox',
        payload: {
          bbox: [10, 20] as unknown as [number, number, number, number],
        },
        confidence: 0.5,
        timing: 0.1,
      };

      const features = evidenceToFeatures([invalidEvidence]);
      expect(features).toHaveLength(0);
    });
  });

  describe('selection filtering & buildFeatureCollection', () => {
    it('packages features in a valid FeatureCollection', () => {
      const features = evidenceToFeatures([
        {
          id: 'b1',
          tool: 't1',
          type: 'bbox',
          payload: { bbox: [1, 2, 3, 4] },
          confidence: 0.9,
          timing: 0.1,
        },
      ]);
      const collection = buildFeatureCollection(features);
      expect(collection.type).toBe('FeatureCollection');
      expect(collection.features).toHaveLength(1);
    });

    it('filters matching selectedId identically to MapLibre halo filter', () => {
      const evList: Evidence[] = [
        {
          id: 'ev-1',
          tool: 't1',
          type: 'bbox',
          payload: { bbox: [70, 20, 71, 21] },
          confidence: 0.9,
          timing: 0.1,
        },
        {
          id: 'ev-2',
          tool: 't2',
          type: 'bbox',
          payload: { bbox: [72, 22, 73, 23] },
          confidence: 0.95,
          timing: 0.2,
        },
      ];

      const features = evidenceToFeatures(evList);
      const selectedId = 'ev-2';
      const highlighted = features.filter((f) => f.properties.id === selectedId);

      expect(highlighted).toHaveLength(1);
      expect(highlighted[0].id).toBe('ev-2');

      const nonExistent = features.filter((f) => f.properties.id === 'unknown');
      expect(nonExistent).toHaveLength(0);
    });
  });

  describe('bounds calculation and viewport out-of-view detection', () => {
    const bboxEv: Evidence = {
      id: 'ev-box',
      tool: 'vqa',
      type: 'bbox',
      payload: { bbox: [77.0, 28.0, 78.5, 29.5] },
      confidence: 0.9,
      timing: 0.2,
    };

    it('getFeatureBounds computes exact [minLon, minLat, maxLon, maxLat]', () => {
      const features = evidenceToFeatures([bboxEv]);
      const bounds = getFeatureBounds(features[0]);
      expect(bounds).toEqual([77.0, 28.0, 78.5, 29.5]);
    });

    it('getCollectionBounds returns enclosing bounds for multiple features', () => {
      const ev2: Evidence = {
        id: 'ev-box-2',
        tool: 'vqa',
        type: 'bbox',
        payload: { bbox: [76.5, 27.5, 77.5, 28.5] },
        confidence: 0.85,
        timing: 0.1,
      };
      const features = evidenceToFeatures([bboxEv, ev2]);
      const bounds = getCollectionBounds(features);
      expect(bounds).toEqual([76.5, 27.5, 78.5, 29.5]);
    });

    it('getCollectionBounds returns null for empty feature set', () => {
      expect(getCollectionBounds([])).toBeNull();
    });

    it('isOutsideViewport returns false when bbox is strictly within viewport', () => {
      const featureBounds: [number, number, number, number] = [77.0, 28.0, 78.5, 29.5];
      const viewport: [number, number, number, number] = [76.0, 27.0, 79.0, 30.0];

      expect(isOutsideViewport(featureBounds, viewport)).toBe(false);
    });

    it('isOutsideViewport returns true when bbox is outside or partially outside', () => {
      const featureBounds: [number, number, number, number] = [77.0, 28.0, 78.5, 29.5];

      // Partially outside to the west
      expect(isOutsideViewport(featureBounds, [77.5, 27.0, 80.0, 30.0])).toBe(true);
      // Partially outside to the east
      expect(isOutsideViewport(featureBounds, [76.0, 27.0, 78.0, 30.0])).toBe(true);
      // Partially outside to the south
      expect(isOutsideViewport(featureBounds, [76.0, 28.5, 79.0, 30.0])).toBe(true);
      // Partially outside to the north
      expect(isOutsideViewport(featureBounds, [76.0, 27.0, 79.0, 29.0])).toBe(true);
      // Completely out of view
      expect(isOutsideViewport(featureBounds, [10.0, 10.0, 20.0, 20.0])).toBe(true);
    });

    it('normalizeBoundsForFit expands zero-area point/degenerate bounds', () => {
      const degenerate: [number, number, number, number] = [77.0, 28.0, 77.0, 28.0];
      const normalized = normalizeBoundsForFit(degenerate, 0.005);
      expect(normalized[0]).toBeCloseTo(76.995);
      expect(normalized[1]).toBeCloseTo(27.995);
      expect(normalized[2]).toBeCloseTo(77.005);
      expect(normalized[3]).toBeCloseTo(28.005);
    });

    it('normalizeBoundsForFit leaves standard bounds unchanged', () => {
      const standard: [number, number, number, number] = [77.0, 28.0, 78.0, 29.0];
      expect(normalizeBoundsForFit(standard)).toEqual([77.0, 28.0, 78.0, 29.0]);
    });
  });

  describe('formatDuration', () => {
    it('formats millisecond and second durations correctly', () => {
      expect(formatDuration(0.045)).toBe('45ms');
      expect(formatDuration(1.234)).toBe('1.23s');
    });
  });
});
