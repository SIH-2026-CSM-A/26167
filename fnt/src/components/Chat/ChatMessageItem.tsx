import React, { useState } from 'react';
import type { ChatMessage, Answer, StatsPayload } from '@/types/contracts';
import { CitationText } from './CitationText';
import { CitationChip } from './CitationChip';
import { EvidenceSummaryCard } from '@/components/EvidenceSummaryCard';
import { downloadEvidencePdf } from '@/services/api';

export interface ChatMessageItemProps {
  message: ChatMessage;
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  hoveredEvidenceId?: string | null;
  onHoverEvidence?: (id: string | null) => void;
}

const ObserverTurn: React.FC<{ content: string }> = ({ content }) => (
  <div className="flex flex-col items-end gap-1 text-right">
    <span
      className="text-[10px] font-medium uppercase tracking-widest"
      style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
    >
      Observer
    </span>
    <p className="max-w-xl whitespace-pre-wrap italic" style={{ color: 'var(--observer)', fontFamily: 'var(--font-sans)' }}>
      {content}
    </p>
  </div>
);

/* Only ever renders numbers that trace back to a real evidence-schema entry — never a
 * fabricated figure. Matches exactly what the old MapHeroMetrics metric-card row showed
 * (confidence / change / AOI area); modality and hazard flag have no backing evidence
 * source today and are deliberately left out, same as that component's own rule. */
const EvidenceMetadataGrid: React.FC<{ answer: Answer }> = ({ answer }) => {
  const statsEvidence = answer.evidence.find((item) => item.type === 'stats');
  const stats = statsEvidence?.payload as StatsPayload | undefined;

  const fields: { label: string; value: string }[] = [
    { label: 'Confidence', value: `${(answer.confidence * 100).toFixed(1)}%` },
  ];
  if (typeof stats?.change_percent === 'number') {
    fields.push({
      label: 'Change',
      value: `${stats.change_percent > 0 ? '+' : ''}${stats.change_percent.toFixed(1)}%`,
    });
  }
  if (typeof stats?.area_sqkm === 'number') {
    fields.push({ label: 'AOI area', value: `${stats.area_sqkm.toLocaleString()} km²` });
  }
  if (fields.length === 0) return null;

  return (
    <div
      className="grid grid-cols-2 gap-x-6 gap-y-2 rounded-lg px-3.5 py-3 text-xs"
      style={{ border: '1px solid var(--line)', background: 'var(--bg-2)' }}
    >
      {fields.map((field) => (
        <div key={field.label}>
          <div
            className="text-[10px] uppercase tracking-wide"
            style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
          >
            {field.label}
          </div>
          <div className="mt-0.5" style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-mono)' }}>
            {field.value}
          </div>
        </div>
      ))}
    </div>
  );
};

/* Condenses TracePanel/ExecutionTracePanel's real step data into a short inline sequence —
 * the underlying step data isn't discarded, just displayed differently here. */
const InlineTraceSequence: React.FC<{ answer: Answer }> = ({ answer }) => {
  if (answer.trace.steps.length === 0) return null;
  const parts = answer.trace.steps.map((step) => {
    const confidence = step.confidence !== null ? ` ${(step.confidence * 100).toFixed(0)}%` : '';
    return `${step.module}/${step.action}${confidence}`;
  });
  return (
    <p className="text-[11px]" style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}>
      Processing. {parts.join(' → ')}.
    </p>
  );
};

const DownloadReportAction: React.FC<{ answer: Answer }> = ({ answer }) => {
  const [isDownloading, setIsDownloading] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        setIsDownloading(true);
        void downloadEvidencePdf(answer).finally(() => setIsDownloading(false));
      }}
      disabled={isDownloading}
      className="self-start text-[11px] font-medium uppercase tracking-wide transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
      style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}
    >
      {isDownloading ? 'Generating PDF…' : 'Download evidence report ↓'}
    </button>
  );
};

const GroundedEvidenceRibbon: React.FC<{
  answer: Answer;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover?: (id: string | null) => void;
}> = ({ answer, selectedId, hoveredId, onSelect, onHover }) => {
  if (!answer.evidence.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 pt-2 text-xs" style={{ borderTop: '1px solid var(--line)' }}>
      <span
        className="font-medium"
        style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
      >
        Citations:
      </span>
      {answer.evidence.map((ev) => (
        <CitationChip
          key={ev.id}
          evidenceId={ev.id}
          evidence={ev}
          isSelected={selectedId === ev.id}
          isHovered={hoveredId === ev.id}
          onClick={onSelect}
          onHover={onHover}
        />
      ))}
    </div>
  );
};

const IntelligenceTurn: React.FC<{
  content: string;
  answer?: Answer;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  onHover?: (id: string | null) => void;
}> = ({ content, answer, selectedId, hoveredId, onSelect, onHover }) => (
  <div className="flex flex-col gap-3">
    <span
      className="text-[10px] font-medium uppercase tracking-widest"
      style={{ color: 'var(--text-low)', fontFamily: 'var(--font-mono)' }}
    >
      Intelligence
    </span>
    <div style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-sans)' }}>
      <CitationText
        text={content}
        evidenceList={answer?.evidence ?? []}
        selectedEvidenceId={selectedId}
        hoveredEvidenceId={hoveredId}
        onSelectEvidence={onSelect}
        onHoverEvidence={onHover}
      />
    </div>
    {answer && <InlineTraceSequence answer={answer} />}
    {answer && <EvidenceMetadataGrid answer={answer} />}
    {answer && answer.evidence.length > 0 && (
      <div className="flex flex-col gap-2">
        {answer.evidence.map((ev) => (
          <EvidenceSummaryCard key={ev.id} evidence={ev} onViewOnMap={onSelect} />
        ))}
      </div>
    )}
    {answer && (
      <GroundedEvidenceRibbon
        answer={answer}
        selectedId={selectedId}
        hoveredId={hoveredId}
        onSelect={onSelect}
        onHover={onHover}
      />
    )}
    {answer && <DownloadReportAction answer={answer} />}
  </div>
);

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  selectedEvidenceId,
  onSelectEvidence,
  hoveredEvidenceId = null,
  onHoverEvidence,
}) => {
  if (message.role === 'user') {
    return <ObserverTurn content={message.content} />;
  }
  return (
    <IntelligenceTurn
      content={message.content}
      answer={message.answer}
      selectedId={selectedEvidenceId}
      hoveredId={hoveredEvidenceId}
      onSelect={onSelectEvidence}
      onHover={onHoverEvidence}
    />
  );
};

export default ChatMessageItem;
