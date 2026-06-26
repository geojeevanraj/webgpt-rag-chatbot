import {
  ChatWebRequest,
  ChatWebResponse,
  ScrapeRequest,
  ScrapeResponse,
  ScrapeStatusResponse,
  SourceDetailResponse,
  SourceSummary,
  WebChatHistoryResponse,
  SourcePagesResponse,
  CitationInfo,
} from "../types/api";


/**
 * Custom application-level API Error wrapper.
 */
export class APIError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Perform a fetch request with a configured execution timeout constraint.
 */
async function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeout?: number } = {}
): Promise<Response> {
  const { timeout = 15000, ...customOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...customOptions,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Generic request helper mapping responses, timeouts, headers, and exceptions.
 */
async function request<T>(
  endpoint: string,
  options: RequestInit & { timeout?: number } = {}
): Promise<T> {
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
  const url = `${API_URL}${endpoint}`;

  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  try {
    const response = await fetchWithTimeout(url, { ...options, headers });

    // Handle 204 No Content requests safely
    if (response.status === 204) {
      return {} as T;
    }

    const data = await response.json();

    if (!response.ok) {
      const detail = data.detail || response.statusText || "An unexpected error occurred.";
      throw new APIError(response.status, detail);
    }

    return data as T;
  } catch (error: any) {
    if (error.name === "AbortError") {
      throw new APIError(408, "Request timed out after 15 seconds.");
    }
    if (error instanceof APIError) {
      throw error;
    }
    throw new APIError(
      0,
      error.message || "Network error. Failed to connect to the backend server."
    );
  }
}

/**
 * Centralized typed API endpoint wrappers.
 */
export const api = {
  /**
   * Retrieve a list of all active scrape jobs/sources (paginated).
   */
  getSources: (limit = 10, offset = 0) =>
    request<SourceSummary[]>(`/sources?limit=${limit}&offset=${offset}`),

  /**
   * Retrieve crawled page metrics for a specific source context.
   */
  getSourceDetails: (jobId: string) =>
    request<SourceDetailResponse>(`/sources/${jobId}`),

  /**
   * Submit a seed URL to launch a recursive background scrape job.
   */
  startScrape: (req: ScrapeRequest) =>
    request<ScrapeResponse>("/scrape", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  /**
   * Query the live crawling/indexing status of a scrape job.
   */
  getScrapeStatus: (jobId: string) =>
    request<ScrapeStatusResponse>(`/scrape/${jobId}`),

  /**
   * Purge all database and vector store indexes for a source context.
   */
  deleteScrape: (jobId: string) =>
    request<void>(`/scrape/${jobId}`, {
      method: "DELETE",
    }),

  /**
   * Submit a chat question grounded in a source (or globally).
   */
  askQuestion: (req: ChatWebRequest) =>
    request<ChatWebResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  /**
   * Submit a chat question and stream the response via Server-Sent Events.
   */
  streamChatResponse: async (
    req: ChatWebRequest,
    callbacks: {
      onStatus?: (text: string) => void;
      onStart?: (model: string) => void;
      onDelta?: (text: string) => void;
      onCitations?: (citations: CitationInfo[]) => void;
      onDone?: (data: { model: string; finish_reason: string; usage: any }) => void;
      onAborted?: () => void;
      onInterrupted?: (message: string, citations: CitationInfo[]) => void;
      onError?: (message: string) => void;
      onHeartbeat?: () => void;
    },
    signal?: AbortSignal
  ) => {
    const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
    const response = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(req),
      signal,
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = data.detail || response.statusText || "An unexpected error occurred.";
      throw new APIError(response.status, detail);
    }

    if (!response.body) {
      throw new APIError(0, "Readable stream not supported by browser.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      let currentEvent = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last partial line in the buffer
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          if (trimmed.startsWith("event:")) {
            currentEvent = trimmed.slice(6).trim();
          } else if (trimmed.startsWith("data:")) {
            const dataStr = trimmed.slice(5).trim();
            try {
              const parsed = JSON.parse(dataStr);
              switch (currentEvent) {
                case "status":
                  callbacks.onStatus?.(parsed.text);
                  break;
                case "start":
                  callbacks.onStart?.(parsed.model);
                  break;
                case "delta":
                  callbacks.onDelta?.(parsed.text);
                  break;
                case "citations":
                  callbacks.onCitations?.(parsed.citations || []);
                  break;
                case "done":
                  callbacks.onDone?.(parsed);
                  break;
                case "aborted":
                  callbacks.onAborted?.();
                  break;
                case "interrupted":
                  callbacks.onInterrupted?.(parsed.message || "Interrupted", parsed.citations || []);
                  break;
                case "error":
                  callbacks.onError?.(parsed.message || "Unknown error");
                  break;
                case "heartbeat":
                  callbacks.onHeartbeat?.();
                  break;
              }
            } catch (err) {
              console.error("Failed to parse SSE data block", dataStr, err);
            }
            currentEvent = ""; // Reset event
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * Retrieve all previous conversation messages for a source context.
   */
  getChatHistory: (jobId: string) =>
    request<WebChatHistoryResponse>(`/chat/history/${jobId}`),

  /**
   * Retrieve successfully crawled pages for a specific source context.
   */
  getSourcePages: (jobId: string) =>
    request<SourcePagesResponse>(`/sources/${jobId}/pages`),
};
