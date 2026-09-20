import React, { useState } from 'react';
import { ConfigSelector, PipelineConfigMode } from '../components/Upload/ConfigSelector';
import { DemoPresetSelector } from '../components/DemoPresetSelector';
import { SlotUploader, SlotModality } from '../components/Upload/SlotUploader';
import { QueryResultCard } from '../components/Upload/QueryResultCard';
import { submitImageQuery, QueryApiError } from '@/services/query';
import type { Answer, Modality } from '../types/contracts';
import type { PresetApplyPayload, PresetSlotData } from '../types/manifest';

export type UploadSourceMode = 'manual' | 'preset';

export interface SlotData {
  label: string;
  file: File | null;
  modality: SlotModality;
  isLocked: boolean;
}

export const UploadPage: React.FC = () => {
  const [sourceMode, setSourceMode] = useState<UploadSourceMode>('manual');
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [mode, setMode] = useState<PipelineConfigMode>('single');
  const [query, setQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestedAction, setSuggestedAction] = useState<string | null>(null);
  const [ambiguousSlots, setAmbiguousSlots] = useState<boolean[]>([]);
  const [result, setResult] = useState<Answer | null>(null);

  const [slots, setSlots] = useState<SlotData[]>([
    { label: 'Primary Imagery', file: null, modality: 'optical', isLocked: false },
  ]);

  const handleSourceChange = (newSource: UploadSourceMode) => {
    setSourceMode(newSource);
    setError(null);
    setResult(null);
  };

  const handleModeChange = (newMode: PipelineConfigMode) => {
    setMode(newMode);
    setResult(null);
    setError(null);
    setSelectedPresetId(null);
    if (newMode === 'single') {
      setSlots([{ label: 'Primary Imagery', file: null, modality: 'optical', isLocked: false }]);
    } else if (newMode === 'cross-modal') {
      setSlots([
        { label: 'Slot 1 (Optical)', file: null, modality: 'optical', isLocked: true },
        { label: 'Slot 2 (SAR)', file: null, modality: 'sar', isLocked: true },
      ]);
    } else {
      setSlots([
        { label: 'Slot 1 (T1 Pass)', file: null, modality: 'optical', isLocked: false },
        { label: 'Slot 2 (T2 Pass)', file: null, modality: 'optical', isLocked: false },
      ]);
    }
  };

  const handleSelectPreset = (payload: PresetApplyPayload) => {
    setMode(payload.mode);
    setSlots(payload.slots as PresetSlotData[]);
    setQuery(payload.query);
    setSelectedPresetId(payload.preset.id);
    setError(null);
    setResult(null);
  };

  const updateSlotFile = (index: number, file: File | null) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, file } : s)));
    setAmbiguousSlots([]);
  };

  const updateSlotModality = (index: number, modality: SlotModality) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, modality } : s)));
    setAmbiguousSlots([]);
  };

  const canSubmit = !loading && query.trim().length > 0 && slots.every((s) => s.file !== null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    const selectedFiles = slots.map((slot) => slot.file).filter((file): file is File => file !== null);
    if (selectedFiles.length !== slots.length) {
      setError('Select a GeoTIFF or TIFF image.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuggestedAction(null);
    setResult(null);

    // Omitting the whole `modality` override lets the backend classify every image from
    // raster metadata (B4) instead of assuming optical — the only way to actually reach
    // MODALITY_UNKNOWN. Mixing an explicit override for one slot with auto-detect for
    // another isn't a shape the backend's `modality` form field supports, so any slot set
    // to 'auto' means none of them are sent.
    const hasAutoSlot = slots.some((slot) => slot.modality === 'auto');
    const modalityOverride = hasAutoSlot ? undefined : (slots.map((slot) => slot.modality) as Modality[]);

    // Slot index IS the temporal order (Slot 1 = 0/before, Slot 2 = 1/after) — sent so
    // the router can bind CHANGE_VQA pre/post images by declared order, not arrival order.
    const captureOrder = slots.map((_, index) => index);

    try {
      const response = await submitImageQuery(
        selectedFiles,
        query.trim(),
        modalityOverride,
        captureOrder
      );
      setResult(response);
      setAmbiguousSlots([]);
    } catch (err) {
      if (err instanceof QueryApiError) {
        setError(err.message);
        setSuggestedAction(err.suggestedAction ?? null);
        // Only 'auto' slots could have been the one the backend couldn't classify —
        // an explicit override can never trigger MODALITY_UNKNOWN.
        setAmbiguousSlots(
          err.reasonCode === 'MODALITY_UNKNOWN' ? slots.map((slot) => slot.modality === 'auto') : []
        );
      } else {
        setError(err instanceof Error ? err.message : 'Network error or backend failed.');
        setAmbiguousSlots([]);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col gap-6">
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4"
        style={{ borderBottom: '1px solid var(--line)' }}
      >
        <div>
          <h1 className="text-2xl" style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }}>
            Satellite Imagery Query
          </h1>
          <p className="text-xs mt-1" style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}>
            Multi-modal earth observation query and analysis pipeline
          </p>
        </div>

        <div
          className="flex items-center gap-1.5 rounded-lg p-1 shrink-0"
          style={{ background: 'var(--bg-2)', border: '1px solid var(--line)' }}
        >
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSourceChange('manual')}
            className="rounded-md px-3 py-1.5 text-xs font-semibold transition-all"
            style={
              sourceMode === 'manual'
                ? { background: 'var(--accent)', color: 'var(--bg-0)' }
                : { color: 'var(--text-low)' }
            }
          >
            Manual Upload
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSourceChange('preset')}
            className="rounded-md px-3 py-1.5 text-xs font-semibold transition-all"
            style={
              sourceMode === 'preset'
                ? { background: 'var(--accent)', color: 'var(--bg-0)' }
                : { color: 'var(--text-low)' }
            }
          >
            Demo Presets
          </button>
        </div>
      </div>

      {sourceMode === 'manual' ? (
        <ConfigSelector selectedMode={mode} onSelectMode={handleModeChange} disabled={loading} />
      ) : (
        <DemoPresetSelector
          onSelectPreset={handleSelectPreset}
          selectedPresetId={selectedPresetId}
          disabled={loading}
        />
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className={`grid gap-4 ${slots.length > 1 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`}>
          {slots.map((slot, index) => (
            <SlotUploader
              key={index}
              label={slot.label}
              slotIndex={index}
              modality={slot.modality}
              isModalityLocked={slot.isLocked}
              file={slot.file}
              onFileSelect={(f) => updateSlotFile(index, f)}
              onModalityChange={(m) => updateSlotModality(index, m)}
              disabled={loading}
              needsClarification={ambiguousSlots[index] ?? false}
            />
          ))}
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            className="text-[11px] font-medium uppercase tracking-widest"
            style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
          >
            Analysis Query
          </label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            placeholder="e.g. Identify land cover classification or detect changes"
            className="w-full rounded-lg px-3.5 py-2.5 text-sm outline-none transition-colors"
            style={{ background: 'var(--bg-2)', border: '1px solid var(--line)', color: 'var(--text-hi)' }}
          />
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-lg px-5 py-2.5 text-xs font-semibold uppercase tracking-wider transition-all disabled:cursor-not-allowed"
          style={
            canSubmit
              ? { background: 'var(--accent)', color: 'var(--bg-0)' }
              : { background: 'var(--bg-2)', color: 'var(--text-low)' }
          }
        >
          {loading ? 'Processing via Backend...' : 'Run Pipeline'}
        </button>
      </form>

      {error && (
        <div
          role="alert"
          className="rounded-lg p-4 text-xs"
          style={{ background: 'rgba(210,87,75,0.12)', border: '1px solid var(--danger)', color: 'var(--danger)' }}
        >
          <strong>Submission Error:</strong> {error}
          {suggestedAction && <p className="mt-1" style={{ color: 'var(--text-mid)' }}>{suggestedAction}</p>}
        </div>
      )}

      {result && <QueryResultCard answer={result} />}
    </div>
  );
};
