import type { PipelineConfigMode } from '@/components/Upload/ConfigSelector';
import type { DemoManifest, DemoPreset, PresetSlotData } from '@/types/manifest';

export const FALLBACK_ERROR_BANNER =
  'Demo preset unavailable. Please use manual upload or verify dataset path.';

export const DEFAULT_MANIFEST_URL = '/data/demo/manifest.json';

export function resolveAssetUrl(manifestUrl: string, assetPath: string): string {
  if (assetPath.startsWith('http://') || assetPath.startsWith('https://') || assetPath.startsWith('/')) {
    return assetPath;
  }
  const lastSlashIndex = manifestUrl.lastIndexOf('/');
  const baseDir = lastSlashIndex !== -1 ? manifestUrl.substring(0, lastSlashIndex + 1) : '';
  return `${baseDir}${assetPath}`;
}

export async function fetchManifestData(url: string): Promise<DemoPreset[]> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load manifest: ${response.status}`);
  }
  const manifest = (await response.json()) as DemoManifest;
  if (!manifest || !Array.isArray(manifest.presets) || manifest.presets.length === 0) {
    throw new Error('Manifest does not contain valid presets');
  }
  return manifest.presets;
}

export async function loadPresetAssetFiles(
  preset: DemoPreset,
  manifestUrl: string,
): Promise<Record<string, File>> {
  const files: Record<string, File> = {};
  for (const asset of preset.assets) {
    const assetUrl = resolveAssetUrl(manifestUrl, asset.path);
    const res = await fetch(assetUrl);
    if (!res.ok) {
      throw new Error(`Asset fetch failed with status ${res.status}`);
    }
    const blob = await res.blob();
    const filename = asset.path.split('/').pop() || `${asset.id}.tif`;
    const mime = filename.endsWith('.png') ? 'image/png' : 'image/tiff';
    files[asset.role] = new File([blob], filename, { type: mime });
  }
  return files;
}

export function mapPresetToSlotsAndMode(
  preset: DemoPreset,
  filesByRole: Record<string, File>,
): { mode: PipelineConfigMode; slots: PresetSlotData[] } {
  const hasOpticalSar = preset.assets.some((a) => a.role === 'optical_image' || a.role === 'sar_image');
  if (hasOpticalSar) {
    return {
      mode: 'cross-modal',
      slots: [
        { label: 'Slot 1 (Optical)', file: filesByRole['optical_image'] ?? null, modality: 'optical', isLocked: true },
        { label: 'Slot 2 (SAR)', file: filesByRole['sar_image'] ?? null, modality: 'sar', isLocked: true },
      ],
    };
  }

  const hasPrePost = preset.assets.some((a) => a.role === 'pre_image' || a.role === 'post_image');
  if (hasPrePost) {
    const preAsset = preset.assets.find((a) => a.role === 'pre_image');
    const postAsset = preset.assets.find((a) => a.role === 'post_image');
    return {
      mode: 'bi-temporal',
      slots: [
        {
          label: 'Slot 1 (T1 Pass)',
          file: filesByRole['pre_image'] ?? null,
          modality: preAsset?.modality ?? 'optical',
          isLocked: false,
        },
        {
          label: 'Slot 2 (T2 Pass)',
          file: filesByRole['post_image'] ?? null,
          modality: postAsset?.modality ?? 'optical',
          isLocked: false,
        },
      ],
    };
  }

  const imgAsset = preset.assets.find((a) => a.role === 'image');
  return {
    mode: 'single',
    slots: [
      {
        label: 'Primary Imagery',
        file: filesByRole['image'] ?? null,
        modality: imgAsset?.modality ?? 'optical',
        isLocked: false,
      },
    ],
  };
}
