import { afterEach, expect, test, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DemoPresetSelector } from '../DemoPresetSelector';
import { FALLBACK_ERROR_BANNER } from '@/utils/demoPresets';
import { UploadPage } from '@/pages/UploadPage';
import type { DemoManifest } from '@/types/manifest';

const mockManifest: DemoManifest = {
  schema_version: '1.0',
  presets: [
    {
      id: 'single-image-land-cover',
      label: 'Land-cover and object overview',
      query: 'Describe the land-cover and major objects visible in this image.',
      intent: 'vqa',
      tool: 'vqa_grounding',
      scenario: 'single_image',
      assets: [
        {
          id: 'sen1floods11-bolivia-103757-optical',
          path: 'assets/sen1floods11_bolivia_103757_s2_optical.tif',
          modality: 'optical',
          role: 'image',
        },
      ],
    },
    {
      id: 'cross-modal-built-up-water',
      label: 'Optical + SAR built-up and water',
      query: 'Use the optical and SAR images together to identify built-up and water-covered regions.',
      intent: 'fusion',
      tool: 'fusion',
      scenario: 'cross_modal',
      assets: [
        {
          id: 'sen1floods11-bolivia-103757-optical',
          path: 'assets/sen1floods11_bolivia_103757_s2_optical.tif',
          modality: 'optical',
          role: 'optical_image',
        },
        {
          id: 'sen1floods11-bolivia-103757-sar',
          path: 'assets/sen1floods11_bolivia_103757_s1_sar.tif',
          modality: 'sar',
          role: 'sar_image',
        },
      ],
    },
    {
      id: 'bi-temporal-change-location',
      label: 'Built-up change location',
      query: 'What changed between these two dates, and where did the change occur?',
      intent: 'change_vqa',
      tool: 'change_detection',
      scenario: 'bi_temporal_change',
      assets: [
        {
          id: 'levir-cd-train-103-9-before',
          path: 'assets/levir_cd_train_103_9_before.png',
          modality: 'optical',
          role: 'pre_image',
        },
        {
          id: 'levir-cd-train-103-9-after',
          path: 'assets/levir_cd_train_103_9_after.png',
          modality: 'optical',
          role: 'post_image',
        },
      ],
    },
  ],
};

function setupSuccessfulFetch() {
  const fetchSpy = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const urlStr = String(input);
    if (urlStr.endsWith('manifest.json')) {
      return Promise.resolve(
        new Response(JSON.stringify(mockManifest), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }
    if (urlStr.includes('assets/')) {
      return Promise.resolve(new Response(new Blob(['raster bytes']), { status: 200 }));
    }
    return Promise.resolve(new Response('Not found', { status: 404 }));
  });
  vi.stubGlobal('fetch', fetchSpy);
  return fetchSpy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test('renders available presets from manifest data', async () => {
  setupSuccessfulFetch();
  render(<DemoPresetSelector onSelectPreset={vi.fn()} />);

  expect(await screen.findByText('Land-cover and object overview')).toBeInTheDocument();
  expect(screen.getByText('Optical + SAR built-up and water')).toBeInTheDocument();
  expect(screen.getByText('Built-up change location')).toBeInTheDocument();
  expect(screen.getByText('single image')).toBeInTheDocument();
  expect(screen.getByText('cross modal')).toBeInTheDocument();
});

test('selecting a preset updates query and slot states', async () => {
  setupSuccessfulFetch();
  const onSelectPreset = vi.fn();
  const user = userEvent.setup();

  render(<DemoPresetSelector onSelectPreset={onSelectPreset} />);
  const presetChip = await screen.findByText('Optical + SAR built-up and water');
  await user.click(presetChip);

  expect(onSelectPreset).toHaveBeenCalledOnce();
  const payload = onSelectPreset.mock.calls[0][0];
  expect(payload.query).toBe(
    'Use the optical and SAR images together to identify built-up and water-covered regions.',
  );
  expect(payload.mode).toBe('cross-modal');
  expect(payload.slots).toHaveLength(2);
  expect(payload.slots[0].label).toBe('Slot 1 (Optical)');
  expect(payload.slots[0].modality).toBe('optical');
  expect(payload.slots[0].isLocked).toBe(true);
  expect(payload.slots[0].file?.name).toBe('sen1floods11_bolivia_103757_s2_optical.tif');
  expect(payload.slots[1].label).toBe('Slot 2 (SAR)');
  expect(payload.slots[1].modality).toBe('sar');
  expect(payload.slots[1].isLocked).toBe(true);
  expect(payload.slots[1].file?.name).toBe('sen1floods11_bolivia_103757_s1_sar.tif');
});

test('displays the honest fallback message if manifest fetch fails', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Not found', { status: 404 })));
  render(<DemoPresetSelector onSelectPreset={vi.fn()} />);

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent(FALLBACK_ERROR_BANNER);
  expect(screen.queryByText('Land-cover and object overview')).not.toBeInTheDocument();
});

test('displays the honest fallback message if an asset path returns a 404', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const urlStr = String(input);
      if (urlStr.endsWith('manifest.json')) {
        return Promise.resolve(
          new Response(JSON.stringify(mockManifest), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(new Response('Asset not found', { status: 404 }));
    }),
  );
  const onSelect = vi.fn();
  const user = userEvent.setup();

  render(<DemoPresetSelector onSelectPreset={onSelect} />);
  const presetChip = await screen.findByText('Land-cover and object overview');
  await user.click(presetChip);

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent(FALLBACK_ERROR_BANNER);
  expect(onSelect).not.toHaveBeenCalled();
});

test('manual upload remains untouched when toggle is off', async () => {
  setupSuccessfulFetch();
  const user = userEvent.setup();
  render(<UploadPage />);

  expect(screen.getByRole('button', { name: 'Manual Upload' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Demo Presets' })).toBeInTheDocument();

  expect(screen.getByText('Pipeline Configuration')).toBeInTheDocument();
  expect(screen.getByText('Primary Imagery')).toBeInTheDocument();
  expect(screen.queryByText('Land-cover and object overview')).not.toBeInTheDocument();

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  await user.type(queryInput, 'My custom query');
  expect(queryInput).toHaveValue('My custom query');

  await user.click(screen.getByRole('button', { name: 'Demo Presets' }));
  expect(await screen.findByText('Land-cover and object overview')).toBeInTheDocument();

  await user.click(screen.getByRole('button', { name: 'Manual Upload' }));
  expect(screen.getByText('Pipeline Configuration')).toBeInTheDocument();
  expect(screen.queryByText('Land-cover and object overview')).not.toBeInTheDocument();
});

test('selecting a preset in UploadPage populates query, mode, and slots', async () => {
  setupSuccessfulFetch();
  const user = userEvent.setup();
  render(<UploadPage />);

  await user.click(screen.getByRole('button', { name: 'Demo Presets' }));
  const chip = await screen.findByText('Land-cover and object overview');
  await user.click(chip);

  const queryInput = screen.getByPlaceholderText(/e\.g\. Identify land cover classification/i);
  expect(queryInput).toHaveValue(
    'Describe the land-cover and major objects visible in this image.',
  );
  expect(screen.getByText('sen1floods11_bolivia_103757_s2_optical.tif')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run Pipeline' })).toBeEnabled();
});
