import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { SourceSummary } from "../types/api";

export function useSources() {
  const [sources, setSources] = useState<SourceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getSources(100, 0); // Limit to 100 for display
      setSources(data);
    } catch (err: any) {
      setError(err.message || "Failed to load sources from database.");
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteSource = useCallback(async (jobId: string) => {
    setError(null);
    try {
      await api.deleteScrape(jobId);
      // Remove from state list immediately on deletion success
      setSources((prev) => prev.filter((s) => s.job_id !== jobId));
    } catch (err: any) {
      setError(err.message || "Failed to delete source.");
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  return {
    sources,
    loading,
    error,
    refreshSources: fetchSources,
    deleteSource,
  };
}
