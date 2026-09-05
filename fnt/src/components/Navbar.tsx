import React from 'react';
import { NavLink } from 'react-router-dom';
import { Upload, MessageSquare, MapPin, Satellite } from 'lucide-react';

export const Navbar: React.FC = () => {
  const navItems = [
    { to: '/upload', label: 'Upload', icon: Upload },
    { to: '/chat', label: 'Chat & VQA', icon: MessageSquare },
    { to: '/map', label: 'Map View', icon: MapPin },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
            <Satellite className="h-5 w-5" />
          </div>
          <div>
            <span className="text-lg font-bold tracking-tight text-white">SatQuery AI</span>
            <span className="ml-2 text-xs font-medium text-slate-400">SIH26167</span>
          </div>
        </div>

        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-cyan-600/15 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:flex items-center">
          <div className="flex items-center gap-2 rounded-full bg-emerald-950/50 border border-emerald-500/40 px-3 py-1 text-xs font-mono text-emerald-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Tailwind CSS Active</span>
          </div>
        </div>
      </div>
    </header>
  );
};
