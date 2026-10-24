"""
backend/dispatch.py
Email dispatcher supporting:
1. Gmail REST API over HTTPS Port 443 (Primary - Bypasses Render Free Tier SMTP port blocks)
2. Standard SMTP over Port 587 (Local dev / Paid cloud fallback)
3. Resend API (HTTP fallback)
4. Console Mock Simulation (when no credentials are configured)
"""

import os
import base64
import smtplib
import threading
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Dummy / Test Domain & Address Filters ────────────────────────────────────
# Prevents sending live emails to dummy/test mailboxes during development,
# automated tests, or user trials, preventing Google Mail bounce-backs.
DUMMY_DOMAINS = {
    # RFC 2606 & RFC 6761 reserved domains
    "example.com", "example.org", "example.net", "example.edu",
    "test.com", "test.org", "test.net", "test.io", "test.co",
    "testcompany.com", "testmail.com", "testing.com",
    "patel.com", "sharma.com",
    "dummy.com", "dummy.org", "dummy.net",
    "fake.com", "fake.org", "fake.net",
    "sample.com", "sample.org", "sample.net",
    "mock.com", "mock.org", "mock.net",
    "invalid", "localhost", "test", "example",
    "none.com", "email.com",
    # Temporary / Disposable mail domains
    "mailinator.com", "tempmail.com", "10minutemail.com", "throwawaymail.com",
    "guerrillamail.com", "yopmail.com", "trashmail.com", "sharklasers.com"
}

DUMMY_TLDS = (".test", ".example", ".invalid", ".localhost", ".local")

DUMMY_USERS = {"test", "testing", "dummy", "fake", "demo", "sample", "mock", "temp"}


def is_mock_dispatch_forced() -> bool:
    """Returns True if mock email mode is explicitly activated via environment variables."""
    for var in ("MOCK_EMAIL", "TEST_MODE", "MOCK_DISPATCH", "DISABLE_REAL_EMAIL"):
        val = os.getenv(var, "").strip().lower()
        if val in ("true", "1", "yes", "on"):
            return True
    return False


def is_dummy_or_test_email(email: str) -> bool:
    """
    Detects whether an email address is a test, dummy, or disposable address
    that should NEVER be dispatched to live SMTP/Gmail/Resend networks.
    """
    if not email or not isinstance(email, str) or "@" not in email:
        return True

    clean = email.strip().lower()
    user_part, _, domain_part = clean.partition("@")

    # Reject obvious non-domains or missing TLD dot (unless local/test)
    if not domain_part or ("." not in domain_part and domain_part not in {"localhost", "invalid", "test", "example"}):
        return True

    # Check exact dummy domains
    if domain_part in DUMMY_DOMAINS:
        return True

    # Check domain substring matches
    if any(keyword in domain_part for keyword in ("testcompany", "testdomain", "fakemail", "dummydomain")):
        return True

    # Check RFC test TLDs
    if any(domain_part.endswith(tld) for tld in DUMMY_TLDS):
        return True

    # Check test usernames
    if user_part in DUMMY_USERS:
        return True

    # Check user prefix patterns (e.g. test_123, dummy_user)
    if any(user_part.startswith(prefix) for prefix in ("test_", "test.", "test-", "dummy_", "dummy.", "dummy-", "mock_", "mock.", "mock-", "fake_", "fake.", "fake-")):
        return True

    return False



def _get_gmail_access_token() -> str | None:
    """Refreshes the OAuth2 access token for the Gmail REST API."""
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    if not (client_id and client_secret and refresh_token):
        return None

    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        print(f"[GMAIL API ERROR] Failed to refresh token: {resp.text}", flush=True)
    except Exception as e:
        print(f"[GMAIL API EXCEPTION] Token refresh error: {e}", flush=True)
    return None


def _send_via_gmail_api(to_email: str, subject: str, text_content: str, html_content: str = None) -> bool:
    """Dispatches email via Gmail REST API over HTTPS port 443 (Allowed on Render Free Tier)."""
    access_token = _get_gmail_access_token()
    if not access_token:
        return False

    sender = os.getenv("GMAIL_SENDER") or os.getenv("SMTP_EMAIL", "pyashkumar0312@gmail.com")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Aanandi TechnoSoft <{sender}>"
    msg["To"] = to_email

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    if html_content:
        msg.attach(MIMEText(html_content, "html", "utf-8"))

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    api_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(api_url, headers=headers, json={"raw": raw_message}, timeout=15)
        if resp.status_code in (200, 201):
            print(f"[GMAIL API SUCCESS] Email successfully dispatched to {to_email}", flush=True)
            return True
        print(f"[GMAIL API FAILURE] HTTP {resp.status_code}: {resp.text}", flush=True)
    except Exception as e:
        print(f"[GMAIL API EXCEPTION] Failed to send: {e}", flush=True)
    return False


