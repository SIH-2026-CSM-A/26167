import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { AuthApiError } from '@/services/auth';
import { DemoCredentialsBanner } from './DemoCredentialsBanner';
import {
  DEFAULT_DEMO_CREDENTIALS,
  isDemoCredentialsVisible,
  type DemoCredentials,
} from '@/utils/demoCredentials';

type Mode = 'login' | 'register';

export interface AuthFormProps {
  mode: Mode;
  onSuccess: () => void;
  onModeChange?: (mode: Mode) => void;
}

interface FieldErrors {
  email?: string;
  password?: string;
}

function validate(mode: Mode, email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!email.trim()) {
    errors.email = 'Email is required.';
  } else if (!email.includes('@')) {
    errors.email = 'Enter a valid email address.';
  }
  if (!password) {
    errors.password = 'Password is required.';
  } else if (mode === 'register' && password.length < 8) {
    errors.password = 'Password must be at least 8 characters.';
  }
  return errors;
}

export const AuthForm: React.FC<AuthFormProps> = ({ mode, onSuccess, onModeChange }) => {
  const { login, register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [suggestedAction, setSuggestedAction] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const showDemoBanner = isDemoCredentialsVisible();

  const handleAutoFill = (credentials: DemoCredentials = DEFAULT_DEMO_CREDENTIALS) => {
    setEmail(credentials.email);
    setPassword(credentials.password);
    setFieldErrors({});
    setFormError(null);
    if (mode !== 'login' && onModeChange) {
      onModeChange('login');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const errors = validate(mode, email, password);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setFormError(null);
    setSuggestedAction(null);
    setIsSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password);
      }
      onSuccess();
    } catch (error) {
      if (error instanceof AuthApiError) {
        setFormError(error.message);
        setSuggestedAction(error.suggestedAction ?? null);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5" style={{ fontFamily: 'var(--font-sans)' }}>
      {showDemoBanner && <DemoCredentialsBanner onAutoFill={handleAutoFill} />}

      {formError && (
        <div
          role="alert"
          className="rounded-md px-3 py-2 text-sm"
          style={{ background: 'rgba(210,87,75,0.12)', border: '1px solid var(--danger)', color: 'var(--text-hi)' }}
        >
          <p>{formError}</p>
          {suggestedAction && (
            <p className="mt-1" style={{ color: 'var(--text-mid)' }}>
              {suggestedAction}
            </p>
          )}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="auth-email"
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          Identification
        </label>
        <input
          id="auth-email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="rounded-md px-3 py-2.5 text-sm outline-none transition-colors"
          style={{
            background: 'var(--bg-2)',
            border: `1px solid ${fieldErrors.email ? 'var(--danger)' : 'var(--line)'}`,
            color: 'var(--text-hi)',
          }}
          onFocus={(event) => (event.currentTarget.style.boxShadow = '0 0 0 2px var(--accent-dim)')}
          onBlur={(event) => (event.currentTarget.style.boxShadow = 'none')}
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? 'auth-email-error' : undefined}
        />
        {fieldErrors.email && (
          <p id="auth-email-error" className="text-xs" style={{ color: 'var(--danger)' }}>
            {fieldErrors.email}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="auth-password"
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          Access Key
        </label>
        <div className="relative">
          <input
            id="auth-password"
            type={showPassword ? 'text' : 'password'}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-md px-3 py-2.5 pr-10 text-sm outline-none transition-colors"
            style={{
              background: 'var(--bg-2)',
              border: `1px solid ${fieldErrors.password ? 'var(--danger)' : 'var(--line)'}`,
              color: 'var(--text-hi)',
              fontFamily: 'var(--font-mono)',
            }}
            onFocus={(event) => (event.currentTarget.style.boxShadow = '0 0 0 2px var(--accent-dim)')}
            onBlur={(event) => (event.currentTarget.style.boxShadow = 'none')}
            aria-invalid={Boolean(fieldErrors.password)}
            aria-describedby={fieldErrors.password ? 'auth-password-error' : undefined}
          />
          <button
            type="button"
            onClick={() => setShowPassword((value) => !value)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1"
            style={{ color: 'var(--text-low)' }}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
        {fieldErrors.password && (
          <p id="auth-password-error" className="text-xs" style={{ color: 'var(--danger)' }}>
            {fieldErrors.password}
          </p>
        )}
      </div>

      <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-mid)' }}>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={keepSignedIn}
            onChange={(event) => setKeepSignedIn(event.target.checked)}
            style={{ accentColor: 'var(--accent)' }}
          />
          Keep me signed in
        </label>
        <span
          aria-disabled="true"
          title="Password reset isn't available yet"
          className="cursor-not-allowed"
          style={{ color: 'var(--text-low)' }}
        >
          Forgot password?
        </span>
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md py-2.5 text-sm font-semibold transition-opacity disabled:cursor-not-allowed disabled:opacity-60"
        style={{ background: 'var(--accent)', color: 'var(--bg-0)' }}
      >
        {isSubmitting
          ? mode === 'login'
            ? 'Signing in…'
            : 'Creating account…'
          : mode === 'login'
            ? 'Sign in'
            : 'Create account'}
      </button>
    </form>
  );
};

export default AuthForm;
