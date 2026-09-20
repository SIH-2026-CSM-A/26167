import React from 'react';
import { MapPin, Satellite } from 'lucide-react';
import { AuthPanel } from '@/components/auth/AuthPanel';

const TELEMETRY = [
  { label: 'ALT', value: '705 KM' },
  { label: 'VEL', value: '7.5 KM/S' },
  { label: 'SUN', value: '10:32 LT' },
];

const SceneStyles: React.FC = () => (
  <style>{`
    @keyframes satquery-scanline {
      0% { transform: translateY(-100%); }
      100% { transform: translateY(100%); }
    }
    @media (prefers-reduced-motion: no-preference) {
      .satquery-scanline { animation: satquery-scanline 6s linear infinite; }
    }
  `}</style>
);

const ScenePanel: React.FC = () => (
  <div
    className="relative hidden overflow-hidden lg:block"
    style={{
      background: `
        linear-gradient(var(--line-soft) 1px, transparent 1px) 0 0 / 48px 48px,
        linear-gradient(90deg, var(--line-soft) 1px, transparent 1px) 0 0 / 48px 48px,
        var(--bg-1)
      `,
    }}
  >
    <SceneStyles />

    <div
      aria-hidden="true"
      className="satquery-scanline pointer-events-none absolute inset-x-0 h-24"
      style={{
        background: 'linear-gradient(180deg, transparent, var(--accent-dim), transparent)',
      }}
    />

    <div className="relative flex h-full flex-col justify-between p-10" style={{ fontFamily: 'var(--font-mono)' }}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2" style={{ color: 'var(--text-hi)' }}>
          <Satellite className="h-5 w-5" style={{ color: 'var(--accent)' }} />
          <span className="text-sm font-medium tracking-wide">SATQUERY AI</span>
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-[11px] tracking-wide"
          style={{ background: 'var(--ndvi-fill)', color: 'var(--ndvi)', border: '1px solid var(--ndvi)' }}
        >
          SCENE · LIVE FEED (DEMO)
        </span>
      </div>

      <div className="flex flex-col gap-4">
        <div
          className="flex items-center gap-2 text-xs"
          style={{ color: 'var(--text-mid)' }}
        >
          <MapPin className="h-3.5 w-3.5" style={{ color: 'var(--water)' }} />
          <span>AOI 12.9716° N, 77.5946° E</span>
        </div>

        <div className="flex gap-6 text-xs" style={{ color: 'var(--text-low)' }}>
          {TELEMETRY.map((item) => (
            <div key={item.label} className="flex flex-col gap-0.5">
              <span style={{ color: 'var(--text-low)' }}>{item.label}</span>
              <span style={{ color: 'var(--text-hi)' }}>{item.value}</span>
            </div>
          ))}
        </div>

        <p className="max-w-xs text-xs leading-relaxed" style={{ color: 'var(--text-low)' }}>
          Static preview — no live telemetry is connected on this page.
        </p>
      </div>
    </div>
  </div>
);

export const LoginPage: React.FC = () => (
  <div
    className="grid min-h-screen lg:grid-cols-[1fr_460px]"
    style={{ background: 'var(--bg-0)', fontFamily: 'var(--font-sans)' }}
  >
    <ScenePanel />
    <AuthPanel />
  </div>
);

export default LoginPage;
