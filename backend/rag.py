"""
Atlas Vector Search & Knowledge Retrieval (RAG Engine)
Executes semantic and nearest-neighbor retrievals against MongoDB Atlas knowledge chunks.
Dynamically searches the ingested Website Documentation and portfolio knowledge base.
Falls back gracefully to MongoDB text search and structured portfolio knowledge.
"""

import os
import re
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

from db import knowledge_chunks_collection

# In-memory knowledge representing Aanandi TechnoSoft's actual client-facing portfolio & services
FALLBACK_KNOWLEDGE = [
    {
        "title": "Aanandi TechnoSoft Overview & Engineering Excellence",
        "category": "capabilities",
        "content": (
            "Aanandi TechnoSoft LLP (https://aanandi.in) is an elite AI-Powered Product Engineering and Digital Growth Partner. "
            "With 15+ years of engineering experience, 500+ delivered platforms, and 160K+ users globally, we build scalable mobile applications, "
            "enterprise SaaS platforms, and intelligent workflow automations across Sales, Support, Finance, and Operations. "
            "Our engineering is backed by ISO 27001 Certification, CMMI Level 3 process maturity, and GDPR, HIPAA, and SOC2 compliance."
        )
    },
    {
        "title": "Production Portfolio: 9 Live Commercial Platforms",
        "category": "portfolio",
        "content": (
            "Aanandi TechnoSoft has engineered and launched 9 live commercial platforms with verified web demos and Google Play Store apps:\n"
            "1. Uclean Laundry (https://aanandi.in/portfolio/uclean): On-demand laundry order booking, schedule pickups, multi-store dispatch, and live order tracking.\n"
            "2. Swagmee Fashion (https://aanandi.in/portfolio/swagmee): Mobile fashion discovery, curated feeds, and 1-click checkout.\n"
            "3. Jotno Patient (https://aanandi.in/portfolio/jotno): Healthcare EHR system managing electronic prescriptions, doctor appointments, and clinic workflows securely.\n"
            "4. Wedding Gallery (https://aanandi.in/portfolio/weddinggallery): Digital wedding planning, guest RSVP coordination, and event photography inspiration.\n"
            "5. HungerGo Food (https://aanandi.in/portfolio/hungergo): Food delivery ordering app with live map rider dispatch and restaurant integration.\n"
            "6. Careasy Customer (https://aanandi.in/portfolio/careasy): Automotive and home maintenance booking with live technician ETA, digital estimates, and invoicing.\n"
            "7. VHelp (https://aanandi.in/portfolio/vhelp): Vetted emergency assistance, community care, and immediate support service coordination.\n"
            "8. Service Plug (https://aanandi.in/portfolio/serviceplug): Enterprise multi-category service dispatch and structured ticket lifecycle system.\n"
            "9. Grocery Delivery (https://aanandi.in/portfolio/grocery): Dark store multi-hub inventory tracking, barcode scanning, and rapid delivery routing."
        )
    },
    {
        "title": "Core Services & Technical Capabilities",
        "category": "services",
        "content": (
            "Aanandi TechnoSoft engineers high-availability digital solutions tailored for client business growth:\n"
            "- Hyperlocal Ecosystems: Fleet dispatching, multi-store inventory, live GPS map tracking, dynamic surge pricing.\n"
            "- Scalable SaaS Platforms: Multi-tenant web architectures, healthcare EHRs, enterprise RBAC portals.\n"
            "- AI-Powered Growth: Recommendation engines, WhatsApp automation bots, automated billing pipelines, AI workflows.\n"
            "- Mobile Applications: Cross-platform iOS and Android apps built with Flutter and React Native (60-120 FPS native performance).\n"
            "- Web & Frontend: Responsive web applications using React and Next.js (SSR, reactive UI state).\n"
            "- Backend & Cloud: Resilient microservices with Python and Node.js deployed on AWS and Microsoft Azure with CI/CD automation.\n"
            "- Enterprise Integrations: Seamless bi-directional sync with Salesforce, HubSpot, Zoho CRM, PostgreSQL, and Stripe/Razorpay."
        )
    },
    {
        "title": "Workflow Automation Solutions (Department Use Cases)",
        "category": "automation_examples",
        "content": (
            "Practical automation scenarios Aanandi TechnoSoft delivers for enterprise teams:\n"
            "- Sales & Lead Intake (Sales Ops): Automated lead capture, enrichment, qualification scoring, and instant routing to CRM.\n"
            "- Customer Support AI (CX): Ticket classification, automated sentiment tagging, and smart routing to specialized human agents.\n"
            "- Finance Operations (CFO): AI invoice extraction, automated three-way matching, and direct ERP synchronization.\n"
            "- Growth & Follow-up: Automated meeting summarization, pipeline task generation, and stakeholder notifications.\n"
            "- HR & Recruiting: AI resume screening, automated candidate scoring, and calendar scheduling integration.\n"
            "- Internal Operations: Knowledge base search bots that synthesize verified documentation to answer staff queries instantly."
        )
    },
    {
        "title": "Case Studies & Measurable Client Results",
        "category": "case_studies",
        "content": (
            "Verified results from client engagements:\n"
            "- FinTech Revenue Operations: 52% improvement in qualified lead conversion through automated scoring, enrichment, and CRM ownership assignment.\n"
            "- Customer Support AI Agent: 52% faster resolution and cleaner support queues via AI ticket classification and intelligent routing.\n"
            "- FinTech Loan Processing: 38% faster resolution by automating document intake, OCR validation, and CRM workflow orchestration, saving loan officers 3+ hours daily.\n"
            "- Client Testimonials:\n"
            "  * Alex Rivera (COO, Haus): 'The team didn't just build an automation; they re-engineered our entire operations workflow. We're moving twice as fast now.'\n"
            "  * Sarah Jenkins (VP Engineering, DataCorp): 'Finally, an automation partner who actually understands enterprise security requirements. No hand-waving, just solid execution.'"
        )
    },
    {
        "title": "6-Step Delivery Process & Methodology",
        "category": "delivery_process",
        "content": (
            "Aanandi TechnoSoft delivers client engagements through a transparent 6-step milestone process:\n"
            "Step 1 - Discovery: Deep dive into business workflows, bottlenecks, and measurable KPIs.\n"
            "Step 2 - Planning: Architectural blueprints, database schema design, and UX prototypes with clear sprint roadmaps.\n"
            "Step 3 - Development: High-velocity agile sprints with weekly playable builds and modular code.\n"
            "Step 4 - Testing: Comprehensive unit testing, user journey validation, vulnerability scanning, and load stress testing.\n"
            "Step 5 - Launch: Zero-downtime cloud provisioning and deployment to Google Play Store, Apple App Store, and web.\n"
            "Step 6 - Scale: Ongoing performance optimization, 99.9% uptime SLA monitoring, and proactive user feedback iteration."
        )
    },
    {
        "title": "Security, Compliance & Contact Channels",
        "category": "security",
        "content": (
            "Security & Compliance Standards:\n"
            "- ISO 27001 Certified ISMS, CMMI Level 3 maturity, and GDPR, HIPAA, and SOC2 compliance.\n"
            "- Principle of least-privilege data access, comprehensive encryption at rest (AES-256) and in transit (TLS 1.3).\n"
            "Direct Contact:\n"
            "- Direct WhatsApp / Phone: +91 97138 46846\n"
            "- Official Email: info@aanandi.in\n"
            "- Main Website: https://aanandi.in\n"
            "- Live Portfolio: https://aanandi-port.onrender.com/"
        )
    }
]

