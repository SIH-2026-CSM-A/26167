import { afterEach, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UploadPage } from '@/pages/UploadPage';

const successfulAnswer = {
  text: 'A river is visible.',
  evidence: [
    {
      id: 'evidence-1',
      tool: 'internvl_vqa',
      type: 'text',
      payload: {
        source_asset_id: 'asset-1',
        source_filename: 'scene.tif',
        model_id: 'OpenGVLab/InternVL2-2B',
        verified_answer: 'A river is visible.',
      },
      confidence: 0,
      timing: 1.2,
    },
  ],
  trace: {
    trace_id: 'trace-1',
    created_at: '2026-09-05T00:00:00Z',
    steps: [
      {
        module: 'router',
        action: 'route_selected',
        params: { tool: 'internvl_vqa' },
        confidence: null,
        started_at: '2026-09-05T00:00:00Z',
        completed_at: '2026-09-05T00:00:01Z',
        evidence_ids: [],
      },
    ],
  },
  confidence: 0,
  abstained: false,
  abstention_reason: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test('submits the selected GeoTIFF and question and renders the backend answer', async () => {
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(successfulAnswer), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchSpy);
  const user = userEvent.setup();
  render(<UploadPage />);

  const file = new File(['real raster bytes'], 'scene.tif', { type: 'image/tiff' });
  await user.upload(screen.getByLabelText('GeoTIFF or TIFF image'), file);
  await user.type(screen.getByLabelText('Question about this image'), 'What is visible?');
  expect(screen.getByText('scene.tif')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'Run analysis' }));

  expect(await screen.findByText('A river is visible.')).toBeInTheDocument();
  expect(screen.getByText('OpenGVLab/InternVL2-2B')).toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledOnce();
  const requestBody = fetchSpy.mock.calls[0][1]?.body as FormData;
  expect(requestBody.get('query')).toBe('What is visible?');
  expect((requestBody.get('images') as File).name).toBe('scene.tif');
});

test('renders the backend error when analysis fails', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { stage: 'ingestion', message: 'TIFF could not be read' } }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    ),
  );
  const user = userEvent.setup();
  render(<UploadPage />);

  await user.upload(
    screen.getByLabelText('GeoTIFF or TIFF image'),
    new File(['broken'], 'broken.tif', { type: 'image/tiff' }),
  );
  await user.type(screen.getByLabelText('Question about this image'), 'Describe it');
  await user.click(screen.getByRole('button', { name: 'Run analysis' }));

  expect(await screen.findByText('TIFF could not be read')).toBeInTheDocument();
});
