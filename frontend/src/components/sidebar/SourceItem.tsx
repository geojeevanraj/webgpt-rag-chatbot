import React, { useState } from "react";
import { SourceSummary } from "../../types/api";
import { Database, Loader2, Trash2 } from "lucide-react";

interface SourceItemProps {
  source: SourceSummary;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => Promise<void>;
}

export default function SourceItem({
  source,
  isSelected,
  onSelect,
  onDelete,
}: SourceItemProps) {
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Avoid triggering selection on click
    if (!window.confirm(`Are you sure you want to delete all indexed data for ${source.domain}?`)) {
      return;
    }
    setIsDeleting(true);
    try {
      await onDelete();
    } catch (err) {
      // Re-enable delete button if the API deletion fails
      setIsDeleting(false);
    }
  };

  const statusColors = {
    pending: "bg-slate-500 shadow-slate-500/20",
    scraping: "bg-amber-500 animate-pulse shadow-amber-500/20",
    completed: "bg-emerald-500 shadow-emerald-500/20",
    failed: "bg-rose-500 shadow-rose-500/20",
  };

  return (
    <div
      onClick={onSelect}
      className={`group relative flex w-full flex-col gap-2 rounded-lg border p-3 text-left transition cursor-pointer ${
        isSelected
          ? "bg-indigo-600/10 border-indigo-500/30 text-indigo-450"
          : "bg-slate-900/35 border-slate-800/80 text-slate-300 hover:bg-slate-900 hover:text-slate-100"
      }`}
    >
      <div className="flex items-center justify-between gap-2 overflow-hidden">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <Database className="h-4 w-4 text-slate-500 shrink-0" />
          <div className="truncate font-semibold text-slate-200">{source.domain}</div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Status Indicator Badge */}
          <span
            className={`h-2 w-2 rounded-full ${statusColors[source.status] || "bg-slate-500"}`}
            title={`Status: ${source.status}`}
          />

          {/* Delete Action Button */}
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting}
            className="opacity-0 group-hover:opacity-100 hover:text-rose-400 text-slate-500 p-0.5 rounded transition disabled:cursor-not-allowed cursor-pointer"
          >
            {isDeleting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="flex items-center gap-3 text-[10px] text-slate-500 font-medium">
        <div>
          Pages: <span className="font-semibold text-slate-300">{source.pages_scraped}</span>
        </div>
        <div className="h-2.5 w-px bg-slate-800" />
        <div>
          Chunks: <span className="font-semibold text-slate-300">{source.total_chunks}</span>
        </div>
      </div>
    </div>
  );
}
