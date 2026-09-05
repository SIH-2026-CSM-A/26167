import React, { useState, useId } from 'react';
import { ConfigurationSelector } from '@/components/ConfigurationSelector';
import {
  ConfigurationUploadSection,
  type SlotData,
  type SlotTarget,
} from '@/components/ConfigurationUploadSection';
import { QueryInputField } from '@/components/QueryInputField';
import { UploadFormActions } from '@/components/UploadFormActions';
import { QueryResultCard } from '@/components/QueryResultCard';
import { UploadSidebar } from '@/components/UploadSidebar';
import { submitQuery, ApiError } from '@/services/api';
import type { Answer, InputConfiguration, Modality } from '@/services/types';
import { validateImageryFile } from '@/utils/fileValidation';

const DEFAULT_SLOT_STATE: SlotData = {
  file: null,
  modality: 'optical',
  error: null,
};

export const UploadPage: React.FC = () => {
  const queryInputId = useId();

  // Selected configuration: 'single' | 'cross-modal' | 'bi-temporal'
  const [config, setConfig] = useState<InputConfiguration>('single');

  // Single Image State
  const [singleSlot, setSingleSlot] = useState<SlotData>(DEFAULT_SLOT_STATE);

  // Cross-Modal Pair State (Fixed: 1 Optical, 1 SAR)
  const [crossOpticalSlot, setCrossOpticalSlot] = useState<SlotData>({
    file: null,
    modality: 'optical',
    error: null,
  });
  const [crossSarSlot, setCrossSarSlot] = useState<SlotData>({
    file: null,
    modality: 'sar',
    error: null,
  });

  // Bi-Temporal Pair State (T1 and T2 passes)
  const [t1Slot, setT1Slot] = useState<SlotData>({
    file: null,
    modality: 'optical',
    error: null,
  });
  const [t2Slot, setT2Slot] = useState<SlotData>({
    file: null,
    modality: 'optical',
    error: null,
  });

  // Query and execution state
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);

  // Slot update dispatchers
  const handleSlotFileSelect = (file: File, target: SlotTarget) => {
    const validation = validateImageryFile(file);
    const newSlot: SlotData = validation.valid
      ? { file, modality: 'optical', error: null }
      : { file: null, modality: 'optical', error: validation.error || 'Invalid file format.' };

    switch (target) {
      case 'single':
        setSingleSlot((prev) => ({ ...newSlot, modality: prev.modality }));
        break;
      case 'crossOptical':
        setCrossOpticalSlot({ ...newSlot, modality: 'optical' });
        break;
      case 'crossSar':
        setCrossSarSlot({ ...newSlot, modality: 'sar' });
        break;
      case 't1':
        setT1Slot((prev) => ({ ...newSlot, modality: prev.modality }));
        break;
      case 't2':
        setT2Slot((prev) => ({ ...newSlot, modality: prev.modality }));
        break;
    }
  };

  const handleSlotFileRemove = (target: SlotTarget) => {
    switch (target) {
      case 'single':
        setSingleSlot((prev) => ({ ...prev, file: null, error: null }));
        break;
      case 'crossOptical':
        setCrossOpticalSlot((prev) => ({ ...prev, file: null, error: null }));
        break;
      case 'crossSar':
        setCrossSarSlot((prev) => ({ ...prev, file: null, error: null }));
        break;
      case 't1':
        setT1Slot((prev) => ({ ...prev, file: null, error: null }));
        break;
      case 't2':
        setT2Slot((prev) => ({ ...prev, file: null, error: null }));
        break;
    }
  };

  const handleSlotModalityChange = (modality: Modality, target: 'single' | 't1' | 't2') => {
    if (target === 'single') setSingleSlot((prev) => ({ ...prev, modality }));
    else if (target === 't1') setT1Slot((prev) => ({ ...prev, modality }));
    else if (target === 't2') setT2Slot((prev) => ({ ...prev, modality }));
  };

  // Validation calculations
  const isQueryValid = query.trim().length > 0;
  const isSingleValid = config === 'single' && !!singleSlot.file && !singleSlot.error;
  const isCrossModalValid =
    config === 'cross-modal' &&
    !!crossOpticalSlot.file &&
    !crossOpticalSlot.error &&
    !!crossSarSlot.file &&
    !crossSarSlot.error;
  const isBiTemporalValid =
    config === 'bi-temporal' &&
    !!t1Slot.file &&
    !t1Slot.error &&
    !!t2Slot.file &&
    !t2Slot.error;

  const areFilesValid =
    config === 'single'
      ? isSingleValid
      : config === 'cross-modal'
      ? isCrossModalValid
      : isBiTemporalValid;

  const isFormValid = isQueryValid && areFilesValid;

  const getValidationHint = (): string | null => {
    if (!isQueryValid && !areFilesValid) return 'Upload required imagery and enter a query.';
    if (!areFilesValid) {
      if (config === 'single') {
        return singleSlot.error || 'Please upload one satellite image (TIFF or PNG/JPEG).';
      }
      if (config === 'cross-modal') {
        if (!crossOpticalSlot.file) return 'Please upload the Optical image.';
        if (!crossSarSlot.file) return 'Please upload the SAR image.';
        return crossOpticalSlot.error || crossSarSlot.error || null;
      }
      if (config === 'bi-temporal') {
        if (!t1Slot.file) return 'Please upload the T1 pass image.';
        if (!t2Slot.file) return 'Please upload the T2 pass image.';
        return t1Slot.error || t2Slot.error || null;
      }
    }
    return !isQueryValid ? 'Please enter a natural language query for the assistant.' : null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid || isLoading) return;

    setBackendError(null);
    setAnswer(null);
    setIsLoading(true);

    try {
      const items: Array<{ file: File; modality: Modality }> = [];
      if (config === 'single' && singleSlot.file) {
        items.push({ file: singleSlot.file, modality: singleSlot.modality });
      } else if (config === 'cross-modal' && crossOpticalSlot.file && crossSarSlot.file) {
        items.push({ file: crossOpticalSlot.file, modality: 'optical' });
        items.push({ file: crossSarSlot.file, modality: 'sar' });
      } else if (config === 'bi-temporal' && t1Slot.file && t2Slot.file) {
        items.push({ file: t1Slot.file, modality: t1Slot.modality });
        items.push({ file: t2Slot.file, modality: t2Slot.modality });
      }

      const response = await submitQuery({ query, items });
      setAnswer(response);
    } catch (err: unknown) {
      if (err instanceof ApiError) setBackendError(err.message);
      else if (err instanceof Error) setBackendError(err.message);
      else setBackendError('An unexpected error occurred while communicating with the backend.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setAnswer(null);
    setBackendError(null);
    setQuery('');
    setSingleSlot(DEFAULT_SLOT_STATE);
    setCrossOpticalSlot({ file: null, modality: 'optical', error: null });
    setCrossSarSlot({ file: null, modality: 'sar', error: null });
    setT1Slot({ file: null, modality: 'optical', error: null });
    setT2Slot({ file: null, modality: 'optical', error: null });
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Remote Sensing Data Ingestion
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Upload single, bi-temporal, or cross-modal (optical + SAR) satellite imagery.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
              <span className="h-2 w-2 rounded-full bg-cyan-400" />
              <span>POST /query Service</span>
            </span>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        <section className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            <ConfigurationSelector
              config={config}
              onChange={(newConfig) => {
                setConfig(newConfig);
                setAnswer(null);
              }}
            />

            <ConfigurationUploadSection
              config={config}
              singleSlot={singleSlot}
              crossOpticalSlot={crossOpticalSlot}
              crossSarSlot={crossSarSlot}
              t1Slot={t1Slot}
              t2Slot={t2Slot}
              onFileSelect={handleSlotFileSelect}
              onFileRemove={handleSlotFileRemove}
              onModalityChange={handleSlotModalityChange}
            />

            <QueryInputField
              id={queryInputId}
              query={query}
              config={config}
              onChange={setQuery}
              disabled={isLoading}
            />

            <UploadFormActions
              isFormValid={isFormValid}
              isLoading={isLoading}
              validationHint={getValidationHint()}
              backendError={backendError}
              onReset={handleReset}
            />
          </form>

          {answer && <QueryResultCard answer={answer} onReset={handleReset} />}
        </section>

        <UploadSidebar config={config} />
      </div>
    </main>
  );
};
