import React, { useMemo } from "react";
import { Sparkle } from "lucide-react";
import AddSourceForm from "../sidebar/AddSourceForm";
import { SourceSummary } from "../../types/api";
import logo from "../../assets/logo.png";

interface AnimatedHeroProps {
  activeSourceId: string | null;
  activeSource: SourceSummary | null;
  hasMessages: boolean;
  onSendMessage: (text: string) => Promise<void>;
  onScrapeSuccess: (job: any) => void;
}

interface Particle {
  left: number;
  top: number;
  size: number;
  opacity: number;
  delay: number;
  duration: number;
}

export default function AnimatedHero({
  activeSourceId,
  activeSource,
  hasMessages,
  onSendMessage,
  onScrapeSuccess,
}: AnimatedHeroProps) {

  // Generate particle metadata exactly once on initial mount
  const particles = useMemo<Particle[]>(() => {
    return Array.from({ length: 22 }).map(() => ({
      left: Math.random() * 100,
      top: 60 + Math.random() * 35, // Distribute along lower 40% of screen
      size: 1.5 + Math.random() * 3,
      opacity: 0.1 + Math.random() * 0.35,
      delay: -Math.random() * 20, // Negative delay spreads phases immediately upon load
      duration: 15 + Math.random() * 10,
    }));
  }, []);

  // Visual State Determination
  // State 1: Welcome (no active source selected)
  // State 2: Ready to Explore (website selected, no messages yet)
  // State 3: Conversation (website selected and user has active messages)
  const isStateWelcome = activeSourceId === null;
  const isStateConversation = activeSourceId !== null && hasMessages;

  return (
    <div className="absolute inset-0 overflow-hidden select-none pointer-events-none [isolation:isolate] z-0 bg-surface-background">
      
      {/* =================================================================== */}
      {/* 1. Backdrop Layers (Always Mounted, opacity/speed adjusts via class) */}
      {/* =================================================================== */}
      <div 
        className={`absolute inset-0 transition-opacity duration-700 ease-out ${
          isStateConversation ? "opacity-20" : "opacity-100"
        }`}
      >
        {/* Breathing Radial Glow */}
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(91,140,255,0.08)_0%,rgba(139,92,246,0.05)_50%,transparent_100%)] animate-breath gpu-accelerated" />

        {/* Aurora Blurred Wave Layers */}
        <div className="absolute inset-0 opacity-40 mix-blend-screen">
          {/* Wave 1: Slow Accent Blue */}
          <div 
            className={`absolute top-[-20%] left-[-10%] w-[120%] h-[80%] rounded-[40%] bg-accent-blue/15 blur-[100px] animate-wave-slow gpu-accelerated ${
              isStateConversation ? "animate-wave-slow-chat" : ""
            }`}
          />
          {/* Wave 2: Medium Accent Purple */}
          <div 
            className={`absolute top-[-30%] right-[-20%] w-[110%] h-[90%] rounded-[30%] bg-accent-purple/15 blur-[120px] animate-wave-medium gpu-accelerated ${
              isStateConversation ? "animate-wave-medium-chat" : ""
            }`}
          />
          {/* Wave 3: Fast Accent Pink */}
          <div 
            className={`absolute bottom-[-10%] left-[20%] w-[100%] h-[70%] rounded-[50%] bg-accent-pink/5 blur-[90px] animate-wave-fast gpu-accelerated ${
              isStateConversation ? "animate-wave-fast-chat" : ""
            }`}
          />
        </div>

        {/* Floating Particles (Hidden on Mobile for performance) */}
        <div className="absolute inset-0 z-20 hidden md:block">
          {particles.map((p, i) => (
            <div
              key={i}
              className="absolute rounded-full bg-accent-blue/30 blur-[1px] animate-float gpu-accelerated"
              style={{
                left: `${p.left}%`,
                top: `${p.top}%`,
                width: `${p.size}px`,
                height: `${p.size}px`,
                opacity: p.opacity,
                animationDuration: `${p.duration}s`,
                animationDelay: `${p.delay}s`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Backdrop Blend Gradient (Fades bottom edge cleanly into solid background) */}
      <div className="absolute inset-x-0 bottom-0 h-64 bg-gradient-to-t from-surface-background to-transparent z-20 pointer-events-none" />

      {/* =================================================================== */}
      {/* 2. Welcome Landing Panel Content (Slides up & Fades out on Chat Start) */}
      {/* =================================================================== */}
      <div 
        className={`absolute inset-0 flex flex-col items-center justify-center p-6 text-center z-30 transition-all duration-700 ease-out ${
          isStateConversation 
            ? "opacity-0 -translate-y-8 pointer-events-none" 
            : "opacity-100 translate-y-0"
        }`}
      >
        <div className="max-w-xl w-full flex flex-col items-center gap-6">
          
          {/* Staggered Element 1: Sparkle & Logo */}
          <div 
            className="flex flex-col items-center animate-scale-in"
            style={{ animationDelay: "100ms" }}
          >
            {/* Sparkle Icon */}
            <div className="flex justify-center mb-3 animate-sparkle gpu-accelerated">
              <Sparkle className="h-6 w-6 text-accent-blue fill-accent-blue/20" />
            </div>
            {/* Logo */}
            <img
              src={logo}
              alt="WebGPT Logo"
              className="h-16 w-16 object-contain"
            />
          </div>

          {/* Staggered Element 2: Heading */}
          <div
            className="animate-fade-in-up"
            style={{ animationDelay: "250ms" }}
          >
            {isStateWelcome ? (
              <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl font-outfit">
                Welcome to WebGPT
              </h1>
            ) : (
              <h1 className="text-3xl font-bold tracking-tight text-text-primary sm:text-4xl font-outfit">
                Ready to explore?
              </h1>
            )}
          </div>

          {/* Staggered Element 3: Subtitle */}
          <div
            className="animate-fade-in-up"
            style={{ animationDelay: "400ms" }}
          >
            {isStateWelcome ? (
              <p className="text-xs text-text-secondary leading-relaxed max-w-sm mx-auto font-inter">
                Scrape any website and chat with its content using Retrieval-Augmented Generation (RAG).
              </p>
            ) : (
              <p className="text-xs text-text-secondary leading-relaxed max-w-md mx-auto font-inter">
                Ask anything about <span className="font-semibold text-accent-blue">{activeSource ? activeSource.domain : "the website"}</span>. WebGPT will query the local index and render grounded responses.
              </p>
            )}
          </div>

          {/* Staggered Element 4: Floating Input Card / Suggestion Chips */}
          <div
            className="w-full animate-scale-in pointer-events-auto"
            style={{ animationDelay: "550ms" }}
          >
            {isStateWelcome ? (
              /* Center Add Data Source Card (Welcome State) */
              <div className="rounded-3xl border border-border-subtle bg-surface-secondary p-6 shadow-soft hover:shadow-hover transition-all duration-[--transition-normal]">
                <AddSourceForm onSuccess={onScrapeSuccess} />
              </div>
            ) : null}
          </div>

        </div>
      </div>
    </div>
  );
}
