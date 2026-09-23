import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitImageQuery, QueryApiError } from '@/services/query';

describe('submitImageQuery error parsing', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('surfaces the real PipelineError message, reason_code, and suggested_action', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: '1 image was unable to be classified as Optical or SAR from raster metadata alone.',
            stage: 'routing',
            reason_code: 'MODALITY_UNKNOWN',
            suggested_action: 'Re-upload with standard band descriptions, or specify the modality explicitly.',
            trace: { trace_id: 't1', steps: [] },
          },
        }),
        { status: 422 }
      )
    );

    const request = submitImageQuery(
      new File(['image'], 'scene.tif'),
      'What changed here?'
    );

    await expect(request).rejects.toMatchObject({
      message: '1 image was unable to be classified as Optical or SAR from raster metadata alone.',
      reasonCode: 'MODALITY_UNKNOWN',
      suggestedAction: 'Re-upload with standard band descriptions, or specify the modality explicitly.',
    });
    await expect(request).rejects.toBeInstanceOf(QueryApiError);
  });

  it('carries the veto trace the API returns alongside the reason code', async () => {
    const trace = {
      trace_id: 't2',
      created_at: '2026-09-23T00:00:00Z',
      steps: [
        {
          module: 'validation',
          action: 'eo_gates',
          params: { gate: 'crs_consistency', status: 'FAIL' },
          confidence: null,
          started_at: '2026-09-23T00:00:00Z',
          completed_at: '2026-09-23T00:00:00Z',
          evidence_ids: [],
        },
      ],
    };
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: 'Rasters are in different coordinate reference systems.',
            stage: 'validation',
            reason_code: 'EO_CRS_MISMATCH',
            suggested_action: 'Reproject the rasters to a common CRS before uploading.',
            trace,
          },
        }),
        { status: 422 }
      )
    );

    const request = submitImageQuery(new File(['image'], 'scene.tif'), 'Find water');

    await expect(request).rejects.toMatchObject({ reasonCode: 'EO_CRS_MISMATCH', trace });
  });

  it('falls back to the generic message for a plain string detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'at least one image is required' }), { status: 422 })
    );

    const request = submitImageQuery(new File(['image'], 'scene.tif'), 'Describe this');

    await expect(request).rejects.toThrow('at least one image is required');
  });
});