def _send_via_brevo_api(to_email: str, subject: str, text_content: str, html_content: str = None) -> bool:
    """Dispatches email via Brevo (Sendinblue) REST API over HTTPS port 443 (Permanent, never expires)."""
    api_key = os.getenv("BREVO_API_KEY")
    if not api_key:
        return False

    sender_email = os.getenv("BREVO_SENDER_EMAIL") or os.getenv("GMAIL_SENDER") or os.getenv("SMTP_EMAIL", "chawrahiral3@gmail.com")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Aanandi TechnoSoft")

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key.strip(),
        "content-type": "application/json",
    }
    payload = {
        "sender": {"name": sender_name, "email": sender_email.strip()},
        "to": [{"email": to_email.strip()}],
        "subject": subject,
        "textContent": text_content,
    }
    if html_content:
        payload["htmlContent"] = html_content

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        if resp.status_code in (200, 201):
            print(f"[BREVO EMAIL SENT] Real email sent via Brevo API to: {to_email}", flush=True)
            return True
        print(f"[BREVO API ERROR] Status {resp.status_code}: {resp.text}", flush=True)
    except Exception as e:
        print(f"[BREVO API EXCEPTION] Failed to send via Brevo: {e}", flush=True)
    return False


def _send_email_dispatch_sync(to_email: str, subject: str, text_content: str, html_content: str = None) -> dict:
    """
    Synchronous network worker:
    0. Intercepts dummy/test emails and mock mode (console-only simulation).
    1. Tries Gmail REST API over HTTPS (Port 443 - Bypasses Render SMTP port blocking).
    2. Falls back to raw SMTP (local dev on port 587).
    3. Falls back to Secondary SMTP.
    4. Falls back to Resend API.
    5. Falls back to console simulation.
    """
    load_dotenv(override=True)

    # 0. Intercept dummy/test emails or forced mock mode immediately
    if is_mock_dispatch_forced() or is_dummy_or_test_email(to_email):
        print("\n" + "=" * 60, flush=True)
        print(f"[DUMMY/TEST EMAIL SUPPRESSED] TO: {to_email}", flush=True)
        print(f"SUBJECT: {subject}", flush=True)
        print(f"REASON: Dummy/test email domain or mock mode enabled. Real SMTP transmission blocked.", flush=True)
        print(f"CONTENT:\n{text_content}", flush=True)
        print("=" * 60 + "\n", flush=True)
        return {
            "success": True,
            "provider": "mock_filter",
            "mock": True,
            "message": f"Real email suppressed for test/dummy address: {to_email}"
        }

    # 1. Primary: Brevo (Sendinblue) REST API over HTTPS Port 443 (Recommended - permanent key, never expires)
    if os.getenv("BREVO_API_KEY"):
        if _send_via_brevo_api(to_email, subject, text_content, html_content):
            return {"success": True, "provider": "brevo", "mock": False}
        print("[BREVO API FALLBACK] Brevo API failed, trying fallback providers...", flush=True)

    # 2. Secondary: Gmail REST API over HTTPS Port 443
    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        if _send_via_gmail_api(to_email, subject, text_content, html_content):
            return {"success": True, "provider": "gmail_rest_api", "mock": False}
        print("[GMAIL API FALLBACK] Gmail REST API failed, trying fallback providers...", flush=True)

    # 2. Fallback: Primary SMTP (e.g. Gmail SMTP port 587)
    smtp_email = os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")

    if smtp_email and smtp_password:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        from_email = os.getenv("SMTP_FROM_EMAIL", smtp_email)
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Aanandi Sales <{from_email}>"
            msg["To"] = to_email
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
            if html_content:
                msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
            print(f"[SMTP EMAIL SENT] Real email sent to: {to_email} | Subject: {subject}", flush=True)
            return {"success": True, "provider": "smtp", "mock": False}
        except Exception as e:
            print(f"[SMTP ERROR] Primary SMTP failed to send to {to_email}: {e}. Trying secondary...", flush=True)

    # 3. Fallback: Secondary SMTP
    smtp2_user = os.getenv("SMTP2_USER") or os.getenv("SMTP2_EMAIL")
    smtp2_pass = os.getenv("SMTP2_PASS") or os.getenv("SMTP2_PASSWORD")

    if smtp2_user and smtp2_pass:
        smtp2_host = os.getenv("SMTP2_HOST", "smtp.gmail.com").replace("://", "").replace("http", "").replace("https", "").strip("/")
        if not smtp2_host or smtp2_host == "gmail.com":
            smtp2_host = "smtp.gmail.com"
        smtp2_port = int(os.getenv("SMTP2_PORT", "587"))
        try:
            msg2 = MIMEMultipart("alternative")
            msg2["Subject"] = subject
            msg2["From"] = f"Aanandi Sales <{smtp2_user}>"
            msg2["To"] = to_email
            msg2.attach(MIMEText(text_content, "plain", "utf-8"))
            if html_content:
                msg2.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(smtp2_host, smtp2_port, timeout=10) as server:
                server.starttls()
                server.login(smtp2_user, smtp2_pass)
                server.send_message(msg2)
            print(f"[SMTP2 EMAIL SENT] Real email sent via Secondary SMTP to: {to_email}", flush=True)
            return {"success": True, "provider": "smtp2", "mock": False}
        except Exception as e:
            print(f"[SMTP2 ERROR] Secondary SMTP failed: {e}. Trying Resend fallback...", flush=True)

    # 4. Fallback: Resend API
    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key:
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json"
        }
        from_addr = os.getenv("RESEND_FROM_EMAIL", "Aanandi Bot <onboarding@resend.dev>")
        payload = {
            "from": from_addr,
            "to": [to_email],
            "subject": subject,
            "text": text_content
        }
        try:
            response = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=15)
            if response.status_code in [200, 201]:
                print(f"[RESEND EMAIL SENT] Real email sent via Resend API to: {to_email}", flush=True)
                return {"success": True, "provider": "resend", "mock": False}
            print(f"[RESEND API ERROR]: {response.text}", flush=True)
        except Exception as e:
            print(f"[RESEND ERROR]: {e}", flush=True)

    # 5. Fallback: Simulation / Mock Mode
    print(f"\n[MOCK EMAIL DISPATCH] TO: {to_email}\nSUBJECT: {subject}\n{text_content}\n", flush=True)
    return {
        "success": False,
        "mock": True,
        "error": "No configured email provider could deliver the message."
    }


