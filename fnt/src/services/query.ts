import type { Answer } from '@/types/contracts';

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class QueryApiError extends Error {
  /** Create a user-displayable API error. */
  constructor(message: string) {
    super(message);
    this.name = 'QueryApiError';
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
  if (selectedFiles.some((file) => !/\.tiff?$/i.test(file.name))) {
    throw new QueryApiError('Select .tif or .tiff rasters.');
  }

  const form = new FormData();
  form.append('query', normalizedQuery);
  selectedFiles.forEach((file, index) => {
    form.append('images', file, file.name);
    form.append('modality', modalities?.[index] ?? 'optical');
  });

  const response = await fetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    body: form,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new QueryApiError(readErrorMessage(body, response.status));
  }
  return body as Answer;
}

/** Extract FastAPI string or structured details without exposing internal objects. */
function readErrorMessage(body: unknown, status: number): string {
  if (isRecord(body)) {
    const detail = body.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (isRecord(detail) && typeof detail.message === 'string') {
      return detail.message;
    }
  }
  return `Analysis failed with HTTP ${status}.`;
}

/** Narrow an unknown JSON value to a string-keyed object. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
