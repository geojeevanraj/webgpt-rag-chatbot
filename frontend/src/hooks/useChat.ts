import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { WebChatMessage } from "../types/api";

export function useChat(jobId: string | null) {
  const [messages, setMessages] = useState<WebChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    // Determine context scope: null maps to global search scope "global"
    const historyScope = jobId || "global";

    setLoading(true);
    setError(null);
    try {
      const data = await api.getChatHistory(historyScope);
      setMessages(data.messages);
    } catch (err: any) {
      setError(err.message || "Failed to load conversation history.");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  const sendMessage = useCallback(async (question: string) => {
    setError(null);

    // 1. Construct optimistic User message object
    const userMsgId = `user-${Date.now()}`;
    const userMessage: WebChatMessage = {
      id: userMsgId,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };

    // 2. Construct optimistic Assistant placeholder object
    const assistantMsgId = `assistant-${Date.now()}`;
    const assistantPlaceholder: WebChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "", // Empty string signals bouncing loader in UI bubble
      created_at: new Date().toISOString(),
    };

    // Optimistically update list to display immediately
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);

    try {
      const res = await api.askQuestion({
        job_id: jobId,
        question: question,
      });

      // 3. Replace placeholder with final answer and backend citation lists
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantPlaceholder.id
            ? {
                ...msg,
                id: `assistant-res-${Date.now()}`,
                content: res.answer,
                citations: res.citations,
              }
            : msg
        )
      );
    } catch (err: any) {
      setError(err.message || "Failed to query the RAG chatbot.");
      // Replace placeholder message with error details on generation failure
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantPlaceholder.id
            ? {
                ...msg,
                content: `An error occurred while generating this answer: ${
                  err.message || "Connection timed out."
                }`,
              }
            : msg
        )
      );
    }
  }, [jobId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return {
    messages,
    loading,
    error,
    sendMessage,
    clearHistory: () => setMessages([]),
  };
}
