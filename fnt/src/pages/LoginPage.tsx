import React from 'react';
import { AuthPanel } from '@/components/auth/AuthPanel';
import { PageBackdrop } from '@/components/PageBackdrop';

/* The navbar is hidden on this route (see App.tsx) so the photo covers the entire viewport
 * edge to edge; the auth card floats centered on top of it via absolute positioning, not a
 * layout column. No dimming scrim — the auth card's own solid background carries its own
 * legibility. */
export const LoginPage: React.FC = () => (
  <div className="fixed inset-0">
    <PageBackdrop />

    <div
      className="absolute bottom-6 left-6 text-xs tracking-wide"
      style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
    >
      <div>04&deg; 23&apos; 11&quot; N / 114&deg; 18&apos; 42&quot; E</div>
      <div className="mt-1" style={{ color: 'var(--text-low)' }}>
        TERMINAL ACCESS: AI-01_SECURE
      </div>
    </div>

    <div className="absolute inset-0 flex items-center justify-center p-6">
      <AuthPanel />
    </div>
  </div>
);

export default LoginPage;
