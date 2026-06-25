import React from "react";
import { Database, Globe, X } from "lucide-react";
import { ScrapeResponse, SourceSummary } from "../../types/api";
import AddSourceForm from "./AddSourceForm";
import SourceList from "./SourceList";
import logo from "../../assets/logo.png";

interface SidebarProps {
  sources: SourceSummary[];
  activeSourceId: string | null;
  onSelectSource: (sourceId: string | null) => void;
  onDeleteSource: (sourceId: string) => Promise<void>;
  onScrapeSuccess: (job: ScrapeResponse) => void;
  loading: boolean;
  onCloseMobile?: () => void;
}

export default function Sidebar({
  sources,
  activeSourceId,
  onSelectSource,
  onDeleteSource,
  onScrapeSuccess,
  loading,
  onCloseMobile,
}: SidebarProps) {
  // Compute dynamic database statistics based on active sources
  const totalPages = sources.reduce((acc, s) => acc + s.pages_scraped, 0);
  const totalChunks = sources.reduce((acc, s) => acc + s.total_chunks, 0);

  return (
    <aside className="flex h-full w-full flex-col border-r border-slate-800 bg-slate-950 text-slate-100">
      {/* App Branding Logo */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-6">
        <div className="flex items-center gap-2.5">
          <img
            src={logo}
            alt="WebGPT Logo"
            className="h-9 w-9 rounded-lg object-cover shadow-md shadow-indigo-500/15"
          />
          <div>
            <span className="font-semibold text-white tracking-wide">WebGPT</span>
            <span className="ml-1 text-xs text-indigo-400 font-semibold px-1.5 py-0.5 rounded bg-indigo-500/10">
              RAG
            </span>
          </div>
        </div>
        
        {/* Mobile close button wrapper */}
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="rounded p-1 text-slate-400 hover:bg-slate-900 hover:text-white md:hidden cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* 1. Add Source Form Container */}
      <div className="p-4 border-b border-slate-800 shrink-0">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Add Data Source</h2>
          <Globe className="h-4 w-4 text-slate-500" />
        </div>
        <AddSourceForm onSuccess={onScrapeSuccess} />
      </div>

      {/* 2. Interactive Sources List */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Indexed Sources</h2>
        <SourceList
          sources={sources}
          activeSourceId={activeSourceId}
          onSelectSource={(id) => {
            onSelectSource(id);
            if (onCloseMobile) onCloseMobile(); // Close mobile drawer on selection
          }}
          onDeleteSource={onDeleteSource}
          loading={loading}
        />
      </div>

      {/* 3. Dynamic Statistics Section */}
      <div className="border-t border-slate-800 bg-slate-950/70 p-4 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Database Status</h2>
          <Database className="h-4 w-4 text-slate-500" />
        </div>
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="rounded bg-slate-900/40 p-2.5 border border-slate-900">
            <div className="text-lg font-bold text-white tracking-tight">{totalPages}</div>
            <div className="text-[10px] text-slate-500 uppercase font-semibold tracking-wide">Pages Indexed</div>
          </div>
          <div className="rounded bg-slate-900/40 p-2.5 border border-slate-900">
            <div className="text-lg font-bold text-white tracking-tight">{totalChunks}</div>
            <div className="text-[10px] text-slate-500 uppercase font-semibold tracking-wide">Total Chunks</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
