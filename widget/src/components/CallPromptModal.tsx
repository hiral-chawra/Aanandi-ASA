import React, { useState } from 'react';
import { Phone, MessageSquare, Sparkles, X } from 'lucide-react';

interface CallPromptModalProps {
  leadName?: string;
  onYes: () => void;
  onNo: () => void;
}

/**
 * Pre-call opt-in modal overlaid after form interception.
 * Asks: "Would you like to speak with our AI Sales Engineer right now?"
 */
export default function CallPromptModal({ leadName, onYes, onNo }: CallPromptModalProps) {
  const [selecting, setSelecting] = useState<'yes' | 'no' | null>(null);

  const handleYes = () => {
    setSelecting('yes');
    setTimeout(onYes, 300);
  };

  const handleNo = () => {
    setSelecting('no');
    setTimeout(onNo, 300);
  };

  const firstName = leadName?.split(' ')[0];

  return (
    /* Backdrop */
    <div
      className="animate-fade-in"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        background: 'rgba(0, 24, 61, 0.72)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
      }}
    >
      {/* Card */}
      <div
        className="animate-modal-pop"
        style={{
          width: '100%',
          maxWidth: '400px',
          background: 'linear-gradient(160deg, rgba(21,42,80,0.98) 0%, rgba(10,24,56,1) 100%)',
          border: '1px solid rgba(149,145,244,0.35)',
          borderRadius: '24px',
          padding: '32px 28px',
          boxShadow:
            '0 32px 80px rgba(0,0,0,0.7), 0 0 0 1px rgba(149,145,244,0.15), inset 0 1px 0 rgba(255,255,255,0.05)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Background glow */}
        <div
          style={{
            position: 'absolute',
            top: '-60px',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '200px',
            height: '200px',
            background: 'radial-gradient(circle, rgba(90,91,189,0.3) 0%, transparent 70%)',
            pointerEvents: 'none',
          }}
        />

        {/* Dismiss */}
        <button
          onClick={handleNo}
          style={{
            position: 'absolute',
            top: '14px',
            right: '14px',
            width: '30px',
            height: '30px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
            cursor: 'pointer',
            color: 'rgba(192,202,199,0.6)',
            transition: 'all 0.2s',
          }}
        >
          <X size={14} />
        </button>

        {/* AI Avatar with pulse ring */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '24px' }}>
          <div style={{ position: 'relative' }}>
            {/* Outer pulse ring */}
            <div
              style={{
                position: 'absolute',
                inset: '-8px',
                borderRadius: '50%',
                border: '2px solid rgba(149,145,244,0.3)',
              }}
              className="animate-glow-ring"
            />
            {/* Avatar */}
            <div
              style={{
                width: '72px',
                height: '72px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #5A5BBD 0%, #9591F4 50%, #283040 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '2px solid rgba(149,145,244,0.4)',
                boxShadow: '0 8px 24px rgba(90,91,189,0.4)',
                position: 'relative',
              }}
            >
              <span
                style={{
                  fontSize: '32px',
                  fontWeight: 800,
                  color: 'white',
                  letterSpacing: '-1px',
                }}
              >
                A
              </span>
              {/* Active indicator */}
              <div
                style={{
                  position: 'absolute',
                  bottom: '2px',
                  right: '2px',
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  background: '#22C55E',
                  border: '2px solid rgba(10,24,56,1)',
                  boxShadow: '0 0 8px #22C55E',
                }}
                className="animate-dot-breathe"
              />
            </div>
          </div>
        </div>

        {/* Heading */}
        <div style={{ textAlign: 'center', marginBottom: '8px' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(250,216,0,0.1)',
              border: '1px solid rgba(250,216,0,0.25)',
              borderRadius: '100px',
              padding: '4px 12px',
              marginBottom: '14px',
            }}
          >
            <Sparkles size={12} color="#FAD800" />
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#FAD800', letterSpacing: '0.5px' }}>
              AI SALES CALL
            </span>
          </div>

          <h2
            style={{
              fontSize: '22px',
              fontWeight: 800,
              color: '#ffffff',
              lineHeight: '1.25',
              letterSpacing: '-0.4px',
              marginBottom: '10px',
            }}
          >
            {firstName
              ? `Hey ${firstName}, speak to\nAanandi right now?`
              : 'Connect with Aanandi\nAI right now?'}
          </h2>

          <p
            style={{
              fontSize: '13px',
              color: 'rgba(192,202,199,0.75)',
              lineHeight: '1.6',
              maxWidth: '320px',
              margin: '0 auto',
            }}
          >
            Our AI Sales Engineer can answer product questions, qualify your requirements,
            and book a demo — all in{' '}
            <strong style={{ color: '#DBD7FA' }}>under 2 minutes</strong>.
          </p>
        </div>

        {/* Feature pills */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '8px',
            flexWrap: 'wrap',
            margin: '20px 0 28px',
          }}
        >
          {['Instant', 'No hold time', 'AI-powered'].map((f) => (
            <span
              key={f}
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#9591F4',
                background: 'rgba(149,145,244,0.1)',
                border: '1px solid rgba(149,145,244,0.2)',
                borderRadius: '100px',
                padding: '3px 10px',
              }}
            >
              {f}
            </span>
          ))}
        </div>

        {/* CTAs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <button
            onClick={handleYes}
            disabled={selecting !== null}
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '14px',
              fontSize: '15px',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              background:
                selecting === 'yes'
                  ? 'linear-gradient(135deg, #4a5bb0, #8080e0)'
                  : 'linear-gradient(135deg, #FAD800 0%, #e8c500 100%)',
              color: '#00183D',
              border: 'none',
              cursor: selecting !== null ? 'default' : 'pointer',
              transition: 'all 0.3s',
              boxShadow:
                selecting !== 'yes' ? '0 8px 24px rgba(250,216,0,0.3)' : 'none',
              transform: selecting === 'yes' ? 'scale(0.97)' : 'scale(1)',
            }}
          >
            {selecting === 'yes' ? (
              <div
                style={{
                  width: '18px',
                  height: '18px',
                  border: '2px solid rgba(0,24,61,0.3)',
                  borderTopColor: '#00183D',
                  borderRadius: '50%',
                }}
                className="animate-spin"
              />
            ) : (
              <Phone size={16} />
            )}
            {selecting === 'yes' ? 'Connecting…' : 'Yes, Connect Me Now'}
          </button>

          <button
            onClick={handleNo}
            disabled={selecting !== null}
            style={{
              width: '100%',
              padding: '13px',
              borderRadius: '14px',
              fontSize: '14px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              background: 'rgba(90,91,189,0.12)',
              color: '#DBD7FA',
              border: '1px solid rgba(149,145,244,0.25)',
              cursor: selecting !== null ? 'default' : 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              if (!selecting) {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(90,91,189,0.22)';
                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(149,145,244,0.4)';
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(90,91,189,0.12)';
              (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(149,145,244,0.25)';
            }}
          >
            <MessageSquare size={15} />
            No thanks, I'll just chat
          </button>
        </div>

        {/* Trust footer */}
        <p
          style={{
            textAlign: 'center',
            marginTop: '18px',
            fontSize: '10px',
            color: 'rgba(192,202,199,0.4)',
            letterSpacing: '0.3px',
          }}
        >
          🔒 Secure · No recording stored · Powered by Aanandi AI
        </p>
      </div>
    </div>
  );
}
