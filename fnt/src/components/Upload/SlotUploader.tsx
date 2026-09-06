import React, { useRef, useState } from 'react';
import { Modality } from '../../types/contracts';

interface SlotUploaderProps {
  label: string;
  slotIndex: number;
  modality: Modality;
  isModalityLocked: boolean;
  file: File | null;
  onFileSelect: (file: File | null) => void;
  onModalityChange: (modality: Modality) => void;
  disabled?: boolean;
}

const ALLOWED_BENCHMARK_TAGS = ['sen12ms', 'levir', 'sentinel', 'benchmark', 'optical', 'sar', 't1', 't2'];

function validateSatelliteFile(file: File): string | null {
  if (file.size === 0) return 'File is empty (0 bytes).';
  const name = file.name.toLowerCase();
  const ext = name.split('.').pop() || '';
  if (['tif', 'tiff'].includes(ext)) return null;

  if (['png', 'jpg', 'jpeg'].includes(ext)) {
    const matchesBenchmark = ALLOWED_BENCHMARK_TAGS.some((tag) => name.includes(tag));
    if (!matchesBenchmark) {
      return 'PNG/JPG allowed only from recognized benchmark fixtures (e.g. SEN12MS, LEVIR-CD).';
    }
    return null;
  }
  return `Invalid extension (.${ext}). Only GeoTIFF (.tif, .tiff) or benchmark imagery allowed.`;
}

export const SlotUploader: React.FC<SlotUploaderProps> = ({
  label,
  modality,
  isModalityLocked,
  file,
  onFileSelect,
  onModalityChange,
  disabled = false,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (f: File | null) => {
    if (!f) {
      onFileSelect(null);
      setError(null);
      return;
    }
    const err = validateSatelliteFile(f);
    if (err) {
      setError(err);
      onFileSelect(null);
    } else {
      setError(null);
      onFileSelect(f);
    }
  };

  return (
    <div className="flex flex-col gap-2 p-3.5 rounded-lg border border-slate-800 bg-slate-900/50">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">{label}</span>
        <div className="flex items-center gap-1.5">
          <label className="text-[11px] text-slate-400">Modality:</label>
          {isModalityLocked ? (
            <span className="px-2 py-0.5 text-xs font-mono rounded bg-slate-800 border border-slate-700 text-cyan-400">
              {modality} (locked)
            </span>
          ) : (
            <select
              value={modality}
              disabled={disabled}
              onChange={(e) => onModalityChange(e.target.value as Modality)}
              className="bg-slate-950 border border-slate-700 rounded px-2 py-0.5 text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
            >
              <option value="optical">optical</option>
              <option value="sar">sar</option>
            </select>
          )}
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".tif,.tiff,.png,.jpg,.jpeg"
        disabled={disabled}
        className="hidden"
        onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
      />

      <div
        onClick={() => !disabled && inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!disabled && e.dataTransfer.files?.[0]) {
            handleFileChange(e.dataTransfer.files[0]);
          }
        }}
        className={`border-2 border-dashed rounded-md p-4 text-center cursor-pointer transition-colors ${
          error
            ? 'border-rose-700/60 bg-rose-950/20'
            : file
            ? 'border-emerald-700/60 bg-emerald-950/20'
            : 'border-slate-800 hover:border-slate-700 bg-slate-950/40'
        }`}
      >
        {file ? (
          <div className="flex items-center justify-between text-xs text-emerald-400">
            <span className="truncate font-mono">{file.name}</span>
            <span className="text-slate-500 text-[10px]">{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div className="text-xs text-slate-400">
            <span className="text-cyan-400 font-medium">Click to browse</span> or drag satellite image here
          </div>
        )}
      </div>

      {error && <p className="text-[11px] text-rose-400 leading-tight">{error}</p>}
    </div>
  );
};
