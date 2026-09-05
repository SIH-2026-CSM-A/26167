import React, { useRef, useState, useEffect } from 'react';
import {
  UploadCloud,
  FileImage,
  Trash2,
  AlertCircle,
  CheckCircle2,
  Eye,
  Radio,
} from 'lucide-react';
import type { Modality } from '@/services/types';
import {
  formatBytes,
  ACCEPTED_FILE_TYPES_ATTR,
} from '@/utils/fileValidation';

export interface ImageUploadSlotProps {
  id: string;
  label: string;
  sublabel?: string;
  file: File | null;
  modality: Modality;
  allowModalityChange?: boolean;
  required?: boolean;
  error?: string | null;
  onFileSelect: (file: File) => void;
  onFileRemove: () => void;
  onModalityChange?: (modality: Modality) => void;
}

export const ImageUploadSlot: React.FC<ImageUploadSlotProps> = ({
  id,
  label,
  sublabel,
  file,
  modality,
  allowModalityChange = true,
  required = false,
  error,
  onFileSelect,
  onFileRemove,
  onModalityChange,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Generate object URL preview for browser-supported formats (png/jpg/jpeg)
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }

    const name = file.name.toLowerCase();
    if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [file]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      onFileSelect(selected);
    }
    // Reset input value so re-uploading the same file still triggers onChange
    if (e.target) {
      e.target.value = '';
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      onFileSelect(droppedFile);
    }
  };

  const isGeoTiff =
    file && (file.name.toLowerCase().endsWith('.tif') || file.name.toLowerCase().endsWith('.tiff'));

  return (
    <div
      className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/60 p-5 transition-all hover:border-slate-700"
      role="region"
      aria-labelledby={`${id}-label`}
    >
      {/* Header & Modality Controls */}
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2">
            <h3 id={`${id}-label`} className="text-sm font-semibold text-white">
              {label}
            </h3>
            {required && (
              <span className="rounded bg-cyan-950/80 px-1.5 py-0.5 text-[10px] font-medium text-cyan-400 border border-cyan-500/30">
                Required
              </span>
            )}
          </div>
          {sublabel && <p className="mt-0.5 text-xs text-slate-400">{sublabel}</p>}
        </div>

        {/* Modality Selector / Badge */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Modality:</span>
          {allowModalityChange && onModalityChange ? (
            <div className="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800">
              <button
                type="button"
                onClick={() => onModalityChange('optical')}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                  modality === 'optical'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                aria-pressed={modality === 'optical'}
              >
                <Eye className="h-3 w-3" />
                <span>Optical</span>
              </button>
              <button
                type="button"
                onClick={() => onModalityChange('sar')}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                  modality === 'sar'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
                aria-pressed={modality === 'sar'}
              >
                <Radio className="h-3 w-3" />
                <span>SAR</span>
              </button>
            </div>
          ) : (
            <span
              className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-mono font-medium uppercase border ${
                modality === 'optical'
                  ? 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40'
                  : 'bg-indigo-950/60 text-indigo-300 border-indigo-500/40'
              }`}
            >
              {modality === 'optical' ? (
                <Eye className="h-3 w-3" />
              ) : (
                <Radio className="h-3 w-3" />
              )}
              <span>{modality}</span>
            </span>
          )}
        </div>
      </div>

      {/* Main Upload / File Zone */}
      <div className="mt-4 flex-1">
        {!file ? (
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
              isDragOver
                ? 'border-cyan-400 bg-cyan-950/20'
                : error
                ? 'border-red-500/50 bg-red-950/10'
                : 'border-slate-700/80 bg-slate-950/40 hover:border-slate-600'
            }`}
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-cyan-950/70 text-cyan-400 border border-cyan-500/30">
              <UploadCloud className="h-5 w-5" />
            </div>
            <p className="mt-3 text-xs font-medium text-slate-200">
              Drag and drop satellite imagery file here
            </p>
            <p className="mt-1 text-[11px] text-slate-400">
              GeoTIFF/TIFF (<span className="font-mono text-slate-300">.tif, .tiff</span>) or
              Benchmark PNG/JPEG (<span className="font-mono text-slate-300">.png, .jpg</span>)
            </p>

            <input
              ref={fileInputRef}
              id={id}
              type="file"
              accept={ACCEPTED_FILE_TYPES_ATTR}
              onChange={handleFileChange}
              className="sr-only"
              aria-label={`Upload file for ${label}`}
            />

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="mt-4 rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-white border border-slate-700 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-500"
            >
              Browse Local File
            </button>
          </div>
        ) : (
          <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
            <div className="flex items-start gap-3">
              {/* Preview Thumbnail or Format Icon */}
              <div className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 overflow-hidden">
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt={file.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center text-center p-1">
                    <FileImage className="h-6 w-6 text-cyan-400" />
                    <span className="mt-1 text-[9px] font-mono uppercase text-slate-400">
                      {isGeoTiff ? 'GeoTIFF' : 'Image'}
                    </span>
                  </div>
                )}
              </div>

              {/* File Info */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  <p className="truncate text-xs font-medium text-slate-200" title={file.name}>
                    {file.name}
                  </p>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                  <span>{formatBytes(file.size)}</span>
                  <span>•</span>
                  <span className="font-mono text-cyan-400">
                    {isGeoTiff ? 'Geospatial Raster' : file.type || 'Benchmark Image'}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="inline-flex items-center rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                    Modality: {modality.toUpperCase()}
                  </span>
                </div>
              </div>

              {/* Remove Button */}
              <button
                type="button"
                onClick={onFileRemove}
                className="rounded-md p-1.5 text-slate-400 hover:bg-red-950/40 hover:text-red-400 transition-colors"
                title="Remove file"
                aria-label={`Remove file ${file.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Inline Slot Error Display */}
      {error && (
        <div
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-950/30 p-2.5 text-xs text-red-300"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};
