import React, { useEffect, useRef } from 'react';
import { CheckCheck, Clock, AlertCircle } from 'lucide-react';
import type { Message } from '../types';
import ActionCards from './ActionCards';

interface MessageListProps {
  messages: Message[];
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  onSendMessage?: (text: string) => Promise<void>;
  onOpenVoice?: () => void;
}

export default function MessageList({
  messages,
  sessionId,
  leadId,
  apiBase,
  onSendMessage,
  onOpenVoice,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Track which messages contain typing indicator (last assistant msg with no content)
  const lastMsg = messages[messages.length - 1];
  const showTyping =
    lastMsg?.role === 'assistant' &&
    lastMsg.content === '__typing__';

  const visibleMessages = messages.filter((m) => m.content !== '__typing__');

  return (
    <div
      ref={containerRef}
      style={{
        height: '100%',
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: '16px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      {/* Date header */}
      <div style={{ textAlign: 'center', marginBottom: '4px' }}>
        <span
          style={{
            fontSize: '10px',
            fontWeight: 600,
            color: 'rgba(192,202,199,0.5)',
            background: 'rgba(0,0,0,0.2)',
            padding: '3px 10px',
            borderRadius: '100px',
            letterSpacing: '0.5px',
            textTransform: 'uppercase',
          }}
        >
          {new Date().toLocaleDateString('en-IN', { weekday: 'long', month: 'short', day: 'numeric' })}
        </span>
      </div>

      {visibleMessages.map((msg, i) => (
        <MessageBubble
          key={msg.id}
          msg={msg}
          sessionId={sessionId}
          leadId={leadId}
          apiBase={apiBase}
          isLatest={i === visibleMessages.length - 1}
          onSendMessage={onSendMessage}
          onOpenVoice={onOpenVoice}
        />
      ))}

      {/* Typing indicator */}
      {showTyping && (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            gap: '8px',
            animation: 'msg-in-left 0.28s ease both',
          }}
        >
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontWeight: 800,
              color: 'white',
              flexShrink: 0,
            }}
          >
            A
          </div>
          <div
            className="msg-assistant"
            style={{
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

/* ── Single Message Bubble ────────────────────────────────────────── */
interface BubbleProps {
  msg: Message;
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  isLatest: boolean;
  onSendMessage?: (text: string) => Promise<void>;
  onOpenVoice?: () => void;
}

function MessageBubble({
  msg,
  sessionId,
  leadId,
  apiBase,
  isLatest,
  onSendMessage,
  onOpenVoice,
}: BubbleProps) {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div style={{ textAlign: 'center' }}>
        <span
          style={{
            fontSize: '11px',
            color: 'rgba(192,202,199,0.5)',
            background: 'rgba(0,0,0,0.15)',
            padding: '3px 10px',
            borderRadius: '100px',
          }}
        >
          {msg.content}
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        gap: '4px',
        animation: isUser ? 'msg-in-right 0.28s ease both' : 'msg-in-left 0.28s ease both',
      }}
    >
      {/* Avatar (assistant only) */}
      {!isUser && (
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontWeight: 800,
              color: 'white',
              flexShrink: 0,
            }}
          >
            A
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {/* Main bubble */}
            <div
              className="msg-assistant"
              style={{ padding: '10px 14px', maxWidth: '280px' }}
            >
              <div className="msg-content">
                <MarkdownRenderer text={msg.content} />
              </div>

              {/* Tool payload action card */}
              {msg.toolPayload && (
                <div style={{ marginTop: '10px' }}>
                  <ActionCards
                    payload={msg.toolPayload}
                    sessionId={sessionId}
                    leadId={leadId}
                    apiBase={apiBase}
                    onSendMessage={onSendMessage}
                    onOpenVoice={onOpenVoice}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* User bubble */}
      {isUser && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <div
            className="msg-user"
            style={{ padding: '10px 14px', maxWidth: '280px' }}
          >
            {msg.attachments && msg.attachments.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: msg.content ? '8px' : '0' }}>
                {msg.attachments.map((attUrl, i) => (
                  <a
                    key={attUrl + i}
                    href={attUrl.startsWith('/') ? `${apiBase}${attUrl}` : attUrl}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      display: 'block',
                      width: '72px',
                      height: '72px',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      border: '1px solid rgba(255,255,255,0.2)',
                      boxShadow: '0 2px 6px rgba(0,0,0,0.3)',
                    }}
                  >
                    <img
                      src={attUrl.startsWith('/') ? `${apiBase}${attUrl}` : attUrl}
                      alt="Project requirement"
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </a>
                ))}
              </div>
            )}
            {msg.content && (
              <div className="msg-content">
                <MarkdownRenderer text={msg.content} />
              </div>
            )}
          </div>

          {/* Status row */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              paddingRight: '4px',
            }}
          >
            <span
              style={{
                fontSize: '10px',
                color: 'rgba(192,202,199,0.45)',
              }}
            >
              {msg.timestamp.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
            </span>
            <StatusIcon status={msg.status} />
          </div>
        </div>
      )}

      {/* Timestamp for assistant */}
      {!isUser && (
        <span
          style={{
            fontSize: '10px',
            color: 'rgba(192,202,199,0.4)',
            paddingLeft: '36px',
          }}
        >
          {msg.timestamp.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
        </span>
      )}
    </div>
  );
}

