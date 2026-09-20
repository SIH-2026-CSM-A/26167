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
      <label
        className="text-[11px] font-medium uppercase tracking-widest"
        style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
      >
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
              className={`text-left p-3.5 rounded-lg border transition-all ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              style={
                isSelected
                  ? { borderColor: 'var(--accent)', background: 'var(--bg-2)', color: 'var(--text-hi)' }
                  : { borderColor: 'var(--line)', background: 'var(--bg-2)', color: 'var(--text-mid)' }
              }
            >
              <div className="font-medium text-sm" style={{ color: isSelected ? 'var(--accent)' : 'var(--text-hi)' }}>
                {opt.label}
              </div>
              <div className="text-xs mt-1 leading-snug" style={{ color: 'var(--text-low)' }}>
                {opt.description}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
