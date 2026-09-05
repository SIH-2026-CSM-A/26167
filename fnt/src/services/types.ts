/**
 * Typed contracts mirroring backend schemas from `bck/app/contracts/schemas.py`.
 */

export type Modality = 'optical' | 'sar';

export type EvidenceType = 'text' | 'bbox' | 'mask' | 'stats' | 'layer';

export interface Evidence {
  id: string;
  tool: string;
  type: EvidenceType;
  payload: Record<string, unknown>;
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

export type InputConfiguration = 'single' | 'cross-modal' | 'bi-temporal';

export interface ImageSlotState {
  file: File | null;
  modality: Modality;
  error?: string | null;
}
