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
});
