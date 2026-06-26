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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="relative">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter website URL (https://...)"
          disabled={loading}
          className="w-full rounded-full border border-border-subtle bg-surface-primary px-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/50 focus:outline-none focus:ring-1 focus:ring-accent-blue/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-[--transition-fast]"
        />
      </div>

      {error && (
        <div className="rounded-md border border-rose-500/15 bg-rose-500/10 px-4 py-2 text-[10px] font-medium text-rose-400 leading-relaxed font-inter">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-accent-blue to-accent-purple hover:opacity-90 active:scale-[0.98] text-white px-4 py-2 text-xs font-semibold shadow-soft transition-all duration-[--transition-fast] disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer font-outfit"
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
