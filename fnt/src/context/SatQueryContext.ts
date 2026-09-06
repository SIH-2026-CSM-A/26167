import { createContext } from 'react';
import type { Answer, ChatMessage, Evidence, Modality } from '@/types/contracts';

export interface SatQueryContextValue {
  messages: ChatMessage[];
  currentAnswer: Answer | null;
  evidenceList: Evidence[];
  selectedEvidenceId: string | null;
  selectedEvidence: Evidence | null;
  isLoading: boolean;
  error: string | null;
  selectEvidence: (id: string | null) => void;
  submitUserQuery: (
    query: string,
    images: File[],
    modalities: Modality[]
  ) => Promise<void>;
  loadAnswer: (answer: Answer, userQuery?: string) => void;
  clearSession: () => void;
}

export const SatQueryContext = createContext<SatQueryContextValue | undefined>(undefined);

export default SatQueryContext;
