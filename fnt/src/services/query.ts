import type { Answer } from '@/types/contracts';

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class QueryApiError extends Error {
  readonly reasonCode?: string;
  readonly suggestedAction?: string;

  /** Create a user-displayable API error, optionally carrying the backend's veto details. */
  constructor(message: string, reasonCode?: string, suggestedAction?: string) {
    super(message);
    this.name = 'QueryApiError';
    this.reasonCode = reasonCode;
    this.suggestedAction = suggestedAction;
  }
}

/** Upload one or more TIFFs plus their actual question to the backend query endpoint. */
export async function submitImageQuery(
  files: File | File[],
  query: string,
  modalities?: string[]
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
  });

  const response = await fetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    body: form,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, reasonCode, suggestedAction } = readErrorDetail(body, response.status);
    throw new QueryApiError(message, reasonCode, suggestedAction);
  }
  return body as Answer;
}

/** Extract FastAPI string or structured (PipelineError) details without exposing internal objects. */
function readErrorDetail(
  body: unknown,
  status: number
): { message: string; reasonCode?: string; suggestedAction?: string } {
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
      };
    }
  }
  return { message: `Analysis failed with HTTP ${status}.` };
}

/** Narrow an unknown JSON value to a string-keyed object. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
