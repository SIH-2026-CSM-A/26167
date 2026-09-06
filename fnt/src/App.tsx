import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Navbar } from '@/components/Navbar';
import { UploadPage } from '@/pages/UploadPage';
import { ChatPage } from '@/pages/ChatPage';
import { MapPage } from '@/pages/MapPage';
import { SatQueryProvider } from '@/context/SatQueryProvider';

export const App: React.FC = () => {
  return (
    <SatQueryProvider>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/map" element={<MapPage />} />
            <Route path="*" element={<Navigate to="/upload" replace />} />
          </Routes>
        </div>
      </div>
    </SatQueryProvider>
  );
};

export default App;
