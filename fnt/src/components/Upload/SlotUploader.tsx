import React, { useRef, useState } from 'react';
import { Modality } from '../../types/contracts';

export type SlotModality = Modality | 'auto';

interface SlotUploaderProps {
  label: string;
  slotIndex: number;
  modality: SlotModality;
  isModalityLocked: boolean;
  file: File | null;
  onFileSelect: (file: File | null) => void;
  onModalityChange: (modality: SlotModality) => void;
  disabled?: boolean;
  /** Set when a prior submit was vetoed as MODALITY_UNKNOWN and this slot was sent as 'auto' —
   * it's one of the images that could have been the ambiguous one. */
  needsClarification?: boolean;
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
  needsClarification = false,
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
    <div
      className="flex flex-col gap-2 rounded-lg p-3.5"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--line)' }}
    >
      <div className="flex items-center justify-between">
        <span
          className="text-[11px] font-medium uppercase tracking-widest"
          style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
        >
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          <label className="text-[11px]" style={{ color: 'var(--text-low)' }}>
            Modality:
          </label>
          {isModalityLocked ? (
            <span
              className="rounded px-2 py-0.5 text-xs"
              style={{
                background: 'var(--bg-1)',
                border: '1px solid var(--line)',
                color: 'var(--accent)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {modality} (locked)
            </span>
          ) : (
            <select
              value={modality}
              disabled={disabled}
              onChange={(e) => onModalityChange(e.target.value as SlotModality)}
              className="rounded px-2 py-0.5 text-xs outline-none"
              style={{
                background: 'var(--bg-1)',
                border: `1px solid ${needsClarification ? '#e3a66c' : 'var(--line)'}`,
                color: 'var(--text-mid)',
              }}
            >
              <option value="auto">auto-detect</option>
              <option value="optical">optical</option>
              <option value="sar">sar</option>
            </select>
          )}
        </div>
      </div>

      {needsClarification && (
        <p className="text-[11px]" style={{ color: '#e3a66c' }}>
          ⚠ Could be the image the backend couldn&apos;t classify — pick Optical or SAR.
        </p>
      )}

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
        className="cursor-pointer rounded-md border-2 border-dashed p-4 text-center transition-colors"
        style={
          error
            ? { borderColor: 'rgba(210,87,75,0.6)', background: 'rgba(210,87,75,0.08)' }
            : file
            ? { borderColor: 'rgba(94,234,212,0.5)', background: 'var(--accent-dim)' }
            : { borderColor: 'var(--line)', background: 'var(--bg-1)' }
        }
      >
        {file ? (
          <div className="flex items-center justify-between text-xs" style={{ color: 'var(--accent)' }}>
            <span className="truncate" style={{ fontFamily: 'var(--font-mono)' }}>{file.name}</span>
            <span className="text-[10px]" style={{ color: 'var(--text-low)' }}>{(file.size / 1024).toFixed(1)} KB</span>
          </div>
        ) : (
          <div className="text-xs" style={{ color: 'var(--text-low)' }}>
            <span className="font-medium" style={{ color: 'var(--accent)' }}>Click to browse</span> or drag satellite image here
          </div>
        )}
      </div>

      {error && <p className="text-[11px] leading-tight" style={{ color: 'var(--danger)' }}>{error}</p>}
    </div>
  );
};
