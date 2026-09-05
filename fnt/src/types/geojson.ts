export type GeoJSONPosition = [number, number] | [number, number, number];

export interface GeoJSONPoint {
  type: 'Point';
  coordinates: GeoJSONPosition;
}

export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: GeoJSONPosition[][];
}

export interface GeoJSONMultiPolygon {
  type: 'MultiPolygon';
  coordinates: GeoJSONPosition[][][];
}

export type GeoJSONGeometry = GeoJSONPoint | GeoJSONPolygon | GeoJSONMultiPolygon;

export interface GeoJSONFeature<G = GeoJSONGeometry, P = Record<string, unknown>> {
  type: 'Feature';
  id?: string | number;
  geometry: G;
  properties: P;
}

export interface GeoJSONFeatureCollection<
  G = GeoJSONGeometry,
  P = Record<string, unknown>
> {
  type: 'FeatureCollection';
  features: GeoJSONFeature<G, P>[];
}
