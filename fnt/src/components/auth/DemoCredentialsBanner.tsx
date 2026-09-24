import React from 'react';
import { KeyRound, Sparkles } from 'lucide-react';
import { DEFAULT_DEMO_CREDENTIALS, type DemoCredentials } from '@/utils/demoCredentials';

export interface DemoCredentialsBannerProps {
  onAutoFill: (credentials?: DemoCredentials) => void;
  credentials?: DemoCredentials;
  className?: string;
}

export const DemoCredentialsBanner: React.FC<DemoCredentialsBannerProps> = ({
  onAutoFill,
  credentials = DEFAULT_DEMO_CREDENTIALS,
  className = '',
}) => {
  return (
    <aside
      aria-label="Demo Credentials"
      className={`rounded-lg p-3 text-xs ${className}`}
      style={{
        background: 'rgba(232, 147, 90, 0.08)',
        border: '1px solid var(--accent-dim)',
      }}
    >
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-1.5">
          <KeyRound className="h-3.5 w-3.5" style={{ color: 'var(--accent)' }} />
          <span
            className="font-medium uppercase tracking-wider text-[11px]"
            style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
          >
            Demo Credentials
          </span>
        </div>
        <button
          type="button"
          onClick={() => onAutoFill(credentials)}
          className="flex items-center gap-1 rounded px-2.5 py-1 text-[11px] font-semibold transition-opacity hover:opacity-90 active:opacity-75"
          style={{ background: 'var(--accent)', color: 'var(--bg-0)' }}
          title="Auto-fill email and password into form"
        >
          <Sparkles className="h-3 w-3" />
          <span>Auto-fill</span>
        </button>
      </div>

      <div
        className="grid grid-cols-1 sm:grid-cols-2 gap-2 rounded p-2"
        style={{ background: 'var(--bg-2)', border: '1px solid var(--line-soft)' }}
      >
        <div className="flex flex-col gap-0.5 min-w-0">
          <span
            className="text-[10px] uppercase tracking-wider"
            style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
          >
            Email
          </span>
          <span
            className="truncate font-mono select-all text-xs"
            style={{ color: 'var(--text-hi)' }}
          >
            {credentials.email}
          </span>
        </div>

        <div className="flex flex-col gap-0.5 min-w-0">
          <span
            className="text-[10px] uppercase tracking-wider"
            style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
          >
            Password
          </span>
          <span
            className="truncate font-mono select-all text-xs"
            style={{ color: 'var(--text-hi)' }}
          >
            {credentials.password}
          </span>
        </div>
      </div>
    </aside>
  );
};

export default DemoCredentialsBanner;
