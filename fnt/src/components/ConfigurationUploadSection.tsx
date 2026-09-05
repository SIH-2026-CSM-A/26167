import React from 'react';
import { ImageUploadSlot } from '@/components/ImageUploadSlot';
import type { InputConfiguration, Modality } from '@/services/types';

export interface SlotData {
  file: File | null;
  modality: Modality;
  error: string | null;
}

export type SlotTarget = 'single' | 'crossOptical' | 'crossSar' | 't1' | 't2';

export interface ConfigurationUploadSectionProps {
  config: InputConfiguration;
  singleSlot: SlotData;
  crossOpticalSlot: SlotData;
  crossSarSlot: SlotData;
  t1Slot: SlotData;
  t2Slot: SlotData;
  onFileSelect: (file: File, target: SlotTarget) => void;
  onFileRemove: (target: SlotTarget) => void;
  onModalityChange: (modality: Modality, target: 'single' | 't1' | 't2') => void;
}

export const ConfigurationUploadSection: React.FC<ConfigurationUploadSectionProps> = ({
  config,
  singleSlot,
  crossOpticalSlot,
  crossSarSlot,
  t1Slot,
  t2Slot,
  onFileSelect,
  onFileRemove,
  onModalityChange,
}) => {
  if (config === 'single') {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Upload 1 image with specified sensor modality:</span>
          <span className="font-mono text-cyan-400">1 File Required</span>
        </div>
        <ImageUploadSlot
          id="slot-single"
          label="Satellite Imagery File"
          sublabel="Select sensor modality (Optical or SAR) and upload GeoTIFF or benchmark image"
          file={singleSlot.file}
          modality={singleSlot.modality}
          allowModalityChange={true}
          required={true}
          error={singleSlot.error}
          onFileSelect={(file) => onFileSelect(file, 'single')}
          onFileRemove={() => onFileRemove('single')}
          onModalityChange={(modality) => onModalityChange(modality, 'single')}
        />
      </div>
    );
  }

  if (config === 'cross-modal') {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Cross-modal fusion requires exactly one Optical and one SAR image:</span>
          <span className="font-mono text-cyan-400">2 Files Required</span>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <ImageUploadSlot
            id="slot-cross-optical"
            label="Optical Imagery"
            sublabel="Visible / NIR spectrum (e.g. Sentinel-2, Cartosat)"
            file={crossOpticalSlot.file}
            modality="optical"
            allowModalityChange={false}
            required={true}
            error={crossOpticalSlot.error}
            onFileSelect={(file) => onFileSelect(file, 'crossOptical')}
            onFileRemove={() => onFileRemove('crossOptical')}
          />
          <ImageUploadSlot
            id="slot-cross-sar"
            label="SAR Imagery"
            sublabel="Microwave radar backscatter (e.g. Sentinel-1, RISAT-1)"
            file={crossSarSlot.file}
            modality="sar"
            allowModalityChange={false}
            required={true}
            error={crossSarSlot.error}
            onFileSelect={(file) => onFileSelect(file, 'crossSar')}
            onFileRemove={() => onFileRemove('crossSar')}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>Bi-temporal analysis requires two spatially corresponding temporal acquisitions:</span>
        <span className="font-mono text-cyan-400">2 Passes Required</span>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ImageUploadSlot
          id="slot-temporal-t1"
          label="Time 1 (T1) Acquisition"
          sublabel="Pre-event baseline satellite pass"
          file={t1Slot.file}
          modality={t1Slot.modality}
          allowModalityChange={true}
          required={true}
          error={t1Slot.error}
          onFileSelect={(file) => onFileSelect(file, 't1')}
          onFileRemove={() => onFileRemove('t1')}
          onModalityChange={(modality) => onModalityChange(modality, 't1')}
        />
        <ImageUploadSlot
          id="slot-temporal-t2"
          label="Time 2 (T2) Acquisition"
          sublabel="Post-event or secondary temporal satellite pass"
          file={t2Slot.file}
          modality={t2Slot.modality}
          allowModalityChange={true}
          required={true}
          error={t2Slot.error}
          onFileSelect={(file) => onFileSelect(file, 't2')}
          onFileRemove={() => onFileRemove('t2')}
          onModalityChange={(modality) => onModalityChange(modality, 't2')}
        />
      </div>
    </div>
  );
};
