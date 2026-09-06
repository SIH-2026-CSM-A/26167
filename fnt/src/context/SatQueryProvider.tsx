import React, { useState, useMemo, useCallback } from 'react';
import type { Answer, ChatMessage, Modality } from '@/types/contracts';
import { submitQuery } from '@/services/api';
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
  setSelectedId: (id: string | null) => void
) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (query: string, images: File[], modalities: Modality[]) => {
    setIsLoading(true);
    setError(null);
    setMessages((prev) => [...prev, createUserMessage(query)]);
    try {
      const answer = await submitQuery({ query, images, modalities });
      setCurrentAnswer(answer);
      setMessages((prev) => [...prev, createAssistantMessage(answer)]);
      if (answer.evidence.length > 0) setSelectedId(answer.evidence[0].id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query SatQuery pipeline.');
    } finally {
      setIsLoading(false);
    }
  }, [setMessages, setCurrentAnswer, setSelectedId]);

  return { isLoading, error, setError, submit };
}

function useSatQueryState() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentAnswer, setCurrentAnswer] = useState<Answer | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const selectEvidence = useCallback((id: string | null) => setSelectedEvidenceId(id), []);

  const { isLoading, error, setError, submit } = useQueryExecution(
    setMessages,
    setCurrentAnswer,
    selectEvidence
  );

  const evidenceList = useMemo(() => currentAnswer?.evidence ?? [], [currentAnswer]);
  const selectedEvidence = useMemo(
    () => (selectedEvidenceId ? evidenceList.find((ev) => ev.id === selectedEvidenceId) ?? null : null),
    [evidenceList, selectedEvidenceId]
  );

  const loadAnswer = useCallback((answer: Answer, userQuery = 'Analysis Query') => {
    setMessages((prev) => [...prev, createUserMessage(userQuery), createAssistantMessage(answer)]);
    setCurrentAnswer(answer);
    if (answer.evidence.length > 0) setSelectedEvidenceId(answer.evidence[0].id);
  }, []);

  const clearSession = useCallback(() => {
    setMessages([]);
    setCurrentAnswer(null);
    setSelectedEvidenceId(null);
    setError(null);
  }, [setError]);

  return {
    messages,
    currentAnswer,
    evidenceList,
    selectedEvidenceId,
    selectedEvidence,
    isLoading,
    error,
    selectEvidence,
    submitUserQuery: submit,
    loadAnswer,
    clearSession,
  };
}

export const SatQueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const state = useSatQueryState();
  return <SatQueryContext.Provider value={state}>{children}</SatQueryContext.Provider>;
};

export default SatQueryProvider;
