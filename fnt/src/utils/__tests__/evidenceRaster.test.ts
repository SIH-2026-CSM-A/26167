import { describe, expect, it } from 'vitest';
import type { Evidence } from '@/types/contracts';
import {
  buildRasterLayerSpecification,
  buildRasterSourceSpecification,
  evidenceToRasterOverlays,
  resolveRasterTileUrl,
} from '@/utils/evidenceRaster';

function evidence(overrides: Partial<Evidence>): Evidence {
  return {
    id: 'evidence-1',
    tool: 'test',
    type: 'mask',
    payload: {},
    confidence: 1,
    timing: 0,
    ...overrides,
  };
}

describe('evidenceRaster', () => {
  it('keeps an existing XYZ template unchanged', () => {
    const template = 'https://tiles.test/{z}/{x}/{y}.png';
    expect(resolveRasterTileUrl(template)).toBe(template);
  });

  it('converts a raw raster URL to the configured TiTiler XYZ convention', () => {
    const tileUrl = resolveRasterTileUrl('https://data.test/mask.tif');
    expect(tileUrl).toContain('/cog/tiles/WebMercatorQuad/{z}/{x}/{y}?');
    expect(tileUrl).toContain('url=https%3A%2F%2Fdata.test%2Fmask.tif');
  });

  it('creates raster source and layer specifications for mask and layer evidence', () => {
    const overlays = evidenceToRasterOverlays([
      evidence({ payload: { raster_url: 'https://data.test/mask.tif', bounds: [1, 2, 3, 4] } }),
      evidence({ id: 'layer-1', type: 'layer', payload: { tile_url: 'https://tiles.test/{z}/{x}/{y}.png' } }),
    ]);

    expect(overlays).toHaveLength(2);
    expect(buildRasterSourceSpecification(overlays[0])).toMatchObject({
      type: 'raster',
      tileSize: 256,
      bounds: [1, 2, 3, 4],
    });
    expect(buildRasterLayerSpecification(overlays[1])).toMatchObject({
      type: 'raster',
      source: overlays[1].sourceId,
    });
  });

  it('ignores raster evidence without a usable URL', () => {
    expect(evidenceToRasterOverlays([evidence({ payload: { raster_url: ' ' } })])).toEqual([]);
  });
});
