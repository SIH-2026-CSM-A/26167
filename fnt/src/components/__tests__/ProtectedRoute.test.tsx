import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import * as useAuthModule from '@/hooks/useAuth';

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={['/upload']}>
      <Routes>
        <Route path="/login" element={<div>login-sentinel</div>} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <div>protected-content</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  it('redirects to /login when unauthenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setSessionFromAccessToken: vi.fn(),
    });

    renderProtected();

    expect(screen.getByText('login-sentinel')).toBeInTheDocument();
    expect(screen.queryByText('protected-content')).not.toBeInTheDocument();
  });

  it('renders children when authenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: { id: 'u1', email: 'a@example.com', is_verified: true, auth_provider: 'password', created_at: '2026-09-05T00:00:00Z' },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setSessionFromAccessToken: vi.fn(),
    });

    renderProtected();

    expect(screen.getByText('protected-content')).toBeInTheDocument();
  });

  it('renders nothing while loading, then redirects once loading resolves to unauthenticated', async () => {
    const spy = vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: true,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setSessionFromAccessToken: vi.fn(),
    });

    const { rerender } = renderProtected();

    expect(screen.queryByText('login-sentinel')).not.toBeInTheDocument();
    expect(screen.queryByText('protected-content')).not.toBeInTheDocument();

    spy.mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      setSessionFromAccessToken: vi.fn(),
    });
    rerender(
      <MemoryRouter initialEntries={['/upload']}>
        <Routes>
          <Route path="/login" element={<div>login-sentinel</div>} />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <div>protected-content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText('login-sentinel')).toBeInTheDocument());
  });
});
