from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field
from beanie import Document, Indexed
from pymongo import IndexModel, ASCENDING, DESCENDING

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class MessageSubdoc(BaseModel):
    message_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    attachments: List[str] = Field(default_factory=list)  # URLs of uploaded project photos
    timestamp: datetime = Field(default_factory=utc_now)
    status: Optional[str] = "delivered"

class Lead(Document):
    email: Indexed(EmailStr, unique=True)
    phone: Optional[str] = None
    full_name: Optional[str] = None
    company: Optional[str] = None
    brief: Optional[str] = None
    bant_score: int = Field(default=0, ge=0, le=10)
    stage: str = Field(default="NEW_LEAD")  # NEW_LEAD, QUALIFYING, BOOKING_OFFERED, CALL_BOOKED, NURTURE, DISQUALIFIED
    is_verified: bool = False
    otp_code: Optional[str] = None
    otp_expires_at: Optional[datetime] = None
    session_id: Optional[str] = None
    project_photos: List[str] = Field(default_factory=list)  # Linked photo attachments
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "leads"
        indexes = [
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("session_id", ASCENDING)]),
            IndexModel([("stage", ASCENDING)]),
        ]

class Conversation(Document):
    session_id: Indexed(str, unique=True)
    lead_id: Optional[str] = None
    messages: List[MessageSubdoc] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "conversations"
        indexes = [
            IndexModel([("session_id", ASCENDING)], unique=True),
            IndexModel([("lead_id", ASCENDING)]),
        ]

class FollowUpQueue(Document):
    lead_id: str
    session_id: str
    status: str = Field(default="pending")  # "pending", "processed", "cancelled"
    scheduled_at: datetime
    action_type: str = Field(default="90s_engagement")
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    processed_at: Optional[datetime] = None

    class Settings:
        name = "follow_up_queue"
        indexes = [
            IndexModel([("status", ASCENDING), ("scheduled_at", ASCENDING)]),
            IndexModel([("lead_id", ASCENDING)]),
        ]

class BookingRecord(Document):
    lead_id: Optional[str] = None
    session_id: Optional[str] = None
    cal_booking_id: Optional[str] = None
    meeting_type: str = Field(default="Discovery Call")  # 'Enquiry' or 'Project'
    assigned_team: str = Field(default="technical_team")
    meeting_url: Optional[str] = None
    start_time: Optional[datetime] = None
    status: str = Field(default="confirmed")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "booking_records"
        indexes = [
            IndexModel([("lead_id", ASCENDING)]),
            IndexModel([("session_id", ASCENDING)]),
        ]

class CallLog(Document):
    session_id: str
    lead_id: Optional[str] = None
    duration_seconds: int = 0
    transcript: List[Dict[str, str]] = Field(default_factory=list)
    recording_url: Optional[str] = None
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "call_logs"
        indexes = [
            IndexModel([("session_id", ASCENDING)]),
            IndexModel([("lead_id", ASCENDING)]),
        ]

class PaymentTransaction(Document):
    order_id: Indexed(str, unique=True)
    transaction_id: Optional[str] = None
    payment_id: Optional[str] = None
    signature: Optional[str] = None
    amount: int
    currency: str = "INR"
    tier: str = "enquiry"  # "enquiry" or "project"
    status: str = Field(default="PENDING")  # "PENDING", "SUCCESS", "FAILED"
    lead_id: Optional[str] = None
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "payment_transactions"
        indexes = [
            IndexModel([("order_id", ASCENDING)], unique=True),
            IndexModel([("status", ASCENDING)]),
        ]

class KnowledgeChunk(Document):
    title: str
    content: str
    category: str = Field(default="general")
    embedding: List[float] = Field(default_factory=list)  # 1536-dimensional dense float vector
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "knowledge_chunks"
        indexes = [
            IndexModel([("category", ASCENDING)]),
            IndexModel([("title", ASCENDING)]),
        ]

ALL_DOCUMENT_MODELS = [
    Lead,
    Conversation,
    FollowUpQueue,
    BookingRecord,
    CallLog,
    PaymentTransaction,
    KnowledgeChunk,
]
