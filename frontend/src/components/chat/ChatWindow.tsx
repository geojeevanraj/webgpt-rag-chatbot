import React, { useEffect, useRef, useState, useMemo } from "react";
import { useChat } from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import LoadingSpinner from "../common/LoadingSpinner";
import { Globe } from "lucide-react";
import { SourceSummary, SourcePageInfo } from "../../types/api";
import { api } from "../../services/api";
import KnowledgeExplorer from "./KnowledgeExplorer";
import AnimatedHero from "../hero/AnimatedHero";

interface ChatWindowProps {
  activeSourceId: string | null;
  activeSource?: SourceSummary | null;
  onScrapeSuccess?: (job: any) => void;
}

export default function ChatWindow({
  activeSourceId,
  activeSource,
  onScrapeSuccess,
}: ChatWindowProps) {
  const { messages, loading, generating, error, sendMessage } = useChat(activeSourceId);

  // Calculate favicon URL with fallbacks
  const faviconUrl = useMemo(() => {
    if (!activeSource) return null;
    if (activeSource.favicon_url) return activeSource.favicon_url;
    try {
      const url = new URL(activeSource.seed_url);
      return `${url.origin}/favicon.ico`;
    } catch {
      return null;
    }
  }, [activeSource]);

  // Cache fetched pages per source in React state
  const [pagesCache, setPagesCache] = useState<Record<string, SourcePageInfo[]>>({});
  const [isExplorerOpen, setIsExplorerOpen] = useState(false);
  const [loadingPages, setLoadingPages] = useState(false);
  const [pagesError, setPagesError] = useState<string | null>(null);

  useEffect(() => {
    if (!isExplorerOpen || !activeSourceId) return;

    // If already cached, don't fetch again
    if (pagesCache[activeSourceId]) {
      setPagesError(null);
      return;
    }

    const fetchPages = async () => {
      setLoadingPages(true);
      setPagesError(null);
      try {
        const response = await api.getSourcePages(activeSourceId);
        setPagesCache((prev) => ({
          ...prev,
          [activeSourceId]: response.pages,
        }));
      } catch (err: any) {
        setPagesError(err.message || "Failed to load source pages.");
      } finally {
        setLoadingPages(false);
      }
    };

    fetchPages();
  }, [activeSourceId, isExplorerOpen]);

  // Close explorer when source changes to avoid showing stale drawer
  useEffect(() => {
    setIsExplorerOpen(false);
  }, [activeSourceId]);

  // Ref to the scrollable message container
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages load/change
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleRegenerate = async () => {
    const userMessages = messages.filter((m) => m.role === "user");
    if (userMessages.length === 0) return;
    const latestPrompt = userMessages[userMessages.length - 1].content;
    await sendMessage(latestPrompt);
  };

  return (
    <div className="flex flex-1 flex-col min-h-0 overflow-hidden bg-surface-primary relative">
      
      {/* 1. Backdrop Layer: Animated backdrop and State Machine welcome layouts */}
      <AnimatedHero
        activeSourceId={activeSourceId}
        activeSource={activeSource || null}
        hasMessages={messages.length > 0}
        onSendMessage={sendMessage}
        onScrapeSuccess={onScrapeSuccess || (() => {})}
      />

      {/* 2. Chat Overlay Layer: Floating Header, Scroll Feed, and Input pill */}
      {activeSourceId && (
        <div className="flex flex-1 flex-col min-h-0 overflow-hidden relative z-30 pointer-events-auto">
          
          {/* Floating Chat Header */}
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-border-subtle bg-surface-elevated/75 px-6 backdrop-blur-md z-10">
            <div className="flex items-center gap-2.5 min-w-0">
              {/* Website favicon wrapper */}
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border-subtle bg-surface-secondary text-text-muted overflow-hidden relative shadow-inner">
                {faviconUrl ? (
                  <img
                    src={faviconUrl}
                    alt="Favicon"
                    className="h-4.5 w-4.5 object-contain"
                    onError={(e) => {
                      e.currentTarget.onerror = null;
                      e.currentTarget.style.display = "none";
                      const parent = e.currentTarget.parentElement;
                      if (parent) {
                        const fallbackSvg = parent.querySelector(".fallback-globe");
                        if (fallbackSvg) {
                          fallbackSvg.classList.remove("hidden");
                        }
                      }
                    }}
                  />
                ) : null}
                <Globe className={`h-5 w-5 text-text-muted fallback-globe ${faviconUrl ? "hidden" : ""}`} />
              </div>

              {/* Website Details & Metadata */}
              <div className="min-w-0 flex flex-col justify-center">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="text-xs font-semibold text-text-primary truncate cursor-help hover:text-accent-blue transition font-outfit"
                    title={activeSource ? activeSource.seed_url : ""}
                  >
                    {activeSource ? activeSource.domain : "Global Search"}
                  </span>
                </div>
                {activeSource && activeSource.title && (
                  <span className="text-[10px] text-text-secondary truncate leading-tight font-inter" title={activeSource.title}>
                    {activeSource.title}
                  </span>
                )}
                {activeSource && (
                  <p className="text-[10px] text-text-muted font-medium tracking-wide mt-0.5 leading-none font-inter">
                    {activeSource.pages_scraped} {activeSource.pages_scraped === 1 ? "Page" : "Pages"} • {activeSource.total_chunks} Chunks Indexed
                  </p>
                )}
              </div>
            </div>

            {activeSource && activeSource.status === "completed" && (
              <button
                type="button"
                onClick={() => setIsExplorerOpen(true)}
                className="flex items-center gap-2 rounded-full border border-border-subtle bg-surface-elevated px-4 py-2 text-xs text-text-primary hover:border-accent-blue/40 hover:bg-surface-secondary transition-all duration-[--transition-fast] cursor-pointer font-semibold shadow-soft font-outfit shrink-0"
              >
                📚 Knowledge Explorer
              </button>
            )}
          </header>

          {/* Messages Scroll Feed */}
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-6 relative">
            {loading && messages.length === 0 ? (
              // Initial Loading state
              <div className="flex h-full flex-col items-center justify-center text-text-secondary">
                <LoadingSpinner size="md" />
                <span className="mt-2 text-xs font-semibold tracking-wide font-inter">Loading conversation history...</span>
              </div>
            ) : messages.length > 0 ? (
              // Messages list
              <div className="max-w-4xl mx-auto space-y-5">
                {messages.map((msg) => (
                  <MessageBubble key={msg.id} message={msg} onRegenerate={handleRegenerate} />
                ))}
                
                {/* RAG pipeline error notification */}
                {error && (
                  <div className="rounded-lg border border-rose-500/15 bg-rose-500/10 p-4 text-xs text-rose-400 leading-relaxed font-inter">
                    Failed to resolve RAG query: {error}
                  </div>
                )}
              </div>
            ) : null}
          </div>

          {/* Chat text area input */}
          <ChatInput onSend={sendMessage} disabled={generating || loading} />
        </div>
      )}

      {/* Slide-over Knowledge Explorer Drawer */}
      {isExplorerOpen && activeSource && (
        <KnowledgeExplorer
          activeSource={activeSource}
          pages={pagesCache[activeSource.job_id] || []}
          loading={loadingPages}
          error={pagesError}
          onClose={() => setIsExplorerOpen(false)}
        />
      )}
    </div>
  );
}
