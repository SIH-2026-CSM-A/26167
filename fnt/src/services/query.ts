import type { Answer, ExecutionTrace } from '@/types/contracts';
import { authFetch } from '@/services/authFetch';

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class QueryApiError extends Error {
  readonly reasonCode?: string;
  readonly suggestedAction?: string;
  readonly trace?: ExecutionTrace;

  /** Create a user-displayable API error, optionally carrying the backend's veto details. */
  constructor(message: string, reasonCode?: string, suggestedAction?: string, trace?: ExecutionTrace) {
    super(message);
    this.name = 'QueryApiError';
    this.reasonCode = reasonCode;
    this.suggestedAction = suggestedAction;
    this.trace = trace;
  }
}

/** Upload one or more TIFFs plus their actual question to the backend query endpoint. */
export async function submitImageQuery(
  files: File | File[],
  query: string,
  modalities?: string[],
  captureOrder?: number[],
  demo?: { presetId: string; runLive: boolean }
): Promise<Answer> {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    throw new QueryApiError('Enter a question about the image.');
  }
  const selectedFiles = Array.isArray(files) ? files : [files];
  if (selectedFiles.some((file) => !/\.(tiff?|png|jpe?g)$/i.test(file.name))) {
    throw new QueryApiError('Select .tif, .tiff, .png, or .jpg/.jpeg imagery.');
  }

  const form = new FormData();
  form.append('query', normalizedQuery);
  selectedFiles.forEach((file, index) => {
    form.append('images', file, file.name);
    // Omitting `modalities` entirely (vs. passing it) lets the backend classify modality
    // from raster metadata instead of defaulting every image to optical (B4).
    if (modalities) {
      form.append('modality', modalities[index] ?? 'optical');
    }
    if (captureOrder) {
      form.append('capture_order', String(captureOrder[index]));
    }
  });
  // A demo preset is answered from its recorded run unless the user explicitly asks for live.
  if (demo) {
    form.append('demo_preset_id', demo.presetId);
    form.append('run_live', String(demo.runLive));
  }

  const response = await authFetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    body: form,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, reasonCode, suggestedAction, trace } = readErrorDetail(body, response.status);
    throw new QueryApiError(message, reasonCode, suggestedAction, trace);
  }
  return body as Answer;
}

/** Extract FastAPI string or structured (PipelineError) details without exposing internal objects. */
export function readErrorDetail(
  body: unknown,
  status: number
): { message: string; reasonCode?: string; suggestedAction?: string; trace?: ExecutionTrace } {
  if (isRecord(body)) {
    const detail = body.detail;
    if (typeof detail === 'string') {
      return { message: detail };
    }
    if (isRecord(detail) && typeof detail.message === 'string') {
      return {
        message: detail.message,
        reasonCode: typeof detail.reason_code === 'string' ? detail.reason_code : undefined,
        suggestedAction:
          typeof detail.suggested_action === 'string' ? detail.suggested_action : undefined,
        trace:
          isRecord(detail.trace) && Array.isArray(detail.trace.steps)
            ? (detail.trace as unknown as ExecutionTrace)
            : undefined,
      };
    }
  }
  return { message: `Analysis failed with HTTP ${status}.` };
}

/** Narrow an unknown JSON value to a string-keyed object. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
