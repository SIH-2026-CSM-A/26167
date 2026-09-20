import React from 'react';
import { X } from 'lucide-react';
import type { Answer } from '@/types/contracts';
import { HistoryPanel } from '@/components/History/HistoryPanel';
import { TracePanel } from '@/components/Trace/TracePanel';

export interface ConsoleRailProps {
  isOpen: boolean;
  onClose: () => void;
  answer: Answer | null;
  onSelectEvidence: (id: string) => void;
}

/** Collapsed-by-default rail overlaying the map hero (chosen over pushing it, so the
 * MapLibre container's box never resizes — see MapHero/EvidenceMap resize handling). */
export const ConsoleRail: React.FC<ConsoleRailProps> = ({ isOpen, onClose, answer, onSelectEvidence }) => (
  <div
    className={`absolute inset-y-0 left-0 z-20 flex w-[320px] max-w-[85%] flex-col overflow-hidden rounded-l-xl shadow-2xl transition-transform duration-300 ${
      isOpen ? 'translate-x-0' : '-translate-x-full'
    }`}
    style={{ background: 'var(--bg-1)', borderRight: '1px solid var(--line)' }}
    aria-hidden={!isOpen}
  >
    <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid var(--line)' }}>
      <span
        className="text-[10px] font-medium uppercase tracking-widest"
        style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
      >
        History &amp; Trace
      </span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Collapse rail"
        className="rounded p-1 transition-colors hover:opacity-80"
        style={{ color: 'var(--text-low)' }}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
    <div className="flex-1 overflow-hidden" style={{ borderBottom: '1px solid var(--line)' }}>
      <TracePanel answer={answer} onSelectEvidence={onSelectEvidence} showDownload={false} />
    </div>
    <div className="flex-1 overflow-y-auto">
      <HistoryPanel refreshKey={answer} />
    </div>
  </div>
);

export default ConsoleRail;
