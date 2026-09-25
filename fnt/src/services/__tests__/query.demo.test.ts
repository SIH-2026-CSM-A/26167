import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitImageQuery } from '@/services/query';

vi.mock('@/services/authFetch', () => ({ authFetch: vi.fn() }));

describe('submitImageQuery demo fields', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  async function sentForm(demo?: { presetId: string; runLive: boolean }): Promise<FormData> {
    const { authFetch } = await import('@/services/authFetch');
    const mocked = vi.mocked(authFetch);
    mocked.mockResolvedValue(new Response(JSON.stringify({ text: 'ok' }), { status: 200 }));
    await submitImageQuery([new File(['a'], 'a.png')], 'What changed?', undefined, undefined, demo);
    return mocked.mock.calls.at(-1)![1]!.body as FormData;
  }

  it('sends the preset id and run_live=false for a default demo run', async () => {
    const form = await sentForm({ presetId: 'bi-temporal-change-location', runLive: false });
    expect(form.get('demo_preset_id')).toBe('bi-temporal-change-location');
    expect(form.get('run_live')).toBe('false');
  });

  it('sends run_live=true for the explicit Run live action', async () => {
    const form = await sentForm({ presetId: 'bi-temporal-change-location', runLive: true });
    expect(form.get('run_live')).toBe('true');
  });

  it('sends no demo fields for a manual upload', async () => {
    const form = await sentForm();
    expect(form.has('demo_preset_id')).toBe(false);
    expect(form.has('run_live')).toBe(false);
  });
});
