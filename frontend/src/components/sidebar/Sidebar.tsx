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
    <aside className="flex h-full w-full flex-col border-r border-border-subtle bg-surface-primary text-text-primary font-inter">
      {/* App Branding Logo */}
      <div className="flex h-16 shrink-0 items-center justify-between border-b border-border-subtle px-6">
        <div className="flex items-center gap-3">
          <img
            src={logo}
            alt="WebGPT Logo"
            className="h-9 w-9 object-contain"
          />
          <div className="flex items-center">
            <span className="font-semibold text-text-primary tracking-wide font-outfit text-base">WebGPT</span>
            <span className="ml-2 text-[10px] text-accent-blue font-semibold px-2 py-0.5 rounded-sm bg-accent-blue/10 font-outfit uppercase tracking-wider">
              RAG
            </span>
          </div>
        </div>
        
        {/* Mobile close button wrapper */}
        {onCloseMobile && (
          <button
            type="button"
            onClick={onCloseMobile}
            className="rounded-sm p-2 text-text-secondary hover:bg-surface-elevated hover:text-text-primary md:hidden cursor-pointer transition-colors duration-[--transition-fast]"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* 1. Add Source Form Container */}
      <div className="p-4 border-b border-border-subtle shrink-0">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-outfit">Add Data Source</h2>
          <Globe className="h-4 w-4 text-text-muted" />
        </div>
        <AddSourceForm onSuccess={onScrapeSuccess} />
      </div>

      {/* 2. Interactive Sources List */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-outfit">Indexed Sources</h2>
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

      <div className="border-t border-border-subtle bg-surface-primary/70 p-4 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-secondary font-outfit">Database Status</h2>
          <Database className="h-4 w-4 text-text-muted" />
        </div>
        <div className="grid grid-cols-2 gap-4 text-center">
          <div className="rounded-lg bg-surface-secondary p-4 border border-white/[0.06] shadow-soft transition-all duration-200 ease-out hover:-translate-y-[2px] hover:scale-[1.01] hover:bg-surface-secondary/70 hover:shadow-soft">
            <div className="text-xl font-bold text-text-primary tracking-tight font-outfit">{totalPages}</div>
            <div className="text-[9px] text-text-muted uppercase font-medium tracking-wide mt-1">Pages Indexed</div>
          </div>
          <div className="rounded-lg bg-surface-secondary p-4 border border-white/[0.06] shadow-soft transition-all duration-200 ease-out hover:-translate-y-[2px] hover:scale-[1.01] hover:bg-surface-secondary/70 hover:shadow-soft">
            <div className="text-xl font-bold text-text-primary tracking-tight font-outfit">{totalChunks}</div>
            <div className="text-[9px] text-text-muted uppercase font-medium tracking-wide mt-1">Total Chunks</div>
          </div>
        </div>
      </div>
    </aside>
  );

}
