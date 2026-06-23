import React from "react";
import { CitationInfo } from "../../types/api";
import { ExternalLink } from "lucide-react";

interface CitationChipProps {
  citation: CitationInfo;
  index: number;
}

export default function CitationChip({ citation, index }: CitationChipProps) {
  // Truncate title to fit card layouts cleanly
  const displayTitle =
    citation.page_title.length > 50
      ? `${citation.page_title.slice(0, 50)}...`
      : citation.page_title;

  return (
    <a
      href={citation.source_url}
      target="_blank"
      rel="noopener noreferrer"
      title={`Source: ${citation.source_url}`}
      className="group inline-flex items-center gap-1.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 px-2 py-1 text-xs text-indigo-400 hover:text-indigo-300 transition"
    >
      <span className="font-semibold text-indigo-500">[{index}]</span>
      <span className="max-w-[150px] truncate">{displayTitle}</span>
      <ExternalLink className="h-3 w-3 opacity-50 group-hover:opacity-100 transition shrink-0" />
    </a>
  );
}
