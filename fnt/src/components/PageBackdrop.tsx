import React from 'react';

export interface PageBackdropProps {
  /** Defaults to the same NASA Earth Observatory night-lights image used on LoginPage —
   * public domain, U.S. government work.
   * Source: https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg */
  image?: string;
}

/** Fixed, full-viewport photo behind everything — no dimming scrim. Panels keep their own
 * solid backgrounds; the photo only shows through the gaps around/between them. Render this
 * as the first thing a page returns so it paints behind the page's own content, and rely on
 * Navbar's z-50 (see components/Navbar.tsx) to stay above it without a z-index here. */
export const PageBackdrop: React.FC<PageBackdropProps> = ({ image = '/assets/earth-night-lights.jpg' }) => (
  <div
    className="fixed inset-0"
    style={{ backgroundImage: `url(${image})`, backgroundSize: 'cover', backgroundPosition: 'center' }}
    aria-hidden="true"
  />
);

export default PageBackdrop;
