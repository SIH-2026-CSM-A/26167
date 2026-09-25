import { afterEach, describe, expect, it, vi } from 'vitest';
import { AUTH_UNAVAILABLE_MESSAGE, loginRequest, registerRequest } from '@/services/auth';

describe('auth request errors', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the sign-in unavailable message for a 5xx instead of "Analysis failed"', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('Bad Gateway', { status: 502 }));

    await expect(loginRequest('demo@example.com', 'pw')).rejects.toThrow(AUTH_UNAVAILABLE_MESSAGE);
  });

  it('shows the sign-in unavailable message when the network request fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(registerRequest('demo@example.com', 'pw')).rejects.toThrow(AUTH_UNAVAILABLE_MESSAGE);
  });

  it('keeps the backend invalid-credentials message for a 401', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: { message: 'Invalid email or password.' } }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await expect(loginRequest('demo@example.com', 'wrong')).rejects.toThrow('Invalid email or password.');
  });
});
