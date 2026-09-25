import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CachedRunBadge } from '@/components/CachedRunBadge';
import type { CachedRunInfo } from '@/types/contracts';

const cachedRun: CachedRunInfo = {
  recorded_at: '2026-09-25T10:00:00+00:00',
  preset_id: 'bi-temporal-change-location',
  reason: 'demo_default',
  model_identity: null,
  identity_mismatch: false,
};

describe('CachedRunBadge', () => {
  it('labels the answer as a cached demo run with its recording date', () => {
    render(<CachedRunBadge cachedRun={cachedRun} />);
    expect(screen.getByText('Cached demo run')).toBeInTheDocument();
    const expectedDate = new Date(cachedRun.recorded_at).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
    expect(screen.getByText(`Recorded ${expectedDate}`)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run live' })).not.toBeInTheDocument();
  });

  it('explains a fallback and flags a stale recording', () => {
    render(
      <CachedRunBadge cachedRun={{ ...cachedRun, reason: 'INFERENCE_QUOTA', identity_mismatch: true }} />,
    );
    expect(screen.getByText(/over its GPU quota/)).toBeInTheDocument();
    expect(screen.getByText(/different model weights/)).toBeInTheDocument();
  });

  it('offers an explicit Run live action', async () => {
    const onRunLive = vi.fn();
    render(<CachedRunBadge cachedRun={cachedRun} onRunLive={onRunLive} />);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Run live' }));
    expect(onRunLive).toHaveBeenCalledOnce();
  });
});
