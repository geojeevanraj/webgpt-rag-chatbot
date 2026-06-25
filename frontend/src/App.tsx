import React, { useState } from "react";
import Sidebar from "./components/sidebar/Sidebar";
import ChatWindow from "./components/chat/ChatWindow";
import ErrorBoundary from "./components/common/ErrorBoundary";
import { useSources } from "./hooks/useSources";
import { useScrapePolling } from "./hooks/useScrapePolling";
import { AlertCircle, CheckCircle2, Info, Menu, X } from "lucide-react";
import { ScrapeResponse } from "./types/api";
import logo from "./assets/logo.png";

interface ToastMessage {
  id: string;
  type: "success" | "error" | "info";
  message: string;
}

export default function App() {
  // 1. Core State Ownership
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // 2. Custom hooks: load and poll sources
  const { sources, loading, error, refreshSources, deleteSource } = useSources();
  useScrapePolling(sources, refreshSources);

  // Helper to add toast messages that fade out automatically
  const addToast = (type: "success" | "error" | "info", message: string) => {
    const id = `toast-${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  const handleScrapeSuccess = (job: ScrapeResponse) => {
    addToast(
      "success",
      `Scrape job initiated for ${job.seed_url}! Crawling will progress in the background.`
    );
    refreshSources();
  };

  const handleDeleteSource = async (jobId: string) => {
    try {
      await deleteSource(jobId);
      addToast("success", "Source successfully deleted and purged from vector index.");
      // Reset active source context back to global search if active source was deleted
      if (activeSourceId === jobId) {
        setActiveSourceId(null);
      }
    } catch (err: any) {
      addToast("error", err.message || "Failed to purge source index.");
    }
  };

  return (
    <ErrorBoundary>
      <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 antialiased font-sans">
        
        {/* =================================================================== */}
        {/* Side Panel: Desktop (fixed) & Mobile (overlay drawer) */}
        {/* =================================================================== */}
        
        {/* Desktop Sidebar (hidden on mobile, visible md+) */}
        <div className="hidden md:flex h-full w-[320px] shrink-0">
          <Sidebar
            sources={sources}
            activeSourceId={activeSourceId}
            onSelectSource={setActiveSourceId}
            onDeleteSource={handleDeleteSource}
            onScrapeSuccess={handleScrapeSuccess}
            loading={loading}
          />
        </div>

        {/* Mobile Sidebar overlay (visible when toggled) */}
        {mobileSidebarOpen && (
          <div className="fixed inset-0 z-50 flex md:hidden bg-slate-950/80 backdrop-blur-sm">
            <div className="h-full w-[290px] shadow-2xl animate-in slide-in-from-left duration-200">
              <Sidebar
                sources={sources}
                activeSourceId={activeSourceId}
                onSelectSource={setActiveSourceId}
                onDeleteSource={handleDeleteSource}
                onScrapeSuccess={handleScrapeSuccess}
                loading={loading}
                onCloseMobile={() => setMobileSidebarOpen(false)}
              />
            </div>
            {/* Click outside to close drawer */}
            <div className="flex-1" onClick={() => setMobileSidebarOpen(false)} />
          </div>
        )}

        {/* =================================================================== */}
        {/* Workspace: Top bar & scroll feeds */}
        {/* =================================================================== */}
        <div className="flex flex-1 flex-col overflow-hidden">
          
          {/* Mobile Top Header (hidden on desktop) */}
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950 px-4 md:hidden">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(true)}
                className="rounded p-1.5 text-slate-400 hover:bg-slate-900 hover:text-white cursor-pointer"
              >
                <Menu className="h-5.5 w-5.5" />
              </button>
              <img src={logo} alt="WebGPT Logo" className="h-6 w-6 rounded object-cover" />
              <span className="font-semibold text-sm text-white">WebGPT Dashboard</span>
            </div>
            
            {/* Active source banner indicator for quick status checks */}
            <div className="text-[10px] bg-slate-900 px-2 py-1 rounded border border-slate-800 text-slate-400 font-semibold truncate max-w-[150px]">
              {activeSourceId
                ? sources.find((s) => s.job_id === activeSourceId)?.domain || "Scoped Source"
                : "Global Search"}
            </div>
          </header>

          {/* RAG Chat interface container */}
          <ChatWindow
            activeSourceId={activeSourceId}
            onScrapeSuccess={handleScrapeSuccess}
          />
        </div>

        {/* =================================================================== */}
        {/* Floating Toast Notification Deck */}
        {/* =================================================================== */}
        <div className="fixed right-4 top-4 z-50 space-y-2.5 max-w-sm w-full pointer-events-none">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`flex items-start gap-3 rounded-lg border p-4 shadow-xl pointer-events-auto animate-in fade-in slide-in-from-top-4 duration-300 ${
                toast.type === "success"
                  ? "bg-slate-900/95 border-emerald-500/20 text-emerald-400"
                  : toast.type === "error"
                  ? "bg-slate-900/95 border-rose-500/20 text-rose-400"
                  : "bg-slate-900/95 border-slate-800 text-slate-300"
              }`}
            >
              {toast.type === "success" && <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />}
              {toast.type === "error" && <AlertCircle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />}
              {toast.type === "info" && <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />}

              <div className="flex-1 text-xs font-semibold leading-relaxed text-slate-200">
                {toast.message}
              </div>

              <button
                type="button"
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                className="text-slate-500 hover:text-slate-300 rounded p-0.5 transition cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>

      </div>
    </ErrorBoundary>
  );
}
