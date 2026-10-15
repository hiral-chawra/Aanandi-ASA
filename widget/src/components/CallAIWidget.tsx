import React, { useEffect, useRef, useState } from 'react';
import { MicOff, PhoneOff, Mic } from 'lucide-react';
import type { CallStatus } from '../types';
import AudioVisualizer from './AudioVisualizer';
import { useAudioWebSocket } from '../hooks/useAudioWebSocket';

interface CallAIWidgetProps {
  sessionId: string;
  apiBase: string;
  onEnd: () => void;
}

/**
 * Full-screen voice call UI — replaces LiveKit with direct WebSocket PCM streaming.
 * Shows status pill, audio visualizer, mute + end controls, call timer.
 */
export default function CallAIWidget({ sessionId, apiBase, onEnd }: CallAIWidgetProps) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { status, isMuted, toggleMute, disconnect, analyserNode, inputAnalyserNode } =
    useAudioWebSocket({
      apiBase,
      sessionId,
    });

  // Start timer when connected
  useEffect(() => {
    if (status === 'listening' || status === 'speaking' || status === 'thinking') {
      if (!timerRef.current) {
        timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
      }
    }
  }, [status]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const handleEnd = () => {
    disconnect();
    if (timerRef.current) clearInterval(timerRef.current);
    onEnd();
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    const sec = (s % 60).toString().padStart(2, '0');
    return `${m}:${sec}`;
  };

  const statusConfig: Record<
    CallStatus,
    { label: string; color: string; dotColor: string }
  > = {
    idle:       { label: 'Ready',              color: '#C0CAC7', dotColor: '#C0CAC7' },
    connecting: { label: 'Connecting…',        color: '#FAD800', dotColor: '#FAD800' },
    listening:  { label: 'Listening',          color: '#22C55E', dotColor: '#22C55E' },
    thinking:   { label: 'Gemini Thinking…',   color: '#9591F4', dotColor: '#9591F4' },
    speaking:   { label: 'Aanandi Speaking',   color: '#5A5BBD', dotColor: '#5A5BBD' },
    ended:      { label: 'Call Ended',         color: '#EF4444', dotColor: '#EF4444' },
  };

  const cfg = statusConfig[status];

  return (
    <div
      className="animate-slide-up"
      style={{
        position: 'fixed',
        bottom: '136px',
        right: '24px',
        zIndex: 999998,
        width: 'min(380px, calc(100vw - 32px))',
        height: 'min(560px, calc(100vh - 160px))',
        borderRadius: '24px',
        overflow: 'hidden',
        boxShadow: '0 24px 64px rgba(0,0,0,0.7), 0 0 0 1px rgba(149,145,244,0.25)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Animated background */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(160deg, #0a1835 0%, #060f24 60%, #0d2040 100%)',
        }}
      />
      {/* Moving gradient orbs */}
      <div
        style={{
          position: 'absolute',
          top: '10%',
          left: '20%',
          width: '200px',
          height: '200px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(90,91,189,0.25) 0%, transparent 70%)',
          filter: 'blur(40px)',
          animation: 'crystal-pulse 4s ease-in-out infinite',
        }}
      />
      <div
        style={{
          position: 'absolute',
          bottom: '15%',
          right: '10%',
          width: '160px',
          height: '160px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(149,145,244,0.2) 0%, transparent 70%)',
          filter: 'blur(30px)',
          animation: 'crystal-pulse 3.5s ease-in-out infinite 1s',
        }}
      />

      {/* Content */}
      <div
        style={{
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          height: '100%',
          padding: '24px 20px 20px',
        }}
      >
        {/* ── TOP: Status + Timer ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          {/* Status pill */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '7px',
              padding: '6px 14px',
              borderRadius: '100px',
              background: 'rgba(13,34,72,0.7)',
              border: `1px solid ${cfg.color}44`,
              backdropFilter: 'blur(8px)',
            }}
          >
            <div
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: cfg.dotColor,
                boxShadow: `0 0 6px ${cfg.dotColor}`,
              }}
              className={
                status === 'listening' || status === 'thinking' || status === 'connecting'
                  ? 'animate-dot-breathe'
                  : ''
              }
            />
            <span
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: cfg.color,
                letterSpacing: '0.3px',
              }}
            >
              {cfg.label}
            </span>

            {/* Connecting dots */}
            {status === 'thinking' && (
              <div style={{ display: 'flex', gap: '3px', marginLeft: '2px' }}>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    style={{
                      width: '4px',
                      height: '4px',
                      borderRadius: '50%',
                      background: '#9591F4',
                      animation: `dot-bounce 1.2s ease-in-out infinite`,
                      animationDelay: `${i * 0.15}s`,
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Timer */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '100px',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            <ClockIcon />
            <span
              style={{
                fontSize: '13px',
                fontWeight: 700,
                color: '#C0CAC7',
                fontVariantNumeric: 'tabular-nums',
                fontFamily: 'monospace',
              }}
            >
              {formatTime(elapsed)}
            </span>
          </div>
        </div>

        {/* ── CENTER: Avatar + Visualizer ── */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
          }}
        >
          {/* AI Avatar with glow */}
          <div style={{ position: 'relative' }}>
            {(status === 'speaking' || status === 'thinking') && (
              <div
                style={{
                  position: 'absolute',
                  inset: '-16px',
                  borderRadius: '50%',
                  border: `2px solid ${cfg.color}55`,
                }}
                className="animate-glow-ring"
              />
            )}
            <div
              style={{
                width: '96px',
                height: '96px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #5A5BBD 0%, #9591F4 50%, #283040 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: `2px solid ${cfg.color}66`,
                boxShadow: `0 12px 32px rgba(90,91,189,0.4), 0 0 40px ${cfg.color}22`,
                transition: 'border-color 0.5s, box-shadow 0.5s',
              }}
            >
              <span
                style={{
                  fontSize: '44px',
                  fontWeight: 800,
                  color: 'white',
                  letterSpacing: '-2px',
                }}
              >
                A
              </span>
            </div>
          </div>

          <div style={{ textAlign: 'center' }}>
            <div
              style={{
                fontSize: '20px',
                fontWeight: 800,
                color: '#ffffff',
                letterSpacing: '-0.4px',
              }}
            >
              Aanandi AI
            </div>
            <div
              style={{
                fontSize: '12px',
                color: 'rgba(192,202,199,0.6)',
                marginTop: '3px',
              }}
            >
              Sales Engineer · aanandi.in
            </div>
          </div>

          {/* Audio Visualizer */}
          <AudioVisualizer
            analyserNode={analyserNode}
            inputAnalyserNode={inputAnalyserNode}
            status={status}
            isMuted={isMuted}
          />
        </div>

        {/* ── BOTTOM: Controls ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '20px',
            paddingTop: '20px',
          }}
        >
          {/* Mute toggle */}
          <button
            onClick={toggleMute}
            title={isMuted ? 'Unmute' : 'Mute microphone'}
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: isMuted
                ? 'linear-gradient(135deg, #EF4444, #DC2626)'
                : 'rgba(149,145,244,0.15)',
              border: isMuted
                ? '2px solid rgba(239,68,68,0.4)'
                : '2px solid rgba(149,145,244,0.3)',
              cursor: 'pointer',
              color: isMuted ? 'white' : '#9591F4',
              transition: 'all 0.3s',
              boxShadow: isMuted ? '0 4px 16px rgba(239,68,68,0.4)' : 'none',
            }}
          >
            {isMuted ? <MicOff size={22} /> : <Mic size={22} />}
          </button>

          {/* End call — larger, prominent */}
          <button
            onClick={handleEnd}
            title="End call"
            style={{
              width: '72px',
              height: '72px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #EF4444, #DC2626)',
              border: '3px solid rgba(239,68,68,0.3)',
              cursor: 'pointer',
              color: 'white',
              transition: 'all 0.2s',
              boxShadow: '0 8px 24px rgba(239,68,68,0.5)',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1.05)';
              (e.currentTarget as HTMLButtonElement).style.boxShadow =
                '0 12px 32px rgba(239,68,68,0.65)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)';
              (e.currentTarget as HTMLButtonElement).style.boxShadow =
                '0 8px 24px rgba(239,68,68,0.5)';
            }}
          >
            <PhoneOff size={28} />
          </button>

          {/* Speaker volume placeholder */}
          <button
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(149,145,244,0.1)',
              border: '2px solid rgba(149,145,244,0.2)',
              cursor: 'pointer',
              color: '#9591F4',
              transition: 'all 0.2s',
            }}
            title="Speaker (active)"
          >
            <SpeakerIcon />
          </button>
        </div>

        {/* Muted indicator */}
        {isMuted && (
          <div
            style={{
              textAlign: 'center',
              marginTop: '12px',
              fontSize: '12px',
              color: '#EF4444',
              fontWeight: 600,
              letterSpacing: '0.3px',
              animation: 'fade-in 0.2s ease',
            }}
          >
            🔇 Microphone muted
          </div>
        )}
      </div>
    </div>
  );
}

function ClockIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#C0CAC7" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function SpeakerIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
    </svg>
  );
}
