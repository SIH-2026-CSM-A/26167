import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthForm } from './AuthForm';
import { OAuthButtons } from './OAuthButtons';

type Mode = 'login' | 'register';

export const AuthPanel: React.FC = () => {
  const [mode, setMode] = useState<Mode>('login');
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col justify-center" style={{ padding: '0 56px' }}>
      <div className="mx-auto w-full max-w-sm">
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

        <p className="mt-8 text-center text-xs" style={{ color: 'var(--text-low)' }}>
          SatQuery AI — SIH26167. Access is limited to authorized analysts.
        </p>
      </div>
    </div>
  );
};

export default AuthPanel;
