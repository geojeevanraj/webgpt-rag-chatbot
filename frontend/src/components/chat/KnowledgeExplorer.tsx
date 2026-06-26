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
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm transition-opacity duration-300 animate-in fade-in"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-md flex-col border-l border-slate-800 bg-slate-900 shadow-2xl transition-transform duration-300 animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-6 bg-slate-950/50">
          <div className="flex items-center gap-2">
            <span className="text-lg">📚</span>
            <h2 className="text-sm font-semibold text-slate-100">Knowledge Explorer</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white cursor-pointer transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Container */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Summary Card / Statistics */}
          <div className="p-6 border-b border-slate-800/60 bg-slate-950/20">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-4">Source Statistics</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3.5">
                <div className="flex items-center gap-2 text-indigo-400 mb-1.5">
                  <FileText className="h-4 w-4" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Pages</span>
                </div>
                <div className="text-xl font-bold text-slate-100">{activeSource.pages_scraped}</div>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3.5">
                <div className="flex items-center gap-2 text-emerald-400 mb-1.5">
                  <Database className="h-4 w-4" />
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Chunks</span>
                </div>
                <div className="text-xl font-bold text-slate-100">{activeSource.total_chunks}</div>
              </div>
            </div>

            <div className="mt-4 space-y-2.5 text-xs">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/40">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5" /> Domain
                </span>
                <span className="font-semibold text-slate-200 truncate max-w-[200px]" title={activeSource.domain}>
                  {activeSource.domain}
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-800/40">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <Calendar className="h-3.5 w-3.5" /> Indexed
                </span>
                <span className="font-semibold text-slate-200">{formattedDate}</span>
              </div>
              <div className="flex items-start justify-between py-1.5">
                <span className="text-slate-400 shrink-0">Website</span>
                <a
                  href={activeSource.seed_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold text-indigo-400 hover:text-indigo-300 hover:underline inline-flex items-center gap-1 text-right break-all max-w-[240px]"
                >
                  {activeSource.seed_url}
                  <ExternalLink className="h-3 w-3 shrink-0" />
                </a>
              </div>
            </div>
          </div>

          {/* Search Box */}
          <div className="sticky top-0 z-10 bg-slate-900 px-6 py-4 border-b border-slate-800/60 backdrop-blur-md bg-slate-900/90">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search indexed pages..."
                className="w-full rounded-lg border border-slate-800 bg-slate-950/50 py-2 pl-9 pr-4 text-xs text-slate-100 placeholder:text-slate-500 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 transition"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300 text-xs font-semibold cursor-pointer"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Pages List */}
          <div className="p-6 space-y-3">
            {loading ? (
              // Loading state skeleton
              Array.from({ length: 4 }).map((_, idx) => (
                <div key={idx} className="animate-pulse rounded-xl border border-slate-800/80 bg-slate-950/20 p-4 space-y-3">
                  <div className="h-4 bg-slate-800 rounded w-3/4" />
                  <div className="h-3 bg-slate-800 rounded w-5/6" />
                  <div className="flex gap-4 pt-1">
                    <div className="h-3 bg-slate-800 rounded w-16" />
                    <div className="h-3 bg-slate-800 rounded w-16" />
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
              <div className="text-center py-8 text-slate-500">
                <FileText className="h-10 w-10 mx-auto opacity-30 mb-2" />
                <p className="text-xs font-semibold">No indexed pages found.</p>
                {searchQuery && <p className="text-[10px] text-slate-600 mt-1">Try tweaking your search term.</p>}
              </div>
            ) : (
              // Regular list
              filteredPages.map((page) => (
                <div
                  key={page.id}
                  className="rounded-xl border border-slate-800/80 bg-slate-950/20 p-4 hover:border-slate-700 hover:bg-slate-950/40 transition group"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-xs font-bold text-slate-200 line-clamp-2 leading-relaxed group-hover:text-white transition">
                      {page.title || "Untitled Page"}
                    </h4>
                    <a
                      href={page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-500 hover:text-indigo-400 p-0.5 transition shrink-0"
                      title="Open page in a new tab"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1 truncate select-all" title={page.url}>
                    {page.url}
                  </p>
                  <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-800/40 text-[10px] text-slate-400 font-semibold">
                    <div className="flex items-center gap-1">
                      <Database className="h-3 w-3 text-emerald-500" />
                      <span>{page.chunk_count} {page.chunk_count === 1 ? "chunk" : "chunks"}</span>
                    </div>
                    <div>
                      <span className="text-slate-600">Depth:</span> {page.depth}
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
