import React, { useCallback } from 'react';
import type { UIMode } from '../types';

interface ChatLauncherProps {
  uiMode: UIMode;
  unreadCount: number;
  onClick: () => void;
}

/**
 * Circle trigger — Aanandi brand logo on light-lavender (#DBD7FA) background.
 * Outer shape: circle
 * Background: #DBD7FA (lavender — from aanandi.in palette)
 * "A" legs: #283040 dark slate (exact logo color)
 * Gold dot: #FAD800 (exact logo color)
 */
export default function ChatLauncher({
  uiMode,
  unreadCount,
  onClick,
}: ChatLauncherProps) {
  const isOpen      = uiMode !== 'idle';
  const isVoice     = uiMode === 'voice';
  const isConnecting = uiMode === 'modal';

  const dotColor = isVoice
    ? '#3B82F6'   // blue: voice call active
    : isConnecting
    ? '#FAD800'   // gold: connecting/modal
    : '#22C55E';  // green: ready

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onClick();
      }
    },
    [onClick],
  );

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 999999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px',
      }}
    >
      {/* Tooltip — only when widget is closed */}
      {!isOpen && (
        <div
          style={{
            background: 'rgba(13,34,72,0.95)',
            border: '1px solid rgba(149,145,244,0.35)',
            color: '#DBD7FA',
            fontSize: '12px',
            fontWeight: 600,
            padding: '5px 13px',
            borderRadius: '100px',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
            pointerEvents: 'none',
            animation: 'fade-in 0.3s ease both',
            letterSpacing: '0.2px',
          }}
        >
          Chat with Aanandi AI ✦
        </div>
      )}

      {/* Circle button wrapper */}
      <div style={{ position: 'relative' }}>
        <button
          onClick={onClick}
          onKeyDown={handleKeyDown}
          aria-label={isOpen ? 'Close Aanandi chat' : 'Open Aanandi chat'}
          aria-expanded={isOpen}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            width: '52px',
            height: '52px',
            position: 'relative',
            outline: 'none',
            WebkitTapHighlightColor: 'transparent',
            borderRadius: '50%',
          }}
          className={!isOpen ? 'animate-crystal-pulse' : ''}
        >
          <AanandiCircleLogo isOpen={isOpen} isVoice={isVoice} />
        </button>

        {/* Status dot — top-right of circle */}
        <span
          style={{
            position: 'absolute',
            top: '1px',
            right: '1px',
            width: '11px',
            height: '11px',
            borderRadius: '50%',
            background: dotColor,
            border: '2px solid #ffffff',
            boxShadow: `0 0 6px ${dotColor}, 0 2px 4px rgba(0,0,0,0.3)`,
            transition: 'background 0.4s ease, box-shadow 0.4s ease',
            pointerEvents: 'none',
            zIndex: 1,
          }}
          className="animate-dot-breathe"
        />

        {/* Unread count badge — top-left */}
        {unreadCount > 0 && !isOpen && (
          <span
            style={{
              position: 'absolute',
              top: '1px',
              left: '1px',
              minWidth: '20px',
              height: '20px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #FAD800, #e8c500)',
              color: '#00183D',
              fontSize: '10px',
              fontWeight: 800,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 4px',
              border: '2px solid #ffffff',
              boxShadow: '0 2px 8px rgba(250,216,0,0.55)',
              pointerEvents: 'none',
              zIndex: 1,
            }}
            className="animate-badge-pulse"
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   AANANDI CIRCLE LOGO SVG
   Circle background: #DBD7FA (lavender — aanandi.in palette)
   "A" legs:          #283040 (dark slate — exact logo color)
   Gold dot:          #FAD800 (exact logo color)
══════════════════════════════════════════════════════════════════════ */
function AanandiCircleLogo({
  isOpen,
  isVoice,
}: {
  isOpen: boolean;
  isVoice: boolean;
}) {
  // Circle geometry
  const CX = 50, CY = 50, R = 46;

  // "A" logo geometry — same proportions as the brand mark
  const A_TOP_X  = 50;
  const A_TOP_Y  = 20;   // apex of the A
  const A_LX     = 27;   // left leg bottom x
  const A_RX     = 73;   // right leg bottom x
  const A_BY     = 76;   // legs bottom y
  const DOT_CY   = 59;   // yellow dot vertical center (crossbar position)
  const DOT_R    = 9;    // yellow dot radius
  const LEG_W    = 12;   // leg stroke width

  // Colors — lavender bg stays, accents shift when in voice mode
  const bgColor     = isVoice ? '#c8c2f8' : '#DBD7FA';   // lavender (dimmed in voice)
  const borderColor = isVoice ? '#5A5BBD' : '#9591F4';   // purple accent
  const shadowColor = isVoice ? '#5A5BBD' : '#9591F4';

  return (
    <svg
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        width: '100%',
        height: '100%',
        borderRadius: '50%',
        transform: isOpen ? 'scale(0.88) rotate(-8deg)' : 'scale(1) rotate(0deg)',
        transition: 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
        filter: isOpen
          ? `drop-shadow(0 0 10px ${shadowColor}bb) drop-shadow(0 0 24px ${shadowColor}55)`
          : `drop-shadow(0 4px 14px rgba(0,0,0,0.30)) drop-shadow(0 0 8px ${shadowColor}44)`,
      }}
    >
      <defs>
        {/* Circle background gradient — light lavender with subtle depth */}
        <radialGradient id="circle-bg" cx="40%" cy="35%" r="70%">
          <stop offset="0%"   stopColor={bgColor} />
          <stop offset="60%"  stopColor={isVoice ? '#b8b0f5' : '#cdc8f7'} />
          <stop offset="100%" stopColor={isVoice ? '#9591F4' : '#b8b4f0'} />
        </radialGradient>

        {/* Gold dot gradient */}
        <radialGradient id="dot-gold" cx="38%" cy="32%" r="68%">
          <stop offset="0%"   stopColor="#FFE55C" />
          <stop offset="55%"  stopColor="#FAD800" />
          <stop offset="100%" stopColor="#c9a000" />
        </radialGradient>

        {/* Clip to circle */}
        <clipPath id="circle-clip">
          <circle cx={CX} cy={CY} r={R} />
        </clipPath>

        {/* Inner shadow at bottom of circle */}
        <radialGradient id="inner-shadow" cx="50%" cy="100%" r="70%">
          <stop offset="0%"   stopColor="rgba(90,91,189,0.18)" />
          <stop offset="100%" stopColor="rgba(90,91,189,0)" />
        </radialGradient>

        {/* Sheen gradient — top-left highlight */}
        <radialGradient id="circle-sheen" cx="30%" cy="20%" r="55%">
          <stop offset="0%"   stopColor="rgba(255,255,255,0.45)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
      </defs>

      {/* ── 1. Circle base — lavender background ──────────────── */}
      <circle cx={CX} cy={CY} r={R} fill="url(#circle-bg)" />

      {/* ── 2. Inner shadow at bottom ─────────────────────────── */}
      <circle cx={CX} cy={CY} r={R} fill="url(#inner-shadow)" clipPath="url(#circle-clip)" />

      {/* ── 3. "A" left leg ───────────────────────────────────── */}
      <line
        x1={A_TOP_X} y1={A_TOP_Y}
        x2={A_LX}    y2={A_BY}
        stroke="#283040"
        strokeWidth={LEG_W}
        strokeLinecap="round"
        clipPath="url(#circle-clip)"
      />

      {/* ── 4. "A" right leg ──────────────────────────────────── */}
      <line
        x1={A_TOP_X} y1={A_TOP_Y}
        x2={A_RX}    y2={A_BY}
        stroke="#283040"
        strokeWidth={LEG_W}
        strokeLinecap="round"
        clipPath="url(#circle-clip)"
      />

      {/* ── 5. Gold dot — outer halo (glow) ───────────────────── */}
      <circle
        cx={CX} cy={DOT_CY} r={DOT_R + 5}
        fill="rgba(250,216,0,0.22)"
        clipPath="url(#circle-clip)"
      />

      {/* ── 6. Gold dot — main circle ─────────────────────────── */}
      <circle
        cx={CX} cy={DOT_CY} r={DOT_R}
        fill="url(#dot-gold)"
        clipPath="url(#circle-clip)"
      >
        <animate
          attributeName="r"
          values={`${DOT_R};${DOT_R + 1};${DOT_R}`}
          dur="2.4s"
          repeatCount="indefinite"
        />
      </circle>

      {/* ── 7. Gold dot specular highlight ────────────────────── */}
      <circle
        cx={CX - 3} cy={DOT_CY - 3.5} r="3.5"
        fill="rgba(255,255,255,0.45)"
        clipPath="url(#circle-clip)"
      />

      {/* ── 8. Circle sheen (top-left glass reflection) ───────── */}
      <circle cx={CX} cy={CY} r={R} fill="url(#circle-sheen)" clipPath="url(#circle-clip)" />

      {/* ── 9. Circle outer border ────────────────────────────── */}
      <circle
        cx={CX} cy={CY} r={R}
        fill="none"
        stroke={borderColor}
        strokeWidth="1.8"
        opacity={isOpen ? '0.9' : '0.6'}
      />
    </svg>
  );
}
