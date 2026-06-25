import React from "react";
import { WebChatMessage } from "../../types/api";
import Markdown from "react-markdown";
import CitationChip from "./CitationChip";
import { AlertCircle, User } from "lucide-react";
import logo from "../../assets/logo.png";

interface MessageBubbleProps {
  message: WebChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = !!message.isError;

  // Helper to parse [Source N] and [N] into Markdown link syntax [N](url)
  const renderMessageContent = () => {
    if (isUser || !message.citations || message.citations.length === 0) {
      return message.content;
    }

    const citations = message.citations;

    // Split by code blocks (``` ... ```) first to avoid converting text inside code blocks
    const codeBlockRegex = /(```[\s\S]*?```)/g;
    const parts = message.content.split(codeBlockRegex);

    return parts
      .map((part) => {
        // If it's a fenced code block, return it untouched
        if (part.startsWith("```") && part.endsWith("```")) {
          return part;
        }

        // Split by inline code blocks (` ... `)
        const inlineCodeRegex = /(`[^`]+`)/g;
        const subParts = part.split(inlineCodeRegex);

        return subParts
          .map((subPart) => {
            // If it's an inline code block, return it untouched
            if (subPart.startsWith("`") && subPart.endsWith("`")) {
              return subPart;
            }

            // Perform replacement on text outside code blocks.
            // Negative lookahead (?!\() prevents matching citations that are already links.
            return subPart.replace(/\[(?:Source\s+)?(\d+)\](?!\()/g, (match, numStr) => {
              const index = parseInt(numStr, 10) - 1;
              if (index >= 0 && index < citations.length) {
                const citation = citations[index];
                return `[${numStr}](${citation.source_url})`;
              }
              return match;
            });
          })
          .join("");
      })
      .join("");
  };

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
            <div className="flex items-center gap-1.5 py-1" role="status">
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
                {renderMessageContent()}
              </Markdown>
            </article>
          )}
        </div>

        {/* Cited Sources list */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-2 items-center">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Sources:</span>
            {message.citations.map((citation, index) => (
              <CitationChip
                key={`${citation.source_url}-${index}`}
                citation={citation}
                index={index + 1}
              />
            ))}
          </div>
        )}
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
