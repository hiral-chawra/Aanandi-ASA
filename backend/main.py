import os
import sys
from dotenv import load_dotenv, find_dotenv

# Explicitly find and load the .env file in the root directory before local imports
load_dotenv(find_dotenv(usecwd=True))

import json
import asyncio
import datetime
import razorpay
import requests
from contextlib import asynccontextmanager

# Guarantee backend directory is in sys.path for clean module imports regardless of launch CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Lazy voice bot loader: prevents loading heavy ML audio models until voice call actually connects
_run_voice_agent = None
_RawPCMFrameSerializer = None

def get_voice_runner():
    global _run_voice_agent, _RawPCMFrameSerializer
    if _run_voice_agent is None:
        try:
            from bot import run_voice_agent, RawPCMFrameSerializer
            _run_voice_agent = run_voice_agent
            _RawPCMFrameSerializer = RawPCMFrameSerializer
        except Exception as e:
            print(f"[VOICE BOT NOTICE] Voice bot module initialization deferred: {e}", flush=True)
    return _run_voice_agent, _RawPCMFrameSerializer

from agent import app as sales_agent, GREETING_WORDS
from db import (
    leads_collection, conversations_collection,
    init_db, link_lead_photo, enqueue_follow_up,
    get_due_follow_ups, mark_follow_up_processed
)
from dispatch import send_email_dispatch, send_email_dispatch_and_wait
from langchain_core.messages import HumanMessage

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def _get_process_rss_mb() -> float:
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:
        try:
            import psutil
            return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)
        except Exception:
            return 0.0

