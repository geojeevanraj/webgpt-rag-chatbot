import React from "react";
import { WebChatMessage } from "../../types/api";
import Markdown from "react-markdown";
import { AlertCircle, User, ExternalLink, Globe, Copy, RotateCcw, ThumbsUp, ThumbsDown } from "lucide-react";
import logo from "../../assets/logo.png";

interface MessageBubbleProps {
  message: WebChatMessage;
  onRegenerate?: () => Promise<void>;
}

export default function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = !!message.isError;

  const [liked, setLiked] = React.useState(false);
  const [disliked, setDisliked] = React.useState(false);

  const handleLike = () => {
    setLiked(!liked);
    setDisliked(false);
  };

  const handleDislike = () => {
    setDisliked(!disliked);
    setLiked(false);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    window.dispatchEvent(
      new CustomEvent("app-toast", {
        detail: { type: "success", message: "Response copied to clipboard!" },
      })
    );
  };

  // Deduplicate citations by source_url to prevent rendering duplicate source listings
  const uniqueCitations = message.citations
    ? message.citations.filter(
        (c, index, self) =>
          self.findIndex((t) => t.source_url === c.source_url) === index
      )
    : [];

  return (
    <div className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {/* Bot Avatar */}
      {!isUser && (
        <img
          src={logo}
          alt="WebGPT Logo"
          className="h-10 w-10 shrink-0 object-contain mt-2"
        />
      )}

      <div className={`flex flex-col gap-2 ${isUser ? "max-w-[85%]" : "max-w-[88%]"} ${isUser ? "items-end" : "items-start"} group`}>
        {/* Message Content Bubble */}
        <div
          className={`text-sm leading-relaxed font-inter shadow-soft ${
            isUser
              ? "bg-accent-blue text-surface-background rounded-tr-none rounded-lg p-4 font-medium"
              : isError
              ? "bg-rose-500/10 border border-rose-500/25 text-rose-400 rounded-tl-none rounded-lg p-4"
              : "bg-surface-secondary/65 border border-white/[0.05] text-text-primary rounded-tl-none rounded-[20px] p-5 md:p-6"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isError ? (
            <div className="flex items-start gap-3 py-0.5">
              <AlertCircle className="h-4.5 w-4.5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-300">Generation Failed</p>
                <p className="text-rose-400/90 text-xs mt-1 leading-relaxed">{message.content}</p>
              </div>
            </div>
          ) : message.content === "" ? (
            // Optimistic Bouncing Loader Animation
            <div className="flex items-center gap-1.5 py-1 min-h-[2rem]" role="status">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted" />
              <span className="sr-only">Typing...</span>
            </div>
          ) : (
            // Render markdown content safely
            <article className="prose prose-invert max-w-none text-text-primary prose-sm prose-p:leading-relaxed prose-pre:bg-surface-background prose-pre:border prose-pre:border-border-subtle">
              <Markdown
                components={{
                  a: ({ href, children, ...props }) => {
                    const isCitationLink = typeof children === "string" && /^\d+$/.test(children);
                    
                    if (isCitationLink) {
                      return (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-accent-blue hover:underline font-semibold text-[10px] mx-0.5 align-super bg-accent-blue/10 px-1.5 py-0.5 rounded-sm border border-accent-blue/20 inline-flex items-center cursor-pointer transition-all duration-[--transition-fast]"
                          {...props}
                        >
                          [{children}]
                        </a>
                      );
                    }

                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-accent-blue hover:text-accent-blue/80 underline cursor-pointer transition-colors duration-[--transition-fast]"
                        {...props}
                      >
                        {children}
                      </a>
                    );
                  }
                }}
              >
                {message.content}
              </Markdown>
            </article>
          )}

          {/* Action Bar (Assistant Only) */}
          {!isUser && message.content !== "" && (
            <div className="flex items-center gap-2 mt-3 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-200 ease-out pointer-events-auto">
              <button
                type="button"
                onClick={handleCopy}
                title="Copy response"
                className="bg-surface-secondary border border-white/[0.05] rounded-full p-2 text-text-secondary hover:text-text-primary hover:bg-surface-elevated hover:-translate-y-[1px] transition-all duration-200 ease-out cursor-pointer focus:outline-none"
              >
                <Copy className="h-4 w-4" />
              </button>
              {onRegenerate && (
                <button
                  type="button"
                  onClick={onRegenerate}
                  title="Regenerate response"
                  className="bg-surface-secondary border border-white/[0.05] rounded-full p-2 text-text-secondary hover:text-text-primary hover:bg-surface-elevated hover:-translate-y-[1px] transition-all duration-200 ease-out cursor-pointer focus:outline-none"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              )}
              <button
                type="button"
                onClick={handleLike}
                title="Like response"
                className={`border border-white/[0.05] rounded-full p-2 hover:bg-surface-elevated hover:-translate-y-[1px] transition-all duration-200 ease-out cursor-pointer focus:outline-none ${
                  liked ? "bg-accent-blue text-surface-background hover:bg-accent-blue" : "bg-surface-secondary text-text-secondary hover:text-text-primary"
                }`}
              >
                <ThumbsUp className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={handleDislike}
                title="Dislike response"
                className={`border border-white/[0.05] rounded-full p-2 hover:bg-surface-elevated hover:-translate-y-[1px] transition-all duration-200 ease-out cursor-pointer focus:outline-none ${
                  disliked ? "bg-rose-500 text-text-primary hover:bg-rose-500" : "bg-surface-secondary text-text-secondary hover:text-text-primary"
                }`}
              >
                <ThumbsDown className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Redesigned Compact Card Citations */}
          {!isUser && uniqueCitations.length > 0 && (
            <div className="mt-4 w-full border-t border-border-subtle pt-4 font-inter">
              <h4 className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-3 font-outfit">
                Sources
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {uniqueCitations.map((citation, index) => {
                  const hasTitle =
                    citation.page_title &&
                    citation.page_title.trim() !== "" &&
                    citation.page_title !== "Untitled Page";
                  const displayLabel = hasTitle
                    ? citation.page_title
                    : citation.source_url;

                  // Extract domain and favicon URL
                  let domain = "";
                  let favicon = "";
                  try {
                    const url = new URL(citation.source_url);
                    domain = url.hostname;
                    favicon = `https://www.google.com/s2/favicons?domain=${url.hostname}&sz=32`;
                  } catch {
                    domain = citation.source_url;
                  }

                  return (
                    <a
                      key={`${citation.source_url}-${index}`}
                      href={citation.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group flex items-start gap-3 rounded-[16px] border border-transparent bg-surface-secondary px-3 py-2 hover:bg-surface-secondary/70 hover:border-accent-blue/30 hover:-translate-y-[2px] hover:scale-[1.01] hover:shadow-soft transition-all duration-200 ease-out cursor-pointer shadow-soft"
                    >
                      {/* Favicon Container */}
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-surface-primary overflow-hidden border border-border-subtle">
                        {favicon ? (
                          <img
                            src={favicon}
                            alt="Source favicon"
                            className="h-3.5 w-3.5 object-contain"
                            onError={(e) => {
                              e.currentTarget.onerror = null;
                              e.currentTarget.style.display = "none";
                              const parent = e.currentTarget.parentElement;
                              if (parent) {
                                const fallbackGlobe = parent.querySelector(".fallback-globe");
                                if (fallbackGlobe) fallbackGlobe.classList.remove("hidden");
                              }
                            }}
                          />
                        ) : null}
                        <Globe className={`h-3.5 w-3.5 text-text-muted fallback-globe ${favicon ? "hidden" : ""}`} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 justify-between">
                          <span className="text-xs font-semibold text-text-primary group-hover:text-accent-blue transition-colors duration-200 ease-out line-clamp-1 leading-normal">
                            {displayLabel}
                          </span>
                          <ExternalLink className="h-3.5 w-3.5 text-text-muted shrink-0 transition-colors duration-200 ease-out group-hover:text-accent-blue" />
                        </div>
                        <span className="block text-[10px] text-text-muted truncate mt-0.5 font-normal">
                          {domain}
                        </span>
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-sm bg-surface-secondary text-text-secondary border border-border-subtle shadow-soft mt-2">
          <User className="h-5 w-5" />
        </div>
      )}
    </div>
  );
}
