import React, { useState } from 'react';
import { googleLoginUrl, isroLoginUrl } from '@/services/auth';

export const OAuthButtons: React.FC = () => {
  const [isroMessage, setIsroMessage] = useState<string | null>(null);

  const handleIsroClick = async () => {
    setIsroMessage(null);
    // ponytail: this fetch-probe only works while ISRO is 503-unconfigured (always true
    // today — no Bhuvan credentials exist yet). Once real credentials exist,
    // /auth/isro/login 302-redirects and this fetch would follow the redirect itself
    // instead of handing it to the browser, breaking the button. Switch to a direct
    // window.location.href navigate (like the Google button below) once that happens.
    try {
      const response = await fetch(isroLoginUrl());
      if (response.status === 503) {
        setIsroMessage('ISRO SSO not yet available.');
        return;
      }
    } catch {
      setIsroMessage('ISRO SSO not yet available.');
      return;
    }
    window.location.href = isroLoginUrl();
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-low)' }}>
        <span className="h-px flex-1" style={{ background: 'var(--line)' }} />
        or continue with
        <span className="h-px flex-1" style={{ background: 'var(--line)' }} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => {
            window.location.href = googleLoginUrl();
          }}
          className="rounded-md py-2.5 text-sm font-medium transition-colors"
          style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-hi)' }}
        >
          Google Workspace
        </button>
        <button
          type="button"
          onClick={handleIsroClick}
          className="rounded-md py-2.5 text-sm font-medium transition-colors"
          style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-hi)' }}
        >
          ISRO SSO
        </button>
      </div>

      {isroMessage && (
        <p role="status" className="text-xs" style={{ color: 'var(--text-mid)' }}>
          {isroMessage}
        </p>
      )}
    </div>
  );
};

export default OAuthButtons;