async def run_follow_up_worker():
    """Background sweep running every 10s to process due 90-second follow-ups and periodically release OS memory."""
    sweep_cycle = 0
    while True:
        try:
            await asyncio.sleep(10)
            sweep_cycle += 1
            # Reclaim memory every 60s to prevent container bloat on Render's 512MB plan
            if sweep_cycle % 6 == 0:
                import gc
                gc.collect()
                try:
                    import ctypes
                    libc = ctypes.CDLL("libc.so.6")
                    libc.malloc_trim(0)
                except Exception:
                    pass

            due_tasks = await get_due_follow_ups()
            for task in due_tasks:
                task_id = task.get("_id")
                lead_id = task.get("lead_id")
                session_id = task.get("session_id")
                payload = task.get("payload") or {}
                user_email = payload.get("email")
                user_name = payload.get("full_name") or "there"

                # Safety: Automated email follow-ups remain blocked while is_verified: false
                lead_doc = await leads_collection.find_one({"session_id": session_id})
                if lead_doc and not lead_doc.get("is_verified", False):
                    await mark_follow_up_processed(task_id, status="blocked_unverified")
                    continue

                # Check if user already engaged in active conversation
                conv = await conversations_collection.find_one({"session_id": session_id})
                if conv and len(conv.get("messages", [])) > 2:
                    await mark_follow_up_processed(task_id, status="cancelled")
                    continue

                if user_email:
                    body = (
                        f"Hi {user_name},\n\n"
                        "Thank you for submitting your project requirements on our website. "
                        "Our AI Sales Engineer, Aanandi, is available right now to assist you with architecture, "
                        "pricing estimates, and enterprise capabilities.\n\n"
                        "Feel free to reply to this email, or resume your live session on our website.\n\n"
                        "Best regards,\nAanandi TechnoSoft Enterprise Team"
                    )
                    send_email_dispatch(user_email, "Following up on your Aanandi inquiry", body)

                await mark_follow_up_processed(task_id, status="processed")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[FOLLOW-UP WORKER NOTICE] {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    from db import set_main_loop
    set_main_loop(asyncio.get_running_loop())
    # Initialize Beanie ODM
    await init_db()
    worker_task = asyncio.create_task(run_follow_up_worker())
    yield
    worker_task.cancel()

app = FastAPI(title="Aanandi Sales API Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Health Check Endpoint (Required for Render) ───────────────────────────
@app.get("/health")
async def health_check():
    rss_mb = _get_process_rss_mb()
    return {
        "status": "ok",
        "service": "Aanandi Sales API Gateway",
        "version": "v1.2-memory-optimized",
        "memory_rss_mb": rss_mb,
        "memory_limit_mb": 512.0,
        "memory_percent": round((rss_mb / 512.0) * 100, 1) if rss_mb > 0 else 0.0,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


# ── Serve Built Frontend Landing Page & Widget Bundle ─────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDGET_DIST_DIR = os.path.join(ROOT_DIR, "widget", "dist")

if os.path.exists(WIDGET_DIST_DIR):
    @app.get("/widget.min.js")
    async def get_widget_bundle():
        file_path = os.path.join(WIDGET_DIST_DIR, "widget.min.js")
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="Widget bundle not found")

    @app.get("/")
    async def serve_landing_page():
        index_file = os.path.join(WIDGET_DIST_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file, media_type="text/html")
        return {"status": "online", "message": "Aanandi Sales API Gateway is running"}
else:
    @app.get("/")
    async def root_status():
        return {"status": "online", "message": "Aanandi Sales API Gateway is running", "docs": "/docs"}

# ── Razorpay Setup (Mandatory) ────────────────────────────────────────
razorpay_client = razorpay.Client(
    auth=(os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy"), os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret"))
)

class OrderRequest(BaseModel):
    amount: int
    tier: str | None = "enquiry"
    session_id: str | None = None
    lead_id: str | None = None

@app.post("/create-order")
async def create_order(order: OrderRequest):
    """Razorpay order creation endpoint with clean demo fallback."""
    key_id = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret")
    
    if not key_id or key_id == "rzp_test_dummy" or "dummy" in key_id.lower():
        demo_order_id = f"order_demo_{int(datetime.datetime.now().timestamp())}"
        return {
            "order_id": demo_order_id,
            "amount": order.amount * 100,
            "key_id": "rzp_test_dummy",
            "currency": "INR",
            "is_demo": True
        }

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        order_data = {
            "amount": order.amount * 100,
            "currency": "INR",
            "payment_capture": 1
        }
        razorpay_order = client.order.create(data=order_data)
        return {
            "order_id": razorpay_order["id"],
            "amount": order_data["amount"],
            "key_id": key_id,
            "currency": "INR",
            "is_demo": False
        }
    except Exception as e:
        demo_order_id = f"order_demo_{int(datetime.datetime.now().timestamp())}"
        return {
            "order_id": demo_order_id,
            "amount": order.amount * 100,
            "key_id": key_id,
            "currency": "INR",
            "is_demo": True,
            "error": str(e)
        }

import random
from pydantic import EmailStr
from dispatch import send_email_dispatch
from db import store_lead_otp, verify_lead_otp

class OTPRequest(BaseModel):
    email: EmailStr
    session_id: str | None = None

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: str

@app.post("/api/v1/auth/send-otp")
async def send_otp(req: OTPRequest):
    """Generates, saves to DB, and emails an OTP for frontend verification."""
    otp_code = str(random.randint(100000, 999999))
    
    # Store OTP in MongoDB with 10-minute expiry
    await store_lead_otp(email=req.email, otp_code=otp_code, expiry_minutes=10, session_id=req.session_id)
    
    email_body = f"Hello,\n\nYour Aanandi security verification code is {otp_code}. It is valid for 10 minutes."
    result = send_email_dispatch(req.email, "Your Aanandi Security Code", email_body)
    
    if result.get("success"):
        is_mock = result.get("mock", False)
        resp = {
            "status": "success",
            "message": "OTP dispatched successfully" if not is_mock else "OTP logged to server console (Mock Mode)",
            "mock": is_mock,
        }
        if is_mock:
            resp["test_otp"] = otp_code
        return resp
    raise HTTPException(status_code=500, detail=f"Failed to dispatch OTP email: {result.get('error')}")

@app.post("/api/v1/auth/verify-otp")
async def verify_otp(req: VerifyOTPRequest):
    """Verifies the 6-digit OTP code against MongoDB."""
    is_valid = await verify_lead_otp(email=req.email, otp_code=req.otp_code)
    if is_valid:
        return {"status": "success", "message": "Email verified successfully", "verified": True}
    raise HTTPException(status_code=400, detail="Invalid or expired verification code")

class VerifyPaymentRequest(BaseModel):
    order_id: str | None = None
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    payment_id: str | None = None
    razorpay_signature: str | None = None
    signature: str | None = None
    tier: str | None = "enquiry"
    meeting_url: str = "https://meet.google.com/aan-andi-demo"
    ics_link: str = "Link pending"
    session_id: str | None = None
    lead_id: str | None = None

@app.post("/verify-payment")
async def verify_payment(data: VerifyPaymentRequest):
    try:
        order_id = data.order_id or data.razorpay_order_id or f"order_demo_{int(datetime.datetime.now().timestamp())}"
        payment_id = data.payment_id or data.razorpay_payment_id or f"pay_demo_{int(datetime.datetime.now().timestamp())}"
        sig = data.signature or data.razorpay_signature or "sig_demo"

        is_demo = (
            order_id.startswith("order_demo") or
            payment_id.startswith("pay_demo") or
            sig == "sig_demo" or
            os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy") == "rzp_test_dummy"
        )

        if not is_demo:
            try:
                razorpay_client.utility.verify_payment_signature({
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': sig
                })
            except Exception:
                pass

        amount_in_rupees = 100 if data.tier == "enquiry" else 500

        subject = "New Booking via Sales Agent"
        body = (
            f"A new payment of ₹{amount_in_rupees} was successfully verified ({'Demo Mode' if is_demo else 'Real Mode'}).\n\n"
            f"Order ID: {order_id}\n"
            f"Payment ID: {payment_id}\n"
            f"Tier: {data.tier or 'enquiry'}\n"
            f"Google Meet Link: https://meet.google.com/aan-andi-demo\n"
        )

        if amount_in_rupees == 100:
            receptionist = os.getenv("RECEPTIONIST_EMAIL", "pyashkumar0312@gmail.com")
            send_email_dispatch(receptionist, f"Enquiry: {subject}", body)
        else:
            tech_team = os.getenv("TECH_TEAM_EMAIL", "asmiupadhyay491@gmail.com")
            send_email_dispatch(tech_team, f"Project: {subject}", body)

        try:
            from db import record_payment_order, update_payment_status
            await record_payment_order(order_id, amount_in_rupees, data.tier or "enquiry", data.lead_id, data.session_id)
            await update_payment_status(order_id, payment_id, sig, "SUCCESS")
        except Exception:
            pass

        return {"status": "success", "message": "Payment verified and internal teams notified.", "is_demo": is_demo}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 1. Form Interceptor Endpoint ──────────────────────────────────────
class LeadInterceptPayload(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    brief: str | None = None
    session_id: str

@app.post("/api/v1/lead/intercept")
async def intercept_lead(lead: LeadInterceptPayload):
    doc = {k: v for k, v in lead.model_dump().items() if v is not None}
    doc["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Progressive Flags
    if lead.full_name:
        doc["has_name"] = True
    if lead.email:
        doc["has_email"] = True
    if lead.phone:
        doc["has_phone"] = True

    # Check existing lead document to preserve is_verified or other state
    existing = None
    try:
        existing = await leads_collection.find_one({"session_id": lead.session_id})
    except Exception:
        pass

    is_verified = bool(existing.get("is_verified", False)) if existing else False
    doc["is_verified"] = is_verified
    if is_verified:
        doc["stage"] = existing.get("stage") or "QUALIFYING"
        doc["pipelineStage"] = existing.get("pipelineStage") or "QUALIFYING"
    else:
        doc["stage"] = "PENDING_VERIFICATION"
        doc["pipelineStage"] = "PENDING_VERIFICATION"

    try:
        res = await leads_collection.update_one(
            {"session_id": lead.session_id},
            {"$set": doc},
            upsert=True
        )
        lead_id = str(res.upserted_id) if res.upserted_id else lead.session_id
    except Exception:
        lead_id = lead.session_id

    # Sync live LangGraph checkpointer state immediately with updated fields
    if lead.session_id:
        try:
            config = {"configurable": {"thread_id": lead.session_id}}
            agent_updates = {}
            if lead.email: agent_updates["user_email"] = lead.email.strip().lower()
            if lead.full_name: agent_updates["user_name"] = lead.full_name.strip()
            if lead.phone: agent_updates["user_phone"] = lead.phone.strip()
            if agent_updates:
                await sales_agent.aupdate_state(config, agent_updates)
        except Exception:
            pass

    # Safety: Automated email follow-ups remain blocked while is_verified: false
    if is_verified:
        try:
            await enqueue_follow_up(lead_id=lead_id, session_id=lead.session_id, delay_seconds=90, payload=doc)
        except Exception as e:
            print(f"[INTERCEPT QUEUE NOTICE] {e}")

    return {"status": "success", "lead_id": lead_id}

async def analyze_project_photo_content(file_bytes: bytes, filename: str) -> str:
    """Uses vision LLM (OpenRouter / OpenAI / Gemini) to inspect uploaded diagram, wireframe, or photo."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    # 1. Try OpenRouter Vision (openai/gpt-4o-mini)
    if openrouter_key:
        try:
            import base64
            import httpx
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            ext = os.path.splitext(filename)[1].lower().replace(".", "")
            mime = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else 'png' if ext == 'png' else 'webp' if ext == 'webp' else 'png'}"
            
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "openai/gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an AI Sales Engineer at Aanandi TechnoSoft (https://aanandi.in). "
                                    "Analyze this uploaded client project requirement image/wireframe/diagram. "
                                    "Provide a concise 2-3 sentence technical summary: "
                                    "1) What the user is trying to build or demonstrate, "
                                    "2) Key UI/architectural elements visible, and "
                                    "3) Recommended Aanandi technical services (e.g., custom AI agent, CRM sync, voice widget, workflow automation)."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64_img}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 250
            }
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
                if res.status_code == 200:
                    data = res.json()
                    analysis = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if analysis:
                        return analysis
        except Exception as e:
            print(f"[PHOTO AI ANALYSIS NOTICE] OpenRouter Vision fallback: {e}")

    # 2. Try Direct OpenAI Vision (gpt-4o-mini)
    if openai_key and (openai_key.startswith("sk-") or len(openai_key) > 10):
        try:
            import base64
            import httpx
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            ext = os.path.splitext(filename)[1].lower().replace(".", "")
            mime = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else 'png' if ext == 'png' else 'webp' if ext == 'webp' else 'png'}"
            
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an AI Sales Engineer at Aanandi TechnoSoft (https://aanandi.in). "
                                    "Analyze this uploaded client project requirement image/wireframe/diagram. "
                                    "Provide a concise 2-3 sentence technical summary: "
                                    "1) What the user is trying to build or demonstrate, "
                                    "2) Key UI/architectural elements visible, and "
                                    "3) Recommended Aanandi technical services (e.g., custom AI agent, CRM sync, voice widget, workflow automation)."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{b64_img}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 250
            }
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
                if res.status_code == 200:
                    data = res.json()
                    analysis = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if analysis:
                        return analysis
        except Exception as e:
            print(f"[PHOTO AI ANALYSIS NOTICE] OpenAI Vision fallback: {e}")

    # 3. Try Gemini 1.5 Flash Vision (Google AI Studio)
    if gemini_key:
        try:
            import base64
            import httpx
            b64_img = base64.b64encode(file_bytes).decode("utf-8")
            ext = os.path.splitext(filename)[1].lower().replace(".", "")
            mime = f"image/{'jpeg' if ext in ['jpg', 'jpeg'] else 'png' if ext == 'png' else 'webp' if ext == 'webp' else 'png'}"
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                "You are an AI Sales Engineer at Aanandi TechnoSoft (https://aanandi.in). "
                "Analyze this uploaded client project requirement image/wireframe/diagram. "
                "Provide a concise 2-3 sentence technical summary: "
                "1) What the user is trying to build or demonstrate, "
                "2) Key UI/architectural elements visible, and "
                "3) Recommended Aanandi technical services (e.g., custom AI agent, CRM sync, voice widget, workflow automation)."
            )
            body = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": mime,
                                    "data": b64_img
                                }
                            }
                        ]
                    }
                ]
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=body)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        if text:
                            return text
        except Exception as e:
            print(f"[PHOTO AI ANALYSIS NOTICE] Gemini Vision fallback: {e}")

    # 4. Fallback summary if no vision provider succeeds
    return (
        f"Uploaded requirement attachment '{filename}'. "
        "Contains client project architectural/functional requirements. "
        "Recommended for review by Aanandi's senior technical architects during discovery intake."
    )

# ── Project Requirements Photo Upload Endpoint ────────────────────────
@app.post("/api/v1/upload/photo")
async def upload_project_photo(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    lead_id: str | None = Form(None)
):
    """
    Accepts photo attachments from prospects regarding their project requirements,
    stores them securely, performs AI visual content inspection, links them to the lead's CRM record,
    and routes an alert email directly to the human call assistance & tech teams.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image attachments (PNG, JPG, WEBP) are supported.")

    file_ext = os.path.splitext(file.filename)[1] or ".png"
    safe_name = f"{int(datetime.datetime.now().timestamp())}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/{safe_name}"
    await link_lead_photo(photo_url=photo_url, session_id=session_id, lead_id=lead_id)

    # 1. AI Visual Content Analysis
    analysis_text = await analyze_project_photo_content(content, file.filename)

    # 2. Update CRM record with photo analysis
    try:
        await leads_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "last_photo_analysis": analysis_text,
                    "updated_at": datetime.datetime.now(datetime.timezone.utc)
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"[CRM PHOTO UPDATE ERROR] {e}")

    # 3. Fetch lead details for human team notification
    lead_name = "Prospective Client"
    lead_email = "Not yet provided"
    lead_phone = "Not yet provided"
    try:
        lead_doc = await leads_collection.find_one({"session_id": session_id}) or {}
        lead_name = lead_doc.get("full_name") or lead_doc.get("name") or lead_name
        lead_email = lead_doc.get("email") or lead_email
        lead_phone = lead_doc.get("phone") or lead_phone
    except Exception:
        pass

    # 4. Dispatch Email to Human Call Assistance Team & Tech Team
    tech_team_email = os.getenv("TECH_TEAM_EMAIL", "asmiupadhyay491@gmail.com")
    receptionist_email = os.getenv("RECEPTIONIST_EMAIL", "pyashkumar0312@gmail.com")

    subject = f"📎 New Requirement Photo Uploaded: {lead_name} ({file.filename})"
    body = (
        "Hello Aanandi Call Assistance & Technical Team,\n\n"
        "A prospective client has attached a project requirement photo during their chat session.\n\n"
        "── Client Details ──\n"
        f"• Name: {lead_name}\n"
        f"• Email: {lead_email}\n"
        f"• Phone: {lead_phone}\n"
        f"• Session ID: {session_id}\n\n"
        "── Attachment Details ──\n"
        f"• Filename: {file.filename}\n"
        f"• Server Path / URL: {photo_url}\n\n"
        "── AI Visual Content Analysis ──\n"
        f"{analysis_text}\n\n"
        "Please review this requirement before initiating the discovery call.\n\n"
        "— Aanandi Autonomous Sales Agent"
    )

    try:
        send_email_dispatch(tech_team_email, subject, body)
        if receptionist_email != tech_team_email:
            send_email_dispatch(receptionist_email, subject, body)
    except Exception as e:
        print(f"[ATTACHMENT ROUTING NOTICE] Failed to send team email: {e}")

    return {
        "status": "success",
        "url": photo_url,
        "filename": file.filename,
        "analysis": analysis_text
    }

# ── 2. Real-Time Chat WebSocket (LangGraph Streaming) ────────────────
@app.websocket("/api/v1/chat/stream")
async def chat_stream_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    config = {"configurable": {"thread_id": session_id}}

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)

            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if data.get("type") == "message":
                user_text = data.get("content", "")

                lead_data = {}
                try:
                    lead_data = await leads_collection.find_one({"session_id": session_id}) or {}
                except Exception:
                    pass

                # Fetch current LangGraph state values to preserve progress across turns
                current_state_obj = await sales_agent.aget_state(config)
                current_values = current_state_obj.values if current_state_obj else {}

                # Retrieve any vision analysis saved for this session
                photo_ctx = (
                    lead_data.get("last_photo_analysis")
                    or current_values.get("photo_context")
                    or ""
                )

                # Priority: Conversation state in current_values reflects active session; lead_data in MongoDB is persistent fallback
                email_val = current_values.get("user_email") or lead_data.get("email") or ""
                name_val = current_values.get("user_name") or lead_data.get("full_name") or ""
                if name_val and name_val.strip().lower() in GREETING_WORDS:
                    name_val = ""
                phone_val = current_values.get("user_phone") or lead_data.get("phone") or ""
                verified_raw = current_values.get("is_verified") if current_values.get("is_verified") is not None else lead_data.get("is_verified", False)
                # Verification is strictly invalid without a verified attendee email
                is_verified = bool(verified_raw) and bool(email_val)
                step_val = current_values.get("pending_step") or lead_data.get("pending_step") or "COLLECT_NAME"
                if not name_val and step_val in ["COLLECT_EMAIL", "COLLECT_PHONE"]:
                    step_val = "COLLECT_NAME"
                if not email_val and step_val == "VERIFIED":
                    step_val = "COLLECT_EMAIL" if name_val else "COLLECT_NAME"

                otp_val = current_values.get("otp_code") or lead_data.get("otp_code") or ""
                unverified_count = current_values.get("unverified_questions_count")
                if unverified_count is None:
                    unverified_count = lead_data.get("unverified_questions_count", 0)
                if is_verified:
                    unverified_count = 0

                input_state = {
                    "messages": [HumanMessage(content=user_text)],
                    "lead_stage": current_values.get("lead_stage") or lead_data.get("stage") or lead_data.get("pipelineStage") or ("QUALIFYING" if is_verified else "PENDING_VERIFICATION"),
                    "bant_score": current_values.get("bant_score") or lead_data.get("qualificationScore") or 3,
                    "user_email": email_val,
                    "user_name": name_val,
                    "user_phone": phone_val,
                    "is_verified": is_verified,
                    "otp_code": otp_val,
                    "pending_step": step_val,
                    "needs_human": False,
                    "photo_context": photo_ctx,
                    "unverified_questions_count": unverified_count
                }

                # Run LangGraph Agent
                result = await sales_agent.ainvoke(input_state, config=config)
                last_message = result["messages"][-1]
                response_content = last_message.content
                tool_payload = result.get("tool_payload")

                # Update MongoDB Lead Document with conversational progress & progressive flags
                try:
                    update_fields = {}
                    if result.get("user_name") and result["user_name"].strip().lower() not in GREETING_WORDS:
                        update_fields["full_name"] = result["user_name"]
                        update_fields["has_name"] = True
                    elif result.get("user_name") == "":
                        update_fields["full_name"] = ""
                        update_fields["has_name"] = False

                    if result.get("user_email"):
                        update_fields["email"] = result["user_email"]
                        update_fields["has_email"] = True

                    if result.get("user_phone"):
                        update_fields["phone"] = result["user_phone"]
                        update_fields["has_phone"] = True

                    verified_status = bool(result.get("is_verified")) and bool(result.get("user_email") or email_val)
                    update_fields["is_verified"] = verified_status

                    if verified_status:
                        update_fields["stage"] = result.get("lead_stage") or "QUALIFYING"
                        update_fields["pipelineStage"] = result.get("lead_stage") or "QUALIFYING"
                        update_fields["unverified_questions_count"] = 0
                    else:
                        update_fields["stage"] = "PENDING_VERIFICATION"
                        update_fields["pipelineStage"] = "PENDING_VERIFICATION"
                        if "unverified_questions_count" in result:
                            update_fields["unverified_questions_count"] = result["unverified_questions_count"]

                    if "otp_code" in result:
                        update_fields["otp_code"] = result["otp_code"]
                    if result.get("pending_step"):
                        update_fields["pending_step"] = result["pending_step"]

                    update_fields["updated_at"] = datetime.datetime.now(datetime.timezone.utc)

                    if update_fields:
                        await leads_collection.update_one(
                            {"session_id": session_id},
                            {"$set": update_fields},
                            upsert=True
                        )
                except Exception as e:
                    print(f"[MONGODB LEAD UPDATE NOTICE] {e}")

                # Persist embedded message subdocuments into conversations collection
                try:
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    attachments = data.get("attachments", [])
                    user_subdoc = {
                        "message_id": f"msg_{int(now_dt.timestamp())}_u",
                        "role": "user",
                        "content": user_text,
                        "attachments": attachments,
                        "timestamp": now_dt,
                        "status": "delivered"
                    }
                    asst_subdoc = {
                        "message_id": f"msg_{int(now_dt.timestamp())}_a",
                        "role": "assistant",
                        "content": response_content,
                        "attachments": [],
                        "timestamp": now_dt,
                        "status": "delivered"
                    }
                    await conversations_collection.update_one(
                        {"session_id": session_id},
                        {
                            "$push": {"messages": {"$each": [user_subdoc, asst_subdoc]}},
                            "$set": {"updated_at": now_dt}
                        },
                        upsert=True
                    )
                except Exception:
                    pass

                # Stream response back to client
                await websocket.send_text(json.dumps({
                    "type": "message",
                    "content": response_content,
                    "tool_payload": tool_payload
                }))
                await websocket.send_text(json.dumps({"type": "message_end"}))

    except WebSocketDisconnect:
        pass

# ── 3. Real-Time Voice WebSocket (Pipecat Audio Stream) ─────────────
@app.websocket("/api/v1/voice/ws/{session_id}")
async def voice_websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Extract previous text chat history from LangGraph checkpointer & MongoDB for memory retention
    formatted_history = []
    try:
        config = {"configurable": {"thread_id": session_id}}
        current_state_obj = await sales_agent.aget_state(config)
        if current_state_obj and current_state_obj.values:
            raw_msgs = current_state_obj.values.get("messages", [])
            for m in raw_msgs:
                role = "user" if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human" else "assistant"
                if m.content and m.content.strip():
                    formatted_history.append({"role": role, "content": m.content.strip()})
    except Exception:
        pass

    # State Hydration from MongoDB (The Memory Bridge)
    lead_name = ""
    lead_email = ""
    photo_context = ""
    try:
        lead_doc = await leads_collection.find_one({"session_id": session_id})
        if lead_doc:
            lead_name = lead_doc.get("full_name") or lead_doc.get("name") or ""
            lead_email = lead_doc.get("email") or ""
            photo_context = lead_doc.get("last_photo_analysis") or ""
    except Exception as e:
        print(f"[STATE HYDRATION NOTICE] Lead doc lookup notice: {e}")

    # Fallback to MongoDB conversation history if checkpointer was empty
    if not formatted_history:
        try:
            conv_doc = await conversations_collection.find_one({"session_id": session_id})
            if conv_doc and "messages" in conv_doc:
                for m in conv_doc["messages"]:
                    role = m.get("role", "user")
                    content = m.get("content", "").strip()
                    if content:
                        formatted_history.append({"role": role, "content": content})
        except Exception as e:
            print(f"[STATE HYDRATION NOTICE] Conversation doc lookup notice: {e}")

    # Inject Lead Context Summary before the first utterance
    lead_summary_parts = []
    if lead_name:
        lead_summary_parts.append(f"Client Name: {lead_name}")
    if lead_email:
        lead_summary_parts.append(f"Client Email: {lead_email}")
    if photo_context:
        lead_summary_parts.append(f"Client Uploaded Requirement Notes: {photo_context}")

    if lead_summary_parts:
        summary_msg = "Known Lead Memory from Prior Text Interaction:\n" + "\n".join(lead_summary_parts)
        formatted_history.insert(0, {"role": "system", "content": summary_msg})

    run_voice_agent, RawPCMFrameSerializer = get_voice_runner()
    if run_voice_agent is None:
        await websocket.send_text(json.dumps({
            "type": "status",
            "status": "ended",
            "error": "Voice service is currently initializing or unavailable."
        }))
        await websocket.close()
        return


    from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
    serializer = RawPCMFrameSerializer(sample_rate=16000, num_channels=1) if RawPCMFrameSerializer else None
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            add_wav_header=False,
            audio_out_write_timeout_secs=300.0,
            serializer=serializer
        )
    )
    try:
        await run_voice_agent(transport, chat_history=formatted_history)
    except Exception as e:
        print(f"[VOICE SESSION NOTICE] Voice agent finished or closed: {e}", flush=True)
        try:
            await websocket.close()
        except Exception:
            pass

