import { useContext } from 'react';
import { SatQueryContext, type SatQueryContextValue } from '@/context/SatQueryContext';

export function useSatQuery(): SatQueryContextValue {
  const context = useContext(SatQueryContext);
  if (!context) {
    throw new Error('useSatQuery must be used within a SatQueryProvider');
  }
  return context;
}

export default useSatQuery;
