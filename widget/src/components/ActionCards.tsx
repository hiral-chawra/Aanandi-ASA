import React, { useEffect, useState } from 'react';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  Shield,
  Mic,
  PhoneCall,
  CreditCard,
  Sparkles,
  UserCheck,
  Code2,
  RefreshCw,
  Edit3,
  Mail,
  User,
  Phone,
  ArrowRight,
} from 'lucide-react';
import type { ToolPayload, TimeSlot, BookingPayload, EscrowPayload } from '../types';

interface ActionCardsProps {
  payload: ToolPayload;
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  onSendMessage?: (text: string) => Promise<void>;
  onOpenVoice?: () => void;
}

export default function ActionCards({
  payload,
  sessionId,
  leadId,
  apiBase,
  onSendMessage,
  onOpenVoice,
}: ActionCardsProps) {
  if (payload.type === 'lead_form') {
    return (
      <LeadFormCard
        payload={payload}
        sessionId={sessionId}
        apiBase={apiBase}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'otp_options') {
    return (
      <OtpOptionsCard
        payload={payload}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'mcq') {
    return (
      <MCQCard
        payload={payload}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'call_routing') {
    return (
      <CallRoutingCard
        payload={payload}
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
        onOpenVoice={onOpenVoice}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'payment_tier') {
    return (
      <RazorpayCheckoutCard
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
        attendeeEmail={payload.data?.user_email}
        attendeeName={payload.data?.user_name}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'calendar') {
    return (
      <CalendarCard
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
        attendeeEmail={payload.data?.user_email}
        attendeeName={payload.data?.user_name}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (payload.type === 'escrow') {
    return (
      <EscrowCard
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
      />
    );
  }

  return null;
}

/* ══════════════════════════════════════════════════════════════════════
   1. LEAD FORM CARD (Interactive HTML Input Boxes inside Chat Bubble)
══════════════════════════════════════════════════════════════════════ */
function LeadFormCard({
  payload,
  sessionId,
  apiBase,
  onSendMessage,
}: {
  payload: ToolPayload;
  sessionId: string;
  apiBase: string;
  onSendMessage?: (text: string) => Promise<void>;
}) {
  const fields = payload.data?.fields || ['name', 'email', 'phone'];
  const title = payload.data?.title || 'Quick Verification Details';

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    // Field validations
    if (fields.includes('name') && !name.trim()) {
      setErrorMsg('Please enter your full name');
      return;
    }
    if (fields.includes('email') && (!email.trim() || !email.includes('@') || !email.includes('.'))) {
      setErrorMsg('Please enter a valid email address');
      return;
    }
    if (fields.includes('phone') && !phone.trim()) {
      setErrorMsg('Please enter your phone number');
      return;
    }

    setIsSubmitting(true);
    try {
      // 1. Send data to Lead Interceptor API
      await fetch(`${apiBase}/api/v1/lead/intercept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          full_name: name.trim() || undefined,
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
        }),
      });

      setSubmitted(true);

      // 2. Dispatch combined message to websocket stream
      if (onSendMessage) {
        let textMsg = '';
        if (fields.length === 1 && fields[0] === 'email') {
          textMsg = email.trim();
        } else if (fields.length === 1 && fields[0] === 'phone') {
          textMsg = phone.trim();
        } else if (fields.length === 1 && fields[0] === 'name') {
          textMsg = name.trim();
        } else {
          textMsg = `My details - Name: ${name.trim()}, Email: ${email.trim()}, Phone: ${phone.trim()}`;
        }
        await onSendMessage(textMsg);
      }
    } catch {
      setErrorMsg('Submission failed. Please try again.');
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <CardShell title="Details Submitted" icon={<CheckCircle size={14} color="#22C55E" />}>
        <div style={{ textAlign: 'center', padding: '6px 0', color: '#22C55E', fontSize: '12px', fontWeight: 600 }}>
          ✓ Information updated! Processing verification…
        </div>
      </CardShell>
    );
  }

  return (
    <CardShell title={title} icon={<UserCheck size={14} color="#9591F4" />}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Name input */}
        {fields.includes('name') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: '#DBD7FA', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <User size={12} color="#9591F4" /> Full Name
            </label>
            <input
              type="text"
              placeholder="e.g. Rahul Sharma"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '10px',
                background: 'rgba(10,24,56,0.8)',
                border: '1px solid rgba(149,145,244,0.3)',
                color: '#ffffff',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>
        )}

        {/* Email input */}
        {fields.includes('email') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: '#DBD7FA', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Mail size={12} color="#9591F4" /> Email Address
            </label>
            <input
              type="email"
              placeholder="e.g. rahul@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '10px',
                background: 'rgba(10,24,56,0.8)',
                border: '1px solid rgba(149,145,244,0.3)',
                color: '#ffffff',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>
        )}

        {/* Phone input */}
        {fields.includes('phone') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label style={{ fontSize: '11px', fontWeight: 600, color: '#DBD7FA', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Phone size={12} color="#9591F4" /> Phone Number
            </label>
            <input
              type="tel"
              placeholder="e.g. +91 9876543210"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={isSubmitting}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '10px',
                background: 'rgba(10,24,56,0.8)',
                border: '1px solid rgba(149,145,244,0.3)',
                color: '#ffffff',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>
        )}

        {errorMsg && (
          <div style={{ fontSize: '11px', color: '#EF4444', textAlign: 'center', marginTop: '2px' }}>
            {errorMsg}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          style={{
            marginTop: '4px',
            width: '100%',
            padding: '10px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
            border: 'none',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '13px',
            cursor: isSubmitting ? 'default' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            boxShadow: '0 4px 14px rgba(90,91,189,0.35)',
            transition: 'all 0.2s ease',
          }}
        >
          {isSubmitting ? (
            <>
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTopColor: '#ffffff',
                  borderRadius: '50%',
                }}
                className="animate-spin"
              />
              Submitting…
            </>
          ) : (
            <>
              Verify & Continue <ArrowRight size={14} />
            </>
          )}
        </button>
      </form>
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   2. OTP OPTIONS CARD (Escape Hatch for Resend / Change Email)
══════════════════════════════════════════════════════════════════════ */
function OtpOptionsCard({
  payload,
  onSendMessage,
}: {
  payload: ToolPayload;
  onSendMessage?: (text: string) => Promise<void>;
}) {
  const [otpCode, setOtpCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const targetEmail = (payload.data?.user_email as string) || 'your email';

  const handleVerify = async () => {
    const code = otpCode.replace(/\D/g, '').trim();
    if (code.length !== 6 || isSubmitting) return;
    setIsSubmitting(true);
    try {
      if (onSendMessage) {
        await onSendMessage(code);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (onSendMessage) {
      await onSendMessage('resend code');
    }
  };

  const handleChangeEmail = async () => {
    if (onSendMessage) {
      await onSendMessage('change email');
    }
  };

  return (
    <CardShell title="6-Digit Verification Code" icon={<Shield size={14} color="#FAD800" />}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <p style={{ fontSize: '11px', color: '#DBD7FA', margin: 0, lineHeight: '1.4' }}>
          Code sent to: <strong style={{ color: '#ffffff' }}>{targetEmail}</strong>
        </p>

        {/* Input box for 6-digit OTP */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            maxLength={6}
            placeholder="123456"
            value={otpCode}
            onChange={(e) => setOtpCode(e.target.value)}
            style={{
              flex: 1,
              padding: '9px 12px',
              borderRadius: '10px',
              background: 'rgba(10,24,56,0.8)',
              border: '1px solid rgba(149,145,244,0.3)',
              color: '#FAD800',
              fontSize: '15px',
              fontWeight: 700,
              letterSpacing: '3px',
              textAlign: 'center',
              outline: 'none',
            }}
          />
          <button
            onClick={handleVerify}
            disabled={otpCode.length !== 6 || isSubmitting}
            style={{
              padding: '9px 14px',
              borderRadius: '10px',
              background:
                otpCode.length === 6
                  ? 'linear-gradient(135deg, #5A5BBD, #9591F4)'
                  : 'rgba(149,145,244,0.15)',
              border: 'none',
              color: otpCode.length === 6 ? '#ffffff' : 'rgba(255,255,255,0.4)',
              fontWeight: 700,
              fontSize: '12px',
              cursor: otpCode.length === 6 ? 'pointer' : 'default',
            }}
          >
            Verify
          </button>
        </div>

        {/* Escape Hatch Buttons */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
          <button
            onClick={handleResend}
            style={{
              padding: '8px 10px',
              borderRadius: '9px',
              background: 'rgba(149,145,244,0.1)',
              border: '1px solid rgba(149,145,244,0.25)',
              color: '#DBD7FA',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(149,145,244,0.2)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(149,145,244,0.1)';
            }}
          >
            <RefreshCw size={12} color="#9591F4" /> Resend Code
          </button>

          <button
            onClick={handleChangeEmail}
            style={{
              padding: '8px 10px',
              borderRadius: '9px',
              background: 'rgba(250,216,0,0.08)',
              border: '1px solid rgba(250,216,0,0.25)',
              color: '#FAD800',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '5px',
              transition: 'all 0.2s ease',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(250,216,0,0.15)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(250,216,0,0.08)';
            }}
          >
            <Edit3 size={12} color="#FAD800" /> Change Email
          </button>
        </div>
      </div>
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   3. MCQ CARD (Clickable Options)
══════════════════════════════════════════════════════════════════════ */
function MCQCard({
  payload,
  onSendMessage,
}: {
  payload: ToolPayload;
  onSendMessage?: (text: string) => Promise<void>;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const options: string[] =
    payload.data?.options && Array.isArray(payload.data.options) && payload.data.options.length > 0
      ? payload.data.options
      : [
          'Which projects have you made so far?',
          'Tell me about Custom CRM Integrations',
          'How do AI Voice Bots work?',
          'Talk to AI or Book Call',
        ];

  const title = payload.data?.title || 'Suggested Options';

  const handleClick = async (opt: string) => {
    if (selected) return;
    setSelected(opt);
    if (onSendMessage) {
      await onSendMessage(opt);
    }
  };

  return (
    <CardShell title={title} icon={<Sparkles size={14} color="#9591F4" />}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {options.map((optionText, idx) => {
          const isThisSelected = selected === optionText;
          return (
            <button
              key={idx}
              onClick={() => handleClick(optionText)}
              disabled={Boolean(selected)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '12px',
                background: isThisSelected
                  ? 'linear-gradient(135deg, #5A5BBD, #9591F4)'
                  : 'rgba(149,145,244,0.1)',
                border: isThisSelected
                  ? '1px solid #9591F4'
                  : '1px solid rgba(149,145,244,0.25)',
                color: isThisSelected ? '#ffffff' : '#DBD7FA',
                fontSize: '13px',
                fontWeight: 600,
                textAlign: 'left',
                cursor: selected ? 'default' : 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                boxShadow: isThisSelected ? '0 4px 14px rgba(90,91,189,0.4)' : 'none',
                opacity: selected && !isThisSelected ? 0.4 : 1,
              }}
            >
              <span>{optionText}</span>
              {isThisSelected && <CheckCircle size={14} color="#ffffff" />}
            </button>
          );
        })}
      </div>
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   4. CALL ROUTING CARD ("Talk to AI" vs "Book Human Expert")
══════════════════════════════════════════════════════════════════════ */
function CallRoutingCard({
  payload,
  sessionId,
  leadId,
  apiBase,
  onOpenVoice,
  onSendMessage,
}: {
  payload: ToolPayload;
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  onOpenVoice?: () => void;
  onSendMessage?: (text: string) => Promise<void>;
}) {
  const [step, setStep] = useState<'routing' | 'tier_select' | 'calendar' | 'checkout'>('routing');
  const [selectedTier, setSelectedTier] = useState<'enquiry' | 'project'>('enquiry');
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);

  if (step === 'checkout' && selectedSlot) {
    return (
      <RazorpayCheckoutCard
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
        tier={selectedTier}
        attendeeEmail={payload.data?.user_email}
        attendeeName={payload.data?.user_name}
        slot={selectedSlot}
        onSendMessage={onSendMessage}
      />
    );
  }

  if (step === 'calendar') {
    return (
      <CalendarCard
        sessionId={sessionId}
        leadId={leadId}
        apiBase={apiBase}
        tier={selectedTier}
        attendeeEmail={payload.data?.user_email}
        attendeeName={payload.data?.user_name}
        onSendMessage={onSendMessage}
        onSlotConfirmed={(slot) => {
          setSelectedSlot(slot);
          setStep('checkout');
        }}
      />
    );
  }

  if (step === 'tier_select') {
    return (
      <CardShell title="Select Meeting Tier" icon={<CreditCard size={14} color="#9591F4" />}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Tier 1: ₹100 Enquiry */}
          <button
            onClick={() => {
              setSelectedTier('enquiry');
              setStep('calendar');
            }}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '12px',
              background: 'rgba(149,145,244,0.1)',
              border: '1px solid rgba(149,145,244,0.3)',
              color: '#ffffff',
              cursor: 'pointer',
              textAlign: 'left',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'rgba(149,145,244,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <UserCheck size={16} color="#9591F4" />
              </div>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff' }}>
                  General Enquiry Call
                </div>
                <div style={{ fontSize: '11px', color: '#DBD7FA' }}>
                  Routed to Receptionist Team
                </div>
              </div>
            </div>
            <div
              style={{
                padding: '6px 10px',
                borderRadius: '8px',
                background: '#5A5BBD',
                color: 'white',
                fontSize: '12px',
                fontWeight: 800,
              }}
            >
              ₹100
            </div>
          </button>

          {/* Tier 2: ₹500 Project Discussion */}
          <button
            onClick={() => {
              setSelectedTier('project');
              setStep('calendar');
            }}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, rgba(250,216,0,0.15), rgba(250,216,0,0.05))',
              border: '1px solid rgba(250,216,0,0.4)',
              color: '#ffffff',
              cursor: 'pointer',
              textAlign: 'left',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'rgba(250,216,0,0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Code2 size={16} color="#FAD800" />
              </div>
              <div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff' }}>
                  Technical Project Discussion
                </div>
                <div style={{ fontSize: '11px', color: '#DBD7FA' }}>
                  Routed to Senior Tech Leads
                </div>
              </div>
            </div>
            <div
              style={{
                padding: '6px 10px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #FAD800, #E8C500)',
                color: '#00183D',
                fontSize: '12px',
                fontWeight: 800,
              }}
            >
              ₹500
            </div>
          </button>
        </div>
      </CardShell>
    );
  }

  return (
    <CardShell title="How would you like to connect?" icon={<PhoneCall size={14} color="#9591F4" />}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {/* Option A: Talk to AI */}
        <button
          onClick={onOpenVoice}
          style={{
            width: '100%',
            padding: '12px 14px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #1E3460 0%, #2D2E8B 100%)',
            border: '1px solid rgba(149,145,244,0.4)',
            color: '#ffffff',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            transition: 'all 0.2s ease',
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}
        >
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Mic size={18} color="white" />
          </div>
          <div style={{ textAlign: 'left', flex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: 700, color: '#ffffff' }}>
              Live AI Voice Call (Free)
            </div>
            <div style={{ fontSize: '11px', color: '#DBD7FA', marginTop: '2px' }}>
              Instant voice interaction · No waiting time
            </div>
          </div>
        </button>

        {/* Option B: Book Human Call */}
        <button
          onClick={() => setStep('tier_select')}
          style={{
            width: '100%',
            padding: '12px 14px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #FAD800 0%, #E8C500 100%)',
            border: 'none',
            color: '#00183D',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            transition: 'all 0.2s ease',
            boxShadow: '0 4px 16px rgba(250,216,0,0.25)',
          }}
        >
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: '#00183D',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Calendar size={18} color="#FAD800" />
          </div>
          <div style={{ textAlign: 'left', flex: 1 }}>
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#00183D' }}>
              Book Human Expert Call (Paid)
            </div>
            <div style={{ fontSize: '11px', color: '#00255C', fontWeight: 600, marginTop: '2px' }}>
              Select Date/Time first · ₹100 or ₹500 QR
            </div>
          </div>
        </button>
      </div>
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   5. CALENDAR CARD (Slot Picker - Pick Slot BEFORE Payment)
══════════════════════════════════════════════════════════════════════ */
type CalendarState = 'loading' | 'picking' | 'confirming' | 'booked' | 'error';

function CalendarCard({
  sessionId,
  leadId,
  apiBase,
  tier = 'enquiry',
  attendeeEmail,
  attendeeName,
  onSendMessage,
  onSlotConfirmed,
}: {
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  tier?: 'enquiry' | 'project';
  attendeeEmail?: string;
  attendeeName?: string;
  onSendMessage?: (text: string) => Promise<void>;
  onSlotConfirmed?: (slot: TimeSlot) => void;
}) {
  const [state, setState] = useState<CalendarState>('loading');
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  const [bookingUrl, setBookingUrl] = useState('');
  const [bookingEmail, setBookingEmail] = useState('');
  const [bookingEmailSent, setBookingEmailSent] = useState<boolean | null>(null);
  const [weekOffset, setWeekOffset] = useState(0);
  const [retryCount, setRetryCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');

  const amount = tier === 'enquiry' ? 100 : 500;

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(
          `${apiBase}/api/v1/scheduling/availability?session_id=${sessionId}&week_offset=${weekOffset}`
        );
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.detail || 'Could not load live Cal.com availability.');
        }
        const data: { slots: TimeSlot[] } = await res.json();
        setSlots(data.slots.filter((s) => s.available));
        setState('picking');
      } catch (error) {
        setSlots([]);
        setErrorMsg(error instanceof Error ? error.message : 'Could not load live Cal.com availability.');
        setState('error');
      }
    };
    setState('loading');
    load();
  }, [apiBase, sessionId, weekOffset, retryCount]);

  const handleProceedToPayment = async () => {
    if (!selectedSlot) return;
    if (onSlotConfirmed) {
      onSlotConfirmed(selectedSlot);
      return;
    }
    setState('confirming');
    try {
      const payload: BookingPayload = {
        slot_start: selectedSlot.start,
        slot_end: selectedSlot.end,
        lead_id: leadId ?? 'anonymous',
        session_id: sessionId,
        user_email: attendeeEmail,
        user_name: attendeeName,
      };
      const res = await fetch(`${apiBase}/api/v1/scheduling/book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.status !== 'confirmed') {
        throw new Error(data.detail || 'Cal.com could not confirm the booking.');
      }
      setBookingUrl(data.meeting_url ?? '#');
      setBookingEmail(data.email_sent_to || attendeeEmail || '');
      setBookingEmailSent(data.email_delivery_status === 'sent');
      setState('booked');
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Unknown error');
      setState('error');
    }
  };

  if (state === 'loading') {
    return (
      <CardShell title="Select Meeting Date & Time" icon={<Calendar size={14} />}>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '20px' }}>
          <div
            style={{
              width: '24px',
              height: '24px',
              border: '2px solid rgba(149,145,244,0.2)',
              borderTopColor: '#9591F4',
              borderRadius: '50%',
            }}
            className="animate-spin"
          />
        </div>
      </CardShell>
    );
  }

  if (state === 'booked') {
    return (
      <CardShell title="Booking Confirmed!" icon={<CheckCircle size={14} color="#22C55E" />}>
        <div style={{ textAlign: 'center', padding: '8px 0' }}>
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>🎉</div>
          <p style={{ fontSize: '12px', color: '#DBD7FA', marginBottom: '10px', lineHeight: '1.5' }}>
            {bookingEmailSent
              ? `Your demo is confirmed! A confirmation was sent to ${bookingEmail || 'your email'}. Check your spam folder if it is missing.`
              : `Your demo is confirmed, but we could not send a confirmation email to ${bookingEmail || 'your email'}. Check for the Cal.com invite or contact our team.`}
          </p>
          {bookingUrl && bookingUrl !== '#' && (
            <a
              href={bookingUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '7px 14px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
                color: 'white',
                fontSize: '12px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              View Meeting Link →
            </a>
          )}
        </div>
      </CardShell>
    );
  }

  if (state === 'error') {
    return (
      <CardShell title="Calendar Unavailable" icon={<AlertCircle size={14} color="#EF4444" />}>
        <p style={{ fontSize: '12px', color: '#DBD7FA', textAlign: 'center', marginBottom: '8px' }}>{errorMsg}</p>
        <button
          onClick={() => setRetryCount((count) => count + 1)}
          style={{
            width: '100%',
            padding: '9px',
            borderRadius: '10px',
            background: 'rgba(149,145,244,0.12)',
            border: '1px solid rgba(149,145,244,0.25)',
            color: '#DBD7FA',
            cursor: 'pointer',
            fontWeight: 700,
          }}
        >
          Retry
        </button>
      </CardShell>
    );
  }

  const byDate = slots.reduce<Record<string, TimeSlot[]>>((acc, slot) => {
    const date = new Date(slot.start).toLocaleDateString('en-IN', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    });
    if (!acc[date]) acc[date] = [];
    acc[date].push(slot);
    return acc;
  }, {});

  const dates = Object.keys(byDate);

  return (
    <CardShell title={`Pick Slot (${tier.toUpperCase()} - ₹${amount})`} icon={<Calendar size={14} color="#9591F4" />}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <button
          onClick={() => setWeekOffset((w) => Math.max(0, w - 1))}
          disabled={weekOffset === 0}
          style={{
            width: '26px',
            height: '26px',
            borderRadius: '7px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: weekOffset === 0 ? 'transparent' : 'rgba(149,145,244,0.1)',
            border: '1px solid rgba(149,145,244,0.2)',
            cursor: weekOffset === 0 ? 'not-allowed' : 'pointer',
            color: weekOffset === 0 ? 'rgba(149,145,244,0.3)' : '#9591F4',
          }}
        >
          <ChevronLeft size={14} />
        </button>
        <span style={{ fontSize: '11px', color: '#C0CAC7', fontWeight: 600 }}>
          {weekOffset === 0 ? 'This week' : `+${weekOffset} week${weekOffset > 1 ? 's' : ''}`}
        </span>
        <button
          onClick={() => setWeekOffset((w) => w + 1)}
          style={{
            width: '26px',
            height: '26px',
            borderRadius: '7px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(149,145,244,0.1)',
            border: '1px solid rgba(149,145,244,0.2)',
            cursor: 'pointer',
            color: '#9591F4',
          }}
        >
          <ChevronRight size={14} />
        </button>
      </div>

      <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {dates.length === 0 ? (
          <p style={{ fontSize: '12px', color: '#C0CAC7', textAlign: 'center', padding: '12px 0' }}>
            No available slots. Try next week →
          </p>
        ) : (
          dates.map((date) => (
            <div key={date}>
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#9591F4',
                  marginBottom: '6px',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}
              >
                {date}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '5px' }}>
                {byDate[date].map((slot) => {
                  const time = new Date(slot.start).toLocaleTimeString('en-IN', {
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true,
                  });
                  const isSelected = selectedSlot?.start === slot.start;
                  return (
                    <button
                      key={slot.start}
                      onClick={() => setSelectedSlot(isSelected ? null : slot)}
                      className={`slot-btn${isSelected ? ' selected' : ''}`}
                    >
                      {time}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {selectedSlot && (
        <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid rgba(149,145,244,0.15)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '8px' }}>
            <Clock size={12} color="#9591F4" />
            <span style={{ fontSize: '11px', color: '#DBD7FA', fontWeight: 600 }}>
              Selected: {new Date(selectedSlot.start).toLocaleString('en-IN', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: true,
              })}
            </span>
          </div>
          <button
            onClick={handleProceedToPayment}
            style={{
              width: '100%',
              padding: '10px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #FAD800, #e8c500)',
              color: '#00183D',
              border: 'none',
              fontWeight: 800,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
            }}
          >
            Lock Slot & Pay ₹{amount} via Razorpay →
          </button>
        </div>
      )}
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   6. RAZORPAY CHECKOUT CARD (QR / JS SDK Checkout AFTER Slot Selection)
══════════════════════════════════════════════════════════════════════ */
type CheckoutState = 'idle' | 'creating' | 'checkout' | 'verifying' | 'success' | 'error';

function loadRazorpayScript(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

function RazorpayCheckoutCard({
  sessionId,
  leadId,
  apiBase,
  tier = 'enquiry',
  slot,
  attendeeEmail,
  attendeeName,
  onSendMessage,
}: {
  sessionId: string;
  leadId: string | null;
  apiBase: string;
  tier?: 'enquiry' | 'project';
  slot?: TimeSlot;
  attendeeEmail?: string;
  attendeeName?: string;
  onSendMessage?: (text: string) => Promise<void>;
}) {
  const [state, setState] = useState<CheckoutState>('idle');
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [bookingDetails, setBookingDetails] = useState<{
    meetingUrl?: string;
    timeFmt?: string;
    attendeeEmail?: string;
    emailSent?: boolean;
  } | null>(null);

  const amount = tier === 'enquiry' ? 100 : 500;

  const slotTimeStr = slot
    ? new Date(slot.start).toLocaleString('en-IN', {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      })
    : 'Selected Slot';

  const handleCheckout = async () => {
    setState('creating');
    setErrorMsg('');

    try {
      // 1. Create Razorpay order
      let orderId = `order_demo_${Date.now()}`;
      let keyId = 'rzp_test_dummy';
      let currency = 'INR';

      try {
        const res = await fetch(`${apiBase}/create-order`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tier,
            amount,
            session_id: sessionId,
            lead_id: leadId,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          orderId = data.order_id || orderId;
          keyId = data.key_id || keyId;
          currency = data.currency || currency;
        }
      } catch {
        // Fallback for dev mode
      }

      // Helper function to execute post-payment booking
      const executeBooking = async (pId: string, sig: string) => {
        setState('verifying');

        // Verify Payment
        const paymentRes = await fetch(`${apiBase}/verify-payment`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            order_id: orderId,
            payment_id: pId,
            signature: sig,
            session_id: sessionId,
            lead_id: leadId,
            tier: tier,
          }),
        });
        const paymentData = await paymentRes.json().catch(() => ({}));
        if (!paymentRes.ok || paymentData.status !== 'success') {
          throw new Error(paymentData.detail || 'Payment could not be verified.');
        }

        // Call Cal.com / Booking endpoint to finalize meeting & send email calendar invite
        if (slot) {
          const bookRes = await fetch(`${apiBase}/api/v1/scheduling/book`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              slot_start: slot.start,
              slot_end: slot.end,
              lead_id: leadId || 'anonymous',
              session_id: sessionId,
              tier: tier,
              user_email: attendeeEmail,
              user_name: attendeeName,
            }),
          });
          const bookingData = await bookRes.json().catch(() => ({}));
          if (!bookRes.ok || bookingData.status !== 'confirmed') {
            throw new Error(bookingData.detail || 'Cal.com could not confirm the booking.');
          }
          setBookingDetails({
            meetingUrl: bookingData.meeting_url,
            timeFmt: bookingData.scheduled_time,
            attendeeEmail: bookingData.email_sent_to || attendeeEmail,
            emailSent: bookingData.email_delivery_status === 'sent',
          });
        }

        setState('success');

        if (onSendMessage) {
          await onSendMessage(
            `Payment of ₹${amount} confirmed for ${tier === 'enquiry' ? 'Enquiry' : 'Project'} call on ${slotTimeStr}.`
          );
        }
      };

      // Demo mode handling
      if (keyId === 'rzp_test_dummy' || orderId.startsWith('order_demo')) {
        setTimeout(async () => {
          await executeBooking(`pay_demo_${Date.now()}`, 'sig_demo');
        }, 1200);
        return;
      }

      // Real Razorpay SDK launch
      const loaded = await loadRazorpayScript();
      if (!loaded) throw new Error('Failed to load Razorpay SDK');

      setState('checkout');

      const options = {
        key: keyId,
        amount: amount * 100,
        currency: currency,
        name: 'Aanandi Sales',
        description: `${tier === 'enquiry' ? 'Enquiry' : 'Project'} Call (${slotTimeStr})`,
        order_id: orderId,
        handler: async function (response: any) {
          await executeBooking(
            response.razorpay_payment_id || `pay_${Date.now()}`,
            response.razorpay_signature || 'sig_demo'
          );
        },
        modal: {
          ondismiss: function () {
            setState('idle');
          },
        },
        theme: { color: '#5A5BBD' },
      };

      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Checkout failed');
      setState('error');
    }
  };

  if (state === 'success') {
    return (
      <CardShell title="Booking & Payment Confirmed!" icon={<CheckCircle size={14} color="#22C55E" />}>
        <div style={{ textAlign: 'center', padding: '8px 4px' }}>
          <div style={{ fontSize: '32px', marginBottom: '4px' }}>🎉</div>
          <div style={{ fontSize: '14px', fontWeight: 800, color: '#ffffff', marginBottom: '4px' }}>
            ₹{amount} Payment Verified & Meeting Booked!
          </div>
          <p style={{ fontSize: '12px', color: '#DBD7FA', margin: '0 0 10px 0', lineHeight: '1.5' }}>
            📅 <strong>{bookingDetails?.timeFmt || slotTimeStr}</strong>
            <br />
            {bookingDetails
              ? bookingDetails.emailSent
                ? `A confirmation was sent to ${bookingDetails.attendeeEmail || 'your email'}. Check your spam folder if it is missing.`
                : `We could not send a confirmation email to ${bookingDetails.attendeeEmail || 'your email'}. Check for the Cal.com invite or contact our team.`
              : 'Your payment is confirmed.'}
          </p>
          {bookingDetails?.meetingUrl && (
            <a
              href={bookingDetails.meetingUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #5A5BBD, #9591F4)',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              Join Google Meet →
            </a>
          )}
        </div>
      </CardShell>
    );
  }

  return (
    <CardShell title={`Pay ₹${amount} to Lock Slot`} icon={<CreditCard size={14} color="#FAD800" />}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ background: 'rgba(149,145,244,0.1)', padding: '10px', borderRadius: '10px', border: '1px solid rgba(149,145,244,0.2)' }}>
          <div style={{ fontSize: '11px', color: '#DBD7FA' }}>Selected Time Slot:</div>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#FAD800', marginTop: '2px' }}>
            🕒 {slotTimeStr}
          </div>
          <div style={{ fontSize: '11px', color: '#C0CAC7', marginTop: '4px' }}>
            Tier: {tier === 'enquiry' ? 'General Enquiry (₹100)' : 'Technical Project (₹500)'}
          </div>
        </div>

        <button
          onClick={handleCheckout}
          disabled={state === 'creating' || state === 'checkout' || state === 'verifying'}
          style={{
            width: '100%',
            padding: '12px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #FAD800, #E8C500)',
            border: 'none',
            color: '#00183D',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '14px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            boxShadow: '0 4px 16px rgba(250,216,0,0.3)',
          }}
        >
          {state === 'creating' || state === 'verifying' ? (
            <>
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid rgba(0,24,61,0.3)',
                  borderTopColor: '#00183D',
                  borderRadius: '50%',
                }}
                className="animate-spin"
              />
              {state === 'creating' ? 'Launching Razorpay Checkout…' : 'Verifying & Booking Cal.com…'}
            </>
          ) : (
            <>Pay ₹{amount} via Razorpay QR / Card</>
          )}
        </button>

        {errorMsg && (
          <div style={{ fontSize: '12px', color: '#EF4444', textAlign: 'center' }}>
            {errorMsg}
          </div>
        )}
      </div>
    </CardShell>
  );
}

