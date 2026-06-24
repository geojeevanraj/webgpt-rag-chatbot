import { useEffect, useRef } from "react";
import { SourceSummary } from "../types/api";

/**
 * Custom hook to poll the sources list while there are active scraping or pending jobs.
 *
 * It monitors the list of sources. If any job status is 'scraping' or 'pending',
 * it sets up a 3-second interval to refresh the sources list. As soon as all
 * active scraping finishes, the interval is cleared automatically.
 *
 * @param sources List of active sources.
 * @param onRefresh Callback function to refresh sources from the server.
 */
export function useScrapePolling(
  sources: SourceSummary[],
  onRefresh: () => void
) {
  const refreshRef = useRef(onRefresh);
  refreshRef.current = onRefresh;

  useEffect(() => {
    // Check if any indexing jobs are in progress
    const hasActiveScrape = sources.some(
      (s) => s.status === "scraping" || s.status === "pending"
    );

    if (!hasActiveScrape) return;

    // Set up interval for live status updates
    const intervalId = setInterval(() => {
      refreshRef.current();
    }, 3000); // Poll every 3 seconds

    return () => {
      clearInterval(intervalId);
    };
  }, [sources]);
}