async def get_embedding(text: str) -> List[float]:
    """Generates 1536-dimensional float embedding using OpenRouter or OpenAI."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {openrouter_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/text-embedding-3-small",
                    "input": text
                },
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data and "embedding" in data[0]:
                    return data[0]["embedding"]
        except Exception as e:
            print(f"[RAG NOTICE] OpenRouter embedding error: {e}")

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and not openai_key.startswith("sk-dummy"):
        try:
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(model="text-embedding-3-small", api_key=openai_key)
            return await embedder.aembed_query(text)
        except Exception as e:
            print(f"[RAG NOTICE] OpenAI embedding error: {e}")

    return [0.0] * 1536

async def vector_search_knowledge(
    query_text: str,
    limit: int = 3,
    num_candidates: int = 50,
    category_filter: Optional[str] = None
) -> str:
    """
    Executes $vectorSearch against knowledge_chunks in MongoDB Atlas.
    If Atlas vectorSearch is unavailable, performs native MongoDB text/regex query
    across the ingested Website Documentation and portfolio chunks.
    Falls back gracefully to structured in-memory portfolio knowledge.
    """
    # 1. Try MongoDB Atlas $vectorSearch if vector index is configured
    try:
        query_vector = await get_embedding(query_text)
        if any(v != 0.0 for v in query_vector[:10]):
            pipeline: List[Dict[str, Any]] = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": num_candidates,
                        "limit": limit
                    }
                }
            ]
            if category_filter:
                pipeline[0]["$vectorSearch"]["filter"] = {"category": category_filter}
                
            pipeline.append({
                "$project": {
                    "_id": 0,
                    "title": 1,
                    "content": 1,
                    "category": 1,
                    "score": {"$meta": "vectorSearchScore"}
                }
            })

            cursor = knowledge_chunks_collection.aggregate(pipeline)
            results = await cursor.to_list(length=limit)
            if results:
                formatted = []
                for doc in results:
                    score = doc.get("score", 0.0)
                    formatted.append(f"### {doc.get('title')} (Relevance: {score:.2f})\n{doc.get('content')}")
                return "\n\n".join(formatted)
    except Exception as e:
        print(f"[RAG NOTICE] Atlas $vectorSearch bypassed ({e}), trying database search.")

    # 2. Database Text / Regex Search across the ingested knowledge_chunks
    try:
        # A. Try MongoDB text search if text index exists
        cursor = knowledge_chunks_collection.find(
            {"$text": {"$search": query_text}},
            {"score": {"$meta": "textScore"}, "title": 1, "content": 1, "category": 1}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        results = await cursor.to_list(length=limit)
        if results:
            formatted = []
            for doc in results:
                formatted.append(f"### {doc.get('title')}\n{doc.get('content') or doc.get('chunk_text', '')}")
            return "\n\n".join(formatted)
    except Exception:
        pass

    try:
        # B. Regex search on MongoDB knowledge_chunks
        words = [re.escape(w) for w in query_text.lower().split() if len(w) > 3]
        if words:
            pattern = "|".join(words)
            cursor = knowledge_chunks_collection.find({
                "$or": [
                    {"title": {"$regex": pattern, "$options": "i"}},
                    {"content": {"$regex": pattern, "$options": "i"}},
                    {"category": {"$regex": pattern, "$options": "i"}}
                ]
            }).limit(limit)
            results = await cursor.to_list(length=limit)
            if results:
                formatted = []
                for doc in results:
                    formatted.append(f"### {doc.get('title')}\n{doc.get('content') or doc.get('chunk_text', '')}")
                return "\n\n".join(formatted)
    except Exception as e:
        print(f"[RAG NOTICE] MongoDB regex search notice: {e}")

    # 3. In-memory semantic keyword fallback against clean portfolio knowledge
    q_lower = query_text.lower()
    matches = []
    for item in FALLBACK_KNOWLEDGE:
        title = item["title"].lower()
        content = item["content"].lower()
        if any(word in title or word in content for word in q_lower.split() if len(word) > 3):
            matches.append(f"### {item['title']}\n{item['content']}")

    if matches:
        return "\n\n".join(matches[:limit])

    # 4. Clean Default Overview (Public Portfolio & Services Only)
    return (
        "### Aanandi TechnoSoft Overview & Core Capabilities\n"
        "Aanandi TechnoSoft LLP (https://aanandi.in) is an AI-Powered Product Engineering and Workflow Automation Partner. "
        "With 15+ years of experience and 500+ projects delivered, we build scalable mobile apps (Flutter, React Native), "
        "enterprise SaaS platforms (React, Next.js, Python, Node.js, AWS/Azure), AI automation agents, and CRM integrations (Salesforce, HubSpot, Zoho). "
        "Our portfolio includes 9 live commercial products (Uclean Laundry, Swagmee, Jotno Patient Healthcare EHR, HungerGo, Careasy, etc.). "
        "We are ISO 27001 Certified, CMMI Level 3, and GDPR/HIPAA/SOC2 compliant."
    )
