export interface DemoCredentials {
  email: string;
  password: string;
}

export const DEFAULT_DEMO_CREDENTIALS: DemoCredentials = {
  email: 'demo@example.com',
  password: 'correct-horse-battery',
};

/**
 * Determines whether the demo credentials banner should be displayed.
 *
 * Enabled by default so it displays in both local development and deployed demo environments.
 * Supports explicit override via EXPOSE_DEMO_CREDS or VITE_EXPOSE_DEMO_CREDS flag
 * ('false' | '0' to hide, 'true' | '1' to show).
 */
export function isDemoCredentialsVisible(envOverrides?: {
  EXPOSE_DEMO_CREDS?: string;
  VITE_EXPOSE_DEMO_CREDS?: string;
  NODE_ENV?: string;
  MODE?: string;
}): boolean {
  if (envOverrides) {
    const flag = envOverrides.EXPOSE_DEMO_CREDS ?? envOverrides.VITE_EXPOSE_DEMO_CREDS;
    if (flag === 'false' || flag === '0') return false;
    if (flag === 'true' || flag === '1') return true;
    return true;
  }

  // 1. Process environment (Node / test runner / SSR / Vite define)
  if (typeof process !== 'undefined' && process.env) {
    const procFlag = process.env.EXPOSE_DEMO_CREDS ?? process.env.VITE_EXPOSE_DEMO_CREDS;
    if (procFlag === 'false' || procFlag === '0') return false;
    if (procFlag === 'true' || procFlag === '1') return true;
  }

  // 2. Vite client environment (import.meta.env)
  try {
    if (typeof import.meta !== 'undefined' && import.meta.env) {
      const metaFlag =
        import.meta.env.VITE_EXPOSE_DEMO_CREDS ?? import.meta.env.EXPOSE_DEMO_CREDS;
      if (metaFlag === 'false' || metaFlag === '0') return false;
      if (metaFlag === 'true' || metaFlag === '1') return true;
    }
  } catch {
    // Gracefully ignore if import.meta is unavailable
  }

  // Default: visible unless explicitly turned off
  return true;
}
