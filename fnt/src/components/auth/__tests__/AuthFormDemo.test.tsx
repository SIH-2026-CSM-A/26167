import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthContext, type AuthContextValue } from '@/context/AuthContext';
import { AuthForm } from '../AuthForm';
import * as demoCredsUtil from '@/utils/demoCredentials';

const mockAuthValue: AuthContextValue = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: vi.fn().mockResolvedValue(undefined),
  register: vi.fn().mockResolvedValue(undefined),
  logout: vi.fn().mockResolvedValue(undefined),
  setSessionFromAccessToken: vi.fn().mockResolvedValue(undefined),
};

function renderAuthForm(props: Partial<React.ComponentProps<typeof AuthForm>> = {}) {
  const defaultProps = {
    mode: 'login' as const,
    onSuccess: vi.fn(),
    onModeChange: vi.fn(),
  };
  return render(
    <AuthContext.Provider value={mockAuthValue}>
      <AuthForm {...defaultProps} {...props} />
    </AuthContext.Provider>,
  );
}

describe('AuthForm Demo Credentials & Auto-fill Integration', () => {
  it('renders the Demo Credentials banner and one-click auto-fills credentials', async () => {
    const user = userEvent.setup();
    renderAuthForm();

    expect(screen.getByText('Demo Credentials')).toBeInTheDocument();

    const emailInput = screen.getByLabelText(/identification/i);
    const passwordInput = screen.getByLabelText(/access key/i);

    expect(emailInput).toHaveValue('');
    expect(passwordInput).toHaveValue('');

    const autoFillBtn = screen.getByRole('button', { name: /auto-fill/i });
    await user.click(autoFillBtn);

    expect(emailInput).toHaveValue('demo@example.com');
    expect(passwordInput).toHaveValue('correct-horse-battery');
  });

  it('clears existing validation errors upon auto-fill', async () => {
    const user = userEvent.setup();
    renderAuthForm();

    const submitBtn = screen.getByRole('button', { name: /^sign in$/i });
    await user.click(submitBtn);

    expect(screen.getByText('Email is required.')).toBeInTheDocument();
    expect(screen.getByText('Password is required.')).toBeInTheDocument();

    const autoFillBtn = screen.getByRole('button', { name: /auto-fill/i });
    await user.click(autoFillBtn);

    expect(screen.queryByText('Email is required.')).not.toBeInTheDocument();
    expect(screen.queryByText('Password is required.')).not.toBeInTheDocument();
  });

  it('switches mode to login if auto-fill is triggered during register mode', async () => {
    const user = userEvent.setup();
    const onModeChange = vi.fn();
    renderAuthForm({ mode: 'register', onModeChange });

    const autoFillBtn = screen.getByRole('button', { name: /auto-fill/i });
    await user.click(autoFillBtn);

    expect(onModeChange).toHaveBeenCalledTimes(1);
    expect(onModeChange).toHaveBeenCalledWith('login');

    const emailInput = screen.getByLabelText(/identification/i);
    const passwordInput = screen.getByLabelText(/access key/i);
    expect(emailInput).toHaveValue('demo@example.com');
    expect(passwordInput).toHaveValue('correct-horse-battery');
  });

  it('hides the Demo Credentials banner when isDemoCredentialsVisible returns false', () => {
    vi.spyOn(demoCredsUtil, 'isDemoCredentialsVisible').mockReturnValue(false);

    renderAuthForm();

    expect(screen.queryByText('Demo Credentials')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /auto-fill/i })).not.toBeInTheDocument();

    vi.restoreAllMocks();
  });
});
