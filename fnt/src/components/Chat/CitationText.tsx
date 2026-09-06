import React from 'react';
import type { Evidence } from '@/types/contracts';
import { CitationChip } from './CitationChip';

export interface CitationTextProps {
  text: string;
  evidenceList?: Evidence[];
  selectedEvidenceId?: string | null;
  onSelectEvidence: (id: string) => void;
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

export const CitationText: React.FC<CitationTextProps> = ({
  text,
  evidenceList = [],
  selectedEvidenceId = null,
  onSelectEvidence,
}) => {
  const parts = text.split(/(\[[^\]]+\])/g);

  return (
    <span className="leading-relaxed">
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
                onClick={onSelectEvidence}
              />
            );
          }
        }
        return <span key={index}>{part}</span>;
      })}
    </span>
  );
};

export default CitationText;
