import React from "react";
import { SourceSummary } from "../../types/api";
import SourceItem from "./SourceItem";

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
      {/* 2. Sources Cards Feed */}
      {loading && sources.length === 0 ? (
        <div className="text-center py-6 text-xs text-slate-500">
          Loading indexed sources...
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-8 text-xs text-text-muted leading-relaxed border border-dashed border-border-subtle rounded-lg p-4 bg-surface-primary">
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
