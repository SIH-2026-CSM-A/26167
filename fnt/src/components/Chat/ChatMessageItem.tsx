import React from 'react';
import { Bot, User, Layers } from 'lucide-react';
import type { ChatMessage, Answer } from '@/types/contracts';
import { CitationText } from './CitationText';
import { CitationChip } from './CitationChip';
import { ConfidenceBadge } from './ConfidenceBadge';
import { ExecutionTracePanel } from '@/components/Trace/ExecutionTracePanel';

export interface ChatMessageItemProps {
  message: ChatMessage;
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
}

const UserBubble: React.FC<{ content: string }> = ({ content }) => (
  <div className="flex items-start gap-3 justify-end">
    <div className="rounded-2xl rounded-tr-none bg-cyan-600 px-4 py-3 text-sm text-white max-w-xl shadow-lg shadow-cyan-950/30">
      <p className="whitespace-pre-wrap">{content}</p>
    </div>
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-800 text-white shadow">
      <User className="h-4 w-4" />
    </div>
  </div>
);

const GroundedEvidenceRibbon: React.FC<{
  answer: Answer;
  selectedId: string | null;
  onSelect: (id: string) => void;
}> = ({ answer, selectedId, onSelect }) => {
  if (!answer.evidence.length) return null;
  return (
    <div className="pt-2 border-t border-slate-800/80 flex items-center gap-2 flex-wrap text-xs">
      <span className="flex items-center gap-1 text-slate-400 font-medium">
        <Layers className="h-3 w-3 text-cyan-400" />
        Citations:
      </span>
      {answer.evidence.map((ev) => (
        <CitationChip
          key={ev.id}
          evidenceId={ev.id}
          evidence={ev}
          isSelected={selectedId === ev.id}
          onClick={onSelect}
        />
      ))}
    </div>
  );
};

const AssistantBubble: React.FC<{
  content: string;
  answer?: Answer;
  selectedId: string | null;
  onSelect: (id: string) => void;
}> = ({ content, answer, selectedId, onSelect }) => (
  <div className="flex items-start gap-3">
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30 shadow">
      <Bot className="h-4 w-4" />
    </div>
    <div className="flex-1 space-y-3 max-w-3xl">
      <div className="rounded-2xl rounded-tl-none border border-slate-800 bg-slate-900/90 p-4 text-sm text-slate-200 shadow-xl space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-800">
          <span className="font-semibold text-white">SatQuery Assistant</span>
          {answer && (
            <ConfidenceBadge
              confidence={answer.confidence}
              abstained={answer.abstained}
              abstentionReason={answer.abstention_reason}
            />
          )}
        </div>
        <div className="text-slate-200">
          <CitationText
            text={content}
            evidenceList={answer?.evidence ?? []}
            selectedEvidenceId={selectedId}
            onSelectEvidence={onSelect}
          />
        </div>
        {answer && (
          <GroundedEvidenceRibbon answer={answer} selectedId={selectedId} onSelect={onSelect} />
        )}
      </div>
      {answer?.trace && <ExecutionTracePanel trace={answer.trace} onSelectEvidence={onSelect} />}
    </div>
  </div>
);

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  selectedEvidenceId,
  onSelectEvidence,
}) => {
  if (message.role === 'user') {
    return <UserBubble content={message.content} />;
  }
  return (
    <AssistantBubble
      content={message.content}
      answer={message.answer}
      selectedId={selectedEvidenceId}
      onSelect={onSelectEvidence}
    />
  );
};

export default ChatMessageItem;
