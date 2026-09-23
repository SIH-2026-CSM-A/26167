import React, { useState } from 'react';
import { ConfigSelector, PipelineConfigMode } from '../components/Upload/ConfigSelector';
import { DemoPresetSelector } from '../components/DemoPresetSelector';
import { SlotUploader, SlotModality } from '../components/Upload/SlotUploader';
import { ExecutionTraceToggle, QueryResultCard } from '../components/Upload/QueryResultCard';
import { submitImageQuery, QueryApiError } from '@/services/query';
import type { Answer, ExecutionTrace, Modality } from '../types/contracts';
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
  const [reasonCode, setReasonCode] = useState<string | null>(null);
  const [errorTrace, setErrorTrace] = useState<ExecutionTrace | null>(null);
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
    setReasonCode(null);
    setErrorTrace(null);
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
        setReasonCode(err.reasonCode ?? null);
        setErrorTrace(err.trace ?? null);
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
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-hi)' }}>
            Satellite Imagery Query
          </h1>
          <p className="text-xs mt-1" style={{ color: 'var(--text-mid)' }}>
            Multi-modal earth observation query and analysis pipeline
          </p>
        </div>

        <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-lg shrink-0">
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSourceChange('manual')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              sourceMode === 'manual'
                ? 'bg-cyan-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Manual Upload
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSourceChange('preset')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
              sourceMode === 'preset'
                ? 'bg-cyan-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
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
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">Analysis Query</label>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            placeholder="e.g. Identify land cover classification or detect changes"
            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className={`py-2.5 px-5 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all ${
            canSubmit
              ? 'bg-cyan-600 hover:bg-cyan-500 text-white cursor-pointer shadow-md'
              : 'bg-slate-800 text-slate-500 cursor-not-allowed'
          }`}
        >
          {loading ? 'Processing via Backend...' : 'Run Pipeline'}
        </button>
      </form>

      {error && (
        <div role="alert" className="p-4 bg-rose-950/30 border border-rose-800 rounded-lg text-xs text-rose-300">
          <div className="flex flex-wrap items-center gap-2">
            <strong>Submission Error:</strong> {error}
            {reasonCode && (
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-rose-900/60 border border-rose-700 text-rose-200">
                {reasonCode}
              </span>
            )}
          </div>
          {suggestedAction && <p className="mt-1 text-rose-300/80">{suggestedAction}</p>}
          {errorTrace && errorTrace.steps.length > 0 && (
            <div className="mt-3 border-t border-rose-800/60 pt-3">
              <ExecutionTraceToggle trace={errorTrace} />
            </div>
          )}
        </div>
      )}

      {result && <QueryResultCard answer={result} />}
    </div>
  );
};
