import { describe, expect, it } from 'vitest';
import {
  DEFAULT_DEMO_CREDENTIALS,
  isDemoCredentialsVisible,
} from '../demoCredentials';

describe('demoCredentials utility', () => {
  it('provides default test credentials', () => {
    expect(DEFAULT_DEMO_CREDENTIALS.email).toBe('demo@example.com');
    expect(DEFAULT_DEMO_CREDENTIALS.password).toBe('correct-horse-battery');
  });

  describe('isDemoCredentialsVisible', () => {
    it('returns true by default without flags', () => {
      expect(isDemoCredentialsVisible({})).toBe(true);
    });

    it('returns true when EXPOSE_DEMO_CREDS is set to true or 1', () => {
      expect(isDemoCredentialsVisible({ EXPOSE_DEMO_CREDS: 'true' })).toBe(true);
      expect(isDemoCredentialsVisible({ EXPOSE_DEMO_CREDS: '1' })).toBe(true);
    });

    it('returns true when VITE_EXPOSE_DEMO_CREDS is set to true or 1', () => {
      expect(isDemoCredentialsVisible({ VITE_EXPOSE_DEMO_CREDS: 'true' })).toBe(true);
      expect(isDemoCredentialsVisible({ VITE_EXPOSE_DEMO_CREDS: '1' })).toBe(true);
    });

    it('returns false when EXPOSE_DEMO_CREDS is explicitly false or 0', () => {
      expect(isDemoCredentialsVisible({ EXPOSE_DEMO_CREDS: 'false' })).toBe(false);
      expect(isDemoCredentialsVisible({ EXPOSE_DEMO_CREDS: '0' })).toBe(false);
    });

    it('returns false when VITE_EXPOSE_DEMO_CREDS is explicitly false or 0', () => {
      expect(isDemoCredentialsVisible({ VITE_EXPOSE_DEMO_CREDS: 'false' })).toBe(false);
      expect(isDemoCredentialsVisible({ VITE_EXPOSE_DEMO_CREDS: '0' })).toBe(false);
    });
  });
});
