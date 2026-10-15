import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

MONGODB_URL = os.getenv("MONGODB_URI") or os.getenv("MONGODB_URL") or "mongodb://localhost:27017"
DATABASE_NAME = os.getenv("DATABASE_NAME") or os.getenv("MONGODB_DB_NAME") or "aanandi_sales"
client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]

# Database Collections (All 7 Core Collections)
leads_collection = db["leads"]
conversations_collection = db["conversations"]
payment_transactions_collection = db["payment_transactions"]
booking_records_collection = db["booking_records"]
follow_up_queue_collection = db["follow_up_queue"]
call_logs_collection = db["call_logs"]
knowledge_chunks_collection = db["knowledge_chunks"]

async def init_db():
    """Initializes Beanie ODM with all 7 document models."""
    try:
        from models import ALL_DOCUMENT_MODELS
        from beanie import init_beanie
        await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
        print("[DB SUCCESS] Beanie ODM initialized successfully.")
    except Exception as e:
        print(f"[DB NOTICE] Beanie initialization notice: {e}")

# In-memory fallback for when MongoDB is offline
_in_memory_otps: Dict[str, Any] = {}

# ── OTP & Lead Helpers ────────────────────────────────────────────────────────
async def store_lead_otp(email: str, otp_code: str, expiry_minutes: int = 10, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Stores a 6-digit OTP and its expiration timestamp in the leads document or in-memory fallback.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expiry_minutes)
    clean_email = email.strip().lower()
    
    update_data = {
        "email": clean_email,
        "otp_code": str(otp_code),
        "otp_expires_at": expires_at,
        "is_verified": False,
        "updated_at": now
    }
    if session_id:
        update_data["session_id"] = session_id

    _in_memory_otps[clean_email] = update_data

    try:
        result = await leads_collection.find_one_and_update(
            {"email": clean_email},
            {"$set": update_data},
            upsert=True,
            return_document=True
        )
        return result or update_data
    except Exception as e:
        print(f"[DB NOTICE] MongoDB unavailable ({e}), using in-memory OTP storage.")
        return update_data

async def verify_lead_otp(email: str, otp_code: str) -> bool:
    """
    Verifies the OTP code against MongoDB or in-memory storage.
    If valid and not expired, sets is_verified to True.
    """
    now = datetime.now(timezone.utc)
    clean_email = email.strip().lower()

    # 1. Try Mongo DB
    try:
        lead = await leads_collection.find_one({"email": clean_email})
        if lead:
            stored_otp = lead.get("otp_code")
            expires_at = lead.get("otp_expires_at")
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
                
            if stored_otp == str(otp_code) and expires_at and expires_at > now:
                await leads_collection.update_one(
                    {"_id": lead["_id"]},
                    {"$set": {"is_verified": True, "otp_code": None, "updated_at": now}}
                )
                return True
    except Exception:
        pass

    # 2. Try In-Memory Fallback
    memory_data = _in_memory_otps.get(clean_email)
    if memory_data:
        stored_otp = memory_data.get("otp_code")
        expires_at = memory_data.get("otp_expires_at")
        if stored_otp == str(otp_code) and expires_at and expires_at > now:
            memory_data["is_verified"] = True
            return True
        
    return False

# ── Payment Transactions Helpers ──────────────────────────────────────────────
async def record_payment_order(
    order_id: str,
    amount: int,
    tier: str,
    lead_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Records a new Razorpay payment order in the payment_transactions collection.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "transaction_id": order_id,
        "order_id": order_id,
        "payment_id": None,
        "signature": None,
        "amount": amount, # 100 or 500
        "currency": "INR",
        "tier": tier, # 'enquiry' or 'project'
        "status": "PENDING",
        "lead_id": lead_id,
        "session_id": session_id,
        "created_at": now,
        "updated_at": now
    }
    await payment_transactions_collection.insert_one(doc)
    return doc

async def update_payment_status(
    order_id: str,
    payment_id: str,
    signature: str,
    status: str = "SUCCESS"
) -> bool:
    """
    Updates the transaction status (SUCCESS/FAILED) after Razorpay verification.
    """
    now = datetime.now(timezone.utc)
    result = await payment_transactions_collection.update_one(
        {"order_id": order_id},
        {
            "$set": {
                "payment_id": payment_id,
                "signature": signature,
                "status": status,
                "updated_at": now
            }
        }
    )
    return result.modified_count > 0

# ── Booking Records Helpers ───────────────────────────────────────────────────
async def create_booking_record(
    meeting_type: str,
    assigned_team: str,
    lead_id: Optional[str] = None,
    session_id: Optional[str] = None,
    meeting_url: Optional[str] = None,
    start_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates a record of a booked meeting in the booking_records collection.
    """
    now = datetime.now(timezone.utc)
    doc = {
        "lead_id": lead_id,
        "session_id": session_id,
        "meeting_type": meeting_type, # 'Enquiry' or 'Project'
        "assigned_team": assigned_team, # 'receptionist' or 'technical_team'
        "meeting_url": meeting_url,
        "start_time": start_time,
        "created_at": now
    }
    await booking_records_collection.insert_one(doc)
    return doc

# ── Lead Photo Attachment Helpers ─────────────────────────────────────────────
async def link_lead_photo(photo_url: str, session_id: Optional[str] = None, lead_id: Optional[str] = None, email: Optional[str] = None) -> bool:
    """
    Links an uploaded photo URL to the lead's CRM record so AI can retrieve project requirements.
    """
    now = datetime.now(timezone.utc)
    query: Dict[str, Any] = {}
    if email:
        query["email"] = email.strip().lower()
    elif lead_id:
        query["_id"] = lead_id
    elif session_id:
        query["session_id"] = session_id
    else:
        return False

    try:
        res = await leads_collection.update_one(
            query,
            {
                "$addToSet": {"project_photos": photo_url},
                "$set": {"updated_at": now}
            },
            upsert=True
        )
        return res.acknowledged
    except Exception as e:
        print(f"[DB ERROR] Failed to link photo: {e}")
        return False

# ── Follow-Up Queue Helpers (90-Second Trigger) ──────────────────────────────
async def enqueue_follow_up(lead_id: str, session_id: str, delay_seconds: int = 90, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Schedules an automated engagement sweep task for a newly captured contact form lead.
    """
    now = datetime.now(timezone.utc)
    scheduled_at = now + timedelta(seconds=delay_seconds)
    doc = {
        "lead_id": str(lead_id),
        "session_id": str(session_id),
        "status": "pending",
        "action_type": "90s_engagement",
        "scheduled_at": scheduled_at,
        "payload": payload or {},
        "created_at": now
    }
    await follow_up_queue_collection.insert_one(doc)
    return doc

async def get_due_follow_ups() -> list:
    """Fetches all pending follow-up tasks whose scheduled time has arrived."""
    now = datetime.now(timezone.utc)
    cursor = follow_up_queue_collection.find({
        "status": "pending",
        "scheduled_at": {"$lte": now}
    })
    return await cursor.to_list(length=50)

async def mark_follow_up_processed(task_id, status: str = "processed") -> bool:
    """Marks a follow-up task as processed or cancelled."""
    now = datetime.now(timezone.utc)
    res = await follow_up_queue_collection.update_one(
        {"_id": task_id},
        {"$set": {"status": status, "processed_at": now}}
    )
    return res.modified_count > 0


