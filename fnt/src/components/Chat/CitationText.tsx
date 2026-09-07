import React, { useRef, useEffect, useMemo } from 'react';
import type { Evidence } from '@/types/contracts';
import { CitationChip } from './CitationChip';

export interface CitationTextProps {
  text: string;
  evidenceList?: Evidence[];
  selectedEvidenceId?: string | null;
  hoveredEvidenceId?: string | null;
  onSelectEvidence: (id: string) => void;
  onHoverEvidence?: (id: string | null) => void;
}

function resolveEvidence(
  rawTag: string,
  evidenceList: Evidence[]
): { id: string; ev?: Evidence } | null {
  const inner = rawTag.slice(1, -1).trim();
  const byExactId = evidenceList.find(
    (e) => e.id.toLowerCase() === inner.toLowerCase()
  );
  if (byExactId) return { id: byExactId.id, ev: byExactId };

  const num = parseInt(inner, 10);
  if (!isNaN(num) && num > 0 && num <= evidenceList.length) {
    const byIndex = evidenceList[num - 1];
    return { id: byIndex.id, ev: byIndex };
  }

  if (inner.toLowerCase().startsWith('ev-')) {
    return { id: inner };
  }
  return null;
}

function extractCitedEvidenceIds(text: string, evidenceList: Evidence[]): string[] {
  const matches = text.match(/\[[^\]]+\]/g) || [];
  return matches
    .map((tag) => resolveEvidence(tag, evidenceList)?.id)
    .filter((id): id is string => Boolean(id));
}

interface CitingParagraphProps {
  content: string;
  evidenceList: Evidence[];
  selectedEvidenceId: string | null;
  hoveredEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  onHoverEvidence?: (id: string | null) => void;
}

const CitingParagraph: React.FC<CitingParagraphProps> = ({
  content,
  evidenceList,
  selectedEvidenceId,
  hoveredEvidenceId,
  onSelectEvidence,
  onHoverEvidence,
}) => {
  const paragraphRef = useRef<HTMLParagraphElement>(null);
  const citedIds = useMemo(
    () => extractCitedEvidenceIds(content, evidenceList),
    [content, evidenceList]
  );
  const isCitingSelected = Boolean(selectedEvidenceId && citedIds.includes(selectedEvidenceId));

  useEffect(() => {
    if (isCitingSelected && paragraphRef.current) {
      paragraphRef.current.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    }
  }, [isCitingSelected]);

  const parts = content.split(/(\[[^\]]+\])/g);

  return (
    <p
      ref={paragraphRef}
      data-testid="citing-paragraph"
      data-highlighted={isCitingSelected ? 'true' : 'false'}
      data-evidence-ids={citedIds.join(',')}
      className={`leading-relaxed rounded-lg p-2 transition-all duration-300 ${
        isCitingSelected
          ? 'bg-cyan-950/70 ring-2 ring-cyan-400/80 border-l-4 border-cyan-400 shadow-md shadow-cyan-950/50'
          : 'border-l-4 border-transparent'
      }`}
    >
      {parts.map((part, index) => {
        if (part.startsWith('[') && part.endsWith(']')) {
          const resolved = resolveEvidence(part, evidenceList);
          if (resolved) {
            return (
              <CitationChip
                key={`${resolved.id}-${index}`}
                evidenceId={resolved.id}
                evidence={resolved.ev}
                isSelected={selectedEvidenceId === resolved.id}
                isHovered={hoveredEvidenceId === resolved.id}
                onClick={onSelectEvidence}
                onHover={onHoverEvidence}
              />
            );
          }
        }
        return <span key={index}>{part}</span>;
      })}
    </p>
  );
};

export const CitationText: React.FC<CitationTextProps> = ({
  text,
  evidenceList = [],
  selectedEvidenceId = null,
  hoveredEvidenceId = null,
  onSelectEvidence,
  onHoverEvidence,
}) => {
  const paragraphs = useMemo(() => {
    const raw = text.split(/\n{2,}|\n/).map((p) => p.trim()).filter(Boolean);
    return raw.length > 0 ? raw : [text];
  }, [text]);

  return (
    <div className="space-y-2">
      {paragraphs.map((paragraph, index) => (
        <CitingParagraph
          key={index}
          content={paragraph}
          evidenceList={evidenceList}
          selectedEvidenceId={selectedEvidenceId}
          hoveredEvidenceId={hoveredEvidenceId}
          onSelectEvidence={onSelectEvidence}
          onHoverEvidence={onHoverEvidence}
        />
      ))}
    </div>
  );
};

export default CitationText;
