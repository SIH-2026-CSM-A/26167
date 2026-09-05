import React from 'react';
import { UploadCloud, Layers, Clock } from 'lucide-react';
import type { InputConfiguration } from '@/services/types';

export interface ConfigurationSelectorProps {
  config: InputConfiguration;
  onChange: (config: InputConfiguration) => void;
}

export const ConfigurationSelector: React.FC<ConfigurationSelectorProps> = ({
  config,
  onChange,
}) => {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <label className="block text-xs font-mono uppercase tracking-wider text-slate-400 mb-3">
        Select Imagery Input Configuration
      </label>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {/* 1. Single Image */}
        <button
          type="button"
          onClick={() => onChange('single')}
          className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
            config === 'single'
              ? 'border-cyan-500 bg-cyan-950/30 text-white shadow-sm ring-1 ring-cyan-500/50'
              : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:text-white'
          }`}
          aria-pressed={config === 'single'}
        >
          <div className="flex items-center gap-2">
            <UploadCloud className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-semibold">1. Single Image</span>
          </div>
          <span className="mt-1 text-[11px] text-slate-400">
            Single pass optical or SAR image
          </span>
        </button>

        {/* 2. Cross-Modal Pair */}
        <button
          type="button"
          onClick={() => onChange('cross-modal')}
          className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
            config === 'cross-modal'
              ? 'border-cyan-500 bg-cyan-950/30 text-white shadow-sm ring-1 ring-cyan-500/50'
              : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:text-white'
          }`}
          aria-pressed={config === 'cross-modal'}
        >
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-semibold">2. Cross-Modal Pair</span>
          </div>
          <span className="mt-1 text-[11px] text-slate-400">
            Optical + SAR (Late Fusion)
          </span>
        </button>

        {/* 3. Bi-Temporal Pair */}
        <button
          type="button"
          onClick={() => onChange('bi-temporal')}
          className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
            config === 'bi-temporal'
              ? 'border-cyan-500 bg-cyan-950/30 text-white shadow-sm ring-1 ring-cyan-500/50'
              : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:text-white'
          }`}
          aria-pressed={config === 'bi-temporal'}
        >
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-cyan-400" />
            <span className="text-xs font-semibold">3. Bi-Temporal Pair</span>
          </div>
          <span className="mt-1 text-[11px] text-slate-400">
            T1 + T2 Passes (Change Detection)
          </span>
        </button>
      </div>
    </div>
  );
};
