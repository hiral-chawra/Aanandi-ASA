import { useCallback, useEffect, useRef, useState } from 'react';
import type { CallStatus } from '../types';

interface UseAudioWebSocketOptions {
  apiBase: string;
  sessionId: string;
}

interface UseAudioWebSocketReturn {
  status: CallStatus;
  isMuted: boolean;
  toggleMute: () => void;
  disconnect: () => void;
  analyserNode: AnalyserNode | null;       // AI speaker output
  inputAnalyserNode: AnalyserNode | null;  // mic input
}

// ── AudioWorklet processor source (inlined as string) ─────────────────
// Runs in its own thread, extracts PCM16 from Float32 mic samples
const WORKLET_CODE = `
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._chunkSize = 1600; // 100ms @ 16kHz
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const samples = input[0]; // Float32Array, mono

    for (let i = 0; i < samples.length; i++) {
      // Clamp and convert Float32 [-1,1] → Int16 [-32768,32767]
      const s = Math.max(-1, Math.min(1, samples[i]));
      this._buffer.push(s < 0 ? s * 0x8000 : s * 0x7FFF);
    }

    while (this._buffer.length >= this._chunkSize) {
      const chunk = this._buffer.splice(0, this._chunkSize);
      const pcm = new Int16Array(chunk);
      this.port.postMessage(pcm.buffer, [pcm.buffer]);
    }

    return true; // keep processor alive
  }
}

registerProcessor('pcm16-processor', PCM16Processor);
`;

/**
 * WebAudio PCM audio streaming hook.
 *
 * Audio pipeline (mic → server):
 *   getUserMedia (16kHz mono) → AudioContext → AudioWorkletNode (PCM16Processor)
 *     → postMessage → WebSocket.send(binary ArrayBuffer)
 *
 * Audio pipeline (server → speaker):
 *   WebSocket.onmessage(binary) → decode PCM16 → AudioBuffer → AudioBufferSourceNode → output
 *
 * Connects to: WSS /api/v1/voice/ws/{session_id}
 *
 * Status protocol (JSON from server):
 *   { type: "status", status: "listening"|"thinking"|"speaking" }
 */
