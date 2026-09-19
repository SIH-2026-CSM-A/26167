import type { Answer, Modality } from '@/types/contracts';
import { readErrorDetail } from '@/services/query';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';
const QUERY_TIMEOUT_MS = 180_000;

export interface SubmitQueryOptions {
  query: string;
  images: File[];
  modalities: Modality[];
}

export async function submitQuery(options: SubmitQueryOptions): Promise<Answer> {
  const { query, images, modalities } = options;
  if (!images.length) {
    throw new Error('At least one satellite image is required.');
  }
  if (images.length !== modalities.length) {
    throw new Error('Each image must have a corresponding modality.');
  }

  const formData = new FormData();
  formData.append('query', query);

  for (let i = 0; i < images.length; i++) {
    formData.append('images', images[i]);
    formData.append('modality', modalities[i]);
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), QUERY_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/query`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('Query timed out. Check the backend and retry.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const { message, suggestedAction } = readErrorDetail(body, response.status);
    throw new Error([message, suggestedAction].filter(Boolean).join(' '));
  }

  const data = (await response.json()) as Answer;
  return data;
}

export async function downloadEvidencePdf(answer: Answer): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/export-pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answer),
  });
  if (!response.ok) {
    throw new Error('Failed to generate PDF report');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const traceId = answer.trace?.trace_id || 'report';
  a.download = `evidence-${traceId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function downloadEvidenceGeoJson(answer: Answer): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/evidence/export-geojson`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answer),
  });
  if (!response.ok) {
    throw new Error('Failed to export GeoJSON');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const traceId = answer.trace?.trace_id || 'report';
  a.download = `evidence-${traceId}.geojson`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
