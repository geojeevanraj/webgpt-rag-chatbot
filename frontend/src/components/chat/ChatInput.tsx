import React, { useState, KeyboardEvent, ChangeEvent, useRef, useEffect } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => Promise<void>;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
  };

  useEffect(() => {
    adjustHeight();
  }, [input]);

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send message on Enter without shift key pressed
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    // Enforce strict 1000 character limit constraint
    if (val.length <= 1000) {
      setInput(val);
    }
  };

  return (
    <div className="p-4 border-t border-slate-800 bg-slate-950/20 shrink-0">
      <div className="max-w-3xl mx-auto">
        <div className="relative flex items-end rounded-lg border border-slate-800 bg-slate-900/60 p-1.5 focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/30 transition">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about the scraped pages..."
            disabled={disabled}
            rows={1}
            className="w-full resize-none bg-transparent px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-[160px] overflow-y-auto"
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !input.trim()}
            className={`flex h-9 w-9 items-center justify-center rounded-md transition shrink-0 cursor-pointer mb-0.5 ${
              input.trim() && !disabled
                ? "bg-indigo-600 text-white hover:bg-indigo-500"
                : "bg-slate-900/50 text-slate-600 cursor-not-allowed"
            }`}
          >
            <SendHorizontal className="h-4.5 w-4.5" />
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-slate-500">
          <div>WebGPT uses local vector databases to ground all answers.</div>
          <div className={input.length >= 900 ? "text-amber-500" : ""}>
            {input.length}/1000
          </div>
        </div>
      </div>
    </div>
  );
}
