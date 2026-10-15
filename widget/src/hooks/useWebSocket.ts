import { useCallback, useEffect, useRef, useState } from 'react';
import type { Message, ToolPayloadType, WSStatus } from '../types';

interface UseWebSocketOptions {
  apiBase: string;
  sessionId: string;
  enabled: boolean;
  onMessage?: (msg: Message) => void;
}

interface UseWebSocketReturn {
  sendMessage: (text: string, attachments?: string[]) => Promise<void>;
  status: WSStatus;
  latency: number;
}

/**
 * Bidirectional text chat streaming hook.
 *
 * Connects to: WSS /api/v1/chat/stream?session_id={id}
 *
 * Protocol:
 *   - Send:    JSON { type: "message", content: string }
 *   - Receive: JSON { type: "token"|"message"|"tool"|"ping", ... }
 *
 * Streaming tokens are assembled into a single assistant message that
 * updates the UI as each token arrives (streaming experience).
 */
export function useWebSocket({
  apiBase,
  sessionId,
  enabled,
  onMessage,
}: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WSStatus>('closed');
  const [latency, setLatency] = useState<number>(0);

  // Track in-progress streaming message
  const streamingMsgRef = useRef<Message | null>(null);
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pingTimeRef = useRef<number>(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!enabled) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

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
    const url = `${wsUrl}/api/v1/chat/stream?session_id=${sessionId}`;

    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;
    setStatus('connecting');

    ws.onopen = () => {
      setStatus('open');
      // Start ping/latency measurement
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          pingTimeRef.current = Date.now();
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 5000);
    };

    ws.onclose = (ev) => {
      setStatus('closed');
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
      // Reconnect if not intentional close
      if (ev.code !== 1000 && enabled) {
        setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onmessage = (ev) => {
      try {
        const payload = JSON.parse(ev.data as string) as Record<string, unknown>;

        switch (payload.type) {
          case 'pong':
            setLatency(Date.now() - pingTimeRef.current);
            break;

          case 'token': {
            // Streaming token — append to in-progress message
            const token = payload.content as string;
            if (!streamingMsgRef.current) {
              const msg: Message = {
                id: `ai-${Date.now()}`,
                role: 'assistant',
                content: token,
                status: 'sending',
                timestamp: new Date(),
              };
              streamingMsgRef.current = msg;
              onMessageRef.current?.(msg);
            } else {
              // Update in-place by mutating ref and re-firing with same id
              streamingMsgRef.current = {
                ...streamingMsgRef.current,
                content: streamingMsgRef.current.content + token,
              };
              onMessageRef.current?.(streamingMsgRef.current);
            }
            break;
          }

          case 'message': {
            // Complete message (non-streaming)
            const msg: Message = {
              id: `ai-${Date.now()}`,
              role: 'assistant',
              content: (payload.content as string) ?? '',
              status: 'delivered',
              timestamp: new Date(),
              toolPayload: payload.tool_payload as Message['toolPayload'],
            };
            streamingMsgRef.current = null;
            onMessageRef.current?.(msg);
            break;
          }

          case 'message_end': {
            // Finalize the streaming message
            if (streamingMsgRef.current) {
              const finalMsg: Message = {
                ...streamingMsgRef.current,
                status: 'delivered',
                toolPayload: payload.tool_payload as Message['toolPayload'],
              };
              streamingMsgRef.current = null;
              onMessageRef.current?.(finalMsg);
            }
            break;
          }

          case 'tool': {
            // Backend-triggered tool event with inline action card
            const msg: Message = {
              id: `tool-${Date.now()}`,
              role: 'tool',
              content: (payload.message as string) ?? 'Here are your options:',
              status: 'delivered',
              timestamp: new Date(),
              toolPayload: {
                type: payload.tool_type as ToolPayloadType,
                data: payload.data as Record<string, unknown>,
              },
            };
            onMessageRef.current?.(msg);
            break;
          }

          default:
            break;
        }
      } catch {
        // Non-JSON message; ignore
      }
    };
  }, [apiBase, sessionId, enabled]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      wsRef.current?.close(1000, 'Component unmounting');
      wsRef.current = null;
      if (pingTimerRef.current) clearInterval(pingTimerRef.current);
    };
  }, [connect, enabled]);

  const sendMessage = useCallback(async (text: string, attachments?: string[]): Promise<void> => {
    if (wsRef.current?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected');
    }
    wsRef.current.send(JSON.stringify({ type: 'message', content: text, attachments: attachments || [] }));
    // Add a streaming typing indicator immediately
    onMessageRef.current?.({
      id: `typing-${Date.now()}`,
      role: 'assistant',
      content: '__typing__',
      status: 'sending',
      timestamp: new Date(),
    });
  }, []);

  return { sendMessage, status, latency };
}
