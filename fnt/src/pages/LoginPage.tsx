import React from 'react';
import { AuthPanel } from '@/components/auth/AuthPanel';

/* Full-bleed Earth photo: NASA Earth Observatory "Night Lights 2012 Map" (Suomi NPP/VIIRS
 * day-night band composite) — public domain, U.S. government work.
 * Source: https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg
 *
 * The navbar is hidden on this route (see App.tsx) so this covers the entire viewport edge
 * to edge; the auth card floats centered on top of it via absolute positioning, not a
 * layout column. */
export const LoginPage: React.FC = () => (
  <div className="fixed inset-0">
    <div
      className="absolute inset-0"
      style={{
        backgroundImage: 'url(/assets/earth-night-lights.jpg)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    />
    <div className="absolute inset-0" style={{ background: 'rgba(13,14,12,0.55)' }} />

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
