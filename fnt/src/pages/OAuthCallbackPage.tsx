import React, { useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

/** Landing spot for the backend's OAuth redirect (see bck/app/api/oauth.py
 * _redirect_with_tokens): the access token arrives as a one-time query param, read once
 * here and never persisted to the URL bar's history beyond this render.
 */
export const OAuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { setSessionFromAccessToken } = useAuth();
  const [status, setStatus] = useState<'pending' | 'done' | 'error'>('pending');

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    if (!accessToken) {
      setStatus('error');
      return;
    }
    setSessionFromAccessToken(accessToken)
      .then(() => setStatus('done'))
      .catch(() => setStatus('error'));
  }, [searchParams, setSessionFromAccessToken]);

  if (status === 'done') return <Navigate to="/upload" replace />;
  if (status === 'error') return <Navigate to="/login" replace />;
  return (
    <div className="flex min-h-screen items-center justify-center" style={{ background: 'var(--bg-0)', color: 'var(--text-mid)' }}>
      Signing you in…
    </div>
  );
};

export default OAuthCallbackPage;
