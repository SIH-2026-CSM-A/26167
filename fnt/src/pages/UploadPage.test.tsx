import { afterEach, expect, test, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
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

test('submits cross-modal optical and SAR imagery with both modalities', async () => {
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(successfulAnswer), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
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

  expect(await screen.findByText('Pipeline Result')).toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledOnce();
  const requestBody = fetchSpy.mock.calls[0][1]?.body as FormData;
  expect(requestBody.get('query')).toBe('Detect changes');
  expect((requestBody.getAll('images')[0] as File).name).toBe('s1.tif');
  expect((requestBody.getAll('images')[1] as File).name).toBe('s2.tif');
  expect(requestBody.getAll('modality')).toEqual(['optical', 'sar']);
  expect(requestBody.getAll('capture_order')).toEqual(['0', '1']);
});

test('submits bi-temporal pair with capture_order in slot order', async () => {
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(successfulAnswer), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchSpy);
  const user = userEvent.setup();
  const { container } = render(<UploadPage />);

  await user.click(screen.getByRole('button', { name: /Bi-Temporal Pair/i }));

  const fileInputs = container.querySelectorAll('input[type="file"]');
  expect(fileInputs.length).toBe(2);

  const t1 = new File(['t1'], 't1.tif', { type: 'image/tiff' });
  const t2 = new File(['t2'], 't2.tif', { type: 'image/tiff' });
  await user.upload(fileInputs[0] as HTMLInputElement, t1);
  await user.upload(fileInputs[1] as HTMLInputElement, t2);

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'What changed?');

  await user.click(screen.getByRole('button', { name: 'Run Pipeline' }));

  expect(await screen.findByText('Pipeline Result')).toBeInTheDocument();
  const requestBody = fetchSpy.mock.calls[0][1]?.body as FormData;
  expect((requestBody.getAll('images')[0] as File).name).toBe('t1.tif');
  expect((requestBody.getAll('images')[1] as File).name).toBe('t2.tif');
  expect(requestBody.getAll('capture_order')).toEqual(['0', '1']);
});

test('MODALITY_UNKNOWN veto surfaces clarification, then resubmit with explicit modality succeeds', async () => {
  const fetchSpy = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            message:
              '1 image was unable to be classified as Optical or SAR from raster metadata alone.',
            stage: 'routing',
            reason_code: 'MODALITY_UNKNOWN',
            suggested_action:
              'Re-upload with standard band descriptions, or specify the modality explicitly.',
            trace: { trace_id: 't1', steps: [] },
          },
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    .mockResolvedValueOnce(
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
  await user.upload(fileInput, file);

  const modalitySelect = screen.getByRole('combobox') as HTMLSelectElement;
  await user.selectOptions(modalitySelect, 'auto');

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'What sensor is this?');

  await user.click(screen.getByRole('button', { name: 'Run Pipeline' }));

  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(
    screen.getByText(/unable to be classified as Optical or SAR/i),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Re-upload with standard band descriptions/i),
  ).toBeInTheDocument();
  expect(screen.getByText(/pick Optical or SAR/i)).toBeInTheDocument();

  const firstRequestBody = fetchSpy.mock.calls[0][1]?.body as FormData;
  expect(firstRequestBody.getAll('modality')).toEqual([]);

  await user.selectOptions(modalitySelect, 'optical');
  await user.click(screen.getByRole('button', { name: 'Run Pipeline' }));

  expect(await screen.findByText('Pipeline Result')).toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
  const secondRequestBody = fetchSpy.mock.calls[1][1]?.body as FormData;
  expect(secondRequestBody.getAll('modality')).toEqual(['optical']);
});

function traceStep(module: string, action: string, params: Record<string, unknown>) {
  return {
    module,
    action,
    params,
    confidence: null,
    started_at: '2026-09-23T00:00:00Z',
    completed_at: '2026-09-23T00:00:00Z',
    evidence_ids: [],
  };
}

async function submitCrossModalPair(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  await user.click(screen.getByRole('button', { name: /Cross-Modal Pair/i }));
  const fileInputs = container.querySelectorAll('input[type="file"]');
  await user.upload(fileInputs[0] as HTMLInputElement, new File(['o'], 'optical.tif', { type: 'image/tiff' }));
  await user.upload(fileInputs[1] as HTMLInputElement, new File(['s'], 'sar.tif', { type: 'image/tiff' }));
  await user.type(
    screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i),
    'Identify water-covered regions.',
  );
  await user.click(screen.getByRole('button', { name: 'Run Pipeline' }));
}

test('EO gate veto shows the reason code badge and the returned execution trace', async () => {
  const gates = ['crs_consistency', 'geographic_overlap', 'gsd_match', 'acquisition_order'];
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: 'Rasters are in different coordinate reference systems.',
            stage: 'validation',
            reason_code: 'EO_CRS_MISMATCH',
            suggested_action: 'Reproject the rasters to a common CRS before uploading.',
            trace: {
              trace_id: 'veto-trace',
              created_at: '2026-09-23T00:00:00Z',
              steps: [
                ...gates.map((gate, i) =>
                  traceStep('validation', 'eo_gates', { gate, status: i === 0 ? 'FAIL' : 'PASS' }),
                ),
                traceStep('validation', 'execution_failed', { message: 'CRS mismatch' }),
              ],
            },
          },
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    ),
  );
  const user = userEvent.setup();
  const { container } = render(<UploadPage />);

  await submitCrossModalPair(user, container);

  const alert = await screen.findByRole('alert');
  expect(within(alert).getByText('EO_CRS_MISMATCH')).toBeInTheDocument();
  expect(within(alert).getByText(/Reproject the rasters/i)).toBeInTheDocument();

  await user.click(within(alert).getByText(/Show Execution Trace/i));
  expect(within(alert).getAllByText('eo_gates')).toHaveLength(4);
  expect(within(alert).getByText(/"gate":"crs_consistency","status":"FAIL"/)).toBeInTheDocument();
});

test('fusion mask evidence renders a summary, never the raw mask arrays', async () => {
  const mask = Array.from({ length: 64 }, () => Array.from({ length: 64 }, () => false));
  const fusionAnswer = {
    ...successfulAnswer,
    text: 'SAR indicates 40.9% water coverage.',
    evidence: [
      {
        id: 'fusion-clear',
        tool: 'fusion.reconcile',
        type: 'mask',
        payload: {
          water_mask: mask,
          region_mask: mask,
          water_fraction: 0.409,
          region: 'clear',
          note: 'SAR indicates 40.9% water coverage in the clear region.',
        },
        confidence: 1.0,
        timing: 0.5,
      },
    ],
  };
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(fusionAnswer), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  );
  const user = userEvent.setup();
  const { container } = render(<UploadPage />);

  await submitCrossModalPair(user, container);

  expect(await screen.findByText('Pipeline Result')).toBeInTheDocument();
  expect(screen.getByText('water 40.9%')).toBeInTheDocument();
  expect(screen.getByText('clear')).toBeInTheDocument();
  expect(screen.getByText('100%')).toBeInTheDocument();
  expect(screen.getByText('SAR indicates 40.9% water coverage in the clear region.')).toBeInTheDocument();
  expect(screen.getByText('Raw evidence data')).toBeInTheDocument();
  expect(container.textContent).not.toContain('false,false');
  expect(container.textContent).toContain('[array of 64 items omitted]');
});
