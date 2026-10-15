"""
MongoDB Atlas Initialization & Index Management Script
Creates all required compound B-Tree indexes, unique constraints,
and seeds initial knowledge chunks for Vector Search.
"""

import os
import sys
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv, find_dotenv

# Ensure backend directory is in python path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

load_dotenv(find_dotenv(usecwd=True))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from models import ALL_DOCUMENT_MODELS, KnowledgeChunk, Lead, Conversation, FollowUpQueue
from pymongo import ASCENDING, DESCENDING, IndexModel

ATLAS_VECTOR_SEARCH_INDEX_JSON = {
    "name": "vector_index",
    "type": "vectorSearch",
    "definition": {
        "fields": [
            {
                "type": "vector",
                "path": "embedding",
                "numDimensions": 1536,
                "similarity": "cosine"
            },
            {
                "type": "filter",
                "path": "category"
            }
        ]
    }
}

SEED_KNOWLEDGE = [
    {
        "title": "Aanandi TechnoSoft Overview & Core Capabilities",
        "category": "capabilities",
        "content": (
            "Aanandi TechnoSoft LLP (https://aanandi.in) is an elite AI-Powered Product Engineering and Digital Growth Partner. "
            "With 15+ years of engineering experience, 500+ completed projects, and 160K+ users globally, we build scalable mobile apps, "
            "enterprise SaaS platforms, and intelligent workflow automations across Sales, Support, Finance, and Operations. "
            "Backed by ISO 27001 Certification, CMMI Level 3 maturity, and GDPR, HIPAA, and SOC2 compliance."
        )
    },
    {
        "title": "Aanandi Portfolio: 9 Live Commercial Platforms",
        "category": "portfolio",
        "content": (
            "Aanandi TechnoSoft has engineered and deployed 9 live commercial platforms with verified web demos and Google Play Store apps: "
            "Uclean Laundry (on-demand laundry booking & tracking), Swagmee Fashion (mobile fashion discovery & 1-click checkout), "
            "Jotno Patient (healthcare EHR, patient records & clinic workflows), Wedding Gallery (digital wedding planning & RSVP), "
            "HungerGo Food (real-time food delivery & dispatch), Careasy Customer (automotive & home repair booking), "
            "VHelp (vetted emergency & community support), Service Plug (multi-category enterprise service dispatch), and "
            "Grocery Delivery (multi-hub dark store inventory & rapid delivery routing)."
        )
    },
    {
        "title": "FinTech Lead Qualification & Revenue Operations",
        "category": "case_studies",
        "content": (
            "Case Study: 52% improvement in qualified lead conversion for a FinTech platform through automated lead scoring, "
            "enrichment workflows, and intelligent CRM routing to advisors within 90 seconds. Eliminated manual data entry and "
            "accelerated prospect handoffs."
        )
    },
    {
        "title": "Customer Support AI Triage & Resolution",
        "category": "case_studies",
        "content": (
            "Case Study: 52% faster ticket resolution and cleaner support queues by deploying AI ticket classification, "
            "knowledge base synthesis, and smart routing to specialized human agents for complex escalations."
        )
    },
    {
        "title": "FinTech Loan Processing Automation",
        "category": "case_studies",
        "content": (
            "Case Study: 38% faster resolution in loan processing through automated document extraction, automated eligibility checks, "
            "and bi-directional CRM orchestration, saving loan officers 3+ hours daily."
        )
    }
]

async def init_mongodb():
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB_NAME", "aanandi_sales")
    
    print(f"[*] Connecting to MongoDB at {mongo_url} (Database: {db_name})...")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=4000)
    db = client[db_name]

    try:
        await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
        print("[+] Beanie ODM initialized successfully.")

        # 1. Compound B-Tree Index for Sub-Millisecond 90s Cron Sweeps
        try:
            print("[*] Creating compound index on follow_up_queue (status, scheduled_at)...")
            await db["follow_up_queue"].create_index(
                [("status", ASCENDING), ("scheduled_at", ASCENDING)],
                name="idx_status_scheduled_at"
            )
        except Exception as e:
            print(f"[i] follow_up_queue index notice: {e}")

        # 2. Unique index on Lead emails
        try:
            print("[*] Creating unique index on leads (email)...")
            await db["leads"].create_index(
                [("email", ASCENDING)],
                unique=True,
                name="uniq_lead_email"
            )
        except Exception as e:
            print(f"[i] leads index notice: {e}")

        # 3. Unique index on Conversations session_id
        try:
            print("[*] Creating unique index on conversations (session_id)...")
            await db["conversations"].create_index(
                [("session_id", ASCENDING)],
                unique=True,
                name="uniq_conversation_session_id"
            )
        except Exception as e:
            print(f"[i] conversations index notice: {e}")

        # 4. Unique index on Payment Transactions order_id
        try:
            print("[*] Creating unique index on payment_transactions (order_id)...")
            await db["payment_transactions"].create_index(
                [("order_id", ASCENDING)],
                unique=True,
                name="uniq_payment_order_id"
            )
        except Exception as e:
            print(f"[i] payment_transactions index notice: {e}")

        # 5. Indexes on Booking Records and Call Logs
        try:
            print("[*] Creating lookup indexes on booking_records and call_logs...")
            await db["booking_records"].create_index([("session_id", ASCENDING)], name="idx_booking_session_id")
            await db["call_logs"].create_index([("session_id", ASCENDING)], name="idx_call_session_id")
        except Exception as e:
            print(f"[i] lookup indexes notice: {e}")

        # 6. Seed Knowledge Chunks for Vector Search if empty
        existing_chunks = await KnowledgeChunk.count()
        print(f"[*] Knowledge chunks in database: {existing_chunks}")
        if existing_chunks == 0:
            print("[*] Seeding initial knowledge chunks...")
            openai_key = os.getenv("OPENAI_API_KEY", "")
            embeddings_model = None
            if openai_key and not openai_key.startswith("sk-dummy"):
                try:
                    from langchain_openai import OpenAIEmbeddings
                    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_key)
                except Exception as e:
                    print(f"[!] Embeddings model initialization notice: {e}")

            for item in SEED_KNOWLEDGE:
                vec = [0.0] * 1536
                if embeddings_model:
                    try:
                        vec = await embeddings_model.aembed_query(item["content"])
                    except Exception:
                        vec = [0.0] * 1536
                
                chunk = KnowledgeChunk(
                    title=item["title"],
                    content=item["content"],
                    category=item["category"],
                    embedding=vec,
                    created_at=datetime.now(timezone.utc)
                )
                await chunk.insert()
            print(f"[+] Seeded {len(SEED_KNOWLEDGE)} knowledge chunks.")

        print("\n" + "=" * 60)
        print("MongoDB Atlas Vector Search Index Configuration:")
        print("=" * 60)
        import json
        print(json.dumps(ATLAS_VECTOR_SEARCH_INDEX_JSON, indent=2))
        print("=" * 60)
        print("[SUCCESS] MongoDB initialization and indexing completed successfully.\n")

    except Exception as e:
        print(f"\n[!] Note: Could not connect to MongoDB cluster at {mongo_url}: {e}")
        print("[!] When deploying to Atlas M10+, provide MONGODB_URL in your .env file.")
        print("\n" + "=" * 60)
        print("MongoDB Atlas Vector Search Index JSON (to paste into Atlas JSON editor):")
        print("=" * 60)
        import json
        print(json.dumps(ATLAS_VECTOR_SEARCH_INDEX_JSON, indent=2))
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(init_mongodb())
