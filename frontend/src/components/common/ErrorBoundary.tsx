import React, { Component, ErrorInfo, ReactNode } from "react";
import { ShieldAlert } from "lucide-react";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught React rendering error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 p-6 text-center text-slate-100 antialiased">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-500 border border-rose-500/20 shadow-xl shadow-rose-500/5 mb-4">
            <ShieldAlert className="h-8 w-8" />
          </div>
          <h1 className="text-lg font-bold text-white tracking-wide">Something went wrong</h1>
          <p className="text-xs text-slate-400 mt-2 max-w-sm leading-relaxed">
            The frontend application encountered an unexpected runtime render crash. 
            Details: {this.state.error?.message || "Unknown error"}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 text-xs font-semibold shadow-sm transition"
          >
            Reload Application
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
