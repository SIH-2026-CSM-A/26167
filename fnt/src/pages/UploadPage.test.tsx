import { afterEach, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UploadPage } from '@/pages/UploadPage';

const successfulAnswer = {
  text: 'A river is visible in the satellite scene.',
  evidence: [
    {
      id: 'evidence-1',
      tool: 'internvl_vqa',
      type: 'text',
      payload: {
        source_asset_id: 'asset-1',
        source_filename: 'scene.tif',
        model_id: 'OpenGVLab/InternVL2-2B',
        description: 'Verified river feature',
      },
      confidence: 0.9,
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
        confidence: 0.95,
        started_at: '2026-09-05T00:00:00Z',
        completed_at: '2026-09-05T00:00:01Z',
        evidence_ids: [],
      },
    ],
  },
  confidence: 0.9,
  abstained: false,
  abstention_reason: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test('renders LIKI-002 multi-slot upload structure and configuration modes', async () => {
  const user = userEvent.setup();
  render(<UploadPage />);

  expect(screen.getByText('Satellite Imagery Query')).toBeInTheDocument();
  expect(screen.getByText('Pipeline Configuration')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Single Image/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Cross-Modal Pair/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Bi-Temporal Pair/i })).toBeInTheDocument();
  expect(screen.getByText('Primary Imagery')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: /Cross-Modal Pair/i }));
  expect(screen.getByText('Slot 1 (Optical)')).toBeInTheDocument();
  expect(screen.getByText('Slot 2 (SAR)')).toBeInTheDocument();
});

test('submits single-image GeoTIFF and question and renders pipeline result', async () => {
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(successfulAnswer), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchSpy);
  const user = userEvent.setup();
  const { container } = render(<UploadPage />);

  const file = new File(['raster data'], 'scene.tif', { type: 'image/tiff' });
  const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
  expect(fileInput).toBeInTheDocument();
  await user.upload(fileInput, file);

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'What is visible?');

  const submitButton = screen.getByRole('button', { name: 'Run Pipeline' });
  expect(submitButton).toBeEnabled();
  await user.click(submitButton);

  expect(await screen.findByText('Pipeline Result')).toBeInTheDocument();
  expect(screen.getByText('A river is visible in the satellite scene.')).toBeInTheDocument();
  expect(screen.getByText(/Grounded Evidence/i)).toBeInTheDocument();
  expect(screen.getByText(/Show Execution Trace/i)).toBeInTheDocument();

  expect(fetchSpy).toHaveBeenCalledOnce();
  const requestBody = fetchSpy.mock.calls[0][1]?.body as FormData;
  expect(requestBody.get('query')).toBe('What is visible?');
  expect((requestBody.get('images') as File).name).toBe('scene.tif');
});

test('renders backend error when query fails', async () => {
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
  const { container } = render(<UploadPage />);

  const file = new File(['broken'], 'broken.tif', { type: 'image/tiff' });
  const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(fileInput, file);

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'Describe it');

  await user.click(screen.getByRole('button', { name: 'Run Pipeline' }));

  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(screen.getByText(/TIFF could not be read/i)).toBeInTheDocument();
});

test('prevents unsupported multi-slot submission with a clear notice', async () => {
  const fetchSpy = vi.fn();
  vi.stubGlobal('fetch', fetchSpy);
  const user = userEvent.setup();
  const { container } = render(<UploadPage />);

  await user.click(screen.getByRole('button', { name: /Cross-Modal Pair/i }));

  const fileInputs = container.querySelectorAll('input[type="file"]');
  expect(fileInputs.length).toBe(2);

  const file1 = new File(['s1'], 's1.tif', { type: 'image/tiff' });
  const file2 = new File(['s2'], 's2.tif', { type: 'image/tiff' });
  await user.upload(fileInputs[0] as HTMLInputElement, file1);
  await user.upload(fileInputs[1] as HTMLInputElement, file2);

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'Detect changes');

  const submitButton = screen.getByRole('button', { name: 'Run Pipeline' });
  expect(submitButton).toBeEnabled();
  await user.click(submitButton);

  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(
    screen.getByText(/Multi-slot pipeline execution is not supported in the YASH-003 single-image VQA slice/i),
  ).toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});
