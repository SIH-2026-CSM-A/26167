import type { Answer, Modality } from '@/types/contracts';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

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

  const response = await fetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson && typeof errJson.detail === 'string') {
        errorDetail = errJson.detail;
      }
    } catch {
      // Use fallback status text if json parsing fails
    }
    throw new Error(errorDetail);
  }

  const data = (await response.json()) as Answer;
  return data;
}
