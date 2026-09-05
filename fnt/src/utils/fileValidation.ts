/**
 * Client-side file validation per Problem Statement:
 * - GeoTIFF/TIFF (.tif, .tiff) for geospatial imagery
 * - PNG/JPEG (.png, .jpg, .jpeg) for prescribed public benchmark datasets
 */

export const ALLOWED_GEOTIFF_EXTENSIONS = ['.tif', '.tiff'] as const;
export const ALLOWED_BENCHMARK_EXTENSIONS = ['.png', '.jpg', '.jpeg'] as const;
export const ALLOWED_EXTENSIONS = [
  ...ALLOWED_GEOTIFF_EXTENSIONS,
  ...ALLOWED_BENCHMARK_EXTENSIONS,
] as const;

export const ACCEPTED_FILE_TYPES_ATTR = '.tif,.tiff,.png,.jpg,.jpeg,image/tiff,image/png,image/jpeg';

export interface ValidationResult {
  valid: boolean;
  error?: string;
  category?: 'geotiff' | 'benchmark';
}

export function validateImageryFile(file: File): ValidationResult {
  if (!file) {
    return { valid: false, error: 'No file provided.' };
  }

  if (file.size === 0) {
    return { valid: false, error: `File "${file.name}" is empty (0 bytes).` };
  }

  const nameLower = file.name.toLowerCase();
  const isGeoTiff = ALLOWED_GEOTIFF_EXTENSIONS.some((ext) => nameLower.endsWith(ext));
  const isBenchmark = ALLOWED_BENCHMARK_EXTENSIONS.some((ext) => nameLower.endsWith(ext));

  if (isGeoTiff) {
    return { valid: true, category: 'geotiff' };
  }

  if (isBenchmark) {
    return { valid: true, category: 'benchmark' };
  }

  return {
    valid: false,
    error: `Invalid file format "${file.name}". Accepted formats: GeoTIFF/TIFF (.tif, .tiff) for geospatial imagery, or PNG/JPEG (.png, .jpg, .jpeg) for benchmark datasets.`,
  };
}

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}
