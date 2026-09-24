import React from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { UploadPage } from '@/pages/UploadPage';
import { ChatPage } from '@/pages/ChatPage';
import { LoginPage } from '@/pages/LoginPage';
import { OAuthCallbackPage } from '@/pages/OAuthCallbackPage';
import { SatQueryProvider } from '@/context/SatQueryProvider';
import { AuthProvider } from '@/context/AuthProvider';
import { ProtectedRoute } from '@/components/ProtectedRoute';

export const App: React.FC = () => {
  const location = useLocation();
  // Login is a full-bleed background scene with the auth card floating on top of it —
  // the navbar's own opaque bar would cut that image short, so it's hidden on this route
  // rather than turned into a transparent overlay bar (cleaner, and its nav links are
  // auth-gated pages that don't make sense to show pre-login anyway).
  const showNavbar = location.pathname !== '/login';

  return (
    <AuthProvider>
      <SatQueryProvider>
        <div
          className="min-h-screen flex flex-col"
          style={{ background: 'var(--bg-0)', color: 'var(--text-hi)' }}
        >
          {showNavbar && <Navbar />}
          <div className="flex-1">
            <Routes>
              <Route path="/" element={<Navigate to="/upload" replace />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/auth/callback" element={<OAuthCallbackPage />} />
              <Route
                path="/upload"
                element={
                  <ProtectedRoute>
                    <UploadPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/chat"
                element={
                  <ProtectedRoute>
                    <ChatPage />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/upload" replace />} />
            </Routes>
          </div>
        </div>
      </SatQueryProvider>
    </AuthProvider>
  );
};

export default App;
