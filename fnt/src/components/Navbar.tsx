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
    <header
      className="sticky top-0 z-50 w-full backdrop-blur-md"
      style={{ borderBottom: '1px solid var(--line)', background: 'rgba(17,18,16,0.85)' }}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ background: 'var(--accent-dim)', color: 'var(--accent)', border: '1px solid var(--accent)' }}
          >
            <Satellite className="h-5 w-5" />
          </div>
          <div>
            <span style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }} className="text-lg">
              SatQuery AI
            </span>
            <span
              className="ml-2 hidden text-xs font-medium sm:inline"
              style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
            >
              SIH26167
            </span>
          </div>
        </div>

        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              aria-label={label}
              className="flex items-center gap-2 rounded-md p-2 text-sm font-medium transition-colors sm:px-3"
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--accent-dim)', color: 'var(--accent)', border: '1px solid var(--accent)' }
                  : { color: 'var(--text-mid)', border: '1px solid transparent' }
              }
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:flex items-center">
          <div
            className="flex items-center gap-2 rounded-full px-3 py-1 text-xs"
            style={{
              background: 'var(--ndvi-fill)',
              border: '1px solid var(--ndvi)',
              color: 'var(--ndvi)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            <span className="h-2 w-2 animate-pulse rounded-full" style={{ background: 'var(--ndvi)' }} />
            <span>Ground link active</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
