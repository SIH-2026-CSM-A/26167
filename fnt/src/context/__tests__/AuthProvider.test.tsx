import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider } from '@/context/AuthProvider';
import { useAuth } from '@/hooks/useAuth';
import { getAuthToken } from '@/services/authFetch';

const user = {
  id: 'u1',
  email: 'a@example.com',
  is_verified: true,
  auth_provider: 'password',
  created_at: '2026-09-05T00:00:00Z',
};

function Probe() {
  const { isAuthenticated, isLoading, login } = useAuth();
  return (
    <div>
      <span data-testid="status">{isLoading ? 'loading' : isAuthenticated ? 'authed' : 'anon'}</span>
      <button onClick={() => login('a@example.com', 'password123')}>login</button>
    </div>
  );
}

describe('AuthProvider', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('cold start calls /auth/refresh exactly once and never /auth/me', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{}', { status: 401 }));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anon'));

    const calledUrls = fetchSpy.mock.calls.map((call) => String(call[0]));
    expect(calledUrls.filter((url) => url.includes('/auth/refresh'))).toHaveLength(1);
    expect(calledUrls.some((url) => url.includes('/auth/me'))).toBe(false);
  });

  it('on successful refresh, hydrates the user and sets the module-level auth token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ user, access_token: 'refreshed-token', token_type: 'bearer', expires_in: 900 }),
        { status: 200 }
      )
    );

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authed'));
    expect(getAuthToken()).toBe('refreshed-token');
  });

  it('on failed refresh, leaves the user unauthenticated without crashing', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 401 }));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anon'));
  });

  it('login stores the access token in memory only, never in localStorage/sessionStorage', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input);
      if (url.includes('/auth/refresh')) return Promise.resolve(new Response('{}', { status: 401 }));
      if (url.includes('/auth/login')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ user, access_token: 'login-token', token_type: 'bearer', expires_in: 900 }),
            { status: 200 }
          )
        );
      }
      return Promise.resolve(new Response('{}', { status: 404 }));
    });
    const storageSetItem = vi.spyOn(Storage.prototype, 'setItem');

    const events = userEvent.setup();
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anon'));

    await events.click(screen.getByText('login'));

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('authed'));
    expect(getAuthToken()).toBe('login-token');
    const tokenWrites = storageSetItem.mock.calls.filter((call) => String(call[1]).includes('login-token'));
    expect(tokenWrites).toHaveLength(0);
  });
});
