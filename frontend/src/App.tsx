import React, { useState } from "react";
import Sidebar from "./components/sidebar/Sidebar";
import LoadingSpinner from "./components/common/LoadingSpinner";
import { Bot, MessageSquare, SendHorizontal } from "lucide-react";

export default function App() {
  // F2 Requirement: Active source state ownership (null = Global Search Mode)
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 antialiased font-sans">
      {/* 320px Sidebar container */}
      <Sidebar
        activeSourceId={activeSourceId}
        onSelectSource={setActiveSourceId}
      />

      {/* Main Conversation Area */}
      <main className="flex flex-1 flex-col overflow-hidden bg-slate-900/40">
        
        {/* Workspace Header */}
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

        {/* Scrollable Conversation Feed Placeholder */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4 max-w-md mx-auto">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 shadow-xl">
              <Bot className="h-7 w-7" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Ask WebGPT Chatbot</h2>
              <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                Query website pages using Retrieval-Augmented Generation. 
                Choose a specific source in the sidebar or use the search field in Global Search Mode.
              </p>
            </div>
            {/* Design verification check showing loader styling */}
            <div className="pt-2 flex items-center gap-2 text-xs text-slate-600 font-medium">
              <LoadingSpinner size="sm" />
              Initializing chat interfaces...
            </div>
          </div>
        </div>

        {/* Fixed Bottom Chat Query Input Placeholder */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/20">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-center rounded-lg border border-slate-800 bg-slate-900/60 p-1.5 focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/30 transition">
              <textarea
                placeholder="Ask a question about the scraped pages..."
                disabled
                rows={1}
                className="w-full resize-none bg-transparent px-3 py-2 text-sm text-slate-400 placeholder:text-slate-600 focus:outline-none disabled:cursor-not-allowed"
              />
              <button
                type="button"
                disabled
                className="flex h-9 w-9 items-center justify-center rounded-md bg-indigo-600/30 text-indigo-400/50 cursor-not-allowed transition shrink-0"
              >
                <SendHorizontal className="h-4.5 w-4.5" />
              </button>
            </div>
            <div className="mt-2 text-[10px] text-center text-slate-600">
              WebGPT uses Gemini 2.5 Flash and local vector databases to ground all answers.
            </div>
          </div>
        </div>

      </main>
    </div>
  );
}