/* ══════════════════════════════════════════════════════════════════════
   7. ESCROW CARD
══════════════════════════════════════════════════════════════════════ */
type EscrowMethod = 'stripe' | 'usdc';
type EscrowState = 'picking' | 'processing' | 'done' | 'error';

const STAKE_AMOUNTS = [5, 10, 25, 50];

function EscrowCard({
  sessionId,
  leadId,
  apiBase,
}: {
  sessionId: string;
  leadId: string | null;
  apiBase: string;
}) {
  const [method, setMethod] = useState<EscrowMethod>('stripe');
  const [amount, setAmount] = useState(10);
  const [state, setState] = useState<EscrowState>('picking');
  const [errorMsg, setErrorMsg] = useState('');
  const [intentUrl, setIntentUrl] = useState('');

  const handleCommit = async () => {
    setState('processing');
    try {
      const payload: EscrowPayload = {
        type: method,
        amount,
        session_id: sessionId,
        lead_id: leadId ?? 'anonymous',
      };
      const res = await fetch(`${apiBase}/api/v1/escrow/initialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to initialize escrow');
      const data = await res.json();
      setIntentUrl(data.checkout_url ?? data.tx_url ?? '#');
      setState('done');
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Unknown error');
      setState('error');
    }
  };

  if (state === 'done') {
    return (
      <CardShell title="Commitment Staked!" icon={<CheckCircle size={14} color="#22C55E" />}>
        <div style={{ textAlign: 'center', padding: '8px 0' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>🔒</div>
          <p style={{ fontSize: '12px', color: '#DBD7FA', marginBottom: '10px', lineHeight: '1.5' }}>
            ${amount} hold placed via {method === 'stripe' ? 'Stripe' : 'USDC on Base'}.{' '}
            <strong style={{ color: '#22C55E' }}>Fully refundable</strong> if you attend.
          </p>
          {intentUrl && intentUrl !== '#' && (
            <a
              href={intentUrl}
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '7px 14px',
                borderRadius: '8px',
                background: 'rgba(34,197,94,0.15)',
                border: '1px solid rgba(34,197,94,0.3)',
                color: '#22C55E',
                fontSize: '12px',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              View Transaction →
            </a>
          )}
        </div>
      </CardShell>
    );
  }

  return (
    <CardShell title="Commitment Stake" icon={<Shield size={14} color="#FAD800" />}>
      <div className="toggle-group" style={{ marginBottom: '12px' }}>
        <button
          className={`toggle-btn${method === 'stripe' ? ' active' : ''}`}
          onClick={() => setMethod('stripe')}
        >
          💳 Stripe (Web2)
        </button>
        <button
          className={`toggle-btn${method === 'usdc' ? ' active' : ''}`}
          onClick={() => setMethod('usdc')}
        >
          ◎ USDC (Web3)
        </button>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#9591F4', marginBottom: '6px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
          Stake Amount
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px' }}>
          {STAKE_AMOUNTS.map((amt) => (
            <button
              key={amt}
              onClick={() => setAmount(amt)}
              className={`slot-btn${amount === amt ? ' selected' : ''}`}
            >
              ${amt}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          background: 'rgba(250,216,0,0.06)',
          border: '1px solid rgba(250,216,0,0.2)',
          borderRadius: '8px',
          padding: '8px 10px',
          marginBottom: '10px',
        }}
      >
        <div style={{ display: 'flex', gap: '6px' }}>
          <Zap size={12} color="#FAD800" style={{ flexShrink: 0, marginTop: '1px' }} />
          <p style={{ fontSize: '10px', color: 'rgba(250,216,0,0.85)', lineHeight: '1.6' }}>
            <strong>Attendance Commitment:</strong> Your ${amount} is fully refunded
            within 10 minutes of joining. No-shows forfeit the stake.
          </p>
        </div>
      </div>

      {state === 'error' && (
        <p style={{ fontSize: '11px', color: '#EF4444', marginBottom: '8px', textAlign: 'center' }}>{errorMsg}</p>
      )}

      <button
        onClick={handleCommit}
        disabled={state === 'processing'}
        style={{
          width: '100%',
          padding: '10px',
          borderRadius: '10px',
          background:
            state === 'processing'
              ? 'rgba(90,91,189,0.4)'
              : 'linear-gradient(135deg, #5A5BBD, #9591F4)',
          color: 'white',
          border: 'none',
          fontWeight: 700,
          fontSize: '13px',
          cursor: state === 'processing' ? 'default' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
        }}
      >
        {state === 'processing' ? (
          <>
            <div style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%' }} className="animate-spin" />
            Processing…
          </>
        ) : (
          <>
            <Shield size={14} />
            Stake ${amount} {method === 'stripe' ? 'via Stripe' : 'in USDC'}
          </>
        )}
      </button>
    </CardShell>
  );
}

/* ── Shared card shell ────────────────────────────────────────────── */
function CardShell({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: 'linear-gradient(145deg, rgba(21,42,80,0.9) 0%, rgba(10,24,56,0.95) 100%)',
        border: '1px solid rgba(149,145,244,0.25)',
        borderRadius: '14px',
        padding: '14px',
        width: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          marginBottom: '12px',
          paddingBottom: '10px',
          borderBottom: '1px solid rgba(149,145,244,0.12)',
        }}
      >
        <span style={{ color: '#9591F4' }}>{icon}</span>
        <span style={{ fontSize: '12px', fontWeight: 700, color: '#DBD7FA', letterSpacing: '0.2px' }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}
