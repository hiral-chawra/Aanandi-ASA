import os
import requests
import smtplib
import threading
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

def _send_email_dispatch_sync(to_email: str, subject: str, text_content: str) -> dict:
    """
    Synchronous network worker that sends an email using SMTP or Resend API.
    """
    # Reload .env on dispatch call to capture dynamically updated credentials
    load_dotenv(override=True)

    # 1. Try Standard SMTP (e.g. Gmail SMTP)
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if smtp_user and smtp_password:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        from_email = os.getenv("SMTP_FROM_EMAIL", smtp_user)
        try:
            msg = MIMEMultipart()
            msg["From"] = f"Aanandi Sales <{from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(text_content, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            print(f"[SMTP EMAIL SENT] Real email sent to: {to_email} | Subject: {subject}", flush=True)
            return {"success": True, "provider": "smtp", "mock": False}
        except Exception as e:
            print(f"[SMTP ERROR] Primary SMTP failed to send email to {to_email}: {e}. Trying secondary SMTP...", flush=True)

    # 1B. Try Secondary SMTP (SMTP2_USER / SMTP2_PASS)
    smtp2_user = os.getenv("SMTP2_USER") or os.getenv("SMTP2_EMAIL")
    smtp2_pass = os.getenv("SMTP2_PASS") or os.getenv("SMTP2_PASSWORD")

    if smtp2_user and smtp2_pass:
        smtp2_host_raw = os.getenv("SMTP2_HOST", "smtp.gmail.com")
        smtp2_host = smtp2_host_raw.replace("://", "").replace("http", "").replace("https", "").strip("/")
        if not smtp2_host or smtp2_host == "gmail.com":
            smtp2_host = "smtp.gmail.com"
        smtp2_port = int(os.getenv("SMTP2_PORT", "587"))
        try:
            msg2 = MIMEMultipart()
            msg2["From"] = f"Aanandi Sales <{smtp2_user}>"
            msg2["To"] = to_email
            msg2["Subject"] = subject
            msg2.attach(MIMEText(text_content, "plain"))

            with smtplib.SMTP(smtp2_host, smtp2_port, timeout=15) as server:
                server.starttls()
                server.login(smtp2_user, smtp2_pass)
                server.send_message(msg2)
            print(f"[SMTP2 EMAIL SENT] Real email sent via Secondary SMTP ({smtp2_user}) to: {to_email} | Subject: {subject}", flush=True)
            return {"success": True, "provider": "smtp2", "mock": False}
        except Exception as e:
            print(f"[SMTP2 ERROR] Secondary SMTP failed to send email to {to_email}: {e}. Attempting Resend API fallback...", flush=True)

    # 2. Try Resend API (Fallback or primary if no SMTP)
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
            else:
                err_text = response.text
                print(f"[RESEND API ERROR]: {err_text}", flush=True)
                return {"success": False, "error": f"Resend API Error: {err_text}", "mock": False}
        except Exception as e:
            print(f"[RESEND ERROR]: {str(e)}", flush=True)
            return {"success": False, "error": str(e), "mock": False}

    # Do not treat a logged/mock email as a delivered email.
    print(
        f"[EMAIL ERROR] No configured email provider could send a message to {to_email}.",
        flush=True,
    )
    return {
        "success": False,
        "mock": True,
        "error": "No configured email provider could send the message."
    }


async def send_email_dispatch_and_wait(to_email: str, subject: str, text_content: str) -> dict:
    """Send an email without blocking the event loop and return its delivery result."""
    load_dotenv(override=True)
    return await asyncio.to_thread(
        _send_email_dispatch_sync,
        to_email,
        subject,
        text_content,
    )


def send_email_dispatch(to_email: str, subject: str, text_content: str) -> dict:
    """
    Non-blocking email dispatcher. Spawns network email sending in a background daemon thread
    so the API/WebSocket loop finishes instantly without blocking the UI.
    """
    load_dotenv(override=True)
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp2_user = os.getenv("SMTP2_USER") or os.getenv("SMTP2_EMAIL")
    smtp2_pass = os.getenv("SMTP2_PASS") or os.getenv("SMTP2_PASSWORD")
    resend_api_key = os.getenv("RESEND_API_KEY")

    has_real_creds = bool((smtp_user and smtp_password) or (smtp2_user and smtp2_pass) or resend_api_key)

    # Spawn thread to handle network dispatch asynchronously
    thread = threading.Thread(
        target=_send_email_dispatch_sync,
        args=(to_email, subject, text_content),
        daemon=True
    )
    thread.start()

    return {
        "success": True,
        "mock": not has_real_creds,
        "message": "Email dispatch initiated asynchronously in background thread."
    }