/* ── Status Icon ──────────────────────────────────────────────────── */
function StatusIcon({ status }: { status: Message['status'] }) {
  if (status === 'sending') {
    return (
      <div
        style={{
          width: '10px',
          height: '10px',
          border: '1.5px solid rgba(149,145,244,0.4)',
          borderTopColor: '#9591F4',
          borderRadius: '50%',
        }}
        className="animate-spin"
      />
    );
  }
  if (status === 'error') {
    return <AlertCircle size={10} color="#EF4444" />;
  }
  // delivered
  return <CheckCheck size={10} color="#9591F4" />;
}

/* ── Simple Markdown Renderer ─────────────────────────────────────── */
function MarkdownRenderer({ text }: { text: string }) {
  // Parse basic markdown: **bold**, *italic*, `code`, lists
  const lines = text.split('\n');

  return (
    <>
      {lines.map((line, i) => {
        // Unordered list item
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '3px' }}>
              <span style={{ color: '#9591F4', flexShrink: 0, marginTop: '1px' }}>•</span>
              <span>{parseInline(line.slice(2))}</span>
            </div>
          );
        }
        // Ordered list item
        if (/^\d+\.\s/.test(line)) {
          const dotIdx = line.indexOf('. ');
          const num = line.slice(0, dotIdx);
          const rest = line.slice(dotIdx + 2);
          return (
            <div key={i} style={{ display: 'flex', gap: '6px', marginBottom: '3px' }}>
              <span style={{ color: '#9591F4', flexShrink: 0 }}>{num}.</span>
              <span>{parseInline(rest)}</span>
            </div>
          );
        }
        // Heading level 3
        if (line.startsWith('### ')) {
          return (
            <p key={i} style={{ fontWeight: 700, fontSize: '13px', color: '#DBD7FA', marginBottom: '4px' }}>
              {parseInline(line.slice(4))}
            </p>
          );
        }
        // Empty line → spacer
        if (line.trim() === '') {
          return <div key={i} style={{ height: '6px' }} />;
        }
        // Normal paragraph
        return (
          <p key={i} style={{ marginBottom: i < lines.length - 1 ? '4px' : '0' }}>
            {parseInline(line)}
          </p>
        );
      })}
    </>
  );
}

/** Inline markdown: **bold**, *italic*, `code` */
function parseInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Regex: **bold** | *italic* | `code`
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) {
      parts.push(text.slice(last, match.index));
    }
    if (match[2]) {
      parts.push(<strong key={match.index} style={{ fontWeight: 700, color: '#DBD7FA' }}>{match[2]}</strong>);
    } else if (match[3]) {
      parts.push(<em key={match.index} style={{ fontStyle: 'italic', color: '#C0CAC7' }}>{match[3]}</em>);
    } else if (match[4]) {
      parts.push(
        <code key={match.index} style={{
          background: 'rgba(0,0,0,0.3)',
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '12px',
          fontFamily: 'monospace',
          color: '#FAD800',
        }}>
          {match[4]}
        </code>
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    parts.push(text.slice(last));
  }
  return parts;
}
