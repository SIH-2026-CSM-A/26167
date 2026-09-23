import { expect, test } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EvidenceSummaryCard } from '@/components/EvidenceSummaryCard';
import type { Evidence } from '@/types/contracts';

test('raw evidence data elides large arrays and never prints raster masks', async () => {
  const mask = Array.from({ length: 512 }, () => Array.from({ length: 512 }, () => false));
  const evidence: Evidence = {
    id: 'fusion-clear',
    tool: 'fusion.reconcile',
    type: 'mask',
    payload: {
      water_mask: mask,
      region: 'clear',
      bbox: [1, 2, 3, 4],
      note: 'SAR indicates 40.9% water coverage in the clear region.',
    },
    confidence: 1.0,
    timing: 0.5,
  };
  const user = userEvent.setup();
  const { container } = render(<EvidenceSummaryCard evidence={evidence} />);

  await user.click(screen.getByText('Raw evidence data'));
  const raw = container.querySelector('pre')?.textContent ?? '';
  expect(raw).toContain('"water_mask": "[array of 512 items omitted]"');
  expect(raw).toContain('"region": "clear"');
  expect(raw).toContain('1,');
  expect(raw).not.toContain('false');
});

test('raw evidence data is capped at 2,000 characters', async () => {
  const evidence: Evidence = {
    id: 'long-text',
    tool: 'internvl_vqa',
    type: 'text',
    payload: { raw_model_answer: 'x'.repeat(5000) },
    confidence: 0.5,
    timing: 0.1,
  };
  const user = userEvent.setup();
  const { container } = render(<EvidenceSummaryCard evidence={evidence} />);

  await user.click(screen.getByText('Raw evidence data'));
  const raw = container.querySelector('pre')?.textContent ?? '';
  expect(raw.endsWith('… (truncated)')).toBe(true);
  expect(raw.length).toBe(2000 + '\n… (truncated)'.length);
});
