import React, { useState } from 'react';
import { ConfigSelector, PipelineConfigMode } from '../components/Upload/ConfigSelector';
import { SlotUploader } from '../components/Upload/SlotUploader';
import { QueryResultCard } from '../components/Upload/QueryResultCard';
import { submitQuery } from '../services/api';
import type { Answer, Modality } from '../types/contracts';

interface SlotData {
  label: string;
  file: File | null;
  modality: Modality;
  isLocked: boolean;
}

export const UploadPage: React.FC = () => {
  const [mode, setMode] = useState<PipelineConfigMode>('single');
  const [query, setQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Answer | null>(null);

  const [slots, setSlots] = useState<SlotData[]>([
    { label: 'Primary Imagery', file: null, modality: 'optical', isLocked: false },
  ]);

  const handleModeChange = (newMode: PipelineConfigMode) => {
    setMode(newMode);
    setResult(null);
    setError(null);
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

  const updateSlotFile = (index: number, file: File | null) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, file } : s)));
  };

  const updateSlotModality = (index: number, modality: Modality) => {
    setSlots((prev) => prev.map((s, i) => (i === index ? { ...s, modality } : s)));
  };

  const canSubmit = !loading && query.trim().length > 0 && slots.every((s) => s.file !== null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const images: File[] = [];
      const modalities: Modality[] = [];

      slots.forEach((slot) => {
        if (slot.file) {
          images.push(slot.file);
          modalities.push(slot.modality);
        }
      });

      const response = await submitQuery({
        query: query.trim(),
        images,
        modalities,
      });

      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error or backend failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Satellite Imagery Query</h1>
        <p className="text-xs text-slate-400 mt-1">Multi-modal earth observation query and analysis pipeline</p>
      </div>

      <ConfigSelector selectedMode={mode} onSelectMode={handleModeChange} disabled={loading} />

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
        <div className="p-4 bg-rose-950/30 border border-rose-800 rounded-lg text-xs text-rose-300">
          <strong>Submission Error:</strong> {error}
        </div>
      )}

      {result && <QueryResultCard answer={result} />}
    </div>
  );
};
