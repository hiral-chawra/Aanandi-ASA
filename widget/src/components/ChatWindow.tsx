import React, { useEffect, useRef, useState } from 'react';
import {
  X,
  Minimize2,
  Zap,
} from 'lucide-react';
import type { Message, WSStatus } from '../types';
import MessageList from './MessageList';
import { useWebSocket as _useWebSocket } from '../hooks/useWebSocket';

interface ChatWindowProps {
  messages: Message[];
  wsStatus: WSStatus;
  latency: number;
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  onSendMessage: (text: string, attachments?: string[]) => Promise<void>;
  onOpenVoice: () => void;
  onClose: () => void;
}

export default function ChatWindow({
  messages,
  wsStatus,
  latency,
  sessionId,
  leadId,
  apiBase,
  onSendMessage,
  onOpenVoice,
  onClose,
}: ChatWindowProps) {
  const [inputValue, setInputValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [attachedPhotos, setAttachedPhotos] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  }, [inputValue]);

  // Focus input on open
  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 100);
  }, []);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', sessionId);
      if (leadId) formData.append('lead_id', leadId);

      const res = await fetch(`${apiBase}/api/v1/upload/photo`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        if (data.url) {
          setAttachedPhotos((prev) => [...prev, data.url]);
        }
      }
    } catch (err) {
      console.error('Failed to upload photo attachment:', err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const removePhoto = (index: number) => {
    setAttachedPhotos((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = async () => {
    const text = inputValue.trim();
    const photos = [...attachedPhotos];
    if ((!text && photos.length === 0) || isSending || isUploading) return;
    setInputValue('');
    setAttachedPhotos([]);
    setIsSending(true);
    try {
      await onSendMessage(text, photos);
    } finally {
      setIsSending(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Status indicator config
  const statusConfig = {
    connecting: { color: '#FAD800', label: 'Connecting…', pulse: true },
    open:       { color: '#22C55E', label: 'Live',        pulse: false },
    closed:     { color: '#EF4444', label: 'Offline',     pulse: false },
    error:      { color: '#EF4444', label: 'Error',       pulse: false },
  }[wsStatus] ?? { color: '#C0CAC7', label: 'Unknown', pulse: false };

  return (
    <div
      className="animate-slide-up"
      style={{
        position: 'fixed',
        bottom: '136px',
        right: '24px',
        zIndex: 999998,
        width: 'min(380px, calc(100vw - 32px))',
        height: isMinimized ? 'auto' : 'min(620px, calc(100vh - 160px))',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '20px',
        overflow: 'hidden',
        boxShadow: '0 24px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(149,145,244,0.2)',
      }}
    >
      {/* ── Glass background ── */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'linear-gradient(160deg, rgba(21,42,80,0.97) 0%, rgba(10,24,56,0.99) 100%)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
        }}
      />

      {/* ── Content wrapper ── */}
      <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', height: '100%' }}>

        {/* ── HEADER ── */}
        <div
          style={{
            padding: '16px 16px 14px',
            borderBottom: '1px solid rgba(149,145,244,0.15)',
            background: 'linear-gradient(135deg, rgba(30,52,96,0.6) 0%, rgba(13,34,72,0.4) 100%)',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Avatar */}
            <div style={{ position: 'relative', flexShrink: 0 }}>
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '18px',
                  fontWeight: 800,
                  color: 'white',
                  boxShadow: '0 4px 12px rgba(90,91,189,0.4)',
                  border: '1px solid rgba(149,145,244,0.3)',
                }}
              >
                A
              </div>
              {/* Online dot */}
              <div
                style={{
                  position: 'absolute',
                  bottom: '-1px',
                  right: '-1px',
                  width: '11px',
                  height: '11px',
                  borderRadius: '50%',
                  background: statusConfig.color,
                  border: '2px solid rgba(10,24,56,0.99)',
                  boxShadow: `0 0 6px ${statusConfig.color}`,
                }}
                className={statusConfig.pulse ? 'animate-dot-breathe' : ''}
              />
            </div>

            {/* Title & subtitle */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span
                  style={{
                    fontSize: '14px',
                    fontWeight: 700,
                    color: '#ffffff',
                    letterSpacing: '-0.2px',
                  }}
                >
                  Aanandi AI
                </span>
                {/* Latency badge */}
                {wsStatus === 'open' && (
                  <span className="latency-badge">
                    ~{latency}ms
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginTop: '2px' }}>
                <Zap size={10} color="#FAD800" />
                <span
                  style={{
                    fontSize: '11px',
                    color: 'rgba(192,202,199,0.7)',
                    fontWeight: 500,
                  }}
                >
                  Powered by Gemini 1.5 Flash · Whisper STT
                </span>
              </div>
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
              {/* Minimize */}
              <button
                onClick={() => setIsMinimized((m) => !m)}
                title={isMinimized ? 'Expand' : 'Minimize'}
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  color: '#C0CAC7',
                }}
              >
                <Minimize2 size={14} />
              </button>

              {/* Close */}
              <button
                onClick={onClose}
                title="Close"
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  color: '#C0CAC7',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.15)';
                  (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(239,68,68,0.3)';
                  (e.currentTarget as HTMLButtonElement).style.color = '#EF4444';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)';
                  (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(255,255,255,0.1)';
                  (e.currentTarget as HTMLButtonElement).style.color = '#C0CAC7';
                }}
              >
                <X size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* ── MESSAGE AREA ── */}
        {!isMinimized && (
          <>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <MessageList
                messages={messages}
                sessionId={sessionId}
                leadId={leadId}
                apiBase={apiBase}
                onSendMessage={onSendMessage}
                onOpenVoice={onOpenVoice}
              />
            </div>

            {/* ── INPUT FOOTER ── */}
            <div
              style={{
                padding: '12px 14px 14px',
                borderTop: '1px solid rgba(149,145,244,0.12)',
                background: 'rgba(10,24,56,0.6)',
                flexShrink: 0,
              }}
            >
              {/* Photo preview strip */}
              {(attachedPhotos.length > 0 || isUploading) && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '8px',
                    padding: '6px 10px',
                    background: 'rgba(0,0,0,0.35)',
                    borderRadius: '10px',
                    border: '1px solid rgba(149,145,244,0.25)',
                    overflowX: 'auto',
                  }}
                >
                  {attachedPhotos.map((url, i) => (
                    <div
                      key={url + i}
                      style={{
                        position: 'relative',
                        width: '42px',
                        height: '42px',
                        borderRadius: '6px',
                        overflow: 'hidden',
                        border: '1px solid rgba(149,145,244,0.4)',
                        flexShrink: 0,
                      }}
                    >
                      <img
                        src={url.startsWith('/') ? `${apiBase}${url}` : url}
                        alt="attachment"
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                      <button
                        onClick={() => removePhoto(i)}
                        title="Remove attachment"
                        style={{
                          position: 'absolute',
                          top: '2px',
                          right: '2px',
                          width: '14px',
                          height: '14px',
                          borderRadius: '50%',
                          background: 'rgba(0,0,0,0.7)',
                          color: 'white',
                          border: 'none',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '10px',
                          lineHeight: 1,
                        }}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  {isUploading && (
                    <div
                      style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: '6px',
                        background: 'rgba(149,145,244,0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <div
                        style={{
                          width: '14px',
                          height: '14px',
                          border: '2px solid rgba(149,145,244,0.3)',
                          borderTopColor: '#9591F4',
                          borderRadius: '50%',
                        }}
                        className="animate-spin"
                      />
                    </div>
                  )}
                  <span style={{ fontSize: '11px', color: '#DBD7FA' }}>
                    {isUploading ? 'Uploading project photo…' : `${attachedPhotos.length} photo attached`}
                  </span>
                </div>
              )}

              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: '8px',
                  background: 'rgba(21,42,80,0.7)',
                  border: '1px solid rgba(149,145,244,0.2)',
                  borderRadius: '14px',
                  padding: '8px 10px 8px 14px',
                  transition: 'border-color 0.2s, box-shadow 0.2s',
                }}
                onFocusCapture={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = 'rgba(149,145,244,0.6)';
                  (e.currentTarget as HTMLDivElement).style.boxShadow =
                    '0 0 0 3px rgba(149,145,244,0.12)';
                }}
                onBlurCapture={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor =
                    'rgba(149,145,244,0.2)';
                  (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
                }}
              >
                <textarea
                  ref={textareaRef}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type your message…"
                  rows={1}
                  style={{
                    flex: 1,
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: '#ffffff',
                    fontSize: '14px',
                    lineHeight: '1.5',
                    resize: 'none',
                    maxHeight: '120px',
                    fontFamily: 'inherit',
                    caretColor: '#9591F4',
                  }}
                />

                {/* Photo attachment input & button */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  title="Attach project photo"
                  style={{
                    flexShrink: 0,
                    width: '32px',
                    height: '32px',
                    borderRadius: '9px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(149,145,244,0.1)',
                    border: '1px solid rgba(149,145,244,0.2)',
                    cursor: 'pointer',
                    color: '#9591F4',
                    transition: 'all 0.2s',
                  }}
                >
                  <PaperclipIcon />
                </button>

                {/* Mic → voice */}
                <button
                  onClick={onOpenVoice}
                  title="Switch to voice"
                  style={{
                    flexShrink: 0,
                    width: '32px',
                    height: '32px',
                    borderRadius: '9px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(149,145,244,0.1)',
                    border: '1px solid rgba(149,145,244,0.2)',
                    cursor: 'pointer',
                    color: '#9591F4',
                    transition: 'all 0.2s',
                  }}
                >
                  <MicIcon />
                </button>

                {/* Send */}
                <button
                  onClick={handleSend}
                  disabled={(!inputValue.trim() && attachedPhotos.length === 0) || isSending || isUploading}
                  style={{
                    flexShrink: 0,
                    width: '32px',
                    height: '32px',
                    borderRadius: '9px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background:
                      (inputValue.trim() || attachedPhotos.length > 0) && !isSending && !isUploading
                        ? 'linear-gradient(135deg, #5A5BBD, #9591F4)'
                        : 'rgba(90,91,189,0.15)',
                    border: 'none',
                    cursor: (inputValue.trim() || attachedPhotos.length > 0) && !isSending ? 'pointer' : 'default',
                    color: (inputValue.trim() || attachedPhotos.length > 0) && !isSending ? 'white' : 'rgba(149,145,244,0.4)',
                    transition: 'all 0.2s',
                    boxShadow:
                      (inputValue.trim() || attachedPhotos.length > 0) && !isSending
                        ? '0 2px 8px rgba(90,91,189,0.4)'
                        : 'none',
                  }}
                >
                  {isSending || isUploading ? (
                    <div
                      style={{
                        width: '14px',
                        height: '14px',
                        border: '2px solid rgba(255,255,255,0.3)',
                        borderTopColor: 'white',
                        borderRadius: '50%',
                      }}
                      className="animate-spin"
                    />
                  ) : (
                    <SendIcon />
                  )}
                </button>
              </div>

              {/* Powered-by footer */}
              <div
                style={{
                  textAlign: 'center',
                  marginTop: '8px',
                  fontSize: '10px',
                  color: 'rgba(192,202,199,0.45)',
                  letterSpacing: '0.3px',
                }}
              >
                Aanandi AI · Enterprise Sales Intelligence
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* ── Inline SVG Icons ─────────────────────────────────────────────── */
function PaperclipIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="22" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 2-7 20-4-9-9-4Z" />
      <path d="M22 2 11 13" />
    </svg>
  );
}
