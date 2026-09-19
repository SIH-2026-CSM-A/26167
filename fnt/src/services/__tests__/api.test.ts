import { afterEach, describe, expect, it, vi } from 'vitest';
import { submitQuery } from '@/services/api';

describe('submitQuery', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('converts a stalled request into a retryable timeout error', async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }));

    const request = submitQuery({ query: 'test query', images: [new File(['image'], 'scene.tif')], modalities: ['optical'] });
    const rejection = expect(request).rejects.toThrow('Query timed out. Check the backend and retry.');
    await vi.advanceTimersByTimeAsync(180_000);

    await rejection;
  });

  it('surfaces structured veto detail instead of a bare status-code message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: 'Temporal order not specified — use the bi-temporal Upload slots to indicate before/after.',
            reason_code: 'TEMPORAL_ORDER_MISSING',
            suggested_action:
              "Re-submit via the Upload page's bi-temporal slots (Slot 1 = before, Slot 2 = after) instead of Chat.",
          },
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    );

    const request = submitQuery({
      query: 'What changed?',
      images: [new File(['a'], 't1.tif'), new File(['b'], 't2.tif')],
      modalities: ['optical', 'optical'],
    });

    await expect(request).rejects.toThrow(
      /Temporal order not specified.*Re-submit via the Upload page's bi-temporal slots/,
    );
  });
});
