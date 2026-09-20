import React from 'react';

/* Data-meaning colors only (--water/--ndvi/--thermal), per tokens.css's own semantic-color
 * rule — never reused as a decorative/interactive accent elsewhere. */
const LEGEND_ITEMS = [
  { label: 'Water', color: 'var(--water)' },
  { label: 'Vegetation', color: 'var(--ndvi)' },
  { label: 'Built-up', color: 'var(--thermal)' },
] as const;

export const Legend: React.FC = () => (
  <div className="flex gap-4 px-4 pb-3 text-xs" style={{ color: 'var(--text-mid)' }}>
    {LEGEND_ITEMS.map((item) => (
      <div key={item.label} className="flex items-center gap-1.5">
        <span
          className="h-2.5 w-2.5 rounded-sm"
          style={{ background: item.color }}
          aria-hidden="true"
        />
        {item.label}
      </div>
    ))}
  </div>
);

export default Legend;
