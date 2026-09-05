import type { GeoJSONFeature, GeoJSONFeatureCollection, GeoJSONGeometry } from './geojson';

export type Modality = 'optical' | 'sar';

export interface ImageInput {
  id: string;
  modality: Modality;
  format: string;
  metadata: Record<string, unknown>;
}

export interface QueryRequest {
  query: string;
  images: ImageInput[];
}

export type EvidenceType = 'text' | 'bbox' | 'mask' | 'stats' | 'layer';

export interface BBoxPayload {
  bbox?: [number, number, number, number];
  crs?: string;
  label?: string;
  description?: string;
  geojson?: GeoJSONFeature | GeoJSONFeatureCollection;
  [key: string]: unknown;
}

export interface MaskPayload {
  geojson?: GeoJSONFeature | GeoJSONFeatureCollection | GeoJSONGeometry;
  raster_url?: string;
  bounds?: [number, number, number, number];
  color?: string;
  opacity?: number;
  label?: string;
  [key: string]: unknown;
}

export interface StatsPayload {
  metrics?: Record<string, number | string>;
  area_sqkm?: number;
  change_percent?: number;
  [key: string]: unknown;
}

export interface LayerPayload {
  tile_url?: string;
  bounds?: [number, number, number, number];
  opacity?: number;
  label?: string;
  [key: string]: unknown;
}

export interface Evidence<T = Record<string, unknown>> {
  id: string;
  tool: string;
  type: EvidenceType;
  payload: T;
  confidence: number;
  timing: number;
}

export interface TraceStep {
  module: string;
  action: string;
  params: Record<string, unknown>;
  confidence: number | null;
  started_at: string;
  completed_at: string | null;
  evidence_ids: string[];
}

export interface ExecutionTrace {
  trace_id: string;
  steps: TraceStep[];
  created_at: string;
}

export interface Answer {
  text: string;
  evidence: Evidence[];
  trace: ExecutionTrace;
  confidence: number;
  abstained: boolean;
  abstention_reason: string | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  images?: { file: File; modality: Modality; previewUrl: string }[];
  answer?: Answer;
}
