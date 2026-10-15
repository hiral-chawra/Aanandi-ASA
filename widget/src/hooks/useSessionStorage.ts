import { useCallback, useEffect, useState } from 'react';

const SESSION_KEY = 'aanandi_session_id';
const LEAD_KEY    = 'aanandi_lead_id';
const THREAD_KEY  = 'aanandi_thread_id';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function getCrossTab(key: string): string | null {
  try {
    return localStorage.getItem(key) || sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function getOrCreateSessionId(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
    if (existing) {
      sessionStorage.setItem(SESSION_KEY, existing);
      localStorage.setItem(SESSION_KEY, existing);
      return existing;
    }
    const fresh = generateId();
    sessionStorage.setItem(SESSION_KEY, fresh);
    localStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return generateId();
  }
}

function persistCrossTab(key: string, value: string) {
  try {
    sessionStorage.setItem(key, value);
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/**
 * Manages conversation persistence across browser tabs.
 * Uses shared localStorage with sessionStorage fallback and
 * listens to window storage events to synchronize changes across tabs in real-time.
 */
export function useSessionStorage() {
  const [sessionId, setSessionIdState] = useState<string>(() => getOrCreateSessionId());
  const [leadId, setLeadIdState] = useState<string | null>(() => getCrossTab(LEAD_KEY));
  const [threadId, setThreadIdState] = useState<string | null>(() => getCrossTab(THREAD_KEY));

  // Listen to storage events from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === SESSION_KEY && e.newValue) {
        setSessionIdState(e.newValue);
      } else if (e.key === LEAD_KEY) {
        setLeadIdState(e.newValue);
      } else if (e.key === THREAD_KEY) {
        setThreadIdState(e.newValue);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const setLeadId = useCallback((id: string) => {
    persistCrossTab(LEAD_KEY, id);
    setLeadIdState(id);
  }, []);

  const setThreadId = useCallback((id: string) => {
    persistCrossTab(THREAD_KEY, id);
    setThreadIdState(id);
  }, []);

  return { sessionId, leadId, threadId, setLeadId, setThreadId };
}
