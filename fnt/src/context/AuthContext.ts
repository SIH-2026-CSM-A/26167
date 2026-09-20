import { createContext } from 'react';
import type { UserPublic } from '@/services/auth';

export interface AuthContextValue {
  user: UserPublic | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Used by the OAuth callback page: the redirect only carries an access token, so this
   * fetches the user record for it and hydrates the session the same way login()/register() do.
   */
  setSessionFromAccessToken: (accessToken: string) => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export default AuthContext;
