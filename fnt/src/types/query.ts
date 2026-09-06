export interface EvidencePayload {
  source_asset_id?: string;
  source_filename?: string | null;
  source_format?: string;
  source_metadata?: Record<string, unknown>;
  model_id?: string;
  raw_model_answer?: string;
  verified_answer?: string;
  supporting_observations?: string[];
  rejected_claims?: string[];
  confidence_available?: boolean;
  [key: string]: unknown;
}

export interface Evidence {
  id: string;
  tool: string;
  type: string;
  payload: EvidencePayload;
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
