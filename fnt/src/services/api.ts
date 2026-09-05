import type { Answer, Modality } from './types';

export class ApiError extends Error {
  statusCode: number;
  details?: unknown;

  constructor(message: string, statusCode: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

export interface QuerySubmissionItem {
  file: File;
  modality: Modality;
}

export interface QueryRequestPayload {
  query: string;
  items: QuerySubmissionItem[];
}

interface ImportMetaWithEnv {
  env?: {
    VITE_API_BASE_URL?: string;
    DEV?: boolean;
  };
}

/**
 * Resolves the base URL for API requests.
 * Uses `VITE_API_BASE_URL` when provided. In Vite dev mode, falls back to
 * `http://localhost:8000` (the standard FastAPI backend host). In production, defaults to ''.
 */
function getApiBaseUrl(): string {
  const meta = import.meta as unknown as ImportMetaWithEnv;
  if (meta?.env?.VITE_API_BASE_URL) {
    return meta.env.VITE_API_BASE_URL;
  }
  if (meta?.env?.DEV) {
    return 'http://localhost:8000';
  }
  return '';
}

/**
 * Submits a natural language query with one or more satellite images to the backend.
 *
 * Backend endpoint: POST /query
 * Content-Type: multipart/form-data
 * Fields:
 *   - query: string
 *   - images: repeated file field (UploadFile)
 *   - modality: repeated form field ('optical' | 'sar'), 1:1 in order with images
 */
export async function submitQuery({ query, items }: QueryRequestPayload): Promise<Answer> {
  if (!items || items.length === 0) {
    throw new ApiError('At least one image is required for analysis.', 400);
  }

  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    throw new ApiError('A non-empty text query is required.', 400);
  }

  const formData = new FormData();
  formData.append('query', trimmedQuery);

  // In accordance with FastAPI contract: images and modality must have the same length and order
  for (const item of items) {
    formData.append('images', item.file, item.file.name);
    formData.append('modality', item.modality);
  }

  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/query`;

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      body: formData,
    });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : 'Network error occurred while contacting backend.';
    throw new ApiError(
      `Failed to connect to backend at ${endpoint}. Please ensure the SatQuery AI backend server is running. (${message})`,
      0,
      err
    );
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status} (${response.statusText})`;
    let parsedDetails: unknown = null;
    try {
      const errorJson = await response.json();
      parsedDetails = errorJson;
      if (typeof errorJson?.detail === 'string') {
        errorDetail = errorJson.detail;
      } else if (Array.isArray(errorJson?.detail)) {
        errorDetail = errorJson.detail
          .map((item: { msg?: string; loc?: (string | number)[] }) => {
            const field = item.loc ? item.loc.join('.') : '';
            return field ? `${field}: ${item.msg}` : item.msg || JSON.stringify(item);
          })
          .join('; ');
      }
    } catch {
      // Non-JSON response body
    }
    throw new ApiError(errorDetail, response.status, parsedDetails);
  }

  const answer: Answer = await response.json();
  return answer;
}
