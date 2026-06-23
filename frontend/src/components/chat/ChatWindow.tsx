import React, { useEffect, useRef } from "react";
import { useChat } from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import LoadingSpinner from "../common/LoadingSpinner";
import { Bot, MessageSquare } from "lucide-react";

interface ChatWindowProps {
  activeSourceId: string | null;
}

export default function ChatWindow({ activeSourceId }: ChatWindowProps) {
  const { messages, loading, error, sendMessage } = useChat(activeSourceId);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom of the conversation feed on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-slate-900/40">
      
      {/* Dynamic Header */}
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950/50 px-6 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
            <MessageSquare className="h-4.5 w-4.5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">
              {activeSourceId ? "Website Scraped Context" : "Global Search Mode"}
            </h1>
            <p className="text-[10px] text-slate-500 font-medium">
              {activeSourceId ? `Source ID: ${activeSourceId}` : "Searching across all compiled data stores"}
            </p>
          </div>
        </div>
      </header>

      {/* Main Conversation Thread Feed */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading && messages.length === 0 ? (
          // Initial History Loading state
          <div className="flex h-full flex-col items-center justify-center text-slate-500">
            <LoadingSpinner size="md" />
            <span className="mt-2 text-xs font-semibold tracking-wide">Loading conversation history...</span>
          </div>
        ) : messages.length === 0 ? (
          // Welcome / Empty state
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4 max-w-md mx-auto">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 shadow-xl">
              <Bot className="h-7 w-7" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Ask WebGPT</h2>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Query website pages using Retrieval-Augmented Generation. 
                Select a specific source from the sidebar or use the search field in Global Search Mode.
              </p>
            </div>
          </div>
        ) : (
          // Scrollable messages list
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            
            {/* Inline RAG error display */}
            {error && (
              <div className="rounded-lg border border-rose-500/15 bg-rose-500/10 p-3 text-xs text-rose-450 leading-relaxed">
                Failed to resolve RAG query: {error}
              </div>
            )}
            
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Fixed bottom textarea chat input card */}
      <ChatInput onSend={sendMessage} disabled={loading} />
    </div>
  );
}
