import React, { useState, useMemo, useCallback } from 'react';
import type { Answer, ChatMessage, Modality } from '@/types/contracts';
import { submitQuery, type SubmitQueryOptions } from '@/services/api';
import { SatQueryContext } from './SatQueryContext';

function createUserMessage(content: string): ChatMessage {
  return { id: `user-${Date.now()}`, role: 'user', content, timestamp: new Date().toISOString() };
}

function createAssistantMessage(answer: Answer): ChatMessage {
  return {
    id: `bot-${Date.now()}`,
    role: 'assistant',
    content: answer.text,
    timestamp: new Date().toISOString(),
    answer,
  };
}

function useQueryExecution(
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  setCurrentAnswer: React.Dispatch<React.SetStateAction<Answer | null>>,
  setSelectedId: (id: string | null) => void,
  setLastSubmission: React.Dispatch<React.SetStateAction<SubmitQueryOptions | null>>
) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlightRef = React.useRef(false);

  const submit = useCallback(async (query: string, images: File[], modalities: Modality[]) => {
    if (inFlightRef.current) {
      return false;
    }

    const submission: SubmitQueryOptions = {
      query,
      images: [...images],
      modalities: [...modalities],
    };

    inFlightRef.current = true;
    setLastSubmission(submission);
    setIsLoading(true);
    setError(null);
    setMessages((prev) => [...prev, createUserMessage(query)]);
    try {
      const answer = await submitQuery(submission);
      setCurrentAnswer(answer);
      setMessages((prev) => [...prev, createAssistantMessage(answer)]);
      if (answer.evidence.length > 0) setSelectedId(answer.evidence[0].id);
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query SatQuery pipeline.');
      return false;
    } finally {
      setIsLoading(false);
      inFlightRef.current = false;
    }
  }, [setMessages, setCurrentAnswer, setSelectedId, setLastSubmission]);

  return { isLoading, error, setError, submit };
}

function useSatQueryState() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentAnswer, setCurrentAnswer] = useState<Answer | null>(null);
  const [lastSubmission, setLastSubmission] = useState<SubmitQueryOptions | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [hoveredEvidenceId, setHoveredEvidenceId] = useState<string | null>(null);
  const selectEvidence = useCallback((id: string | null) => setSelectedEvidenceId(id), []);
  const hoverEvidence = useCallback((id: string | null) => setHoveredEvidenceId(id), []);

  const { isLoading, error, setError, submit } = useQueryExecution(
    setMessages,
    setCurrentAnswer,
    selectEvidence,
    setLastSubmission
  );

  const evidenceList = useMemo(() => currentAnswer?.evidence ?? [], [currentAnswer]);
  const selectedEvidence = useMemo(
    () => (selectedEvidenceId ? evidenceList.find((ev) => ev.id === selectedEvidenceId) ?? null : null),
    [evidenceList, selectedEvidenceId]
  );

  const loadAnswer = useCallback((answer: Answer, userQuery = 'Analysis Query') => {
    setMessages((prev) => [...prev, createUserMessage(userQuery), createAssistantMessage(answer)]);
    setCurrentAnswer(answer);
    setLastSubmission(null);
    if (answer.evidence.length > 0) setSelectedEvidenceId(answer.evidence[0].id);
    setError(null);
  }, [setError]);

  const clearSession = useCallback(() => {
    setMessages([]);
    setCurrentAnswer(null);
    setLastSubmission(null);
    setSelectedEvidenceId(null);
    setHoveredEvidenceId(null);
    setError(null);
  }, [setError]);

  const retryLastSubmission = useCallback(async () => {
    if (!lastSubmission) {
      return false;
    }

    return submit(lastSubmission.query, lastSubmission.images, lastSubmission.modalities);
  }, [lastSubmission, submit]);

  return {
    messages,
    currentAnswer,
    lastSubmission,
    evidenceList,
    selectedEvidenceId,
    selectedEvidence,
    hoveredEvidenceId,
    isLoading,
    error,
    selectEvidence,
    hoverEvidence,
    submitUserQuery: submit,
    retryLastSubmission,
    loadAnswer,
    clearSession,
  };
}

export const SatQueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const state = useSatQueryState();
  return <SatQueryContext.Provider value={state}>{children}</SatQueryContext.Provider>;
};

export default SatQueryProvider;
