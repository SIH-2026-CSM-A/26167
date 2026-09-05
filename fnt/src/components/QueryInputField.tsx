import React from 'react';
import { FileQuestion } from 'lucide-react';
import type { InputConfiguration } from '@/services/types';

export interface QueryInputFieldProps {
  id: string;
  query: string;
  config: InputConfiguration;
  onChange: (query: string) => void;
  disabled?: boolean;
}

export const QueryInputField: React.FC<QueryInputFieldProps> = ({
  id,
  query,
  config,
  onChange,
  disabled = false,
}) => {
  const getPlaceholder = () => {
    switch (config) {
      case 'single':
        return 'Ask a question (e.g. "Identify all water bodies in this scene and quantify their surface area")';
      case 'cross-modal':
        return 'Ask a cross-modal question (e.g. "Cross-reference optical cloud-covered areas with SAR backscatter to locate flooded infrastructure")';
      case 'bi-temporal':
        return 'Ask a change detection question (e.g. "Detect and report urban expansion and new construction between T1 and T2 passes")';
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 space-y-3">
      <div className="flex items-center justify-between">
        <label
          htmlFor={id}
          className="text-xs font-mono uppercase tracking-wider text-slate-300"
        >
          Natural Language Query
        </label>
        <span className="text-[11px] text-slate-500">{query.trim().length} characters</span>
      </div>

      <div className="relative">
        <textarea
          id={id}
          rows={3}
          value={query}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={getPlaceholder()}
          className="w-full rounded-lg border border-slate-700 bg-slate-950/70 p-3 text-sm text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors disabled:opacity-50"
          aria-required="true"
        />
      </div>

      {/* Query Quick Suggestions */}
      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <span className="text-[11px] text-slate-400 flex items-center gap-1">
          <FileQuestion className="h-3 w-3 text-cyan-400" />
          Suggestions:
        </span>
        {config === 'single' && (
          <>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange('Identify all agricultural fields and analyze crop density.')}
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Crop density
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange('Locate water bodies and calculate coverage area.')}
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Water bodies
            </button>
          </>
        )}
        {config === 'cross-modal' && (
          <>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(
                  'Detect flooded zones where optical view is obscured by cloud cover using SAR backscatter.'
                )
              }
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Cloud-penetrating flood detection
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(
                  'Reconcile high-reflectance optical zones with SAR roughness signatures.'
                )
              }
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Optical-SAR reconciliation
            </button>
          </>
        )}
        {config === 'bi-temporal' && (
          <>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(
                  'Detect urban expansion and new building footprint changes between T1 and T2.'
                )
              }
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Urban expansion
            </button>
            <button
              type="button"
              disabled={disabled}
              onClick={() =>
                onChange(
                  'Quantify deforestation and vegetation loss between the two acquisition passes.'
                )
              }
              className="rounded bg-slate-800 hover:bg-slate-700 px-2 py-0.5 text-[11px] text-slate-300 transition-colors disabled:opacity-50"
            >
              Vegetation change
            </button>
          </>
        )}
      </div>
    </div>
  );
};
