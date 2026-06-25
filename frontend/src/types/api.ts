/**
 * TypeScript API request/response type definitions matching FastAPI schemas.
 */

export interface ScrapeRequest {
  url: string;
  max_depth?: number;
  max_pages?: number;
}

export interface ScrapeResponse {
  job_id: string;
  status: string;
  seed_url: string;
  created_at: string;
}

export interface PageInfo {
  url: string;
  title: string;
  depth: number;
  chunk_count: number;
  status: "scraped" | "failed";
  error_message: string | null;
}

export interface ScrapeStatusResponse {
  job_id: string;
  seed_url: string;
  domain: string;
  status: "pending" | "scraping" | "completed" | "failed";
  max_depth: number;
  max_pages: number;
  pages_scraped: number;
  pages_failed: number;
  total_chunks: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  pages: PageInfo[];
}

export interface CitationInfo {
  source_url: string;
  page_title: string;
}

export interface ChatWebRequest {
  job_id: string | null;
  question: string;
}

export interface ChatWebResponse {
  answer: string;
  citations: CitationInfo[];
}

export interface WebChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: CitationInfo[] | null;
  created_at: string;
  isError?: boolean;
}

export interface WebChatHistoryResponse {
  messages: WebChatMessage[];
}

export interface SourceSummary {
  job_id: string;
  seed_url: string;
  domain: string;
  status: "pending" | "scraping" | "completed" | "failed";
  pages_scraped: number;
  total_chunks: number;
  created_at: string;
}

export interface PageSummary {
  url: string;
  title: string;
  depth: number;
  chunk_count: number;
}

export interface SourceDetailResponse {
  job_id: string;
  domain: string;
  pages: PageSummary[];
}

export interface ApiError {
  status: number;
  detail: string;
}


