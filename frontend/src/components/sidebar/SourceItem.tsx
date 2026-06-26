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
      className={`group relative flex w-full flex-col gap-2.5 rounded-lg border p-3 text-left transition-all duration-200 ease-out cursor-pointer hover:-translate-y-[2px] hover:scale-[1.01] hover:shadow-soft ${
        isSelected
          ? "bg-surface-elevated border-accent-blue/30 text-text-primary shadow-soft"
          : "bg-surface-secondary border-white/[0.06] text-text-secondary hover:bg-surface-secondary/70 hover:text-text-primary"
      }`}
    >
      {/* Selected Left Accent Indicator */}
      {isSelected && (
        <div className="absolute left-0 top-2.5 bottom-2.5 w-1 bg-accent-blue rounded-r" />
      )}

      <div className="flex items-center justify-between gap-4 overflow-hidden">
        <div className="flex items-center gap-3 overflow-hidden">
          <Database className={`h-4 w-4 shrink-0 transition-colors duration-[--transition-fast] ${isSelected ? "text-accent-blue" : "text-text-muted"}`} />
          <div className="truncate font-semibold text-text-primary font-outfit text-sm">{source.domain}</div>
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
            className="opacity-100 md:opacity-0 md:group-hover:opacity-100 focus-within:opacity-100 hover:text-rose-400 text-text-muted p-1 rounded-sm transition-all duration-[--transition-fast] disabled:cursor-not-allowed cursor-pointer hover:bg-rose-500/10"
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
      <div className="flex items-center gap-4 text-[10px] text-text-muted font-medium font-inter">
        <div>
          Pages: <span className="font-semibold text-text-secondary">{source.pages_scraped}</span>
        </div>
        <div className="h-3 w-px bg-border-subtle" />
        <div>
          Chunks: <span className="font-semibold text-text-secondary">{source.total_chunks}</span>
        </div>
      </div>
    </div>
  );
}
