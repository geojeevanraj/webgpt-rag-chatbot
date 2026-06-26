import React, { useState, useMemo } from "react";
import { X, Search, FileText, Database, Calendar, Globe, ExternalLink } from "lucide-react";
import { SourceSummary, SourcePageInfo } from "../../types/api";

interface KnowledgeExplorerProps {
  activeSource: SourceSummary;
  pages: SourcePageInfo[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
}

export default function KnowledgeExplorer({
  activeSource,
  pages,
  loading,
  error,
  onClose,
}: KnowledgeExplorerProps) {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredPages = useMemo(() => {
    if (!searchQuery.trim()) return pages;
    const lowerQuery = searchQuery.toLowerCase();
    return pages.filter(
      (p) =>
        (p.title && p.title.toLowerCase().includes(lowerQuery)) ||
        (p.url && p.url.toLowerCase().includes(lowerQuery))
    );
  }, [pages, searchQuery]);

  // Format creation date
  const formattedDate = useMemo(() => {
    try {
      const date = new Date(activeSource.created_at);
      return date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return activeSource.created_at;
    }
  }, [activeSource.created_at]);

  return (
    <>
      {/* Backdrop (Flat background overlay, no blur) */}
      <div
        className="fixed inset-0 z-40 bg-surface-background/80 transition-opacity duration-300 animate-in fade-in"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border-subtle bg-surface-primary shadow-soft transition-transform duration-[--transition-normal] animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-border-subtle px-6 bg-surface-secondary font-outfit">
          <div className="flex items-center gap-2">
            <span className="text-lg">📚</span>
            <h2 className="text-sm font-semibold text-text-primary">Knowledge Explorer</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm p-2 text-text-secondary hover:bg-surface-elevated hover:text-text-primary cursor-pointer transition-colors duration-[--transition-fast]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Container */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Summary Card / Statistics */}
          <div className="p-6 border-b border-border-subtle bg-surface-secondary/20">
            <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted mb-4 font-outfit">Source Statistics</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border border-white/[0.06] bg-surface-secondary p-3 shadow-soft transition-all duration-200 ease-out hover:-translate-y-[2px] hover:scale-[1.01] hover:bg-surface-secondary/70 hover:shadow-soft">
                <div className="flex items-center gap-2 text-accent-blue mb-1 font-outfit">
                  <FileText className="h-3.5 w-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Pages</span>
                </div>
                <div className="text-lg font-bold text-text-primary font-outfit">{activeSource.pages_scraped}</div>
              </div>

              <div className="rounded-lg border border-white/[0.06] bg-surface-secondary p-3 shadow-soft transition-all duration-200 ease-out hover:-translate-y-[2px] hover:scale-[1.01] hover:bg-surface-secondary/70 hover:shadow-soft">
                <div className="flex items-center gap-2 text-emerald-400 mb-1 font-outfit">
                  <Database className="h-3.5 w-3.5" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-text-secondary">Chunks</span>
                </div>
                <div className="text-lg font-bold text-text-primary font-outfit">{activeSource.total_chunks}</div>
              </div>
            </div>

            <div className="mt-4 space-y-3 text-xs font-inter">
              <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
                <span className="text-text-secondary flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-text-muted" /> Domain
                </span>
                <span className="font-semibold text-text-primary truncate max-w-[200px]" title={activeSource.domain}>
                  {activeSource.domain}
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
                <span className="text-text-secondary flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5 text-text-muted" /> Indexed
                </span>
                <span className="font-semibold text-text-primary">{formattedDate}</span>
              </div>
              <div className="flex items-start justify-between py-1.5">
                <span className="text-text-secondary shrink-0">Website</span>
                <a
                  href={activeSource.seed_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-accent-blue hover:text-accent-blue/80 hover:underline inline-flex items-center gap-1 text-right break-all max-w-[240px] transition-colors duration-[--transition-fast]"
                >
                  {activeSource.seed_url}
                  <ExternalLink className="h-3 w-3 shrink-0" />
                </a>
              </div>
            </div>
          </div>

          {/* Search Box (No blur flat header style) */}
          <div className="sticky top-0 z-10 bg-surface-primary/95 px-6 py-3 border-b border-border-subtle">
            <div className="relative">
              <Search className="absolute left-3.5 top-2 h-4 w-4 text-text-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search indexed pages..."
                className="w-full rounded-full border border-border-subtle bg-surface-secondary py-1.5 pl-10 pr-4 text-xs text-text-primary placeholder:text-text-muted focus:border-accent-blue/50 focus:outline-none focus:ring-1 focus:ring-accent-blue/30 transition-all duration-200 ease-out font-inter"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3.5 top-2 text-text-muted hover:text-text-primary text-xs font-semibold cursor-pointer transition-colors duration-200 ease-out"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Pages List */}
          <div className="p-6 space-y-4 font-inter">
            {loading ? (
              // Loading state skeleton
              Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="animate-pulse rounded-lg border border-border-subtle bg-surface-secondary/45 p-4 space-y-4">
                  <div className="h-4 bg-surface-elevated rounded w-3/4" />
                  <div className="h-3 bg-surface-elevated rounded w-5/6" />
                  <div className="flex gap-4 pt-1">
                    <div className="h-3 bg-surface-elevated rounded w-16" />
                    <div className="h-3 bg-surface-elevated rounded w-16" />
                  </div>
                </div>
              ))
            ) : error ? (
              // Error state
              <div className="rounded-lg border border-rose-500/15 bg-rose-500/10 p-4 text-center">
                <p className="text-xs text-rose-400 font-semibold">{error}</p>
              </div>
            ) : filteredPages.length === 0 ? (
              // Empty search state
              <div className="text-center py-8 text-text-muted">
                <FileText className="h-10 w-10 mx-auto opacity-30 mb-2" />
                <p className="text-xs font-semibold">No indexed pages found.</p>
                {searchQuery && <p className="text-[10px] text-text-muted mt-1">Try tweaking your search term.</p>}
              </div>
            ) : (
              // Regular list
              filteredPages.map((page) => (
                <div
                  key={page.id}
                  className="rounded-lg border border-transparent bg-surface-secondary/40 px-4 py-3 hover:border-accent-blue/30 hover:bg-surface-secondary/60 hover:-translate-y-[2px] hover:scale-[1.01] hover:shadow-soft transition-all duration-200 ease-out group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-xs font-semibold text-text-primary line-clamp-2 leading-relaxed group-hover:text-accent-blue transition-colors duration-200 ease-out font-inter">
                      {page.title || "Untitled Page"}
                    </h4>
                    <a
                      href={page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-text-muted hover:text-accent-blue p-0.5 transition-colors duration-200 ease-out shrink-0"
                      title="Open page in a new tab"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                  <p className="text-[10px] text-text-muted mt-1 truncate select-all font-inter" title={page.url}>
                    {page.url}
                  </p>
                  <div className="flex items-center gap-4 mt-2.5 pt-2.5 border-t border-border-subtle text-[10px] text-text-secondary font-semibold font-inter">
                    <div className="flex items-center gap-1">
                      <Database className="h-3 w-3 text-emerald-500" />
                      <span>{page.chunk_count} {page.chunk_count === 1 ? "chunk" : "chunks"}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Depth:</span> {page.depth}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </>
  );
}
