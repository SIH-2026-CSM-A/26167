import { setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

export const MAPLIBRE_WORKER_URL = workerUrl;

let isWorkerConfigured = false;

/** Configure MapLibre to use the Vite-bundled worker asset once per process. */
export function configureMapLibreWorker(): void {
  if (isWorkerConfigured) {
    return;
  }

  setWorkerUrl(MAPLIBRE_WORKER_URL);
  isWorkerConfigured = true;
}
