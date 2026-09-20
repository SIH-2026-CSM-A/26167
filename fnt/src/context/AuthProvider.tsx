import React, { useCallback, useEffect, useState } from 'react';
import {
  loginRequest,
  logoutRequest,
  meRequest,
  refreshRequest,
  registerRequest,
  type UserPublic,
} from '@/services/auth';
import { setAuthToken, setRefreshHandler } from '@/services/authFetch';
import { AuthContext, type AuthContextValue } from './AuthContext';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const applySession = useCallback((nextUser: UserPublic, accessToken: string) => {
    setUser(nextUser);
    setAuthToken(accessToken);
  }, []);

  const clearSession = useCallback(() => {
    setUser(null);
    setAuthToken(null);
  }, []);

  // Cold-start restore: there is never an access token in memory on a fresh page load
  // (memory-only storage), so GET /auth/me would always 401 regardless of session
  // validity. /auth/refresh is the only thing that can still be valid across a reload
  // (httpOnly, path=/auth cookie) and already returns the full user + token in one call.
  useEffect(() => {
    let cancelled = false;
    refreshRequest()
      .then((result) => {
        if (cancelled) return;
        if (result) applySession(result.user, result.access_token);
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applySession]);

  useEffect(() => {
    setRefreshHandler(async () => {
      const result = await refreshRequest().catch(() => null);
      if (!result) {
        clearSession();
        window.location.href = '/login';
        return null;
      }
      applySession(result.user, result.access_token);
      return result.access_token;
    });
    return () => setRefreshHandler(null);
  }, [applySession, clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const result = await loginRequest(email, password);
      applySession(result.user, result.access_token);
    },
    [applySession]
  );

  const register = useCallback(
    async (email: string, password: string) => {
      const result = await registerRequest(email, password);
      applySession(result.user, result.access_token);
    },
    [applySession]
  );

  const logout = useCallback(async () => {
    await logoutRequest().catch(() => undefined);
    clearSession();
  }, [clearSession]);

  const setSessionFromAccessToken = useCallback(async (accessToken: string) => {
    const nextUser = await meRequest(accessToken);
    applySession(nextUser, accessToken);
  }, [applySession]);

  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    setSessionFromAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthProvider;
