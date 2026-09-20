import React, { useRef, useState } from 'react';
import { PanelLeft, ShieldCheck, AlertCircle } from 'lucide-react';
import { useSatQuery } from '@/hooks/useSatQuery';
import { ChatMessageItem } from '@/components/Chat/ChatMessageItem';
import { ChatInput } from '@/components/Chat/ChatInput';
import { MapHero } from '@/components/Map/MapHero';
import type { EvidenceMapHandle } from '@/components/Map/EvidenceMap';
import { ConsoleRail } from '@/components/Console/ConsoleRail';
import type { ChatMessage } from '@/types/contracts';

const EmptyChatNotice: React.FC = () => (
  <div className="rounded-lg p-4 text-sm" style={{ border: '1px solid var(--line)', color: 'var(--text-mid)' }}>
    Welcome to SatQuery AI. Attach satellite passes (Optical / SAR) and submit your query to
    run intent routing, feature grounding, and change detection.
  </div>
);

// ponytail: no dedicated model-identity API field yet, so this falls back to a
// hardcoded string until B14's backend metadata is exposed to the frontend.
const FALLBACK_MODEL_IDENTITY = 'InternVL3-2B + LoRA (YASH-004)';

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
      className="mb-4 flex items-center gap-3 rounded-lg p-3 text-xs"
      style={{ border: '1px solid var(--danger)', background: 'rgba(210,87,75,0.12)', color: 'var(--text-hi)' }}
    >
      <AlertCircle className="h-4 w-4 shrink-0" style={{ color: 'var(--danger)' }} />
      <span className="flex-1">{error}</span>
      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          disabled={isRetrying}
          className="shrink-0 rounded-md px-3 py-1 text-[11px] font-semibold uppercase tracking-wider disabled:cursor-not-allowed disabled:opacity-60"
          style={{ border: '1px solid var(--danger)', color: 'var(--danger)' }}
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

  const [isRailOpen, setIsRailOpen] = useState(false);
  const mapRef = useRef<EvidenceMapHandle>(null);

  const toggleRail = () => {
    setIsRailOpen((open) => !open);
    // Overlay was chosen over pushing the map specifically so the MapLibre container's
    // box never changes size — this resize call is a cheap safety net in case the rail
    // ever clips/masks the container in a way that does change its visible box.
    window.setTimeout(() => mapRef.current?.resize(), 320);
  };

  const modelIdentity =
    [...messages]
      .reverse()
      .flatMap((message) => message.answer?.evidence ?? [])
      .map((evidence) => evidence.payload?.model_id)
      .find((value): value is string => typeof value === 'string') ?? null;

  return (
    <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1
            className="text-2xl sm:text-3xl"
            style={{ color: 'var(--text-hi)', fontFamily: 'var(--font-display)' }}
          >
            Mission Console
          </h1>
          <p className="mt-1 text-xs sm:text-sm" style={{ color: 'var(--text-low)' }}>
            Natural language interrogation powered by {modelIdentity ?? FALLBACK_MODEL_IDENTITY} with
            strict evidence grounding.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleRail}
            aria-pressed={isRailOpen}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
            style={
              isRailOpen
                ? { border: '1px solid var(--accent)', background: 'var(--accent-dim)', color: 'var(--accent)' }
                : { border: '1px solid var(--line)', background: 'var(--bg-2)', color: 'var(--text-low)' }
            }
          >
            <PanelLeft className="h-4 w-4" />
            <span>{isRailOpen ? 'Hide History & Trace' : 'History & Trace'}</span>
          </button>
          <div
            className="hidden items-center gap-1.5 rounded-md px-3 py-1.5 text-xs sm:flex"
            style={{ border: '1px solid var(--line)', color: 'var(--text-mid)' }}
          >
            <ShieldCheck className="h-4 w-4" style={{ color: 'var(--accent)' }} />
            <span>Verification Active</span>
          </div>
        </div>
      </div>

      <ChatErrorBanner
        error={error}
        canRetry={Boolean(error && lastSubmission)}
        isRetrying={isLoading}
        onRetry={() => {
          void retryLastSubmission();
        }}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="relative h-[720px] overflow-hidden rounded-xl">
          <MapHero
            evidenceList={evidenceList}
            selectedEvidenceId={selectedEvidenceId}
            hoveredEvidenceId={hoveredEvidenceId}
            onSelectEvidence={selectEvidence}
            onHoverEvidence={hoverEvidence}
            ref={mapRef}
          />
          <ConsoleRail
            isOpen={isRailOpen}
            onClose={() => setIsRailOpen(false)}
            answer={currentAnswer}
            onSelectEvidence={selectEvidence}
          />
        </div>

        <div
          className="flex h-[720px] flex-col overflow-hidden rounded-xl"
          style={{ border: '1px solid var(--line)', background: 'var(--bg-1)' }}
        >
          <div className="flex-1 space-y-5 overflow-y-auto p-4 sm:p-6">
            {messages.length === 0 ? (
              <EmptyChatNotice />
            ) : (
              messages.map((msg: ChatMessage) => (
                <ChatMessageItem
                  key={msg.id}
                  message={msg}
                  selectedEvidenceId={selectedEvidenceId}
                  hoveredEvidenceId={hoveredEvidenceId}
                  onSelectEvidence={selectEvidence}
                  onHoverEvidence={hoverEvidence}
                />
              ))
            )}
          </div>
          <ChatInput onSubmit={submitUserQuery} isLoading={isLoading} />
        </div>
      </div>
    </main>
  );
};

export default ChatPage;