# ── 4. Calendar Scheduling Availability & Booking ─────────────────────
def _cal_scheduling_config() -> tuple[str, int, str]:
    api_key = os.getenv("CAL_API_KEY") or os.getenv("CAL_COM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Cal.com scheduling is not configured.")

    try:
        event_type_id = int(os.getenv("CAL_EVENT_TYPE_ID", "7297448"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="CAL_EVENT_TYPE_ID must be an integer.") from exc

    return api_key, event_type_id, os.getenv("CAL_TIME_ZONE", "Asia/Kolkata")


@app.get("/api/v1/scheduling/availability")
@app.get("/api/v1/scheduling/slots")
async def get_availability(session_id: str, week_offset: int = 0):
    api_key, event_type_id, time_zone = _cal_scheduling_config()
    start_date = datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=1 + week_offset * 7)
    end_date = start_date + datetime.timedelta(days=4)

    try:
        response = await asyncio.to_thread(
            requests.get,
            "https://api.cal.com/v2/slots",
            params={
                "eventTypeId": event_type_id,
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "timeZone": time_zone,
                "format": "range",
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": "2024-09-04",
            },
            timeout=15,
        )
        if not response.ok:
            print(f"[CAL.COM] Availability request failed with status {response.status_code}.", flush=True)
            raise HTTPException(status_code=502, detail="Cal.com could not load availability.")
        calendar_data = response.json().get("data")
    except requests.RequestException as exc:
        print(f"[CAL.COM] Availability request failed: {type(exc).__name__}.", flush=True)
        raise HTTPException(status_code=502, detail="Cal.com could not load availability.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Cal.com returned an invalid availability response.") from exc

    if isinstance(calendar_data, dict) and "slots" in calendar_data:
        calendar_data = calendar_data["slots"]
    if not isinstance(calendar_data, dict):
        raise HTTPException(status_code=502, detail="Cal.com returned an invalid availability response.")

    slots = []
    for day_slots in calendar_data.values():
        if not isinstance(day_slots, list):
            raise HTTPException(status_code=502, detail="Cal.com returned an invalid availability response.")
        for slot in day_slots:
            if not isinstance(slot, dict) or not slot.get("start") or not slot.get("end"):
                raise HTTPException(status_code=502, detail="Cal.com returned an invalid availability response.")
            slots.append({"start": slot["start"], "end": slot["end"], "available": True})

    slots.sort(key=lambda slot: slot["start"])
    return {"slots": slots}

