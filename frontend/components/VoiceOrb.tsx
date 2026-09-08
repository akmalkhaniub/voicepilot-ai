"use client";

import React, { useEffect, useRef } from "react";

interface VoiceOrbProps {
  state: string; // IDLE, LISTENING, THINKING, SPEAKING, INTERRUPTED
  audioLevel: number; // 0.0 to 1.0
}

export const VoiceOrb: React.FC<VoiceOrbProps> = ({ state, audioLevel }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationId: number;
    let phase = 0;

    const render = () => {
      phase += 0.04;
      const width = canvas.width;
      const height = canvas.height;
      const centerX = width / 2;
      const centerY = height / 2;

      ctx.clearRect(0, 0, width, height);

      // Base radius calculation reacting to audio level
      const pulseMultiplier = state === "SPEAKING" ? 1.6 : state === "LISTENING" ? 1.2 : 0.4;
      const dynamicRadius = 70 + audioLevel * 50 * pulseMultiplier + Math.sin(phase * 1.5) * 4;

      // Color scheme according to state
      let color1 = "rgba(6, 182, 212, 0.8)"; // Cyan
      let color2 = "rgba(59, 130, 246, 0.5)"; // Blue
      let color3 = "rgba(16, 185, 129, 0.3)"; // Emerald

      if (state === "THINKING") {
        color1 = "rgba(168, 85, 247, 0.8)"; // Purple
        color2 = "rgba(99, 102, 241, 0.6)"; // Indigo
        color3 = "rgba(236, 72, 153, 0.3)";
      } else if (state === "INTERRUPTED") {
        color1 = "rgba(244, 63, 94, 0.9)"; // Rose / Red
        color2 = "rgba(239, 68, 68, 0.6)";
        color3 = "rgba(251, 146, 60, 0.4)";
      } else if (state === "SPEAKING") {
        color1 = "rgba(16, 185, 129, 0.9)"; // Emerald
        color2 = "rgba(6, 182, 212, 0.7)";  // Cyan
        color3 = "rgba(34, 197, 94, 0.4)";
      }

      // Outer ambient glow ring
      const gradientGlow = ctx.createRadialGradient(
        centerX, centerY, dynamicRadius * 0.4,
        centerX, centerY, dynamicRadius * 1.8
      );
      gradientGlow.addColorStop(0, color1);
      gradientGlow.addColorStop(0.5, color2);
      gradientGlow.addColorStop(1, "rgba(0,0,0,0)");

      ctx.beginPath();
      ctx.arc(centerX, centerY, dynamicRadius * 1.8, 0, Math.PI * 2);
      ctx.fillStyle = gradientGlow;
      ctx.fill();

      // Deformed wave orb
      ctx.beginPath();
      const points = 16;
      for (let i = 0; i < points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const waveOffset = Math.sin(angle * 3 + phase * 2) * (8 + audioLevel * 25);
        const r = dynamicRadius + waveOffset;
        const x = centerX + Math.cos(angle) * r;
        const y = centerY + Math.sin(angle) * r;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.closePath();

      const innerGrad = ctx.createRadialGradient(
        centerX - 15, centerY - 15, 10,
        centerX, centerY, dynamicRadius
      );
      innerGrad.addColorStop(0, "#ffffff");
      innerGrad.addColorStop(0.3, color1);
      innerGrad.addColorStop(0.8, color2);
      innerGrad.addColorStop(1, color3);

      ctx.fillStyle = innerGrad;
      ctx.fill();

      animationId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [state, audioLevel]);

  return (
    <div className="relative flex flex-col items-center justify-center p-4">
      <canvas
        ref={canvasRef}
        width={320}
        height={320}
        className="cursor-pointer transition-transform duration-300 hover:scale-105"
      />
      <div className="mt-2 flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-4 py-1.5 backdrop-blur-md">
        <span
          className={`h-2.5 w-2.5 rounded-full ${
            state === "SPEAKING"
              ? "bg-emerald-400 animate-pulse"
              : state === "LISTENING"
              ? "bg-cyan-400 animate-pulse"
              : state === "THINKING"
              ? "bg-purple-400 animate-spin"
              : state === "INTERRUPTED"
              ? "bg-rose-500"
              : "bg-slate-500"
          }`}
        />
        <span className="text-xs font-semibold tracking-wider uppercase text-slate-300">
          {state}
        </span>
      </div>
    </div>
  );
};
