"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export interface LatencyMetrics {
  vad_ms: number;
  stt_ms: number;
  llm_ttft_ms: number;
  tts_ttfb_ms: number;
  total_e2e_ms: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  latency?: number;
}

export function useVoiceAgent(serverUrl: string = "ws://localhost:8000/ws/voice-agent") {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [agentState, setAgentState] = useState<string>("IDLE"); // IDLE, LISTENING, THINKING, SPEAKING, INTERRUPTED
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentAssistantText, setCurrentAssistantText] = useState<string>("");
  const [audioLevel, setAudioLevel] = useState<number>(0);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<LatencyMetrics>({
    vad_ms: 1.1,
    stt_ms: 140,
    llm_ttft_ms: 85,
    tts_ttfb_ms: 95,
    total_e2e_ms: 285,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const isMutedRef = useRef<boolean>(false);

  isMutedRef.current = isMuted;

  const startSession = useCallback(async () => {
    try {
      // 1. Initialize AudioContext at 16,000 Hz
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      // 2. Load custom AudioWorklet processor
      await audioCtx.audioWorklet.addModule("/audio-processor.js");

      // 3. Request user microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 4. Create source and worklet node
      const micSource = audioCtx.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioCtx, "voicepilot-audio-processor");
      workletNodeRef.current = workletNode;

      // Connect mic -> worklet -> speaker output
      micSource.connect(workletNode);
      workletNode.connect(audioCtx.destination);

      // 5. Connect WebSocket
      const ws = new WebSocket(serverUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setAgentState("LISTENING");
      };

      ws.onclose = () => {
        setIsConnected(false);
        setAgentState("IDLE");
      };

      ws.onerror = (err) => {
        console.error("VoiceAgent WebSocket error:", err);
      };

      // 6. Handle messages from server (audio chunks and JSON telemetry)
      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          // Binary frame: Incoming 16kHz PCM audio chunk from TTS
          const pcm16 = new Int16Array(event.data);
          const float32 = new Float32Array(pcm16.length);
          let sumSquares = 0;

          for (let i = 0; i < pcm16.length; i++) {
            const s = pcm16[i] / 32768.0;
            float32[i] = s;
            sumSquares += s * s;
          }

          // Calculate output volume for reactive orb
          const rms = Math.sqrt(sumSquares / pcm16.length);
          setAudioLevel(Math.min(1.0, rms * 4));

          // Forward to AudioWorklet for jitter-free playback
          workletNode.port.postMessage({
            type: "AUDIO_PLAYBACK",
            data: float32.buffer,
          }, [float32.buffer]);

        } else if (typeof event.data === "string") {
          // Text frame: Control & Telemetry JSON
          try {
            const payload = JSON.parse(event.data);
            if (payload.type === "STATE_CHANGE") {
              setAgentState(payload.state);
            } else if (payload.type === "INTERRUPT") {
              // Instant Barge-In: Halt local audio immediately
              setAgentState("INTERRUPTED");
              workletNode.port.postMessage({ type: "CLEAR_PLAYBACK" });
              setAudioLevel(0);
            } else if (payload.type === "LATENCY_TELEMETRY") {
              setMetrics(payload.metrics);
            } else if (payload.type === "AGENT_PARTIAL_TEXT") {
              setCurrentAssistantText((prev) => (prev ? `${prev} ${payload.text}` : payload.text));
            } else if (payload.type === "TRANSCRIPT") {
              if (payload.role === "user") {
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Math.random().toString(36).substring(7),
                    role: "user",
                    content: payload.text,
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
                    latency: payload.stt_ms,
                  },
                ]);
                setCurrentAssistantText("");
              } else if (payload.role === "assistant") {
                setMessages((prev) => [
                  ...prev,
                  {
                    id: Math.random().toString(36).substring(7),
                    role: "assistant",
                    content: payload.text,
                    timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
                  },
                ]);
                setCurrentAssistantText("");
              }
            }
          } catch (e) {
            console.error("Error parsing WS message JSON:", e);
          }
        }
      };

      // 7. Handle audio captured from microphone by AudioWorklet
      workletNode.port.onmessage = (event) => {
        if (event.data.type === "MIC_PCM" && !isMutedRef.current) {
          const buffer = event.data.buffer;
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(buffer);
          }

          // Compute mic input volume
          const pcm16 = new Int16Array(buffer);
          let sum = 0;
          for (let i = 0; i < pcm16.length; i++) {
            sum += Math.abs(pcm16[i]);
          }
          const avg = sum / pcm16.length;
          // When user is speaking, update audio level
          if (agentState === "LISTENING") {
            setAudioLevel(Math.min(1.0, avg / 4000));
          }
        }
      };

    } catch (err) {
      console.error("Failed to start voice agent session:", err);
      setIsConnected(false);
      setAgentState("IDLE");
    }
  }, [serverUrl, agentState]);

  const endSession = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsConnected(false);
    setAgentState("IDLE");
    setAudioLevel(0);
    setCurrentAssistantText("");
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => !prev);
  }, []);

  useEffect(() => {
    return () => {
      endSession();
    };
  }, [endSession]);

  return {
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
  };
}
