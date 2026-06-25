import React, { useEffect, useRef } from "react";
import { useChat } from "../../hooks/useChat";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import LoadingSpinner from "../common/LoadingSpinner";
import { Bot, MessageSquare } from "lucide-react";
import AddSourceForm from "../sidebar/AddSourceForm";
import logo from "../../assets/logo.png";


interface ChatWindowProps {
  activeSourceId: string | null;
  onScrapeSuccess?: (job: any) => void;
}

export default function ChatWindow({ activeSourceId, onScrapeSuccess }: ChatWindowProps) {
  const { messages, loading, generating, error, sendMessage } = useChat(activeSourceId);
  // Ref to the scrollable message container — we scroll it directly so the browser
  // window never scrolls. scrollIntoView() is intentionally avoided because it
  // walks up the ancestor chain and can scroll the <body> when layout is in flux
  // (e.g. the tiny typing-indicator bubble being replaced by a tall response card).
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Imperatively scroll the overflow container to its bottom after every message change.
  // Using scrollTop = scrollHeight is guaranteed to target only this container.
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const suggestions = [
    "What is the main purpose of this website?",
    "Summarize the key sections or features discussed.",
    "List any technical requirements or specifications.",
  ];

  if (!activeSourceId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center bg-slate-900/40 p-6 text-center">
        <div className="max-w-md w-full space-y-6">
          {/* Logo and Greeting */}
          <img
            src={logo}
            alt="WebGPT Logo"
            className="h-16 w-16 rounded-2xl object-cover shadow-xl shadow-indigo-500/15 mx-auto border border-slate-800 bg-slate-950/45 p-1"
          />
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
              Hello, this is WebGPT
            </h1>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed max-w-sm mx-auto">
              Enter a website URL below to recursively crawl, index, and query the site using grounded RAG.
            </p>
          </div>

          {/* Centered Add Source Input card */}
          <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-5 shadow-2xl backdrop-blur">
            <AddSourceForm onSuccess={onScrapeSuccess || (() => {})} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col min-h-0 overflow-hidden bg-slate-900/40">
      
      {/* Dynamic Header */}
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950/50 px-6 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
            <MessageSquare className="h-4.5 w-4.5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">
              Website Scraped Context
            </h1>
            <p className="text-[10px] text-slate-500 font-medium">
              Source ID: {activeSourceId}
            </p>
          </div>
        </div>
      </header>

      {/* Main Conversation Thread Feed — this is the ONLY scrollable container */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-6">
        {loading && messages.length === 0 ? (
          // Initial History Loading state
          <div className="flex h-full flex-col items-center justify-center text-slate-500">
            <LoadingSpinner size="md" />
            <span className="mt-2 text-xs font-semibold tracking-wide">Loading conversation history...</span>
          </div>
        ) : messages.length === 0 ? (
          // Welcome / Empty state
          <div className="flex flex-col items-center justify-center h-full text-center space-y-5 max-w-lg mx-auto">
            <img
              src={logo}
              alt="WebGPT Logo"
              className="h-14 w-14 rounded-2xl object-cover shadow-xl border border-slate-800 bg-slate-950/45 p-1"
            />
            <div>
              <h2 className="text-base font-semibold text-white">Ask WebGPT</h2>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed max-w-md mx-auto">
                Query website pages using Retrieval-Augmented Generation. 
                Select a specific source from the sidebar or use the search field in Global Search Mode.
              </p>
            </div>

            {/* Quick start suggestion chips */}
            <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-2.5 max-w-md pt-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => sendMessage(s)}
                  className="rounded-lg border border-slate-800/80 bg-slate-900/20 px-3.5 py-2 text-xs text-slate-400 hover:border-indigo-500/40 hover:bg-indigo-600/5 hover:text-indigo-400 transition cursor-pointer text-left sm:text-center w-full sm:w-auto"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          // Scrollable messages list
          <div className="max-w-3xl mx-auto space-y-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            
            {/* Inline RAG error display for global state load errors */}
            {error && (
              <div className="rounded-lg border border-rose-500/15 bg-rose-500/10 p-3 text-xs text-rose-400 leading-relaxed">
                Failed to resolve RAG query: {error}
              </div>
            )}
          </div>
        )}
      </div>



      {/* Fixed bottom textarea chat input card */}
      <ChatInput onSend={sendMessage} disabled={generating || loading} />
    </div>
  );
}
