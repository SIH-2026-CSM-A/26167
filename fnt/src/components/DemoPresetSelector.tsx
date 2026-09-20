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
      <div
        role="alert"
        className="rounded-lg p-4 text-xs"
        style={{ background: 'rgba(210,87,75,0.12)', border: '1px solid var(--danger)', color: 'var(--danger)' }}
      >
        {error}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-4 text-xs" style={{ color: 'var(--text-low)' }}>
        Loading demo presets...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <label
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          Curated Demo Presets (F24)
        </label>
        <span className="text-[11px]" style={{ color: 'var(--text-low)' }}>
          Auto-populates query &amp; verified imagery
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2 lg:grid-cols-3">
        {presets.map((preset) => {
          const isSelected = selectedPresetId === preset.id;
          const isLoadingThis = loadingPresetId === preset.id;
          const isDisabled = disabled || loadingPresetId !== null;
          return (
            <button
              key={preset.id}
              type="button"
              disabled={isDisabled}
              onClick={() => handleSelectPreset(preset)}
              className={`flex flex-col justify-between rounded-lg border p-3 text-left transition-all ${
                isDisabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
              }`}
              style={
                isSelected
                  ? { borderColor: 'var(--accent)', background: 'var(--bg-2)', color: 'var(--text-hi)' }
                  : { borderColor: 'var(--line)', background: 'var(--bg-2)', color: 'var(--text-mid)' }
              }
            >
              <div>
                <div className="mb-1 flex items-center justify-between gap-1.5">
                  <span
                    className="truncate text-xs font-semibold"
                    style={{ color: isSelected ? 'var(--accent)' : 'var(--text-hi)' }}
                  >
                    {preset.label}
                  </span>
                  <span
                    className="shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase"
                    style={{
                      background: 'var(--bg-1)',
                      border: '1px solid var(--line)',
                      color: 'var(--accent)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {preset.scenario.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="line-clamp-2 text-[11px] italic leading-snug" style={{ color: 'var(--text-low)' }}>
                  &quot;{preset.query}&quot;
                </p>
              </div>

              <div
                className="mt-2.5 flex items-center justify-between pt-1.5 text-[10px]"
                style={{ color: 'var(--text-low)', borderTop: '1px solid var(--line-soft)' }}
              >
                <span>
                  {preset.assets.length} {preset.assets.length === 1 ? 'asset' : 'assets'}
                </span>
                {isLoadingThis ? (
                  <span className="animate-pulse font-medium" style={{ color: 'var(--accent)' }}>
                    Loading files...
                  </span>
                ) : isSelected ? (
                  <span className="font-medium" style={{ color: 'var(--accent)' }}>Active</span>
                ) : (
                  <span>Select preset</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
