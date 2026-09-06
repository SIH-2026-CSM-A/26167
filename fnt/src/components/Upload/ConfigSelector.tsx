import React from 'react';

export type PipelineConfigMode = 'single' | 'cross-modal' | 'bi-temporal';

interface ConfigSelectorProps {
  selectedMode: PipelineConfigMode;
  onSelectMode: (mode: PipelineConfigMode) => void;
  disabled?: boolean;
}

const CONFIG_OPTIONS: { id: PipelineConfigMode; label: string; description: string }[] = [
  {
    id: 'single',
    label: 'Single Image',
    description: 'Single satellite scene with selectable modality.',
  },
  {
    id: 'cross-modal',
    label: 'Cross-Modal Pair',
    description: 'Optical + SAR pair. Slot 1 is locked to Optical; Slot 2 is locked to SAR.',
  },
  {
    id: 'bi-temporal',
    label: 'Bi-Temporal Pair',
    description: 'T1 + T2 temporal pair. Modality selectable per slot.',
  },
];

export const ConfigSelector: React.FC<ConfigSelectorProps> = ({
  selectedMode,
  onSelectMode,
  disabled = false,
}) => {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
        Pipeline Configuration
      </label>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {CONFIG_OPTIONS.map((opt) => {
          const isSelected = selectedMode === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelectMode(opt.id)}
              className={`text-left p-3.5 rounded-lg border transition-all ${
                isSelected
                  ? 'border-cyan-500 bg-cyan-950/30 text-white shadow-sm shadow-cyan-950'
                  : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700'
              } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div className="font-medium text-sm text-slate-100">{opt.label}</div>
              <div className="text-xs text-slate-400 mt-1 leading-snug">{opt.description}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
