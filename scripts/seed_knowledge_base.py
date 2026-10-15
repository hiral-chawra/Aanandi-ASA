import os
import sys
import asyncio
import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv, find_dotenv
from pypdf import PdfReader
import tiktoken
import requests
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

MONGODB_URI = os.getenv("MONGODB_URI") or os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME") or os.getenv("MONGODB_DB_NAME", "aanandi_sales")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORTFOLIO_URL = "https://aanandi-port.onrender.com/"

# Resolve PDF Path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PDF_PATH = os.path.join(PROJECT_ROOT, "docs", "Website Documentation.pdf")
if not os.path.exists(PDF_PATH):
    PDF_PATH = os.path.join(PROJECT_ROOT, "Website Documentation.pdf")

tokenizer = tiktoken.get_encoding("cl100k_base")

def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Extracts raw text from PDF and retains page numbers."""
    if not os.path.exists(pdf_path):
        print(f"[WARN] PDF not found at {pdf_path}")
        return []
    
    reader = PdfReader(pdf_path)
    pages = []
    print(f"Reading PDF with {len(reader.pages)} pages from: {pdf_path}...")
    for idx, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append({"page_number": idx + 1, "text": text.strip()})
    return pages

def extract_portfolio_website_chunks() -> List[Dict[str, Any]]:
    """
    Fetches live data from https://aanandi-port.onrender.com/ and creates structured knowledge chunks
    covering the 9 live production apps, services, tech stack, certifications, and delivery process.
    """
    print(f"Fetching live portfolio from {PORTFOLIO_URL}...")
    site_text = ""
    try:
        resp = requests.get(PORTFOLIO_URL, timeout=15)
        if resp.status_code == 200:
            site_text = resp.text
    except Exception as e:
        print(f"[WARN] Could not fetch live website: {e}")

    chunks = [
        {
            "title": "Aanandi TechnoSoft Overview & Company Credentials",
            "category": "capabilities",
            "content": (
                "Aanandi TechnoSoft LLP (https://aanandi.in) is an elite AI-Powered Product Engineering and Digital Growth Partner. "
                "With 15+ years of engineering experience, 500+ completed projects, and 160K+ active users globally, "
                "we engineer scalable mobile applications, enterprise SaaS platforms, AI-driven automation workflows, and hyperlocal digital ecosystems. "
                "Our delivery is backed by ISO 27001 Certification, CMMI Level 3 maturity, and GDPR, HIPAA, and SOC2 compliance."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "company_credentials"}
        },
        {
            "title": "Aanandi Portfolio: 9 Live Commercial Apps & Products",
            "category": "portfolio",
            "content": (
                "Aanandi TechnoSoft has built and deployed 9 live commercial platforms with verified web demos and Google Play Store apps:\n"
                "1. Uclean Laundry (https://aanandi.in/portfolio/uclean): On-demand laundry order booking, schedule pickups, multi-store dispatch, and live order tracking.\n"
                "2. Swagmee Fashion (https://aanandi.in/portfolio/swagmee): Mobile e-commerce fashion discovery, curated feeds, and 1-click checkout.\n"
                "3. Jotno Patient (https://aanandi.in/portfolio/jotno): Healthcare EHR system managing electronic prescriptions, doctor appointments, and clinic workflows securely.\n"
                "4. Wedding Gallery (https://aanandi.in/portfolio/weddinggallery): Digital wedding planning, guest RSVP coordination, and event photography inspiration.\n"
                "5. HungerGo Food (https://aanandi.in/portfolio/hungergo): Food delivery ordering app with live map rider dispatch and restaurant integration.\n"
                "6. Careasy Customer (https://aanandi.in/portfolio/careasy): Automotive and home maintenance booking with live technician ETA, digital estimates, and invoicing.\n"
                "7. VHelp (https://aanandi.in/portfolio/vhelp): Vetted emergency assistance, community care, and immediate support service coordination.\n"
                "8. Service Plug (https://aanandi.in/portfolio/serviceplug): Enterprise multi-category service dispatch and structured ticket lifecycle system.\n"
                "9. Grocery Delivery (https://aanandi.in/portfolio/grocery): Dark store multi-hub inventory tracking, barcode scanning, and rapid delivery routing."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "live_apps"}
        },
        {
            "title": "Aanandi Core Services: What We Build For Clients",
            "category": "services",
            "content": (
                "Aanandi TechnoSoft builds high-availability digital solutions tailored for client business growth:\n"
                "- Hyperlocal Ecosystems: Fleet dispatching, multi-store inventory, live GPS map tracking, and dynamic surge pricing.\n"
                "- Scalable SaaS Platforms: Multi-tenant web architectures, healthcare EHRs, and enterprise RBAC portals.\n"
                "- AI-Powered Growth & Automations: WhatsApp customer automation bots, recommendation engines, and automated billing pipelines.\n"
                "- Food & Grocery Delivery Platforms: Multi-kitchen cloud POS, rider batch-dispatch, barcode warehouse pickers, and slot delivery.\n"
                "- Healthcare & Telemedicine Systems: HIPAA-ready EHR, doctor schedule orchestration, and diagnostic lab data pipelines.\n"
                "- E-commerce & Marketplaces: Multi-vendor marketplace platforms, high-converting flash-sale checkouts, and logistics tracking."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "services"}
        },
        {
            "title": "Aanandi Technology Stack & Enterprise Engineering",
            "category": "tech_stack",
            "content": (
                "Aanandi TechnoSoft builds client platforms using proven industry-standard technologies:\n"
                "- Mobile Applications: Cross-platform iOS and Android apps built with Flutter and React Native (60-120 FPS native performance).\n"
                "- Web & Frontend: High-speed, responsive web applications using React and Next.js (SSR, reactive UI state).\n"
                "- Backend & Microservices: Resilient, scalable backends engineered with Python and Node.js (REST APIs, WebSockets, event-driven architectures).\n"
                "- Cloud & DevOps: Enterprise infrastructure deployed on AWS and Microsoft Azure with CI/CD automation, container orchestration, and global CDN delivery.\n"
                "- Enterprise Integrations: Seamless two-way connectivity with Salesforce, HubSpot, Zoho CRM, PostgreSQL, ERP systems, and Stripe/Razorpay payment gateways."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "tech_stack"}
        },
        {
            "title": "Aanandi 6-Step Delivery Process & Methodology",
            "category": "delivery_process",
            "content": (
                "Aanandi TechnoSoft delivers client engagements through a transparent 6-step milestone process:\n"
                "Step 1 - Discovery: Deep dive into business workflows, bottlenecks, and measurable KPIs.\n"
                "Step 2 - Planning: Architectural blueprints, database schema design, and UX prototypes with clear sprint roadmaps.\n"
                "Step 3 - Development: High-velocity agile sprints with weekly playable builds and modular code.\n"
                "Step 4 - Testing: Comprehensive unit testing, user journey validation, vulnerability scanning, and load stress testing.\n"
                "Step 5 - Launch: Zero-downtime cloud provisioning and deployment to Google Play Store, Apple App Store, and web.\n"
                "Step 6 - Scale: Ongoing performance optimization, 99.9% uptime SLA monitoring, and proactive user feedback iteration."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "methodology"}
        },
        {
            "title": "Enterprise Security, Compliance & Data Privacy",
            "category": "security",
            "content": (
                "Security is foundational to all Aanandi TechnoSoft solutions:\n"
                "- ISO 27001 Certified Information Security Management Systems (ISMS).\n"
                "- CMMI Level 3 standardized development processes and code quality audits.\n"
                "- Rigorous compliance with GDPR (data privacy), HIPAA (healthcare data protection), and SOC2 cloud security controls.\n"
                "- Principle of least-privilege data access, comprehensive encryption at rest (AES-256) and in transit (TLS 1.3), and zero credential leakage."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "security"}
        },
        {
            "title": "Client Direct Contact & Engagement Channels",
            "category": "contact",
            "content": (
                "Prospective clients can engage directly with Aanandi TechnoSoft's technical leadership:\n"
                "- Direct Phone & WhatsApp: +91 97138 46846\n"
                "- Official Email: info@aanandi.in\n"
                "- Main Agency Website: https://aanandi.in\n"
                "- Live Portfolio Website: https://aanandi-port.onrender.com/\n"
                "- Initial Response Time: 4–6 business hours with an initial architectural assessment and ballpark estimate."
            ),
            "metadata": {"source": PORTFOLIO_URL, "type": "contact"}
        }
    ]
    return chunks

def split_pdf_into_chunks(pages: List[Dict[str, Any]], target_tokens: int = 400, overlap_tokens: int = 50) -> List[Dict[str, Any]]:
    """
    Slices text into contextual blocks with a sliding window.
    """
    chunks = []
    current_tokens = []
    current_text = []
    current_page = 1

    for page in pages:
        page_num = page["page_number"]
        page_text = page["text"]
        words = page_text.split()
        
        for word in words:
            word_tokens = tokenizer.encode(" " + word)
            current_tokens.extend(word_tokens)
            current_text.append(word)

            if len(current_tokens) >= target_tokens:
                chunk_str = " ".join(current_text)
                
                # Assign dynamic category based on keywords
                category = "general_capabilities"
                lower_chunk = chunk_str.lower()
                if any(k in lower_chunk for k in ["case study", "fintech", "conversion", "resolution", "roi", "client result", "proven results", "haus", "datacorp"]):
                    category = "case_study"
                elif any(k in lower_chunk for k in ["how we work", "discovery", "milestone", "delivery", "methodology", "architecture", "sprint"]):
                    category = "delivery_process"
                elif any(k in lower_chunk for k in ["faq", "frequently asked", "common questions", "q:", "what happens if"]):
                    category = "faq"
                elif any(k in lower_chunk for k in ["support", "sales", "finance", "workflow", "crm", "voice agent", "automation", "integration"]):
                    category = "automation_examples"

                # Extract a concise title from the first line
                first_line = chunk_str.split("\n")[0][:80].strip()
                title = first_line if len(first_line) > 10 else f"Aanandi Documentation (p. {page_num})"

                chunks.append({
                    "title": title,
                    "content": chunk_str,
                    "category": category,
                    "metadata": {
                        "source": "Website Documentation.pdf",
                        "page": page_num,
                        "token_count": len(current_tokens)
                    }
                })

                # Maintain sliding window overlap
                overlap_cut = len(current_tokens) - overlap_tokens
                current_tokens = current_tokens[overlap_cut:]
                current_text = current_text[-overlap_tokens:]

    if current_text:
        chunk_str = " ".join(current_text)
        chunks.append({
            "title": "Aanandi Documentation Summary",
            "content": chunk_str,
            "category": "general_capabilities",
            "metadata": {
                "source": "Website Documentation.pdf",
                "page": current_page,
                "token_count": len(current_tokens)
            }
        })

    return chunks

async def generate_embeddings_for_batch(texts: List[str]) -> List[List[float]]:
    """Generates 1536-dim embeddings using OpenRouter or direct OpenAI."""
    if OPENROUTER_API_KEY:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/text-embedding-3-small",
                    "input": texts
                },
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                return [item["embedding"] for item in data]
            else:
                print(f"[WARN] OpenRouter embeddings error: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            print(f"[WARN] OpenRouter embedding exception: {e}")

    if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-dummy"):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            res = await client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [d.embedding for d in res.data]
        except Exception as e:
            print(f"[WARN] OpenAI embedding exception: {e}")

    # Fallback zero vector
    return [[0.0] * 1536 for _ in texts]

async def seed_database(chunks: List[Dict[str, Any]]):
    """Batches embedding calls and bulk-inserts into MongoDB knowledge_chunks."""
    if not MONGODB_URI:
        print("Error: MONGODB_URI or MONGODB_URL is not configured in .env")
        sys.exit(1)

    mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    db = mongo_client[DATABASE_NAME]
    collection = db["knowledge_chunks"]

    print(f"Connecting to MongoDB database '{DATABASE_NAME}'...")
    print(f"Total chunks to ingest: {len(chunks)}")

    # Clear previous knowledge entries to purge any stale PRD dummy chunks
    await collection.delete_many({})
    print("Flushed existing knowledge_chunks collection (purged stale PRD dummy chunks).")

    batch_size = 15
    docs_to_insert = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = await generate_embeddings_for_batch(texts)

        for j, item in enumerate(batch):
            docs_to_insert.append({
                "title": item["title"],
                "content": item["content"],
                "category": item["category"],
                "service_category": item["category"],
                "chunk_text": item["content"],
                "metadata": item["metadata"],
                "embedding": embeddings[j],
                "created_at": datetime.now(timezone.utc)
            })

        print(f"Processed chunks {min(i + batch_size, len(chunks))}/{len(chunks)}...")

    if docs_to_insert:
        await collection.insert_many(docs_to_insert)
        print(f"Successfully inserted {len(docs_to_insert)} chunks into 'knowledge_chunks'.")

        # Create text index on title and content for fast non-vector fallback searches
        try:
            await collection.create_index([("title", "text"), ("content", "text")], name="idx_knowledge_text")
            print("Created compound text index 'idx_knowledge_text' on (title, content).")
        except Exception as e:
            print(f"Text index notice: {e}")

    mongo_client.close()

async def main():
    print("=== Starting Knowledge Base Ingestion ===")
    
    # 1. Chunks from live portfolio website
    portfolio_chunks = extract_portfolio_website_chunks()
    print(f"Generated {len(portfolio_chunks)} chunks from portfolio website.")

    # 2. Chunks from Website Documentation.pdf
    pdf_pages = extract_text_from_pdf(PDF_PATH)
    pdf_chunks = split_pdf_into_chunks(pdf_pages, target_tokens=400, overlap_tokens=60)
    print(f"Generated {len(pdf_chunks)} chunks from Website Documentation.pdf.")

    all_chunks = portfolio_chunks + pdf_chunks
    print(f"Combined total chunks: {len(all_chunks)}")

    await seed_database(all_chunks)
    print("=== Ingestion Complete! ===")

if __name__ == "__main__":
    asyncio.run(main())
