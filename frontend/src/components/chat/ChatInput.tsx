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
      if (!disabled) {
        handleSubmit();
      }
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
    <div className="p-4 border-t border-border-subtle bg-surface-primary shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end rounded-3xl border border-border-subtle bg-surface-elevated p-2 focus-within:border-accent-blue/50 focus-within:ring-1 focus-within:ring-accent-blue/30 transition-all duration-200 ease-out">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about this website..."
            readOnly={disabled}
            rows={1}
            className={`w-full resize-none bg-transparent px-4 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none max-h-[160px] overflow-y-auto font-inter ${
              disabled ? "opacity-50 cursor-not-allowed select-none" : ""
            }`}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !input.trim()}
            className={`flex h-9 w-9 items-center justify-center rounded-full transition-all duration-200 ease-out hover:brightness-[1.05] shrink-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-accent-blue/40 mb-0.5 ${
              input.trim() && !disabled
                ? "bg-accent-blue text-surface-background hover:bg-accent-blue/90 active:bg-accent-blue/80 shadow-soft"
                : "bg-surface-secondary text-text-muted cursor-not-allowed"
            }`}
          >
            <SendHorizontal className="h-4.5 w-4.5" />
          </button>
        </div>

        <div className="mt-2 flex items-center justify-between px-2 text-[10px] text-text-muted font-inter">
          <div>WebGPT uses local vector databases to ground all answers.</div>
          <div className={input.length >= 900 ? "text-amber-500 font-semibold" : ""}>
            {input.length}/1000
          </div>
        </div>
      </div>
    </div>
  );

}
