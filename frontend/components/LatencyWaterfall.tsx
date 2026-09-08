"use client";

import React from "react";
import { LatencyMetrics } from "../hooks/useVoiceAgent";
import { Activity, Gauge, Zap, Waves, Cpu } from "lucide-react";

interface LatencyWaterfallProps {
  metrics: LatencyMetrics;
}

export const LatencyWaterfall: React.FC<LatencyWaterfallProps> = ({ metrics }) => {
  const steps = [
    {
      name: "VAD Inference (Silero ONNX)",
      value: metrics.vad_ms,
      unit: "ms",
      target: "< 2ms",
      icon: Cpu,
      color: "bg-cyan-500",
      textColor: "text-cyan-400",
    },
    {
      name: "STT Streaming (Deepgram/Whisper)",
      value: metrics.stt_ms,
      unit: "ms",
      target: "< 150ms",
      icon: Waves,
      color: "bg-blue-500",
      textColor: "text-blue-400",
    },
    {
      name: "LLM Time-to-First-Token (Groq)",
      value: metrics.llm_ttft_ms,
      unit: "ms",
      target: "< 100ms",
      icon: Zap,
      color: "bg-purple-500",
      textColor: "text-purple-400",
    },
    {
      name: "TTS First-Audio-Packet (Cartesia/Sonic)",
      value: metrics.tts_ttfb_ms,
      unit: "ms",
      target: "< 100ms",
      icon: Gauge,
      color: "bg-emerald-500",
      textColor: "text-emerald-400",
    },
  ];

  const isPassingSLA = metrics.total_e2e_ms <= 300;

  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-xl shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-cyan-400" />
          <h3 className="font-semibold text-sm tracking-wide text-slate-200">
            Real-Time Latency Telemetry Waterfall
          </h3>
        </div>
        <div
          className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            isPassingSLA
              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800/50"
              : "bg-amber-950/60 text-amber-400 border border-amber-800/50"
          }`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current animate-ping" />
          {isPassingSLA ? "Sub-300ms SLA Pass" : "Near-Threshold"}
        </div>
      </div>

      {/* Waterfall Bars */}
      <div className="space-y-3.5">
        {steps.map((step, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 text-slate-400 font-medium">
                <step.icon className={`h-3.5 w-3.5 ${step.textColor}`} />
                {step.name}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-slate-500 text-[10px]">Target: {step.target}</span>
                <span className={`font-mono font-semibold ${step.textColor}`}>
                  {step.value} {step.unit}
                </span>
              </div>
            </div>
            {/* Progress Bar Representation */}
            <div className="h-1.5 w-full rounded-full bg-slate-800/80 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${step.color}`}
                style={{ width: `${Math.min(100, Math.max(8, (step.value / 250) * 100))}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Total Roundtrip E2E Banner */}
      <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/60 p-3.5 flex items-center justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-slate-400">
            End-to-End Voice-to-Voice Latency
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            Mic speech stop → AudioWorklet speaker playback
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-emerald-400">
            {metrics.total_e2e_ms} ms
          </div>
          <div className="text-[10px] text-emerald-400 font-medium">Real-Time Human Parity</div>
        </div>
      </div>
    </div>
  );
};
