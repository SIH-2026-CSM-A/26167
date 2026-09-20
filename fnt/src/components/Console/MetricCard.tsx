import React from 'react';

export interface MetricCardProps {
  label: string;
  value: string;
  tone?: 'default' | 'up' | 'warn';
}

const TONE_COLOR: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: 'var(--text-hi)',
  up: '#8fc79e',
  warn: '#e3a66c',
};

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, tone = 'default' }) => (
  <div
    className="flex-1 rounded-lg px-3.5 py-2.5"
    style={{ background: 'var(--bg-2)', border: '1px solid var(--line)' }}
  >
    <div
      className="text-[10px] uppercase tracking-wide"
      style={{ color: 'var(--text-low)' }}
    >
      {label}
    </div>
    <div
      className="mt-1 text-lg font-semibold"
      style={{ color: TONE_COLOR[tone], fontFamily: 'var(--font-mono)' }}
    >
      {value}
    </div>
  </div>
);

export default MetricCard;
