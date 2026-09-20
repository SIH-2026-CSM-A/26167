/** Bridges React auth state into plain fetch call sites (query.ts, api.ts) that can't call
 * useContext. Holds the current access token as a module-level value the AuthProvider keeps
 * in sync, attaches it as a Bearer header, and retries exactly once through a registered
 * refresh handler on a 401.
 */

let currentToken: string | null = null;

export function setAuthToken(token: string | null): void {
  currentToken = token;
}

export function getAuthToken(): string | null {
  return currentToken;
}

type RefreshHandler = () => Promise<string | null>;

let refreshHandler: RefreshHandler | null = null;

export function setRefreshHandler(handler: RefreshHandler | null): void {
  refreshHandler = handler;
}

function withAuthHeader(init: RequestInit, token: string | null): RequestInit {
  if (!token) return init;
  return {
    ...init,
    headers: { ...(init.headers ?? {}), Authorization: `Bearer ${token}` },
  };
}

/** fetch wrapper: attaches the current access token, and on a 401 attempts exactly one
 * refresh + retry before giving up. Both /query entry points (query.ts, api.ts) route
 * through this instead of duplicating header/retry logic.
 */
export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  let response = await fetch(input, withAuthHeader(init, currentToken));
  if (response.status === 401 && refreshHandler) {
    const newToken = await refreshHandler();
    if (newToken) {
      response = await fetch(input, withAuthHeader(init, newToken));
    }
  }
  return response;
}
