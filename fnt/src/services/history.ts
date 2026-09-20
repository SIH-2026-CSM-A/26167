import { authFetch } from '@/services/authFetch';
import { readErrorDetail } from '@/services/query';
import type { QueryHistoryItem } from '@/types/contracts';

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class HistoryApiError extends Error {
  readonly reasonCode?: string;
  readonly suggestedAction?: string;

  constructor(message: string, reasonCode?: string, suggestedAction?: string) {
    super(message);
    this.name = 'HistoryApiError';
    this.reasonCode = reasonCode;
    this.suggestedAction = suggestedAction;
  }
}

export async function getHistory(): Promise<QueryHistoryItem[]> {
  const response = await authFetch(`${API_BASE_URL}/history`, { method: 'GET' });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, reasonCode, suggestedAction } = readErrorDetail(body, response.status);
    throw new HistoryApiError(message, reasonCode, suggestedAction);
  }
  return body as QueryHistoryItem[];
}
