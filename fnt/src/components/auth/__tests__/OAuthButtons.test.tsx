import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OAuthButtons } from '@/components/auth/OAuthButtons';

describe('OAuthButtons', () => {
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    // @ts-expect-error -- replacing window.location for a navigation assertion
    delete window.location;
    // @ts-expect-error -- minimal stub, only `href` is exercised
    window.location = { href: '' };
  });

  afterEach(() => {
    window.location = originalLocation;
    vi.restoreAllMocks();
  });

  it('Google click navigates directly to /auth/google/login', async () => {
    const user = userEvent.setup();
    render(<OAuthButtons />);

    await user.click(screen.getByRole('button', { name: 'Google Workspace' }));

    expect(window.location.href).toContain('/auth/google/login');
  });

  it('ISRO click on a 503 probe shows the inline message and does not navigate', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 503 }));
    const user = userEvent.setup();
    render(<OAuthButtons />);

    await user.click(screen.getByRole('button', { name: 'ISRO SSO' }));

    expect(await screen.findByText('ISRO SSO not yet available.')).toBeInTheDocument();
    expect(window.location.href).toBe('');
  });

  it('ISRO click when the probe does not 503 navigates', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    const user = userEvent.setup();
    render(<OAuthButtons />);

    await user.click(screen.getByRole('button', { name: 'ISRO SSO' }));

    await waitFor(() => expect(window.location.href).toContain('/auth/isro/login'));
  });
});
