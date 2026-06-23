import React from "react";
import { WebChatMessage } from "../../types/api";
import Markdown from "react-markdown";
import CitationChip from "./CitationChip";
import { Bot, User } from "lucide-react";

interface MessageBubbleProps {
  message: WebChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {/* Bot Avatar */}
      {!isUser && (
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/10 shadow-sm">
          <Bot className="h-4.5 w-4.5" />
        </div>
      )}

      <div className={`flex flex-col gap-2 max-w-[85%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Message Content Bubble */}
        <div
          className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? "bg-indigo-600 text-white rounded-br-none shadow-md shadow-indigo-600/10"
              : "bg-slate-900/50 border border-slate-800 text-slate-100 rounded-bl-none shadow-sm"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
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
              <Markdown>{message.content}</Markdown>
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
