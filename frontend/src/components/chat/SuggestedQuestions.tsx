import React, { useEffect, useState } from "react";
import { api } from "../../services/api";
import { HelpCircle, Sparkles } from "lucide-react";

interface SuggestedQuestionsProps {
  jobId: string | null;
  onSelectQuestion: (question: string) => void;
  disabled?: boolean;
}

export default function SuggestedQuestions({
  jobId,
  onSelectQuestion,
  disabled = false,
}: SuggestedQuestionsProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // 1. Never fetch suggestions in global search mode
    if (!jobId || jobId.toLowerCase() === "global") {
      setSuggestions([]);
      return;
    }

    let active = true;
    const fetchSuggestions = async () => {
      setLoading(true);
      try {
        const res = await api.getSuggestions(jobId);
        if (active) {
          setSuggestions(res.suggestions || []);
        }
      } catch (err) {
        // Hide SuggestedQuestions section on Groq/fetch failures
        console.warn("Failed to fetch suggested questions:", err);
        if (active) {
          setSuggestions([]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchSuggestions();

    return () => {
      active = false;
    };
  }, [jobId]);

  // Hide container if there are no suggestions and it's not loading
  if (!loading && suggestions.length === 0) {
    return null;
  }

  return (
    <div className="w-full px-6 py-2 select-none shrink-0 border-t border-slate-900/10 bg-slate-950/5">
      <div className="max-w-3xl mx-auto space-y-2">
        {/* Section Header */}
        <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
          <span>Suggested Questions</span>
        </div>

        {loading ? (
          // Pulse Loading skeletons
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2" role="status">
            <span className="sr-only">Generating AI suggestions...</span>
            {[...Array(4)].map((_, i) => (
              <div
                key={`skeleton-${i}`}
                className="h-10 w-full rounded-lg bg-slate-900/40 border border-slate-800/40 animate-pulse flex items-center px-4"
              >
                <div className="h-2.5 w-3/4 rounded bg-slate-800/60" />
              </div>
            ))}
          </div>
        ) : (
          // Hover-able suggestion chips
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {suggestions.map((q, idx) => (
              <button
                key={`${jobId}-sugg-${idx}`}
                type="button"
                disabled={disabled}
                onClick={() => onSelectQuestion(q)}
                className="group flex w-full items-center justify-between text-left rounded-lg border border-slate-800 bg-slate-950/20 px-3.5 py-2.5 text-xs text-slate-300 hover:border-indigo-500/40 hover:bg-indigo-600/5 hover:text-indigo-400 transition-all duration-200 outline-none focus-visible:ring-1.5 focus-visible:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                <span className="truncate pr-2">{q}</span>
                <HelpCircle className="h-3.5 w-3.5 shrink-0 text-slate-600 group-hover:text-indigo-400/80 transition-colors" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
