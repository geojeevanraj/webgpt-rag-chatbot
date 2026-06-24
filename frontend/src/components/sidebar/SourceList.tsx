import React from "react";
import { SourceSummary } from "../../types/api";
import SourceItem from "./SourceItem";
import { LayoutGrid } from "lucide-react";

interface SourceListProps {
  sources: SourceSummary[];
  activeSourceId: string | null;
  onSelectSource: (sourceId: string | null) => void;
  onDeleteSource: (sourceId: string) => Promise<void>;
  loading: boolean;
}

export default function SourceList({
  sources,
  activeSourceId,
  onSelectSource,
  onDeleteSource,
  loading,
}: SourceListProps) {
  return (
    <div className="space-y-2">
      {/* 1. Global Search Trigger Option */}
      <button
        type="button"
        onClick={() => onSelectSource(null)}
        className={`mb-2.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition text-left cursor-pointer ${
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

      {/* 2. Sources Cards Feed */}
      {loading && sources.length === 0 ? (
        <div className="text-center py-6 text-xs text-slate-500">
          Loading indexed sources...
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-8 text-xs text-slate-500 leading-relaxed border border-dashed border-slate-800 rounded-lg p-4 bg-slate-900/10">
          No data sources indexed yet. Submitting a URL in the form above to begin.
        </div>
      ) : (
        <div className="space-y-2">
          {sources.map((source) => (
            <SourceItem
              key={source.job_id}
              source={source}
              isSelected={activeSourceId === source.job_id}
              onSelect={() => onSelectSource(source.job_id)}
              onDelete={() => onDeleteSource(source.job_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
