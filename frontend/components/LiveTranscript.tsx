"use client";

import React, { useEffect, useRef } from "react";
import { ChatMessage } from "../hooks/useVoiceAgent";
import { User, Bot, Sparkles, Terminal } from "lucide-react";

interface LiveTranscriptProps {
  messages: ChatMessage[];
  currentAssistantText: string;
}

export const LiveTranscript: React.FC<LiveTranscriptProps> = ({
  messages,
  currentAssistantText,
}) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, currentAssistantText]);

  return (
    <div className="flex h-full flex-col rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <h3 className="font-semibold text-sm tracking-wide text-slate-200">
            Live Conversational Stream
          </h3>
        </div>
        <span className="text-xs text-slate-500 font-mono">16kHz Full-Duplex</span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto pr-2 scrollbar-thin scrollbar-thumb-slate-800"
      >
        {messages.length === 0 && !currentAssistantText && (
          <div className="flex h-48 flex-col items-center justify-center text-center text-slate-500">
            <Sparkles className="h-8 w-8 mb-2 text-slate-600 animate-pulse" />
            <p className="text-xs font-medium">Session initialized. Click "Start Call" to begin speaking.</p>
            <p className="text-[11px] text-slate-600 mt-1">Silero VAD will automatically detect when you finish speaking.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-slate-950 shadow-md">
                <Bot className="h-4 w-4" />
              </div>
            )}

            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-xs leading-relaxed shadow-lg ${
                msg.role === "user"
                  ? "bg-cyan-600 text-white rounded-br-none"
                  : "bg-slate-800/90 text-slate-200 border border-slate-700/60 rounded-bl-none"
              }`}
            >
              <div className="flex items-center justify-between gap-4 mb-1 text-[10px] opacity-75">
                <span className="font-semibold">{msg.role === "user" ? "You" : "VoicePilot"}</span>
                <span>{msg.timestamp}</span>
              </div>
              <p>{msg.content}</p>
            </div>

            {msg.role === "user" && (
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-300 border border-slate-700">
                <User className="h-4 w-4" />
              </div>
            )}
          </div>
        ))}

        {/* Real-time incoming streaming words from assistant */}
        {currentAssistantText && (
          <div className="flex gap-3 justify-start">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 text-slate-950 shadow-md animate-pulse">
              <Bot className="h-4 w-4" />
            </div>
            <div className="max-w-[80%] rounded-2xl rounded-bl-none bg-slate-800/90 border border-cyan-500/40 px-4 py-2.5 text-xs leading-relaxed text-slate-200 shadow-lg">
              <div className="flex items-center gap-2 mb-1 text-[10px] text-cyan-400">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-ping" />
                <span>Streaming clause...</span>
              </div>
              <p>{currentAssistantText}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
