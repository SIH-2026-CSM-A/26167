import React from 'react';
import { Send, Bot, ShieldCheck } from 'lucide-react';

export const ChatPage: React.FC = () => {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            VLM Assistant & Query
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Natural language interrogation powered by InternVL2-2B with strict evidence grounding.
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-1.5 rounded-md border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs text-slate-300">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Verification Layer Active</span>
        </div>
      </div>

      <div className="flex flex-col h-[520px] rounded-xl border border-slate-800 bg-slate-900/40">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-cyan-600/20 text-cyan-400 border border-cyan-500/30">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900 p-4 text-sm text-slate-200 max-w-xl">
              <p>
                Welcome to SatQuery AI. Upload an image pair or select existing satellite passes to
                begin analysis, change detection, or feature grounding.
              </p>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-800 p-4 bg-slate-950/40">
          <form
            onSubmit={(e) => e.preventDefault()}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Ask a question about the satellite imagery (e.g. 'Identify flooded zones in the SAR pass')..."
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
            <button
              type="submit"
              className="inline-flex items-center justify-center rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-500 transition-colors"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </main>
  );
};
