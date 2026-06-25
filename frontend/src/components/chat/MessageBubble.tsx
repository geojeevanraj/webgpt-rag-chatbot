import React from "react";
import { WebChatMessage } from "../../types/api";
import Markdown from "react-markdown";
import { AlertCircle, User, ExternalLink } from "lucide-react";
import logo from "../../assets/logo.png";

interface MessageBubbleProps {
  message: WebChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = !!message.isError;

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
          className="h-8 w-8 shrink-0 rounded-lg object-cover border border-slate-800 bg-slate-950/45 p-0.5 shadow-sm"
        />
      )}

      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Message Content Bubble */}
        <div
          className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-indigo-600 text-white rounded-br-none shadow-md shadow-indigo-600/10"
              : isError
              ? "bg-rose-500/10 border border-rose-500/25 text-rose-400 rounded-bl-none shadow-md shadow-rose-500/5"
              : "bg-slate-900/50 border border-slate-800 text-slate-100 rounded-bl-none shadow-sm"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : isError ? (
            <div className="flex items-start gap-2.5 py-0.5">
              <AlertCircle className="h-4.5 w-4.5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-300">Generation Failed</p>
                <p className="text-rose-400/90 text-xs mt-1 leading-relaxed">{message.content}</p>
              </div>
            </div>
          ) : message.content === "" ? (
            // Optimistic Bouncing Loader Animation
            // min-h keeps the placeholder bubble close to a real response height so the
            // scroll container's scrollHeight doesn't wildly change between states.
            <div className="flex items-center gap-1.5 py-1 min-h-[2rem]" role="status">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
              <span className="sr-only">Typing...</span>
            </div>
          ) : (
            // Render markdown content safely
            <article className="prose prose-invert max-w-none text-slate-100 prose-sm prose-p:leading-relaxed prose-pre:bg-slate-950 prose-pre:border prose-pre:border-slate-800">
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
                          className="text-blue-400 hover:underline font-semibold text-xs mx-0.5 align-super bg-blue-500/10 px-1 py-0.5 rounded border border-blue-500/20 inline-flex items-center cursor-pointer transition-all"
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
                        className="text-indigo-400 hover:text-indigo-300 underline cursor-pointer"
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

          {/* Sources Section */}
          {!isUser && uniqueCitations.length > 0 && (
            <div className="mt-3 w-full border-t border-slate-800/80 pt-3">
              <h4 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Sources
              </h4>
              <div className="flex flex-col gap-2">
                {uniqueCitations.map((citation, index) => (
                  <a
                    key={`${citation.source_url}-${index}`}
                    href={citation.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-start gap-2.5 rounded border border-slate-800/80 bg-slate-950/20 p-2.5 hover:bg-slate-900/40 hover:border-slate-700/80 transition-all duration-200"
                  >
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-800 text-[10px] font-bold text-indigo-400 group-hover:bg-indigo-950/40 group-hover:text-indigo-300 transition-colors">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-medium text-slate-200 group-hover:text-indigo-400 transition-colors line-clamp-1">
                          {citation.page_title}
                        </span>
                        <ExternalLink className="h-3.5 w-3.5 text-slate-500 opacity-0 group-hover:opacity-100 group-hover:text-indigo-400 transition-all shrink-0 ml-0.5" />
                      </div>
                      <span className="block text-[10px] text-slate-500 truncate mt-0.5">
                        {citation.source_url}
                      </span>
                    </div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>


      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 text-slate-300 border border-slate-700 shadow-sm">
          <User className="h-4.5 w-4.5" />
        </div>
      )}
    </div>
  );
}
