import React from 'react';
import { Send, Loader2, RefreshCw, Info, AlertCircle } from 'lucide-react';

export interface UploadFormActionsProps {
  isFormValid: boolean;
  isLoading: boolean;
  validationHint: string | null;
  backendError: string | null;
  onReset: () => void;
}

export const UploadFormActions: React.FC<UploadFormActionsProps> = ({
  isFormValid,
  isLoading,
  validationHint,
  backendError,
  onReset,
}) => {
  return (
    <div className="space-y-4">
      {/* Validation Notice Banner if Form is Incomplete */}
      {!isFormValid && validationHint && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-2.5 text-xs text-slate-400"
        >
          <Info className="h-4 w-4 text-cyan-400 shrink-0" />
          <span>{validationHint}</span>
        </div>
      )}

      {/* Backend / Network Error Banner */}
      {backendError && (
        <div
          role="alert"
          className="rounded-lg border border-red-500/40 bg-red-950/40 p-4 text-xs text-red-200 space-y-1"
        >
          <div className="flex items-center gap-2 font-semibold text-red-300">
            <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
            <span>Backend Query Failed</span>
          </div>
          <p className="pl-6 leading-relaxed">{backendError}</p>
        </div>
      )}

      {/* Submit & Reset Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
        <button
          type="button"
          onClick={onReset}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-800 hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Reset Form</span>
        </button>

        <button
          type="submit"
          disabled={!isFormValid || isLoading}
          className={`inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition-all ${
            !isFormValid || isLoading
              ? 'cursor-not-allowed bg-slate-800 text-slate-500 border border-slate-700'
              : 'bg-cyan-600 hover:bg-cyan-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-600 shadow-cyan-950/50 hover:shadow-cyan-900/40'
          }`}
          aria-busy={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-white" />
              <span>Executing Pipeline...</span>
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span>Submit Query (POST /query)</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
