import React from "react";
import { Database, Globe, HelpCircle, LayoutGrid, Plus, ShieldAlert } from "lucide-react";

interface SidebarProps {
  activeSourceId: string | null;
  onSelectSource: (sourceId: string | null) => void;
}

export default function Sidebar({ activeSourceId, onSelectSource }: SidebarProps) {
  // Static mock sources for design previewing (F2 Requirement: Only layout, no business logic)
  const mockSources = [
    { id: "job-uuid-1", domain: "docs.python.org", status: "completed", pages: 12 },
    { id: "job-uuid-2", domain: "react.dev", status: "scraping", pages: 4 },
    { id: "job-uuid-3", domain: "fastapi.tiangolo.com", status: "failed", pages: 0 },
  ];

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-r border-slate-800 bg-slate-950 text-slate-100">
      {/* App Branding Logo */}
      <div className="flex h-16 items-center border-b border-slate-800 px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-md shadow-indigo-500/20">
            WG
          </div>
          <div>
            <span className="font-semibold text-white tracking-wide">WebGPT</span>
            <span className="ml-1 text-xs text-indigo-400 font-semibold px-1.5 py-0.5 rounded bg-indigo-500/10">RAG</span>
          </div>
        </div>
      </div>

      {/* 1. Add Source Section Placeholder */}
      <div className="p-4 border-b border-slate-800">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Add Data Source</h2>
          <Globe className="h-4 w-4 text-slate-500" />
        </div>
        <div className="space-y-2.5">
          <div className="relative">
            <input
              type="text"
              placeholder="Enter URL to scrape..."
              disabled
              className="w-full rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm text-slate-400 placeholder:text-slate-600 focus:outline-none"
            />
          </div>
          <button
            type="button"
            disabled
            className="flex w-full items-center justify-center gap-1.5 rounded-md bg-indigo-600/50 px-3 py-2 text-xs font-medium text-slate-300 transition"
          >
            <Plus className="h-4 w-4" />
            Scrape Site (Disabled)
          </button>
        </div>
      </div>

      {/* 2. Sources Section */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Indexed Sources</h2>
        
        {/* Global Search Option */}
        <button
          type="button"
          onClick={() => onSelectSource(null)}
          className={`mb-2.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition text-left ${
            activeSourceId === null
              ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/25"
              : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
          }`}
        >
          <LayoutGrid className="h-4 w-4 shrink-0" />
          <div className="flex-1 overflow-hidden">
            <div className="truncate">All Sources (Global Search)</div>
          </div>
        </button>

        {/* Mock Sources List Container */}
        <div className="space-y-2">
          {mockSources.map((source) => {
            const isSelected = activeSourceId === source.id;
            return (
              <button
                key={source.id}
                type="button"
                onClick={() => onSelectSource(source.id)}
                className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-sm font-medium transition text-left ${
                  isSelected
                    ? "bg-indigo-600/15 text-indigo-400 border-indigo-500/25"
                    : "bg-slate-900/35 border-slate-800/80 text-slate-300 hover:bg-slate-900 hover:text-slate-100"
                }`}
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <Database className="h-4 w-4 text-slate-500 shrink-0" />
                  <div className="truncate">{source.domain}</div>
                </div>
                
                {/* Status Indicator Badges */}
                <div className="flex items-center">
                  {source.status === "completed" && (
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/20" title="Completed" />
                  )}
                  {source.status === "scraping" && (
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse shadow-sm shadow-amber-500/20" title="Scraping..." />
                  )}
                  {source.status === "failed" && (
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/20" title="Failed" />
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Statistics Section Placeholder */}
      <div className="border-t border-slate-800 bg-slate-950/70 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Database Status</h2>
          <Database className="h-4 w-4 text-slate-500" />
        </div>
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="rounded bg-slate-900/40 p-2.5 border border-slate-900">
            <div className="text-lg font-semibold text-white">16</div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Pages Indexed</div>
          </div>
          <div className="rounded bg-slate-900/40 p-2.5 border border-slate-900">
            <div className="text-lg font-semibold text-white">324</div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Total Chunks</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
