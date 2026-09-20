import { forwardRef } from 'react';
import { EvidenceMap, type EvidenceMapHandle, type EvidenceMapProps } from './EvidenceMap';
import { centroidReadout } from '@/utils/coords';

export interface MapHeroProps extends EvidenceMapProps {
  edgeLabel?: string;
}

/** Full-bleed map hero panel (console-v2): same EvidenceMap instance/logic, wrapped with a
 * rotated edge label and a real coordinate readout derived from the current evidence. */
export const MapHero = forwardRef<EvidenceMapHandle, MapHeroProps>(
  ({ edgeLabel = 'SENSOR FEED', evidenceList, className = 'h-full w-full', ...mapProps }, ref) => {
    const coords = centroidReadout(evidenceList);

    return (
      <div className="relative h-full w-full overflow-hidden rounded-xl" style={{ border: '1px solid var(--line)' }}>
        <EvidenceMap ref={ref} evidenceList={evidenceList} className={className} {...mapProps} />

        <span
          className="pointer-events-none absolute left-3 top-1/2 z-10 -translate-y-1/2 select-none text-[10px] font-medium uppercase tracking-[0.35em]"
          style={{
            writingMode: 'vertical-rl',
            transform: 'translateY(-50%) rotate(180deg)',
            color: 'var(--text-low)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {edgeLabel}
        </span>

        {coords && (
          <div
            className="pointer-events-none absolute bottom-4 left-4 z-10 text-xs tracking-wide"
            style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
          >
            {coords}
          </div>
        )}
      </div>
    );
  }
);

MapHero.displayName = 'MapHero';

export default MapHero;
