import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DemoCredentialsBanner } from '../DemoCredentialsBanner';

describe('DemoCredentialsBanner', () => {
  it('renders the Demo Credentials heading and credentials', () => {
    render(<DemoCredentialsBanner onAutoFill={vi.fn()} />);

    expect(screen.getByText('Demo Credentials')).toBeInTheDocument();
    expect(screen.getByText('demo@example.com')).toBeInTheDocument();
    expect(screen.getByText('correct-horse-battery')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /auto-fill/i })).toBeInTheDocument();
  });

  it('renders custom credentials if provided', () => {
    const custom = {
      email: 'analyst@satquery.gov.in',
      password: 'custom-mission-key-2026',
    };
    render(<DemoCredentialsBanner onAutoFill={vi.fn()} credentials={custom} />);

    expect(screen.getByText('analyst@satquery.gov.in')).toBeInTheDocument();
    expect(screen.getByText('custom-mission-key-2026')).toBeInTheDocument();
  });

  it('invokes onAutoFill with credentials when clicked', async () => {
    const handleAutoFill = vi.fn();
    const user = userEvent.setup();

    render(<DemoCredentialsBanner onAutoFill={handleAutoFill} />);

    const autoFillBtn = screen.getByRole('button', { name: /auto-fill/i });
    await user.click(autoFillBtn);

    expect(handleAutoFill).toHaveBeenCalledTimes(1);
    expect(handleAutoFill).toHaveBeenCalledWith({
      email: 'demo@example.com',
      password: 'correct-horse-battery',
    });
  });
});
