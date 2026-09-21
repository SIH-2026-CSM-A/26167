import React from 'react';

export interface PhotoLabelProps {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}

/** Guarantees legibility for text sitting directly on a full-bleed page photo
 * (LoginPage/UploadPage) — a tight opaque chip behind just the text, not a full panel.
 * A text-shadow alone proved insufficient over the photo's brightest patches (confirmed
 * live against real screenshots) — opacity is brightness-independent, a shadow isn't. */
export const PhotoLabel: React.FC<PhotoLabelProps> = ({ children, style, className = '' }) => (
  <span
    className={`inline-block rounded px-2 py-1 ${className}`}
    style={{ background: 'var(--bg-1)', width: 'fit-content', ...style }}
  >
    {children}
  </span>
);

export default PhotoLabel;
