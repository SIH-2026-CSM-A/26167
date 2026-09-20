import type { Evidence } from '@/types/contracts';
import { evidenceToFeatures, getCollectionBounds } from './evidenceGeoJson';

function toDms(value: number): string {
  const abs = Math.abs(value);
  const deg = Math.floor(abs);
  const minFloat = (abs - deg) * 60;
  const min = Math.floor(minFloat);
  const sec = Math.round((minFloat - min) * 60);
  return `${String(deg).padStart(2, '0')}° ${String(min).padStart(2, '0')}' ${String(sec).padStart(2, '0')}"`;
}

/** Real lat/long readout derived from the current query's evidence geometry — never a
 * hardcoded placeholder. Returns null when there is no evidence to center on. */
export function centroidReadout(evidenceList: Evidence[]): string | null {
  const bounds = getCollectionBounds(evidenceToFeatures(evidenceList));
  if (!bounds) return null;
  const [west, south, east, north] = bounds;
  const lon = (west + east) / 2;
  const lat = (south + north) / 2;
  return `${toDms(lat)} ${lat >= 0 ? 'N' : 'S'} / ${toDms(lon)} ${lon >= 0 ? 'E' : 'W'}`;
}
