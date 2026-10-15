import { useEffect, useRef } from 'react';
import type { LeadData } from '../types';

interface ContactFormInterceptorProps {
  onCapture: (lead: LeadData) => void;
}

/**
 * Invisible component that listens to native DOM submit events
 * and intercepts any contact-style forms, extracting lead data
 * and routing it through the Aanandi AI flow.
 *
 * Matches forms by:
 *   - action attribute containing "/contact/"
 *   - id = "contact-form"
 *   - class containing "contact"
 *   - data-aanandi="capture" attribute
 */
export default function ContactFormInterceptor({ onCapture }: ContactFormInterceptorProps) {
  const capturedRef = useRef(false); // prevent double-fire

  useEffect(() => {
    const handleSubmit = async (event: Event) => {
      const form = event.target as HTMLFormElement | null;
      if (!form || form.tagName !== 'FORM') return;

      // ── Does this form match our interception criteria? ──────
      const action = form.getAttribute('action') ?? '';
      const id = form.id ?? '';
      const classes = form.className ?? '';
      const dataAttr = form.getAttribute('data-aanandi') ?? '';

      const isContactForm =
        action.toLowerCase().includes('/contact') ||
        id.toLowerCase().includes('contact') ||
        classes.toLowerCase().includes('contact') ||
        dataAttr === 'capture';

      if (!isContactForm) return;
      if (capturedRef.current) return; // only once per form

      // ── Prevent native submit — we handle it ────────────────
      event.preventDefault();
      event.stopPropagation();
      capturedRef.current = true;

      // Reset flag after a short window (allow future submissions)
      setTimeout(() => { capturedRef.current = false; }, 3000);

      // ── Extract form fields ──────────────────────────────────
      const data = new FormData(form);
      const get = (keys: string[]): string | undefined => {
        for (const key of keys) {
          const val = data.get(key);
          if (val && typeof val === 'string' && val.trim()) return val.trim();
        }
        return undefined;
      };

      const lead: LeadData = {
        full_name: get(['full_name', 'name', 'fullname', 'first_name', 'fname']),
        email:     get(['email', 'email_address', 'mail']),
        phone:     get(['phone', 'phone_number', 'mobile', 'tel', 'telephone']),
        company:   get(['company', 'company_name', 'organization', 'org']),
        brief:     get(['brief', 'message', 'description', 'query', 'inquiry', 'notes']),
      };

      // ── Trigger the Aanandi modal ────────────────────────────
      onCapture(lead);
    };

    // Listen on the top-level document (outside Shadow DOM)
    document.addEventListener('submit', handleSubmit, true /* capture phase */);

    return () => {
      document.removeEventListener('submit', handleSubmit, true);
    };
  }, [onCapture]);

  // No visual output
  return null;
}
