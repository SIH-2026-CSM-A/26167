import type { PipelineConfigMode } from '@/components/Upload/ConfigSelector';
import type { Modality } from '@/types/contracts';

export type DemoAssetRole = 'image' | 'pre_image' | 'post_image' | 'optical_image' | 'sar_image';

export type DemoModality = 'optical' | 'sar';

export interface DemoAsset {
  id: string;
  path: string;
  modality: DemoModality;
  role: DemoAssetRole;
}

export interface DemoPreset {
  id: string;
  label: string;
  query: string;
  intent: string;
  tool: string;
  scenario: string;
  assets: DemoAsset[];
}

export interface DemoManifest {
  schema_version: string;
  presets: DemoPreset[];
}

export interface PresetSlotData {
  label: string;
  file: File | null;
  modality: Modality;
  isLocked: boolean;
}

export interface PresetApplyPayload {
  preset: DemoPreset;
  mode: PipelineConfigMode;
  slots: PresetSlotData[];
  query: string;
}
