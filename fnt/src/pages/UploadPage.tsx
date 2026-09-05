import React, { useRef, useState } from 'react';
import { UploadCloud, Layers, AlertCircle, FileCheck, X } from 'lucide-react';

export const UploadPage: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newFiles = Array.from(files);
    setSelectedFiles((prev) => [...prev, ...newFiles]);
    console.log('Ingested files:', newFiles);
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    // Reset value so the exact same file can be selected again if needed
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent<HTMLElement>) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent<HTMLElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const removeFile = (indexToRemove: number) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Remote Sensing Data Ingestion
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Upload single, bi-temporal, or cross-modal (optical + SAR) satellite imagery.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".tif,.tiff,.png,.jpg,.jpeg"
          multiple
          className="hidden"
        />

        {/* Drop & Select Area */}
        <section
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`lg:col-span-2 rounded-xl border border-dashed p-10 text-center transition-colors ${
            isDragging
              ? 'border-cyan-400 bg-cyan-950/30'
              : 'border-slate-700 bg-slate-900/40 hover:border-cyan-500/50'
          }`}
        >
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-cyan-950/60 text-cyan-400 border border-cyan-500/20">
            <UploadCloud className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-base font-semibold text-white">
            Drag & drop GeoTIFF / TIFF / PNG files
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Supports Optical (Sentinel-2, Cartosat) and SAR (Sentinel-1, RISAT-1) modalities
          </p>
          <div className="mt-6 flex justify-center">
            <button
              type="button"
              onClick={handleButtonClick}
              className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-cyan-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 transition-colors"
            >
              Select Imagery Files
            </button>
          </div>

          {/* List of uploaded files */}
          {selectedFiles.length > 0 && (
            <div className="mt-8 text-left border-t border-slate-800 pt-5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
                Selected Files ({selectedFiles.length})
              </h3>
              <ul className="space-y-2">
                {selectedFiles.map((file, idx) => (
                  <li
                    key={idx}
                    className="flex items-center justify-between rounded-lg bg-slate-800/60 px-3 py-2 text-xs text-slate-200 border border-slate-700/60"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FileCheck className="h-4 w-4 text-cyan-400 shrink-0" />
                      <span className="font-medium truncate">{file.name}</span>
                      <span className="text-slate-400">({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(idx)}
                      className="text-slate-400 hover:text-red-400 ml-2"
                      title="Remove file"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Right Info Panels */}
        <aside className="space-y-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <Layers className="h-4 w-4 text-cyan-400" />
              <span>Modalities Supported</span>
            </div>
            <ul className="mt-3 space-y-2 text-xs text-slate-300">
              <li className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>Optical Imagery</span>
                <span className="font-mono text-cyan-400">RGB / NIR</span>
              </li>
              <li className="flex items-center justify-between py-1 border-b border-slate-800">
                <span>SAR Imagery</span>
                <span className="font-mono text-cyan-400">VV / VH (dB)</span>
              </li>
              <li className="flex items-center justify-between py-1">
                <span>Bi-temporal Pair</span>
                <span className="font-mono text-cyan-400">T1 / T2</span>
              </li>
            </ul>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
            <div className="flex items-center gap-2 text-sm font-semibold text-amber-300">
              <AlertCircle className="h-4 w-4 text-amber-400" />
              <span>Ingestion Notice</span>
            </div>
            <p className="mt-2 text-xs text-slate-400 leading-relaxed">
              Files are checked for spatial alignment, projection CRS, and band order prior to
              forwarding to the inference pipeline.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
};