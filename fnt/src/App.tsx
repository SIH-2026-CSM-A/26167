import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { UploadPage } from '@/pages/UploadPage';
import { ChatPage } from '@/pages/ChatPage';
import { MapPage } from '@/pages/MapPage';
import { LoginPage } from '@/pages/LoginPage';
import { OAuthCallbackPage } from '@/pages/OAuthCallbackPage';
import { SatQueryProvider } from '@/context/SatQueryProvider';
import { AuthProvider } from '@/context/AuthProvider';
import { ProtectedRoute } from '@/components/ProtectedRoute';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <SatQueryProvider>
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
          <Navbar />
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
              <Route
                path="/map"
                element={
                  <ProtectedRoute>
                    <MapPage />
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