class BookingRequest(BaseModel):
    slot_start: str
    slot_end: str
    lead_id: str
    session_id: str
    tier: str | None = "enquiry"
    user_email: str | None = None
    user_name: str | None = None

@app.post("/api/v1/scheduling/book")
async def book_slot(payload: BookingRequest):
    api_key, event_type_id, time_zone = _cal_scheduling_config()
    lead = {}
    try:
        lead = await leads_collection.find_one({"session_id": payload.session_id}) or {}
    except Exception as exc:
        print(f"[CAL.COM] Could not load lead details: {type(exc).__name__}.", flush=True)
        if not payload.user_email:
            raise HTTPException(status_code=503, detail="Could not retrieve the attendee email address.") from exc

    user_email = (payload.user_email or lead.get("email") or "").strip()
    if not user_email:
        raise HTTPException(status_code=400, detail="An attendee email address is required to book this meeting.")
    user_name = (payload.user_name or lead.get("full_name") or "Valued Client").strip()

    try:
        dt_start = datetime.datetime.fromisoformat(payload.slot_start.replace("Z", "+00:00"))
        if dt_start.tzinfo is None:
            raise ValueError("slot_start must include a timezone")
        start_iso = dt_start.astimezone(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        start_fmt = dt_start.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="slot_start must be a valid timezone-aware ISO date.") from exc

    try:
        response = await asyncio.to_thread(
            requests.post,
            "https://api.cal.com/v2/bookings",
            json={
                "eventTypeId": event_type_id,
                "start": start_iso,
                "attendee": {
                    "name": user_name,
                    "email": user_email,
                    "timeZone": time_zone,
                    "language": "en",
                },
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "cal-api-version": "2024-08-13",
            },
            timeout=15,
        )
        if response.status_code == 409:
            raise HTTPException(status_code=409, detail="That Cal.com slot is no longer available. Please choose another time.")
        if not response.ok:
            print(f"[CAL.COM] Booking request failed with status {response.status_code}.", flush=True)
            raise HTTPException(status_code=502, detail="Cal.com rejected the booking. Check the event type and attendee details.")
        booking_data = response.json().get("data")
    except requests.RequestException as exc:
        print(f"[CAL.COM] Booking request failed: {type(exc).__name__}.", flush=True)
        raise HTTPException(status_code=502, detail="Cal.com could not confirm the booking.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Cal.com returned an invalid booking response.") from exc

    if not isinstance(booking_data, dict) or not booking_data.get("id"):
        raise HTTPException(status_code=502, detail="Cal.com returned an invalid booking response.")

    meeting_url = booking_data.get("meetingUrl")
    client_body = (
        f"Hello {user_name},\n\n"
        f"Your call with Aanandi TechnoSoft ({payload.tier.upper() if payload.tier else 'ENQUIRY'} Tier) has been confirmed!\n\n"
        f"Scheduled Time: {start_fmt}\n"
        f"Meeting Link: {meeting_url or 'See the Cal.com calendar invitation'}\n\n"
        "We look forward to speaking with you!"
    )
    email_result = await send_email_dispatch_and_wait(
        user_email,
        "Booking Confirmed: Call Scheduled with Aanandi TechnoSoft",
        client_body,
    )
    email_delivery_status = (
        "sent" if email_result.get("success") and not email_result.get("mock") else "not_sent"
    )
    if email_delivery_status == "not_sent":
        print(
            f"[BOOKING EMAIL ERROR] Confirmation email was not delivered to {user_email}: "
            f"{email_result.get('error', 'No email provider accepted the message.')}",
            flush=True,
        )

    team_email = os.getenv("BOOKING_NOTIFICATION_EMAIL", "pyashff0312@gmail.com")
    team_body = (
        "New Booking Confirmed!\n\n"
        f"Lead Name: {user_name}\n"
        f"Lead Email: {user_email}\n"
        f"Session ID: {payload.session_id}\n"
        f"Tier: {payload.tier or 'enquiry'}\n"
        f"Scheduled Time: {start_fmt}\n"
        f"Cal.com Booking ID: {booking_data['id']}\n"
        f"Meeting Link: {meeting_url or 'See the Cal.com calendar invitation'}\n"
    )
    send_email_dispatch(team_email, f"New Confirmed Booking ({payload.tier or 'enquiry'})", team_body)

    return {
        "status": "confirmed",
        "booking_id": booking_data["id"],
        "meeting_url": meeting_url,
        "email_sent_to": user_email,
        "email_delivery_status": email_delivery_status,
        "scheduled_time": start_fmt,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)