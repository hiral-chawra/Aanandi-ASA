// Shared types used across the entire Aanandi widget

export type UIMode = 'idle' | 'chat' | 'voice' | 'modal';

export type CallStatus =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'ended';

export type WSStatus = 'connecting' | 'open' | 'closed' | 'error';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  status: 'sending' | 'delivered' | 'error';
  timestamp: Date;
  toolPayload?: ToolPayload;
  attachments?: string[];
}

export type ToolPayloadType =
  | 'calendar'
  | 'escrow'
  | 'mcq'
  | 'call_routing'
  | 'payment_tier'
  | 'lead_form'
  | 'otp_options';

export interface ToolPayload {
  type: ToolPayloadType;
  data?: Record<string, unknown> & {
    options?: string[];
    title?: string;
    fields?: string[];
    user_email?: string;
    user_name?: string;
    tiers?: Array<{ id: 'enquiry' | 'project'; name: string; amount: number }>;
  };
}

declare global {
  interface Window {
    Razorpay: any;
  }
}

export interface LeadData {
  full_name?: string;
  email?: string;
  phone?: string;
  company?: string;
  brief?: string;
  session_id?: string;
}

export interface TimeSlot {
  start: string; // ISO 8601
  end: string;
  available: boolean;
}

export interface BookingPayload {
  slot_start: string;
  slot_end: string;
  lead_id: string;
  session_id: string;
  tier?: string;
  user_email?: string;
  user_name?: string;
}

export interface EscrowPayload {
  type: 'stripe' | 'usdc';
  amount: number;
  session_id: string;
  lead_id: string;
}

export interface WidgetConfig {
  apiBase: string;
  theme?: 'dark' | 'light';
}
