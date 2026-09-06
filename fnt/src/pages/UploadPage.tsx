import React, { useState } from 'react';
import {
  AlertCircle,
  FileImage,
  Layers,
  LoaderCircle,
  ShieldCheck,
  UploadCloud,
} from 'lucide-react';
import { submitImageQuery } from '@/services/query';
import type { Answer } from '@/types/query';

/** Render the real single-raster upload, VQA response, evidence, and trace workflow. */
export const UploadPage: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [query, setQuery] = useState('');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  /** Store the selected TIFF and clear output belonging to an earlier asset. */
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(event.target.files?.[0] ?? null);
    setAnswer(null);
    setError(null);
  };

  /** Submit the exact file and question to the backend and expose success or failure. */
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedFile) {
      setError('Select a GeoTIFF or TIFF image.');
      return;
    }
    setIsLoading(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await submitImageQuery(selectedFile, query));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Analysis failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-7 max-w-3xl">
        <p className="mb-2 font-mono text-xs uppercase tracking-[0.2em] text-cyan-400">
          Single-image VQA
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
          Remote Sensing Data Ingestion
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          Upload one GeoTIFF, ask a visually answerable question, and inspect the verified model
          answer with its source evidence and execution trace.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-7 lg:grid-cols-[minmax(0,1.35fr)_minmax(19rem,0.65fr)]">
        <form onSubmit={handleSubmit} className="space-y-6">
          <section className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-9 text-center transition-colors focus-within:border-cyan-500/70 hover:border-cyan-500/50 sm:px-10">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-cyan-500/20 bg-cyan-950/60 text-cyan-400">
              <UploadCloud className="h-7 w-7" />
            </div>
            <h2 className="mt-4 text-base font-semibold text-white">GeoTIFF / TIFF source</h2>
            <p className="mt-1 text-xs text-slate-400">
              Raster bytes and geospatial metadata are processed by the backend.
            </p>
            <label
              htmlFor="raster-file"
              className="mt-6 inline-flex cursor-pointer items-center justify-center rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-cyan-500 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-cyan-500"
            >
              Select imagery file
              <input
                id="raster-file"
                aria-label="GeoTIFF or TIFF image"
                className="sr-only"
                type="file"
                accept=".tif,.tiff,image/tiff,image/geotiff"
                onChange={handleFileChange}
              />
            </label>
            {selectedFile && (
              <div className="mx-auto mt-5 flex max-w-md items-center justify-center gap-2 text-sm text-slate-200">
                <FileImage className="h-4 w-4 text-cyan-400" />
                <span>{selectedFile.name}</span>
                <span className="text-slate-500">{formatBytes(selectedFile.size)}</span>
              </div>
            )}
          </section>

          <div>
            <label htmlFor="image-query" className="text-sm font-medium text-slate-200">
              Question about this image
            </label>
            <textarea
              id="image-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              rows={3}
              required
              placeholder="Describe the major visible land-cover or geographic features."
              className="mt-2 w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white placeholder-slate-500 outline-none transition focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading || !selectedFile || !query.trim()}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-cyan-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            {isLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
            {isLoading ? 'Running InternVL2-2B…' : 'Run analysis'}
          </button>

          {error && (
            <div role="alert" className="flex gap-3 border-l-2 border-rose-500 bg-rose-950/30 p-4 text-sm text-rose-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </form>

        <aside className="space-y-6 border-t border-slate-800 pt-6 lg:border-l lg:border-t-0 lg:pl-7 lg:pt-0">
          {!answer ? (
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Layers className="h-4 w-4 text-cyan-400" />
                <span>Analysis output</span>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-slate-400">
                The verified answer, uploaded-asset provenance, and trace will appear here after
                the backend completes.
              </p>
            </div>
          ) : (
            <div className="space-y-7" aria-live="polite">
              <section>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  <ShieldCheck className="h-4 w-4" />
                  Verified answer
                </div>
                <p className="mt-3 text-base leading-7 text-slate-100">
                  {answer.text || answer.abstention_reason}
                </p>
              </section>

              <section>
                <h2 className="text-sm font-semibold text-white">Evidence</h2>
                <div className="mt-3 space-y-4">
                  {answer.evidence.map((item) => (
                    <dl key={item.id} className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-2 border-l border-slate-700 pl-4 text-xs">
                      <dt className="text-slate-500">Source</dt>
                      <dd className="break-all text-slate-200">
                        {item.payload.source_filename ?? item.payload.source_asset_id}
                      </dd>
                      <dt className="text-slate-500">Model</dt>
                      <dd className="break-all text-slate-200">{item.payload.model_id}</dd>
                      <dt className="text-slate-500">Tool</dt>
                      <dd className="font-mono text-cyan-400">{item.tool}</dd>
                    </dl>
                  ))}
                </div>
              </section>

              <details className="border-t border-slate-800 pt-4 text-xs text-slate-300">
                <summary className="cursor-pointer font-semibold text-slate-200">
                  Execution trace · {answer.trace.steps.length} steps
                </summary>
                <ol className="mt-4 space-y-2 border-l border-slate-700 pl-4 font-mono">
                  {answer.trace.steps.map((step, index) => (
                    <li key={`${step.action}-${index}`}>
                      <span className="text-slate-500">{step.module}</span>
                      <span className="mx-2 text-slate-700">/</span>
                      <span className="text-cyan-300">{step.action}</span>
                    </li>
                  ))}
                </ol>
              </details>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
};

/** Format upload size as an honest byte or kibibyte value. */
function formatBytes(size: number): string {
  const bytesPerKibibyte = 1024;
  return size < bytesPerKibibyte
    ? `${size} B`
    : `${(size / bytesPerKibibyte).toFixed(1)} KiB`;
}
