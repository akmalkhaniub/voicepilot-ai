"use client";

import React from "react";
import { useVoiceAgent } from "../hooks/useVoiceAgent";
import { VoiceOrb } from "../components/VoiceOrb";
import { LatencyWaterfall } from "../components/LatencyWaterfall";
import { LiveTranscript } from "../components/LiveTranscript";
import { ControlPanel } from "../components/ControlPanel";
import { Bot, Radio, Cpu, Sparkles } from "lucide-react";

export default function Home() {
  const {
    isConnected,
    agentState,
    messages,
    currentAssistantText,
    audioLevel,
    isMuted,
    metrics,
    startSession,
    endSession,
    toggleMute,
  } = useVoiceAgent();

  return (
    <main className="flex min-h-screen flex-col bg-[#090d16] text-slate-100">
      {/* Top Header */}
      <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-[#090d16]/80 backdrop-blur-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/25">
              <Bot className="h-5 w-5 text-slate-950 font-bold" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight text-lg text-slate-100">
                  VoicePilot <span className="text-cyan-400">AI</span>
                </span>
                <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-semibold text-cyan-400 uppercase tracking-wide">
                  Enterprise Platform
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Full-Duplex Real-Time Conversational Voice Agent
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-400">
              <Cpu className="h-3.5 w-3.5 text-cyan-400" />
              <span>Hybrid Edge-Cloud Architecture</span>
            </div>

            <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1.5 text-xs">
              <Radio
                className={`h-3 w-3 ${
                  isConnected ? "text-emerald-400 animate-pulse" : "text-slate-500"
                }`}
              />
              <span className="font-medium text-slate-300">
                {isConnected ? "Engine Connected" : "Ready"}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 lg:grid-cols-12 gap-6 p-6">
        {/* Left Column: Voice Orb & Interactive Controls */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-800/80 bg-slate-900/40 p-8 backdrop-blur-xl shadow-2xl relative overflow-hidden">
            <div className="absolute -top-24 -left-24 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none" />
            <div className="absolute -bottom-24 -right-24 h-56 w-56 rounded-full bg-blue-500/10 blur-3xl pointer-events-none" />
            
            <VoiceOrb state={agentState} audioLevel={audioLevel} />

            <div className="mt-4 text-center">
              <h2 className="text-base font-semibold text-slate-200">
                {agentState === "IDLE"
                  ? "Ready to Talk"
                  : agentState === "LISTENING"
                  ? "Listening to your voice..."
                  : agentState === "THINKING"
                  ? "Processing intent & tools..."
                  : agentState === "SPEAKING"
                  ? "Streaming synthesized response"
                  : "User Barge-In Interruption Detected"}
              </h2>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">
                Speak normally. You can interrupt the agent at any moment while it is speaking.
              </p>
            </div>
          </div>

          {/* Session Control Panel */}
          <ControlPanel
            isConnected={isConnected}
            isMuted={isMuted}
            agentState={agentState}
            onStartSession={startSession}
            onEndSession={endSession}
            onToggleMute={toggleMute}
          />
        </div>

        {/* Right Column: Live Transcript & Latency Waterfall */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Latency Waterfall Telemetry */}
          <LatencyWaterfall metrics={metrics} />

          {/* Live Transcript Stream */}
          <div className="flex-1 min-h-[360px]">
            <LiveTranscript
              messages={messages}
              currentAssistantText={currentAssistantText}
            />
          </div>
        </div>
      </div>
    </main>
  );
}
