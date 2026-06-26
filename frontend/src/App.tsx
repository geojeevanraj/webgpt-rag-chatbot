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
  const activeSource = sources.find((s) => s.job_id === activeSourceId) || null;
  useScrapePolling(sources, refreshSources);

  // Helper to add toast messages that fade out automatically
  const addToast = (type: "success" | "error" | "info", message: string) => {
    const id = `toast-${Date.now()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  React.useEffect(() => {
    const handleCustomToast = (e: Event) => {
      const customEvent = e as CustomEvent;
      if (customEvent.detail) {
        addToast(customEvent.detail.type, customEvent.detail.message);
      }
    };
    window.addEventListener("app-toast" as any, handleCustomToast);
    return () => window.removeEventListener("app-toast" as any, handleCustomToast);
  }, []);

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
      <div className="flex h-screen h-dvh w-screen overflow-hidden bg-surface-background text-text-primary antialiased font-inter">
        
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
          <div className="fixed inset-0 z-50 flex md:hidden bg-surface-background/80 backdrop-blur-sm">
            <div className="h-full w-[290px] shadow-soft animate-in slide-in-from-left duration-200">
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
        <div className="flex flex-1 flex-col min-h-0 overflow-hidden">
          
          {/* Mobile Top Header (hidden on desktop) */}
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-border-subtle bg-surface-background px-4 md:hidden">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(true)}
                className="rounded-sm p-2 text-text-secondary hover:bg-surface-elevated hover:text-text-primary cursor-pointer transition-colors duration-[--transition-fast]"
              >
                <Menu className="h-5 w-5" />
              </button>
              <img src={logo} alt="WebGPT Logo" className="h-8 w-8 object-contain" />
              <span className="font-semibold text-sm text-text-primary font-outfit">WebGPT Dashboard</span>
            </div>
            
            {/* Active source banner indicator for quick status checks */}
            <div className="text-[10px] bg-surface-secondary px-2.5 py-1.5 rounded-sm border border-border-subtle text-text-secondary font-medium truncate max-w-[150px]">
              {activeSourceId
                ? sources.find((s) => s.job_id === activeSourceId)?.domain || "Scoped Source"
                : "Global Search"}
            </div>
          </header>

          {/* RAG Chat interface container */}
          <ChatWindow
            activeSourceId={activeSourceId}
            activeSource={activeSource}
            onScrapeSuccess={handleScrapeSuccess}
          />
        </div>

        {/* =================================================================== */}
        {/* Floating Toast Notification Deck */}
        {/* =================================================================== */}
        <div className="fixed right-4 top-4 z-50 space-y-4 max-w-sm w-full pointer-events-none">
          {toasts.map((toast) => (
            <div
              key={toast.id}
              className={`flex items-start gap-4 rounded-lg border p-4 shadow-soft pointer-events-auto transition-all duration-[--transition-fast] ${
                toast.type === "success"
                  ? "bg-surface-elevated border-emerald-500/20 text-emerald-400"
                  : toast.type === "error"
                  ? "bg-surface-elevated border-rose-500/20 text-rose-400"
                  : "bg-surface-elevated border-border-subtle text-text-primary"
              }`}
            >
              {toast.type === "success" && <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />}
              {toast.type === "error" && <AlertCircle className="h-5 w-5 text-rose-500 shrink-0 mt-0.5" />}
              {toast.type === "info" && <Info className="h-5 w-5 text-accent-blue shrink-0 mt-0.5" />}

              <div className="flex-1 text-xs font-medium leading-relaxed text-text-primary font-inter">
                {toast.message}
              </div>

              <button
                type="button"
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                className="text-text-muted hover:text-text-primary rounded-sm p-1 transition-colors duration-[--transition-fast] cursor-pointer"
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
