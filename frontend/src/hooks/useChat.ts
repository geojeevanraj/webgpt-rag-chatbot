import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../services/api";
import { WebChatMessage, StreamState } from "../types/api";

export function useChat(jobId: string | null) {
  const [messages, setMessages] = useState<WebChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const generating = streamState !== "idle" && streamState !== "completed" && streamState !== "aborted" && streamState !== "interrupted" && streamState !== "error";

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

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const sendMessage = useCallback(async (question: string) => {
    if (generating) return;
    setError(null);
    setStreamState("searching");

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
      isStreaming: true,
      streamState: "searching",
      statusText: "Searching website...",
    };

    // Optimistically update list to display immediately
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);

    // Token delta buffer
    let accumulatedText = "";
    let lastFlushTime = Date.now();
    let flushTimeout: any = null;

    const flushBuffer = (force = false) => {
      if (flushTimeout) {
        clearTimeout(flushTimeout);
        flushTimeout = null;
      }

      const now = Date.now();
      if (force || now - lastFlushTime >= 40) {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: accumulatedText,
                }
              : msg
          )
        );
        lastFlushTime = now;
      } else {
        flushTimeout = setTimeout(() => flushBuffer(true), 40 - (now - lastFlushTime));
      }
    };

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await api.streamChatResponse(
        {
          job_id: jobId,
          question: question,
        },
        {
          onStatus: (text) => {
            let nextState: StreamState = "searching";
            if (text === "Reading indexed pages...") {
              nextState = "retrieving";
            } else if (text === "Generating answer...") {
              nextState = "generating";
            }
            setStreamState(nextState);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      statusText: text,
                      streamState: nextState,
                    }
                  : msg
              )
            );
          },
          onStart: (model) => {
            setStreamState("generating");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      statusText: undefined,
                      streamState: "generating",
                    }
                  : msg
              )
            );
          },
          onDelta: (text) => {
            setStreamState("generating");
            accumulatedText += text;
            flushBuffer();
          },
          onCitations: (citations) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      citations,
                    }
                  : msg
              )
            );
          },
          onDone: (data) => {
            flushBuffer(true);
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      isStreaming: false,
                      streamState: "completed",
                    }
                  : msg
              )
            );
            setTimeout(() => {
              setStreamState("completed");
            }, 200);
          },
          onAborted: () => {
            flushBuffer(true);
            setStreamState("aborted");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      isStreaming: false,
                      streamState: "aborted",
                    }
                  : msg
              )
            );
          },
          onInterrupted: (message, citations) => {
            flushBuffer(true);
            setStreamState("interrupted");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      isStreaming: false,
                      streamState: "interrupted",
                      citations: citations,
                    }
                  : msg
              )
            );
          },
          onError: (message) => {
            flushBuffer(true);
            setStreamState("error");
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? {
                      ...msg,
                      content: message,
                      isError: true,
                      isStreaming: false,
                      streamState: "error",
                    }
                  : msg
              )
            );
          },
        },
        controller.signal
      );
    } catch (err: any) {
      if (flushTimeout) {
        clearTimeout(flushTimeout);
      }

      if (err.name === "AbortError") {
        setStreamState("aborted");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  isStreaming: false,
                  streamState: "aborted",
                }
              : msg
          )
        );
      } else {
        setStreamState("error");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: err.message || "Failed to generate response.",
                  isError: true,
                  isStreaming: false,
                  streamState: "error",
                }
              : msg
          )
        );
      }
    } finally {
      abortControllerRef.current = null;
    }
  }, [jobId, generating]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return {
    messages,
    loading,
    generating,
    streamState,
    error,
    sendMessage,
    stopGeneration,
    clearHistory: () => setMessages([]),
  };
}
