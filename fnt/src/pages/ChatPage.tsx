import React, { useState } from 'react';
import { ShieldCheck, Map as MapIcon, Bot, AlertCircle } from 'lucide-react';
import { useSatQuery } from '@/hooks/useSatQuery';
import { ChatMessageItem } from '@/components/Chat/ChatMessageItem';
import { ChatInput } from '@/components/Chat/ChatInput';
import { EvidenceMap } from '@/components/Map/EvidenceMap';
import { TracePanel } from '@/components/Trace/TracePanel';
import { HistoryPanel } from '@/components/History/HistoryPanel';
import { Legend } from '@/components/Console/Legend';
import { MetricCard } from '@/components/Console/MetricCard';
import type { Answer, ChatMessage, Modality, StatsPayload } from '@/types/contracts';

/* Only ever renders numbers that trace back to a real evidence-schema entry — never a
 * fabricated figure (e.g. the mockup's static "Hazard flag" has no backing evidence source
 * and is intentionally left out here). */
const MapHeroMetrics: React.FC<{ answer: Answer | null }> = ({ answer }) => {
  if (answer === null) return null;
  const statsEvidence = answer.evidence.find((item) => item.type === 'stats');
  const stats = statsEvidence?.payload as StatsPayload | undefined;

  return (
    <div className="mt-3 flex flex-col gap-2">
      <Legend />
      <div className="flex gap-3">
        {typeof stats?.change_percent === 'number' && (
          <MetricCard
            label="Change detected"
            value={`${stats.change_percent > 0 ? '+' : ''}${stats.change_percent.toFixed(1)}%`}
            tone={stats.change_percent >= 0 ? 'up' : 'default'}
          />
        )}
        <MetricCard label="Confidence" value={`${(answer.confidence * 100).toFixed(1)}%`} />
        {typeof stats?.area_sqkm === 'number' && (
          <MetricCard label="AOI area" value={`${stats.area_sqkm.toLocaleString()} km²`} />
        )}
      </div>
    </div>
  );
};

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
  hoveredEvidenceId: string | null;
  onSelectEvidence: (id: string) => void;
  onHoverEvidence: (id: string | null) => void;
  onSubmit: (query: string, files: File[], modalities: Modality[]) => Promise<boolean>;
  isLoading: boolean;
  isMapVisible: boolean;
}> = ({
  messages,
  selectedEvidenceId,
  hoveredEvidenceId,
  onSelectEvidence,
  onHoverEvidence,
  onSubmit,
  isLoading,
  isMapVisible,
}) => (
  <div
    className={`flex flex-col h-[640px] rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden ${
      isMapVisible ? 'lg:col-span-4' : 'lg:col-span-9'
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
            hoveredEvidenceId={hoveredEvidenceId}
            onSelectEvidence={onSelectEvidence}
            onHoverEvidence={onHoverEvidence}
          />
        ))
      )}
    </div>
    <ChatInput onSubmit={onSubmit} isLoading={isLoading} />
  </div>
);

// ponytail: no dedicated model-identity API field yet, so this falls back to a
// hardcoded string until B14's backend metadata is exposed to the frontend.
const FALLBACK_MODEL_IDENTITY = 'InternVL3-2B + LoRA (YASH-004)';

const ChatPageHeader: React.FC<{
  isMapVisible: boolean;
  onToggleMap: () => void;
  modelIdentity: string | null;
}> = ({ isMapVisible, onToggleMap, modelIdentity }) => (
  <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">VLM Assistant & Query</h1>
      <p className="mt-1 text-xs sm:text-sm text-slate-400">
        Natural language interrogation powered by {modelIdentity ?? FALLBACK_MODEL_IDENTITY} with
        strict evidence grounding.
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

const ChatErrorBanner: React.FC<{
  error: string | null;
  canRetry: boolean;
  isRetrying: boolean;
  onRetry: () => void;
}> = ({ error, canRetry, isRetrying, onRetry }) => {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="mb-4 flex items-center gap-3 rounded-lg border border-rose-500/40 bg-rose-950/40 p-3 text-xs text-rose-300"
    >
      <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
      <span className="flex-1">{error}</span>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={isRetrying}
          className="shrink-0 rounded-md border border-rose-400/40 bg-rose-900/40 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-rose-200 transition hover:bg-rose-900/60 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isRetrying ? 'Retrying...' : 'Retry'}
        </button>
      )}
    </div>
  );
};

export const ChatPage: React.FC = () => {
  const {
    messages,
    currentAnswer,
    evidenceList,
    selectedEvidenceId,
    hoveredEvidenceId,
    selectEvidence,
    hoverEvidence,
    submitUserQuery,
    retryLastSubmission,
    lastSubmission,
    isLoading,
    error,
  } = useSatQuery();
  const [isMapVisible, setIsMapVisible] = useState(true);
  const modelIdentity =
    [...messages]
      .reverse()
      .flatMap((message) => message.answer?.evidence ?? [])
      .map((evidence) => evidence.payload?.model_id)
      .find((value): value is string => typeof value === 'string') ?? null;

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <ChatPageHeader
        isMapVisible={isMapVisible}
        onToggleMap={() => setIsMapVisible(!isMapVisible)}
        modelIdentity={modelIdentity}
      />
      <ChatErrorBanner
        error={error}
        canRetry={Boolean(error && lastSubmission)}
        isRetrying={isLoading}
        onRetry={() => {
          void retryLastSubmission();
        }}
      />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <ChatConversationPane
          messages={messages}
          selectedEvidenceId={selectedEvidenceId}
          hoveredEvidenceId={hoveredEvidenceId}
          onSelectEvidence={(id) => {
            selectEvidence(id);
            if (!isMapVisible) setIsMapVisible(true);
          }}
          onHoverEvidence={hoverEvidence}
          onSubmit={submitUserQuery}
          isLoading={isLoading}
          isMapVisible={isMapVisible}
        />
        {isMapVisible && (
          <div className="lg:col-span-5 flex h-[640px] flex-col">
            <div className="flex-1 min-h-0">
              <EvidenceMap
                evidenceList={evidenceList}
                selectedEvidenceId={selectedEvidenceId}
                hoveredEvidenceId={hoveredEvidenceId}
                onSelectEvidence={selectEvidence}
                onHoverEvidence={hoverEvidence}
                className="h-full w-full"
              />
            </div>
            <MapHeroMetrics answer={currentAnswer} />
          </div>
        )}
        <div
          className="lg:col-span-3 flex h-[640px] flex-col overflow-hidden rounded-xl"
          style={{ background: 'var(--bg-1)', border: '1px solid var(--line)' }}
        >
          <div className="flex-1 overflow-hidden border-b" style={{ borderColor: 'var(--line)' }}>
            <TracePanel answer={currentAnswer} onSelectEvidence={selectEvidence} />
          </div>
          <div className="flex-1 overflow-y-auto">
            <HistoryPanel refreshKey={currentAnswer} />
          </div>
        </div>
      </div>
    </main>
  );
};

export default ChatPage;
