import React, { useState, useRef } from 'react';
import { Send, Paperclip, X, Image as ImageIcon, Loader2 } from 'lucide-react';
import type { Modality } from '@/types/contracts';

export interface ChatInputProps {
  onSubmit: (query: string, files: File[], modalities: Modality[]) => void;
  isLoading: boolean;
}

interface UploadedFileItem {
  file: File;
  modality: Modality;
}

function useUploadedFiles() {
  const [files, setFiles] = useState<UploadedFileItem[]>([]);
  const toggleModality = (index: number) => {
    setFiles((prev) =>
      prev.map((it, i) => (i === index ? { ...it, modality: it.modality === 'optical' ? 'sar' : 'optical' } : it))
    );
  };
  const removeFile = (index: number) => setFiles((prev) => prev.filter((_, i) => i !== index));
  const addFiles = (newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles.map((f) => ({ file: f, modality: 'optical' as Modality }))]);
  };
  const clearFiles = () => setFiles([]);
  return { files, toggleModality, removeFile, addFiles, clearFiles };
}

const UploadedFilesPreview: React.FC<{
  files: UploadedFileItem[];
  onToggle: (index: number) => void;
  onRemove: (index: number) => void;
}> = ({ files, onToggle, onRemove }) => (
  <div className="mb-3 flex items-center gap-2 flex-wrap">
    {files.map((item, idx) => (
      <div
        key={`${item.file.name}-${idx}`}
        className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-200"
      >
        <ImageIcon className="h-3.5 w-3.5 text-cyan-400" />
        <span className="max-w-[120px] truncate">{item.file.name}</span>
        <button
          type="button"
          onClick={() => onToggle(idx)}
          className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase transition-colors ${
            item.modality === 'optical'
              ? 'bg-emerald-950 text-emerald-400 border border-emerald-600/50'
              : 'bg-purple-950 text-purple-400 border border-purple-600/50'
          }`}
          title="Toggle Optical / SAR"
        >
          {item.modality}
        </button>
        <button type="button" onClick={() => onRemove(idx)} className="text-slate-500 hover:text-rose-400">
          <X className="h-3 w-3" />
        </button>
      </div>
    ))}
  </div>
);

const InputFormRow: React.FC<{
  query: string;
  isLoading: boolean;
  onQueryChange: (val: string) => void;
  onAttachClick: () => void;
  onSubmit: (e: React.FormEvent) => void;
}> = ({ query, isLoading, onQueryChange, onAttachClick, onSubmit }) => (
  <form onSubmit={onSubmit} className="flex items-center gap-2">
    <button
      type="button"
      onClick={onAttachClick}
      className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
      title="Attach satellite image(s)"
    >
      <Paperclip className="h-4 w-4" />
    </button>
    <input
      type="text"
      value={query}
      onChange={(e) => onQueryChange(e.target.value)}
      placeholder="Ask a question about the satellite imagery..."
      disabled={isLoading}
      className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 disabled:opacity-50"
    />
    <button
      type="submit"
      disabled={!query.trim() || isLoading}
      className="inline-flex items-center justify-center rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-500 transition-colors disabled:opacity-50 shadow-md shadow-cyan-900/30"
    >
      {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
    </button>
  </form>
);

export const ChatInput: React.FC<ChatInputProps> = ({ onSubmit, isLoading }) => {
  const [query, setQuery] = useState('');
  const { files, toggleModality, removeFile, addFiles, clearFiles } = useUploadedFiles();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isLoading) return;
    onSubmit(query.trim(), files.map((f) => f.file), files.map((f) => f.modality));
    setQuery('');
    clearFiles();
  };

  return (
    <div className="border-t border-slate-800 bg-slate-950/80 p-4">
      {files.length > 0 && (
        <UploadedFilesPreview files={files} onToggle={toggleModality} onRemove={removeFile} />
      )}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => e.target.files && addFiles(Array.from(e.target.files))}
        multiple
        className="hidden"
        accept="image/*,.tif,.tiff"
      />
      <InputFormRow
        query={query}
        isLoading={isLoading}
        onQueryChange={setQuery}
        onAttachClick={() => fileInputRef.current?.click()}
        onSubmit={handleSubmit}
      />
    </div>
  );
};

export default ChatInput;
