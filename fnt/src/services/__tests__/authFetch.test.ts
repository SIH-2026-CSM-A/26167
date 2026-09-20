import { afterEach, describe, expect, it, vi } from 'vitest';
import { authFetch, setAuthToken, setRefreshHandler } from '@/services/authFetch';

describe('authFetch', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAuthToken(null);
    setRefreshHandler(null);
  });

  it('attaches Authorization: Bearer <token> when a token is set', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    setAuthToken('token-1');

    await authFetch('/query');

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer token-1');
  });

  it('sends no Authorization header when no token is set', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));

    await authFetch('/query');

    const init = fetchSpy.mock.calls[0][1] as RequestInit | undefined;
    expect((init?.headers as Record<string, string> | undefined)?.Authorization).toBeUndefined();
  });

  it('on a 401, refreshes exactly once and retries the original request exactly once', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response('{}', { status: 200 }));
    const refreshHandler = vi.fn().mockResolvedValue('token-2');
    setAuthToken('token-1');
    setRefreshHandler(refreshHandler);

    const response = await authFetch('/query');

    expect(response.status).toBe(200);
    expect(refreshHandler).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const retryInit = fetchSpy.mock.calls[1][1] as RequestInit;
    expect((retryInit.headers as Record<string, string>).Authorization).toBe('Bearer token-2');
  });

  it('does not retry infinitely when the refresh handler fails to produce a token', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));
    const refreshHandler = vi.fn().mockResolvedValue(null);
    setRefreshHandler(refreshHandler);

    const response = await authFetch('/query');

    expect(response.status).toBe(401);
    expect(refreshHandler).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('does not attempt a refresh on a non-401 error', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 500 }));
    const refreshHandler = vi.fn().mockResolvedValue('token-2');
    setRefreshHandler(refreshHandler);

    const response = await authFetch('/query');

    expect(response.status).toBe(500);
    expect(refreshHandler).not.toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});
