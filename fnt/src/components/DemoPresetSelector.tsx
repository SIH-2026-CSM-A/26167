import React, { useEffect, useState } from 'react';
import type { DemoPreset, PresetApplyPayload } from '@/types/manifest';
import {
  DEFAULT_MANIFEST_URL,
  FALLBACK_ERROR_BANNER,
  fetchManifestData,
  loadPresetAssetFiles,
  mapPresetToSlotsAndMode,
} from '@/utils/demoPresets';

export interface DemoPresetSelectorProps {
  manifestUrl?: string;
  onSelectPreset: (payload: PresetApplyPayload) => void;
  selectedPresetId?: string | null;
  disabled?: boolean;
}

export const DemoPresetSelector: React.FC<DemoPresetSelectorProps> = ({
  manifestUrl = DEFAULT_MANIFEST_URL,
  onSelectPreset,
  selectedPresetId = null,
  disabled = false,
}) => {
  const [presets, setPresets] = useState<DemoPreset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingPresetId, setLoadingPresetId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchManifestData(manifestUrl);
        if (isMounted) setPresets(data);
      } catch {
        if (isMounted) setError(FALLBACK_ERROR_BANNER);
      } finally {
        if (isMounted) setLoading(false);
      }
    };
    void load();
    return () => {
      isMounted = false;
    };
  }, [manifestUrl]);

  const handleSelectPreset = async (preset: DemoPreset) => {
    try {
      setLoadingPresetId(preset.id);
      setError(null);
      const filesByRole = await loadPresetAssetFiles(preset, manifestUrl);
      const { mode, slots } = mapPresetToSlotsAndMode(preset, filesByRole);
      onSelectPreset({ preset, mode, slots, query: preset.query });
    } catch {
      setError(FALLBACK_ERROR_BANNER);
    } finally {
      setLoadingPresetId(null);
    }
  };

  if (error) {
    return (
      <div role="alert" className="p-4 bg-rose-950/30 border border-rose-800 rounded-lg text-xs text-rose-300">
        {error}
      </div>
    );
  }

  if (loading) {
    return <div className="p-4 text-xs text-slate-400">Loading demo presets...</div>;
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">
          Curated Demo Presets (F24)
        </label>
        <span className="text-[11px] text-slate-500">Auto-populates query & verified imagery</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {presets.map((preset) => {
          const isSelected = selectedPresetId === preset.id;
          const isLoadingThis = loadingPresetId === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              disabled={disabled || loadingPresetId !== null}
              onClick={() => handleSelectPreset(preset)}
              className={`text-left p-3 rounded-lg border transition-all flex flex-col justify-between ${
                isSelected
                  ? 'border-cyan-500 bg-cyan-950/40 text-cyan-200 shadow-sm shadow-cyan-950 ring-1 ring-cyan-500'
                  : 'border-slate-800 bg-slate-900/60 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
              } ${disabled || loadingPresetId !== null ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <div>
                <div className="flex items-center justify-between gap-1.5 mb-1">
                  <span className="font-semibold text-xs text-slate-100 truncate">{preset.label}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded uppercase font-mono bg-slate-800 text-cyan-400 border border-slate-700 shrink-0">
                    {preset.scenario.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2 leading-snug italic">"{preset.query}"</p>
              </div>

              <div className="mt-2.5 flex items-center justify-between text-[10px] text-slate-500 border-t border-slate-800/80 pt-1.5">
                <span>{preset.assets.length} {preset.assets.length === 1 ? 'asset' : 'assets'}</span>
                {isLoadingThis ? (
                  <span className="text-cyan-400 animate-pulse font-medium">Loading files...</span>
                ) : isSelected ? (
                  <span className="text-emerald-400 font-medium">Active</span>
                ) : (
                  <span className="text-slate-500">Select preset</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
