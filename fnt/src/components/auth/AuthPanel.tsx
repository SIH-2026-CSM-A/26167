import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthForm } from './AuthForm';
import { OAuthButtons } from './OAuthButtons';

type Mode = 'login' | 'register';

export const AuthPanel: React.FC = () => {
  const [mode, setMode] = useState<Mode>('login');
  const navigate = useNavigate();

  return (
    <div
      className="w-full max-w-md rounded-xl p-10 shadow-2xl"
      style={{ background: 'var(--bg-1)', border: '1px solid var(--line)' }}
    >
      <div
        className="mb-1 text-[11px] font-medium uppercase tracking-widest"
        style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
      >
        Mission Control / Secure Node
      </div>
      <h1
        className="mb-8 text-3xl leading-tight"
        style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }}
      >
        Observer Authentication
      </h1>

      <div
        className="mb-8 flex rounded-md p-1 text-sm font-medium"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--line)' }}
      >
        {(['login', 'register'] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setMode(option)}
            className="flex-1 rounded py-2 transition-colors"
            style={
              mode === option
                ? { background: 'var(--accent-dim)', color: 'var(--accent)' }
                : { color: 'var(--text-mid)' }
            }
          >
            {option === 'login' ? 'Sign in' : 'Create account'}
          </button>
        ))}
      </div>

      <AuthForm mode={mode} onSuccess={() => navigate('/upload')} />

      <div className="mt-6">
        <OAuthButtons />
      </div>

      <p className="mt-8 text-xs leading-relaxed" style={{ color: 'var(--text-low)' }}>
        Unauthorized access to SatQuery AI systems is strictly prohibited. Access is limited
        to authorized analysts.
      </p>
    </div>
  );
};

export default AuthPanel;
