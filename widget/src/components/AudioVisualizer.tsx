import React, { useRef, useEffect, useCallback } from 'react';
import type { CallStatus } from '../types';

interface AudioVisualizerProps {
  analyserNode: AnalyserNode | null;   // AI speaker audio
  inputAnalyserNode: AnalyserNode | null; // Mic input audio
  status: CallStatus;
  isMuted: boolean;
}

/**
 * Real-time FFT bar visualizer.
 * - Uses requestAnimationFrame for smooth 60fps rendering
 * - Reads frequency data from AnalyserNode (speaker) and inputAnalyserNode (mic)
 * - Falls back to idle sine wave animation when no audio
 * - Color: indigo→purple→lavender gradient bars
 */
export default function AudioVisualizer({
  analyserNode,
  inputAnalyserNode,
  status,
  isMuted,
}: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const phaseRef = useRef(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const BAR_COUNT = 48;
    const BAR_GAP = 3;
    const BAR_WIDTH = (W - BAR_GAP * (BAR_COUNT - 1)) / BAR_COUNT;

    ctx.clearRect(0, 0, W, H);

    // ── Get frequency data ──────────────────────────────────────
    let speakerData: Uint8Array<ArrayBuffer> | null = null;
    let micData: Uint8Array<ArrayBuffer> | null = null;

    if (analyserNode && (status === 'speaking')) {
      const buf = new ArrayBuffer(analyserNode.frequencyBinCount);
      speakerData = new Uint8Array(buf);
      analyserNode.getByteFrequencyData(speakerData);
    }

    if (inputAnalyserNode && !isMuted && status === 'listening') {
      const buf = new ArrayBuffer(inputAnalyserNode.frequencyBinCount);
      micData = new Uint8Array(buf);
      inputAnalyserNode.getByteFrequencyData(micData);
    }

    const hasLiveData = speakerData || micData;

    // ── Draw bars ───────────────────────────────────────────────
    for (let i = 0; i < BAR_COUNT; i++) {
      let normalizedHeight: number;

      if (hasLiveData) {
        // Use live FFT data
        const source = speakerData ?? micData!;
        // Map bar index to FFT bin (focus on lower-mid frequencies)
        const binIndex = Math.floor((i / BAR_COUNT) * (source.length * 0.6));
        normalizedHeight = source[binIndex] / 255;
        // Apply some smoothing with a soft curve
        normalizedHeight = Math.pow(normalizedHeight, 0.7);
      } else {
        // Idle sine wave animation
        phaseRef.current += 0.004;
        const phase = phaseRef.current;
        const offset = (i / BAR_COUNT) * Math.PI * 2;
        const slow = Math.sin(phase * 0.8 + offset) * 0.3 + 0.5;
        const fast = Math.sin(phase * 2.5 + offset * 1.5) * 0.15;
        normalizedHeight = Math.max(0.04, slow + fast);

        if (status === 'thinking') {
          // Faster agitated animation for "thinking"
          const think = Math.sin(phase * 4 + offset * 2) * 0.4 + 0.5;
          normalizedHeight = Math.max(0.08, think);
        }
      }

      const barH = Math.max(3, normalizedHeight * H * 0.85);
      const x = i * (BAR_WIDTH + BAR_GAP);
      const y = (H - barH) / 2;

      // ── Gradient per bar (indigo → purple → lavender) ──────────
      const progress = i / BAR_COUNT;
      const grad = ctx.createLinearGradient(0, y, 0, y + barH);

      if (speakerData) {
        // Speaker: blue → purple
        grad.addColorStop(0, `hsla(${220 + progress * 60}, 80%, 70%, 0.9)`);
        grad.addColorStop(0.5, `hsla(${250 + progress * 40}, 75%, 65%, 0.85)`);
        grad.addColorStop(1, `hsla(${270 + progress * 20}, 70%, 60%, 0.8)`);
      } else if (micData) {
        // Mic input: green → teal
        grad.addColorStop(0, `hsla(${140 + progress * 30}, 70%, 65%, 0.9)`);
        grad.addColorStop(0.5, `hsla(${160 + progress * 20}, 65%, 60%, 0.85)`);
        grad.addColorStop(1, `hsla(${180 + progress * 10}, 60%, 55%, 0.8)`);
      } else {
        // Idle: lavender → slateblue
        const alpha = 0.35 + normalizedHeight * 0.5;
        grad.addColorStop(0, `hsla(${230 + progress * 50}, 65%, 70%, ${alpha})`);
        grad.addColorStop(0.5, `hsla(${250 + progress * 35}, 60%, 65%, ${alpha * 0.9})`);
        grad.addColorStop(1, `hsla(${265 + progress * 20}, 55%, 60%, ${alpha * 0.8})`);
      }

      const radius = Math.min(BAR_WIDTH / 2, barH / 2, 4);
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, BAR_WIDTH, barH, radius);
      ctx.fill();

      // Subtle glow above top of bar
      if (normalizedHeight > 0.3) {
        const glowGrad = ctx.createRadialGradient(
          x + BAR_WIDTH / 2, y, 0,
          x + BAR_WIDTH / 2, y, BAR_WIDTH * 2,
        );
        glowGrad.addColorStop(0, `rgba(149,145,244,${normalizedHeight * 0.3})`);
        glowGrad.addColorStop(1, 'rgba(149,145,244,0)');
        ctx.fillStyle = glowGrad;
        ctx.beginPath();
        ctx.arc(x + BAR_WIDTH / 2, y, BAR_WIDTH * 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    rafRef.current = requestAnimationFrame(draw);
  }, [analyserNode, inputAnalyserNode, status, isMuted]);

  useEffect(() => {
    rafRef.current = requestAnimationFrame(draw);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [draw]);

  // Handle canvas DPI scaling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    if (ctx) ctx.scale(dpr, dpr);
  }, []);

  return (
    <div
      style={{
        width: '100%',
        maxWidth: '320px',
        height: '80px',
        position: 'relative',
        borderRadius: '16px',
        overflow: 'hidden',
        background: 'rgba(0,0,0,0.25)',
        border: '1px solid rgba(149,145,244,0.15)',
      }}
    >
      <canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      />
    </div>
  );
}
