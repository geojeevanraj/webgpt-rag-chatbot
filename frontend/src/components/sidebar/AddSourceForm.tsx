import React, { useState } from "react";
import { api } from "../../services/api";
import { Loader2, Plus } from "lucide-react";
import { ScrapeResponse } from "../../types/api";

interface AddSourceFormProps {
  onSuccess: (job: ScrapeResponse) => void;
}

export default function AddSourceForm({ onSuccess }: AddSourceFormProps) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError("Please enter a URL.");
      return;
    }

    // Basic URL regex check requiring HTTP or HTTPS protocols
    const urlPattern = /^https?:\/\/[^\s$.?#].[^\s]*$/i;
    if (!urlPattern.test(trimmedUrl)) {
      setError("Only valid HTTP/HTTPS URLs are supported.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.startScrape({
        url: trimmedUrl,
        max_depth: 2,
        max_pages: 50,
      });
      setUrl("");
      onSuccess(res);
    } catch (err: any) {
      setError(err.message || "Failed to start scraping pipeline.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="relative">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter website URL (https://...)"
          disabled={loading}
          className="w-full rounded-md border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-indigo-500/50 focus:outline-none focus:ring-1 focus:ring-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition"
        />
      </div>

      {error && (
        <div className="rounded border border-rose-500/15 bg-rose-500/10 px-2.5 py-1.5 text-[10px] font-medium text-rose-450 leading-relaxed">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-1.5 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-2 text-xs font-semibold shadow-sm transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
      >
        {loading ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Indexing...
          </>
        ) : (
          <>
            <Plus className="h-3.5 w-3.5" />
            Scrape Site
          </>
        )}
      </button>
    </form>
  );
}
