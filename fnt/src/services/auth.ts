import { readErrorDetail } from '@/services/query';

const API_BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export interface UserPublic {
  id: string;
  email: string;
  is_verified: boolean;
  auth_provider: string;
  created_at: string;
}

export interface AuthResponse {
  user: UserPublic;
  access_token: string;
  token_type: string;
  expires_in: number;
}

export class AuthApiError extends Error {
  readonly reasonCode?: string;
  readonly suggestedAction?: string;

  constructor(message: string, reasonCode?: string, suggestedAction?: string) {
    super(message);
    this.name = 'AuthApiError';
    this.reasonCode = reasonCode;
    this.suggestedAction = suggestedAction;
  }
}

export const AUTH_UNAVAILABLE_MESSAGE =
  'Sign-in service is unavailable right now. Try again in a minute.';

async function parseAuthResponse(response: Response): Promise<AuthResponse> {
  if (response.status >= 500) {
    throw new AuthApiError(AUTH_UNAVAILABLE_MESSAGE);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, reasonCode, suggestedAction } = readErrorDetail(body, response.status);
    throw new AuthApiError(message, reasonCode, suggestedAction);
  }
  return body as AuthResponse;
}

async function postCredentials(
  path: '/auth/login' | '/auth/register',
  email: string,
  password: string
): Promise<AuthResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  } catch {
    // fetch only rejects on network failure (server down, DNS, CORS), never on HTTP status.
    throw new AuthApiError(AUTH_UNAVAILABLE_MESSAGE);
  }
  return parseAuthResponse(response);
}

export function loginRequest(email: string, password: string): Promise<AuthResponse> {
  return postCredentials('/auth/login', email, password);
}

export function registerRequest(email: string, password: string): Promise<AuthResponse> {
  return postCredentials('/auth/register', email, password);
}

/** Returns null (rather than throwing) on a 401 — a missing/expired refresh cookie is the
 * normal "not logged in" case, not an error worth surfacing.
 */
export async function refreshRequest(): Promise<AuthResponse | null> {
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  });
  if (response.status === 401) return null;
  return parseAuthResponse(response);
}

export async function meRequest(accessToken: string): Promise<UserPublic> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const { message, reasonCode, suggestedAction } = readErrorDetail(body, response.status);
    throw new AuthApiError(message, reasonCode, suggestedAction);
  }
  return body as UserPublic;
}

export async function logoutRequest(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
}

export function googleLoginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`;
}

export function isroLoginUrl(): string {
  return `${API_BASE_URL}/auth/isro/login`;
}
