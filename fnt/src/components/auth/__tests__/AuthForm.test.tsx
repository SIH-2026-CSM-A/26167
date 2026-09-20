import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthForm } from '@/components/auth/AuthForm';
import * as useAuthModule from '@/hooks/useAuth';
import { AuthApiError } from '@/services/auth';

function mockAuth(overrides: Partial<ReturnType<typeof useAuthModule.useAuth>> = {}) {
  return vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn(),
    setSessionFromAccessToken: vi.fn(),
    ...overrides,
  });
}

describe('AuthForm', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('calls login with the typed email/password on submit success', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    mockAuth({ login });
    const onSuccess = vi.fn();
    const user = userEvent.setup();

    render(<AuthForm mode="login" onSuccess={onSuccess} />);
    await user.type(screen.getByLabelText('Identification'), 'a@example.com');
    await user.type(screen.getByLabelText('Access Key'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(login).toHaveBeenCalledWith('a@example.com', 'password123'));
    expect(onSuccess).toHaveBeenCalled();
  });

  it('calls register with the typed email/password in create-account mode', async () => {
    const register = vi.fn().mockResolvedValue(undefined);
    mockAuth({ register });
    const user = userEvent.setup();

    render(<AuthForm mode="register" onSuccess={vi.fn()} />);
    await user.type(screen.getByLabelText('Identification'), 'b@example.com');
    await user.type(screen.getByLabelText('Access Key'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    await waitFor(() => expect(register).toHaveBeenCalledWith('b@example.com', 'password123'));
  });

  it('renders the parsed error message and suggested action on submit failure', async () => {
    const login = vi
      .fn()
      .mockRejectedValue(new AuthApiError('Invalid email or password.', 'INVALID_CREDENTIALS', 'Try again or reset your password.'));
    mockAuth({ login });
    const user = userEvent.setup();

    render(<AuthForm mode="login" onSuccess={vi.fn()} />);
    await user.type(screen.getByLabelText('Identification'), 'a@example.com');
    await user.type(screen.getByLabelText('Access Key'), 'wrongpassword');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument();
    expect(screen.getByText('Try again or reset your password.')).toBeInTheDocument();
  });

  it('shows a disabled/loading button state while submitting', async () => {
    let resolveLogin: () => void = () => undefined;
    const login = vi.fn().mockReturnValue(new Promise<void>((resolve) => (resolveLogin = resolve)));
    mockAuth({ login });
    const user = userEvent.setup();

    render(<AuthForm mode="login" onSuccess={vi.fn()} />);
    await user.type(screen.getByLabelText('Identification'), 'a@example.com');
    await user.type(screen.getByLabelText('Access Key'), 'password123');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    const button = screen.getByRole('button', { name: 'Signing in…' });
    expect(button).toBeDisabled();

    resolveLogin();
    await waitFor(() => expect(login).toHaveBeenCalled());
  });

  it('renders the forgot-password link disabled, with no fake flow', () => {
    mockAuth();
    render(<AuthForm mode="login" onSuccess={vi.fn()} />);

    const link = screen.getByText('Forgot password?');
    expect(link).toHaveAttribute('aria-disabled', 'true');
    expect(link.tagName).not.toBe('A');
  });
});
