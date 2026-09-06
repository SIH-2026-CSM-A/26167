import React, { useState } from 'react';
import { ShieldCheck, Map as MapIcon, Bot, AlertCircle } from 'lucide-react';
import { useSatQuery } from '@/hooks/useSatQuery';
import { ChatMessageItem } from '@/components/Chat/ChatMessageItem';
import { ChatInput } from '@/components/Chat/ChatInput';
import { EvidenceMap } from '@/components/Map/EvidenceMap';
import type { ChatMessage, Modality } from '@/types/contracts';

const EmptyChatNotice: React.FC = () => (
  <div className="flex items-start gap-3">
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
      <Bot className="h-4 w-4" />
    </div>
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-200">
      <p>
        Welcome to SatQuery AI. Attach satellite passes (Optical / SAR) and submit your query
        to run intent routing, feature grounding, and change detection.
      </p>
    </div>
  </div>
);

const ChatConversationPane: React.FC<{
  messages: ChatMessage[];
  selectedEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  onSubmit: (query: string, files: File[], modalities: Modality[]) => void;
  isLoading: boolean;
  isMapVisible: boolean;
}> = ({ messages, selectedEvidenceId, onSelectEvidence, onSubmit, isLoading, isMapVisible }) => (
  <div
    className={`flex flex-col h-[640px] rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden ${
      isMapVisible ? 'lg:col-span-6 xl:col-span-5' : 'lg:col-span-12'
    }`}
  >
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
      {messages.length === 0 ? (
        <EmptyChatNotice />
      ) : (
        messages.map((msg) => (
          <ChatMessageItem
            key={msg.id}
            message={msg}
            selectedEvidenceId={selectedEvidenceId}
            onSelectEvidence={onSelectEvidence}
          />
        ))
      )}
    </div>
    <ChatInput onSubmit={onSubmit} isLoading={isLoading} />
  </div>
);

const ChatPageHeader: React.FC<{ isMapVisible: boolean; onToggleMap: () => void }> = ({
  isMapVisible,
  onToggleMap,
}) => (
  <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">VLM Assistant & Query</h1>
      <p className="mt-1 text-xs sm:text-sm text-slate-400">
        Natural language interrogation powered by InternVL2-2B with strict evidence grounding.
      </p>
    </div>
    <div className="flex items-center gap-2">
      <button
        onClick={onToggleMap}
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
          isMapVisible
            ? 'border-cyan-500/50 bg-cyan-950/60 text-cyan-300'
            : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-white'
        }`}
      >
        <MapIcon className="h-4 w-4" />
        <span>{isMapVisible ? 'Hide Evidence Map' : 'Show Evidence Map'}</span>
      </button>
      <div className="hidden sm:flex items-center gap-1.5 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
        <ShieldCheck className="h-4 w-4 text-emerald-400" />
        <span>Verification Active</span>
      </div>
    </div>
  </div>
);

const ChatErrorBanner: React.FC<{ error: string | null }> = ({ error }) => {
  if (!error) return null;
  return (
    <div className="mb-4 flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-950/40 p-3 text-xs text-rose-300">
      <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
      <span>{error}</span>
    </div>
  );
};

export const ChatPage: React.FC = () => {
  const {
    messages,
    evidenceList,
    selectedEvidenceId,
    selectEvidence,
    submitUserQuery,
    isLoading,
    error,
  } = useSatQuery();
  const [isMapVisible, setIsMapVisible] = useState(true);

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <ChatPageHeader isMapVisible={isMapVisible} onToggleMap={() => setIsMapVisible(!isMapVisible)} />
      <ChatErrorBanner error={error} />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <ChatConversationPane
          messages={messages}
          selectedEvidenceId={selectedEvidenceId}
          onSelectEvidence={(id) => {
            selectEvidence(id);
            if (!isMapVisible) setIsMapVisible(true);
          }}
          onSubmit={submitUserQuery}
          isLoading={isLoading}
          isMapVisible={isMapVisible}
        />
        {isMapVisible && (
          <div className="lg:col-span-6 xl:col-span-7 h-[640px]">
            <EvidenceMap
              evidenceList={evidenceList}
              selectedEvidenceId={selectedEvidenceId}
              onSelectEvidence={selectEvidence}
              className="h-full w-full"
            />
          </div>
        )}
      </div>
    </main>
  );
};

export default ChatPage;
