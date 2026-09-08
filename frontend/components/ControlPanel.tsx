"use client";

import React from "react";
import { Phone, PhoneOff, Mic, MicOff, RefreshCw, Sliders, ShieldCheck } from "lucide-react";

interface ControlPanelProps {
  isConnected: boolean;
  isMuted: boolean;
  agentState: string;
  onStartSession: () => void;
  onEndSession: () => void;
  onToggleMute: () => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  isConnected,
  isMuted,
  agentState,
  onStartSession,
  onEndSession,
  onToggleMute,
}) => {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Sliders className="h-4 w-4 text-cyan-400" />
          <h3 className="font-semibold text-sm tracking-wide text-slate-200">
            Session Controls
          </h3>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Enterprise Secure (TLS)</span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {/* Main Connect / Disconnect Button */}
        {!isConnected ? (
          <button
            onClick={onStartSession}
            className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 px-4 py-3 text-xs font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition-all hover:brightness-110 active:scale-95"
          >
            <Phone className="h-4 w-4" />
            Start Voice Agent
          </button>
        ) : (
          <button
            onClick={onEndSession}
            className="flex items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-3 text-xs font-semibold text-white shadow-lg shadow-rose-600/25 transition-all hover:bg-rose-500 active:scale-95"
          >
            <PhoneOff className="h-4 w-4" />
            End Call
          </button>
        )}

        {/* Mute Toggle */}
        <button
          onClick={onToggleMute}
          disabled={!isConnected}
          className={`flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-xs font-semibold transition-all ${
            isMuted
              ? "border-amber-500/50 bg-amber-500/10 text-amber-400"
              : "border-slate-800 bg-slate-800/60 text-slate-300 hover:bg-slate-800"
          } ${!isConnected ? "opacity-50 cursor-not-allowed" : "active:scale-95"}`}
        >
          {isMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
          {isMuted ? "Unmute Mic" : "Mute Mic"}
        </button>

        {/* Persona Selector */}
        <div className="col-span-2 sm:col-span-1">
          <select className="w-full rounded-xl border border-slate-800 bg-slate-800/60 px-3 py-3 text-xs font-medium text-slate-300 focus:outline-none focus:border-cyan-500">
            <option>Customer Support Agent</option>
            <option>Enterprise Sales Rep</option>
            <option>Technical Triage Engineer</option>
          </select>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-[11px] text-slate-500">
        <span>Audio Transport: Binary WebSockets / 16kHz PCM</span>
        <span className="font-mono">VAD: Silero ONNX (1.07ms)</span>
      </div>
    </div>
  );
};