async def send_email_dispatch_and_wait(to_email: str, subject: str, text_content: str, html_content: str = None) -> dict:
    """Send an email without blocking the event loop and return its delivery result."""
    return await asyncio.to_thread(_send_email_dispatch_sync, to_email, subject, text_content, html_content)


def send_email_dispatch(to_email: str, subject: str, text_content: str, html_content: str = None) -> dict:
    """
    Non-blocking email dispatcher. Spawns network email sending in a background daemon thread
    so the API/WebSocket loop finishes instantly without blocking the UI.
    """
    load_dotenv(override=True)

    # 0. Intercept dummy/test emails or forced mock mode immediately without spawning threads
    if is_mock_dispatch_forced() or is_dummy_or_test_email(to_email):
        print("\n" + "=" * 60, flush=True)
        print(f"[DUMMY/TEST EMAIL SUPPRESSED] TO: {to_email}", flush=True)
        print(f"SUBJECT: {subject}", flush=True)
        print(f"REASON: Dummy/test email domain or mock mode enabled. Real SMTP transmission blocked.", flush=True)
        print(f"CONTENT:\n{text_content}", flush=True)
        print("=" * 60 + "\n", flush=True)
        return {
            "success": True,
            "mock": True,
            "provider": "mock_filter",
            "message": f"Real email suppressed for test/dummy address: {to_email}"
        }

    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    smtp_email = os.getenv("SMTP_EMAIL") or os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS")
    smtp2_user = os.getenv("SMTP2_USER") or os.getenv("SMTP2_EMAIL")
    smtp2_pass = os.getenv("SMTP2_PASS") or os.getenv("SMTP2_PASSWORD")
    resend_api_key = os.getenv("RESEND_API_KEY")

    has_real_creds = bool(
        (client_id and client_secret and refresh_token) or
        (smtp_email and smtp_password) or
        (smtp2_user and smtp2_pass) or
        resend_api_key
    )

    thread = threading.Thread(
        target=_send_email_dispatch_sync,
        args=(to_email, subject, text_content, html_content),
        daemon=True
    )
    thread.start()

    return {
        "success": True,
        "mock": not has_real_creds,
        "message": "Email dispatch initiated asynchronously in background thread."
    }