export function useAudioWebSocket({
  apiBase,
  sessionId,
}: UseAudioWebSocketOptions): UseAudioWebSocketReturn {
  const [status, setStatus] = useState<CallStatus>('connecting');
  const [isMuted, setIsMuted] = useState(false);
  const [analyserNode, setAnalyserNode] = useState<AnalyserNode | null>(null);
  const [inputAnalyserNode, setInputAnalyserNode] = useState<AnalyserNode | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | ScriptProcessorNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const gainNodeRef = useRef<GainNode | null>(null); // mic gain for mute
  const outputGainRef = useRef<GainNode | null>(null);
  const playbackQueueRef = useRef<AudioBuffer[]>([]);
  const nextStartTimeRef = useRef<number>(0);
  const isPlayingRef = useRef(false);
  const isMutedRef = useRef(false);

  // ── Main setup ────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    const setup = async () => {
      try {
        // 1. Request mic
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: 16000,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;

        // 2. Create AudioContext at 16kHz & ensure it is active
        const ctx = new AudioContext({ sampleRate: 16000 });
        if (ctx.state === 'suspended') {
          await ctx.resume();
        }
        audioCtxRef.current = ctx;

        // 3. Mic source → gain (for mute) → analyser → worklet
        const source = ctx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const gainNode = ctx.createGain();
        gainNode.gain.value = 1;
        gainNodeRef.current = gainNode;

        const inputAnalyser = ctx.createAnalyser();
        inputAnalyser.fftSize = 256;
        inputAnalyser.smoothingTimeConstant = 0.7;
        setInputAnalyserNode(inputAnalyser);

        source.connect(gainNode);
        gainNode.connect(inputAnalyser);

        // 4. Output analyser (for speaker)
        const outputAnalyser = ctx.createAnalyser();
        outputAnalyser.fftSize = 256;
        outputAnalyser.smoothingTimeConstant = 0.75;
        setAnalyserNode(outputAnalyser);

        const outputGain = ctx.createGain();
        outputGain.gain.value = 1;
        outputGainRef.current = outputGain;
        outputGain.connect(outputAnalyser);
        outputAnalyser.connect(ctx.destination);

        // 5. AudioWorklet (or ScriptProcessorNode fallback) for PCM extraction
        let processorNode: AudioWorkletNode | ScriptProcessorNode;
        let onPCMChunk: (buffer: ArrayBuffer) => void = () => {};

        try {
          // Try AudioWorklet first
          const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
          const workletUrl = URL.createObjectURL(blob);
          await ctx.audioWorklet.addModule(workletUrl);
          URL.revokeObjectURL(workletUrl);

          const worklet = new AudioWorkletNode(ctx, 'pcm16-processor');
          worklet.port.onmessage = (ev: MessageEvent<ArrayBuffer>) => {
            onPCMChunk(ev.data);
          };
          processorNode = worklet;
        } catch {
          // Fallback: ScriptProcessorNode (deprecated but widely supported)
          const bufferSize = 2048;
          const scriptNode = ctx.createScriptProcessor(bufferSize, 1, 1);
          scriptNode.onaudioprocess = (ev) => {
            const input = ev.inputBuffer.getChannelData(0);
            const output = ev.outputBuffer.getChannelData(0);
            const pcm = new Int16Array(input.length);
            for (let i = 0; i < input.length; i++) {
              const s = Math.max(-1, Math.min(1, input[i]));
              pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
              output[i] = 0; // Prevent echo!
            }
            onPCMChunk(pcm.buffer);
          };
          // ScriptProcessor needs to be connected to destination to run
          scriptNode.connect(ctx.destination);
          processorNode = scriptNode;
        }

        workletNodeRef.current = processorNode;
        inputAnalyser.connect(processorNode);
        if (processorNode instanceof AudioWorkletNode) {
          // AudioWorkletNode doesn't output audio, no need to connect to destination
        }

        // 6. Open WebSocket
        const base = apiBase || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');
        let wsUrl: string;
        if (base.startsWith('https://')) {
          wsUrl = base.replace(/^https:\/\//, 'wss://');
        } else if (base.startsWith('http://')) {
          wsUrl = base.replace(/^http:\/\//, 'ws://');
        } else if (typeof window !== 'undefined' && window.location) {
          const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
          wsUrl = `${proto}//${window.location.host}${base.startsWith('/') ? base : '/' + base}`;
        } else {
          wsUrl = 'ws://localhost:8000';
        }
        wsUrl = wsUrl.replace(/\/$/, '');
        const url = `${wsUrl}/api/v1/voice/ws/${sessionId}`;
        const ws = new WebSocket(url);
        ws.binaryType = 'arraybuffer';
        wsRef.current = ws;

        // Wire PCM sender
        onPCMChunk = (buffer: ArrayBuffer) => {
          if (ws.readyState === WebSocket.OPEN && !isMutedRef.current) {
            ws.send(buffer);
          }
        };

        ws.onopen = () => {
          if (!cancelled) setStatus('listening');
        };

        ws.onclose = () => {
          if (!cancelled) setStatus('ended');
        };

        ws.onerror = () => {
          if (!cancelled) setStatus('ended');
        };

        ws.onmessage = (ev) => {
          if (cancelled) return;

          if (typeof ev.data === 'string') {
            // JSON control message
            try {
              const msg = JSON.parse(ev.data) as Record<string, unknown>;
              if (msg.type === 'status') {
                setStatus(msg.status as CallStatus);
              }
            } catch { /* ignore */ }
          } else if (ev.data instanceof ArrayBuffer && ev.data.byteLength > 0) {
            // Binary PCM audio from Edge TTS / Pipecat
            // Fix: Use DataView to explicitly read Little-Endian 16-bit PCM integers
            // Using Int16Array directly can cause severe static/hissing if network byte order 
            // is misinterpreted or platform native endianness doesn't match the stream.
            const view = new DataView(ev.data);
            const numSamples = Math.floor(ev.data.byteLength / 2);
            const float32 = new Float32Array(numSamples);
            
            for (let i = 0; i < numSamples; i++) {
              // true = Little-Endian. Divide by 32768 to normalize to Web Audio API's expected [-1.0, 1.0] range
              float32[i] = view.getInt16(i * 2, true) / 32768; 
            }
            
            const audioBuffer = ctx.createBuffer(1, float32.length, 16000);
            audioBuffer.copyToChannel(float32, 0);
            playbackQueueRef.current.push(audioBuffer);
            drainPlaybackQueue(ctx);
          }
        };
      } catch (err) {
        console.error('[Aanandi Voice] Setup error:', err);
        if (!cancelled) setStatus('ended');
      }
    };

    setup();

    return () => {
      cancelled = true;
      teardown();
    };
  }, [apiBase, sessionId]);

  // ── Playback queue drain (Sample-accurate timeline scheduling) ────
  const drainPlaybackQueue = (ctx: AudioContext) => {
    while (playbackQueueRef.current.length > 0) {
      const buffer = playbackQueueRef.current.shift();
      if (!buffer) break;

      const node = ctx.createBufferSource();
      node.buffer = buffer;
      if (outputGainRef.current) {
        node.connect(outputGainRef.current);
      } else {
        node.connect(ctx.destination);
      }

      const now = ctx.currentTime;
      if (nextStartTimeRef.current < now) {
        nextStartTimeRef.current = now + 0.02; // Small 20ms jitter buffer
      }

      node.start(nextStartTimeRef.current);
      nextStartTimeRef.current += buffer.duration;
    }
  };

  // ── Teardown ──────────────────────────────────────────────────────
  const teardown = () => {
    wsRef.current?.close(1000, 'User ended call');
    wsRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;
    playbackQueueRef.current = [];
    nextStartTimeRef.current = 0;
    isPlayingRef.current = false;
  };

  // ── Controls ──────────────────────────────────────────────────────
  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      isMutedRef.current = next;
      if (gainNodeRef.current) {
        gainNodeRef.current.gain.value = next ? 0 : 1;
      }
      return next;
    });
  }, []);

  const disconnect = useCallback(() => {
    setStatus('ended');
    teardown();
  }, []);

  return {
    status,
    isMuted,
    toggleMute,
    disconnect,
    analyserNode,
    inputAnalyserNode,
  };
}
