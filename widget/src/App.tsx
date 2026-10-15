import React, { useState, useCallback, useRef } from 'react';
import type { UIMode, Message, LeadData, WidgetConfig } from './types';
import ChatLauncher from './components/ChatLauncher';
import ChatWindow from './components/ChatWindow';
import CallPromptModal from './components/CallPromptModal';
import CallAIWidget from './components/CallAIWidget';
import ContactFormInterceptor from './components/ContactFormInterceptor';
import { useSessionStorage } from './hooks/useSessionStorage';
import { useWebSocket } from './hooks/useWebSocket';

interface AppProps {
  config: WidgetConfig;
}

export default function App({ config }: AppProps) {
  const { sessionId, leadId, setLeadId } = useSessionStorage();

  // ── UI state ──────────────────────────────────────────────────
  const [uiMode, setUiMode] = useState<UIMode>('idle');
  const [unreadCount, setUnreadCount] = useState(0);
  const [capturedLead, setCapturedLead] = useState<LeadData | null>(null);

  // ── Messages ──────────────────────────────────────────────────
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        "👋 Hi! I'm **Aanandi**, your AI Sales Engineer. I can help you automate workflows, book demos, and answer any product questions.\n\nHow can I help you today?",
      status: 'delivered',
      timestamp: new Date(),
    },
  ]);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  // ── WebSocket chat ─────────────────────────────────────────────
  const { sendMessage: wsSend, status: wsStatus, latency } = useWebSocket({
    apiBase: config.apiBase,
    sessionId,
    enabled: uiMode === 'chat',
    onMessage: (msg: Message) => {
      setMessages((prev) => {
        // Filter out obsolete typing indicators when real response arrives
        const clean = prev.filter((m) => m.content !== '__typing__');
        const existingIdx = clean.findIndex((m) => m.id === msg.id);
        if (existingIdx !== -1) {
          const next = [...clean];
          next[existingIdx] = msg;
          return next;
        }
        return [...clean, msg];
      });
      if (uiMode !== 'chat') setUnreadCount((c) => c + 1);
    },
  });

  // ── Handlers ──────────────────────────────────────────────────
  const openChat = useCallback(() => {
    setUiMode('chat');
    setUnreadCount(0);
  }, []);

  const closeChat = useCallback(() => {
    setUiMode('idle');
  }, []);

  const openVoice = useCallback(() => {
    setUiMode('voice');
  }, []);

  const endVoice = useCallback(() => {
    setUiMode('chat');
  }, []);

  const openModal = useCallback(() => {
    setUiMode('modal');
  }, []);

  const handleFormCapture = useCallback(
    async (lead: LeadData) => {
      setCapturedLead(lead);
      // POST lead to backend
      try {
        const res = await fetch(`${config.apiBase}/api/v1/lead/intercept`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...lead, session_id: sessionId }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.lead_id) setLeadId(data.lead_id);
        }
      } catch {
        // silently fail — don't disrupt user
      }
      setUiMode('modal');
    },
    [config.apiBase, sessionId, setLeadId],
  );

  const handleSendMessage = useCallback(
    async (text: string, attachments?: string[]) => {
      if (!text.trim() && (!attachments || attachments.length === 0)) return;

      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: text.trim(),
        attachments: attachments || [],
        status: 'sending',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Optimistic: set to delivered after WS send
      try {
        await wsSend(text.trim(), attachments);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsg.id ? { ...m, status: 'delivered' } : m,
          ),
        );
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === userMsg.id ? { ...m, status: 'error' } : m,
          ),
        );
      }
    },
    [wsSend],
  );

  const handleModalYes = useCallback(() => {
    setUiMode('voice');
  }, []);

  const handleModalNo = useCallback(() => {
    setUiMode('chat');
  }, []);

  // ── Render ────────────────────────────────────────────────────
  return (
    <>
      {/* Floating crystal launcher */}
      <ChatLauncher
        uiMode={uiMode}
        unreadCount={unreadCount}
        onClick={uiMode === 'idle' ? openChat : closeChat}
      />

      {/* Chat window */}
      {uiMode === 'chat' && (
        <ChatWindow
          messages={messages}
          wsStatus={wsStatus}
          latency={latency}
          sessionId={sessionId}
          leadId={leadId}
          apiBase={config.apiBase}
          onSendMessage={handleSendMessage}
          onOpenVoice={openVoice}
          onClose={closeChat}
        />
      )}

      {/* Pre-call opt-in modal */}
      {uiMode === 'modal' && (
        <CallPromptModal
          leadName={capturedLead?.full_name}
          onYes={handleModalYes}
          onNo={handleModalNo}
        />
      )}

      {/* Voice call widget */}
      {uiMode === 'voice' && (
        <CallAIWidget
          sessionId={sessionId}
          apiBase={config.apiBase}
          onEnd={endVoice}
        />
      )}
    </>
  );
}
