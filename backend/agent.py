import os
import re
import random
import operator
import requests
from typing import TypedDict, Annotated, Sequence, Literal
from dotenv import load_dotenv, find_dotenv

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv(find_dotenv(usecwd=True))

cal_api_key = os.getenv("CAL_API_KEY") or os.getenv("CAL_COM_API_KEY", "")

# Define FSM Lead Stages & Pending Steps
LeadStage = Literal["NEW_LEAD", "PENDING_VERIFICATION", "QUALIFYING", "BOOKING_OFFERED", "CALL_BOOKED", "NURTURE", "DISQUALIFIED"]
PendingStep = Literal["COLLECT_NAME", "COLLECT_EMAIL", "COLLECT_PHONE", "VERIFY_OTP", "VERIFIED"]

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    lead_stage: LeadStage
    bant_score: int  # 1-10
    user_name: str
    user_email: str
    user_phone: str
    is_verified: bool
    otp_code: str
    pending_step: PendingStep
    tool_payload: dict | None
    needs_human: bool
    photo_context: str
    unverified_questions_count: int

# Comprehensive Knowledge Base Data (Aanandi TechnoSoft Documentation & Portfolio)
PROJECTS_AND_CASE_STUDIES = """Aanandi TechnoSoft LLP (https://aanandi.in) is an elite AI Integration and Workflow Automation agency. With 15+ years of engineering experience, 500+ delivered platforms, and 160K+ users globally, we build high-availability Autonomous AI Agents, custom workflow automations, and enterprise software solutions:

1. 🚀 **Sales & Lead Intake Automation**:
   - **Automated Lead Intake & 90-Second Response**: Instant prospect qualification, BANT scoring, and automated outreach triggering within 90 seconds of form submissions.
   - **Lead Enrichment & CRM Handoff**: Automated prospect enrichment, ownership routing, and direct bi-directional sync into Salesforce, HubSpot, and Zoho CRM.

2. ⚡ **Customer Support AI Agents & Omnichannel Triage**:
   - **Support Triage & Smart Routing**: AI ticket classification, sentiment analysis, and intelligent escalation to human specialists, resulting in 52% faster resolution times.
   - **24/7 Omnichannel Support**: Autonomous multi-turn resolution for text and voice support across web, WhatsApp, and telephony.

3. 🏥 **Healthcare & Telemedicine Platforms (Jotno Patient EHR)**:
   - **Secure Patient Triage & Clinic Workflows**: HIPAA-compliant electronic prescriptions, appointment scheduling, and direct EHR/EMR integrations.

4. 🏦 **FinTech Operations & Loan Processing Automation**:
   - **Automated KYC & Loan Document Intake**: 38% faster loan processing resolution through automated document OCR extraction, eligibility scoring, and CRM workflow orchestration.
   - **Revenue Operations Lift**: 52% improvement in qualified lead conversion through automated scoring and routing.

5. 📱 **Production Portfolio (9 Live Commercial Platforms)**:
   - Live products backed with verified web demos and Google Play Store apps including Uclean Laundry (laundry booking & tracking), Swagmee Fashion (discovery & checkout), Jotno Patient (healthcare EHR), HungerGo Food (live map food delivery), Careasy Customer (automotive & home repair), VHelp (emergency assistance), Service Plug (enterprise service dispatch), and Grocery Delivery.

6. 🛠️ **Enterprise Delivery Methodology, Timelines & Security**:
   - Transparent 6-step delivery: Discovery → Planning → Development → Testing → Launch → Scale.
   - High-velocity agile sprints with weekly playable builds (never multi-month black-box cycles).
   - Official Project Delivery Timelines:
     * Single Workflow Automations & CRM Integrations: 2 to 3 weeks (typically a few weeks).
     * Multi-System Enterprise Projects with AI Components: 6 to 8 weeks.
     * Architectural Assessment SLA: Ballpark estimate delivered within 4 to 6 business hours (Response SLA < 4 hours).
     * Exact custom delivery dates and milestones are confirmed during a 30-minute discovery session with technical leads.
   - Enterprise security: ISO 27001 Certified ISMS, CMMI Level 3 maturity, least-privilege access, and GDPR, HIPAA, and SOC2 compliance with 99.9% uptime enterprise SLAs."""

# Tools Definition
@tool
def query_knowledge_base(query: str) -> str:
    """Searches product documentation, case studies, fields, and enterprise FAQs for Aanandi TechnoSoft via Atlas Vector Search."""
    try:
        from rag import vector_search_knowledge
        from db import get_main_loop
        import asyncio

        main_loop = get_main_loop()
        if main_loop and main_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(vector_search_knowledge(query), main_loop)
            return future.result(timeout=5)
        else:
            return asyncio.run(vector_search_knowledge(query))
    except Exception as e:
        print(f"[RAG SEARCH NOTICE] Fallback due to: {e}")
        return PROJECTS_AND_CASE_STUDIES

@tool
def generate_booking_link(email: str, name: str) -> str:
    """Generates a custom pre-filled Cal.com scheduling link for the lead."""
    api_k = os.getenv("CAL_API_KEY") or os.getenv("CAL_COM_API_KEY", cal_api_key)
    headers = {
        "Authorization": f"Bearer {api_k}",
        "Content-Type": "application/json",
        "cal-api-version": "2024-08-13",
    }
    
    try:
        response = requests.get("https://api.cal.com/v2/me", headers=headers, timeout=10)
        if response.status_code == 200:
            user_data = response.json().get("data", {})
            username = user_data.get("username", "booking")
            return f"https://cal.com/{username}/discovery-call?name={requests.utils.quote(name)}&email={requests.utils.quote(email)}"
        else:
            return f"https://cal.com/booking?name={requests.utils.quote(name)}&email={requests.utils.quote(email)}"
    except Exception as e:
        return f"Error generating booking link: {str(e)}"

@tool
def send_email(to_email: str, subject: str, body: str) -> str:
    """Sends an email to the lead via Resend API."""
    try:
        from dispatch import send_email_dispatch
        result = send_email_dispatch(to_email=to_email, subject=subject, text_content=body)
        if result.get("success"):
            return f"Email successfully sent to {to_email}."
        else:
            return f"Failed to send email: {result.get('error')}"
    except Exception as e:
        return f"Error sending email: {str(e)}"

tools = [query_knowledge_base, generate_booking_link, send_email]

# ── Intent Helpers ─────────────────────────────────────────────────────────────
GREETING_WORDS = {
    "hi", "hello", "hey", "hay", "heyy", "heyyy", "hii", "hiii",
    "heya", "howdy", "hola", "yo", "sup", "namaste", "start",
    "greetings", "good morning", "good afternoon", "good evening"
}

def is_standalone_greeting(text: str) -> bool:
    """Returns True if the text is solely a greeting or salutation."""
    if not text or not text.strip():
        return False
    clean = re.sub(r'[\s!.,?:;]+', ' ', text.strip().lower()).strip()
    return clean in GREETING_WORDS

def is_user_query(text: str) -> bool:
    """Determines whether text is a user inquiry/question rather than a pure name, email, phone, or OTP input."""
    if not text or not text.strip():
        return False
    
    text_clean = text.strip()
    text_lower = text_clean.lower()

    # Standalone greetings are never user queries
    if is_standalone_greeting(text_clean):
        return False

    words = text_clean.split()

    # Pure email inputs are NOT user queries
    if len(words) <= 2 and "@" in text_clean and "." in text_clean:
        return False

    # Pure phone inputs are NOT user queries
    digits_only = re.sub(r'\D', '', text_clean)
    if len(words) <= 2 and len(digits_only) in [10, 11, 12]:
        return False

    # Pure 6-digit OTP codes are NOT user queries
    if len(words) <= 2 and len(digits_only) == 6:
        return False

    if "?" in text_clean:
        return True

    query_keywords = [
        "what", "which", "how", "who", "where", "why", "can", "could", "would", "should", "will",
        "tell", "show", "need", "want", "project", "projects", "fildes", "field", "fields",
        "work", "worked", "built", "make", "made", "pricing", "cost", "price", "demo",
        "help", "about", "feature", "features", "service", "services", "case", "portfolio",
        "done", "experience", "integrate", "crm", "voice", "bot", "agent", "security",
        "sla", "uptime", "support", "tech", "stack", "ai", "aanandi", "call", "book",
        "appointment", "pay", "payment", "tier", "info", "information", "detail", "details",
        "recommend", "automation", "workflow", "system", "app", "application", "software",
        "company", "firm", "developer", "engineering"
    ]

    # Use word boundary matching so "ai" doesn't match inside "gmail" or "email"
    pattern = r'\b(' + '|'.join(re.escape(kw) for kw in query_keywords) + r')\b'
    if re.search(pattern, text_lower):
        return True

    if len(words) > 4:
        return True

    return False

def extract_name(text: str) -> str | None:
    """Extracts clean name if user is introducing themselves, else None."""
    if not text or not text.strip():
        return None

    text_clean = text.strip()
    text_lower = text_clean.lower()

    # Standalone greetings are NEVER names
    if is_standalone_greeting(text_clean):
        return None

    # Ignore general conversational responses / help queries
    non_names = {
        "hi", "hello", "hey", "hay", "heyy", "heyyy", "hii", "hiii", "heya",
        "howdy", "hola", "yo", "sup", "namaste", "start", "thanks", "thank you",
        "yes", "no", "sure", "ok", "okay", "demo", "pricing", "projects", "services",
        "ai", "bot", "voice", "help", "info", "details",
        "what can you do", "what i can help you with", "how can you help me", "tell me more"
    }
    if text_lower in non_names:
        return None

    # Check for explicit introductory prefixes first (e.g. "My name is John Doe")
    prefixes = ["my name is ", "i am ", "i'm ", "this is ", "call me ", "myself "]
    has_prefix = False
    for p in prefixes:
        if text_lower.startswith(p):
            text_clean = text_clean[len(p):].strip()
            has_prefix = True
            break

    # If no prefix, ensure it's not a general question/query or greeting
    if not has_prefix and (is_user_query(text_clean) or is_standalone_greeting(text_clean)):
        return None

    words = text_clean.split()
    if 1 <= len(words) <= 3 and all(w.replace("-", "").replace(".", "").replace("_", "").isalpha() for w in words):
        common_words = {
            "the", "a", "an", "what", "how", "why", "where", "when", "can", "could", "would",
            "should", "will", "is", "are", "help", "need", "want", "just", "looking", "nothing",
            "anything", "something", "hay", "hey", "hi", "hello", "yo", "sup", "hola", "namaste"
        }
        if not has_prefix and any(w.lower() in common_words for w in words):
            return None
        return text_clean.title()

    return None

def parse_lead_info(text: str) -> dict:
    """
    Extracts name, email, and phone from free-form text or structured form submissions like:
    'My details - Name: John Doe, Email: john@example.com, Phone: 9876543210'
    or 'John Doe john@gmail.com 9876543210' or natural language sentences.
    """
    info = {}
    if not text or not text.strip():
        return info

    # If the entire message is just a greeting, never parse contact info
    if is_standalone_greeting(text):
        return info

    clean_text = text.strip()

    # 1. Extract Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', clean_text)
    if email_match:
        info["email"] = email_match.group(0).lower()

    # 2. Extract Phone (10 to 12 digits, optional leading +, with or without formatting)
    phone_match = re.search(r'(?:(?:\+91|91|0)?[ -]?)?([6-9]\d{9})\b|\b(\d{10,12})\b', clean_text)
    if phone_match:
        digits = "".join(filter(str.isdigit, phone_match.group(0)))
        if len(digits) in [10, 11, 12]:
            info["phone"] = digits

    # 3. Extract Name
    name_label_match = re.search(r'(?:name|full name)\s*[:=-]\s*([^,\n\r|]+)', clean_text, re.IGNORECASE)
    intro_match = re.search(r'\b(?:i am|i\'m|my name is|myself|this is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b', clean_text, re.IGNORECASE)

    if name_label_match:
        raw_name = name_label_match.group(1).strip()
        cleaned_name = extract_name(raw_name) or raw_name.title()
        if cleaned_name and len(cleaned_name) < 40 and not is_standalone_greeting(cleaned_name):
            info["name"] = cleaned_name
    elif intro_match:
        cand_name = intro_match.group(1).strip().title()
        if len(cand_name.split()) <= 2 and not is_user_query(cand_name) and not is_standalone_greeting(cand_name):
            info["name"] = cand_name
    else:
        text_without_contact = clean_text
        if "email" in info and email_match:
            text_without_contact = text_without_contact.replace(email_match.group(0), "")
        if "phone" in info and phone_match:
            text_without_contact = text_without_contact.replace(phone_match.group(0), "")
        # Remove common filler words, greetings, and symbols
        text_without_contact = re.sub(
            r'\b(hey|hello|hi|hay|heyy|heyyy|hii|hiii|heya|hola|howdy|yo|sup|namaste|and|my|details|is|phone|email)\b',
            ' ',
            text_without_contact,
            flags=re.IGNORECASE
        )
        text_without_contact = re.sub(r'[,|;:+\-]', ' ', text_without_contact).strip()

        if text_without_contact and not is_standalone_greeting(text_without_contact):
            extracted = extract_name(text_without_contact)
            if extracted and not is_standalone_greeting(extracted):
                info["name"] = extracted

    return info

def generate_dynamic_followups(user_query: str) -> list[str]:
    """Generates 2-3 dynamic follow-up question chips mapped specifically to the user's business query topic."""
    q_lower = user_query.lower()
    
    # 1. Voice Bots / Omnichannel Support
    if any(k in q_lower for k in ["voice", "audio", "call", "phone", "speech", "talk", "support"]):
        return [
            "How do 24/7 AI Voice & Support Agents handle triage?",
            "Can support agents integrate directly with our CRM?",
            "Talk to AI (Live Voice Consultation)"
        ]
    # 2. Healthcare / Telemedicine
    elif any(k in q_lower for k in ["health", "hospital", "patient", "triage", "ehr", "hipaa", "clinic", "doctor", "medical", "jotno"]):
        return [
            "How does Jotno Patient EHR manage clinic workflows?",
            "Are your healthcare platforms HIPAA & GDPR compliant?",
            "Book a Discovery Call with Healthcare Solutions Team"
        ]
    # 3. CRM / Workflow Automation / ERP
    elif any(k in q_lower for k in ["crm", "salesforce", "hubspot", "zoho", "sync", "lead", "workflow", "automate", "pipeline"]):
        return [
            "How does bi-directional sync work with Salesforce and HubSpot?",
            "Can you automate lead intake and qualification within 90 seconds?",
            "Book a 15-min Workflow Architecture Call"
        ]
    # 4. FinTech / KYC / Loan Processing
    elif any(k in q_lower for k in ["fintech", "kyc", "fraud", "bank", "payment", "loan", "security", "document", "invoice"]):
        return [
            "How did you achieve a 52% conversion lift in FinTech?",
            "How does automated invoice and loan document extraction work?",
            "Schedule a FinTech Automation Consultation"
        ]
    # 5. Delivery Platforms / Hyperlocal / Mobile Apps
    elif any(k in q_lower for k in ["food", "grocery", "laundry", "hyperlocal", "dispatch", "fleet", "app", "mobile", "flutter"]):
        return [
            "Tell me about live platforms like Uclean and HungerGo",
            "How do your real-time dispatch and GPS tracking work?",
            "Explore Our 9 Live Portfolio Apps"
        ]
    # 6. Pricing / Delivery / Timeline
    elif any(k in q_lower for k in ["price", "pricing", "cost", "timeline", "sprint", "milestone", "delivery", "tier", "quote"]):
        return [
            "What is your 6-step milestone delivery process?",
            "What is included in your ISO 27001 & Enterprise SLAs?",
            "Book a Discovery Call to get a Custom Quote"
        ]
    # 7. General / Portfolio
    else:
        return [
            "Tell me about your 9 live commercial portfolio apps",
            "How does Custom CRM & Workflow Automation work?",
            "Book a Discovery Call with Senior Technical Team"
        ]

def generate_ai_answer_with_followups(
    user_query: str,
    kb_data: str,
    chat_history: list[BaseMessage] | None = None,
    lead_context: dict | None = None
) -> tuple[str, list[str]]:
    """
    Generates a personalized, professional sales engineer answer using the verified Knowledge Base,
    respecting full conversational history and lead context, with strict guardrails against
    disclosing internal widget implementation details.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    llm = None
    if openrouter_key:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                api_key=openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
                temperature=0.3,
                request_timeout=10.0
            )
        except Exception:
            pass
    elif openai_key and (openai_key.startswith("sk-") or len(openai_key) > 10):
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                api_key=openai_key,
                model="gpt-4o-mini",
                temperature=0.3,
                request_timeout=10.0
            )
        except Exception:
            pass

    if llm:
        try:

            # Build lead profile context for personalization
            lead_profile_text = ""
            if lead_context:
                lead_parts = []
                if lead_context.get("user_name"):
                    lead_parts.append(f"Prospect Name: {lead_context['user_name']}")
                if lead_context.get("user_email"):
                    lead_parts.append(f"Prospect Email: {lead_context['user_email']}")
                if lead_context.get("user_phone"):
                    lead_parts.append(f"Prospect Phone: {lead_context['user_phone']}")
                if lead_context.get("lead_stage"):
                    lead_parts.append(f"Lifecycle Stage: {lead_context['lead_stage']}")
                if lead_context.get("photo_context"):
                    lead_parts.append(f"Uploaded Project Requirement Notes (from attached diagram/photo): {lead_context['photo_context']}")
                if lead_parts:
                    lead_profile_text = "CURRENT PROSPECT PROFILE:\n" + "\n".join(f"- {p}" for p in lead_parts) + "\n\n"

            sys_prompt = (
                "You are Aanandi, the elite client-facing AI Sales Engineer for Aanandi TechnoSoft LLP (https://aanandi.in).\n"
                "Aanandi TechnoSoft is an AI Integration and Workflow Automation agency with 15+ years of experience, "
                "500+ delivered platforms, and 160K+ users globally, backed by ISO 27001 Certification, CMMI Level 3 maturity, "
                "and GDPR, HIPAA, and SOC2 compliance.\n\n"
                f"{lead_profile_text}"
                "VERIFIED KNOWLEDGE BASE & PORTFOLIO DATA:\n"
                f"{kb_data}\n\n"
                "STRICT PERSONA, MISSION & BOUNDARY RULES:\n"
                "1. STRICTLY CLIENT-FACING SALES ENGINEER: You pitch ONLY Aanandi TechnoSoft's actual client services, "
                "our 9 live portfolio apps (Uclean Laundry, Swagmee Fashion, Jotno Patient Healthcare EHR, HungerGo, Careasy, etc.), "
                "workflow automations (Sales, Support, Finance, HR, Operations), and verified client case studies (e.g., 52% FinTech conversion lift, 52% faster support triage).\n"
                "2. EXPLICITLY FORBIDDEN FROM TALKING ABOUT HOW YOU WERE BUILT: You must NEVER disclose, discuss, or pitch "
                "your own underlying source code, widget architecture, or internal tools. NEVER mention LangGraph, Pipecat, FastAPI, WebSockets, "
                "Web Audio/WebRTC, Shadow DOM, Cal.com API v2, Razorpay QR codes, or internal prompt pipelines.\n"
                "3. DEFLECT ARCHITECTURAL QUERIES GRACEFULLY: If the user asks how you were built or what tech stack you use, "
                "politely clarify that you are Aanandi TechnoSoft's sales representative, and highlight the modern enterprise tech stack "
                "we engineer for our clients (e.g., React, Next.js, Flutter, React Native, Python, Node.js microservices, AWS/Azure, "
                "and enterprise CRM connectors for Salesforce, HubSpot, and Zoho).\n"
                "4. ATTENTIVE TO LEAD'S CHAT KNOWLEDGE: Actively read the prior conversation history. If the lead mentioned their company, "
                "their industry (e.g. healthcare, fintech, e-commerce, logistics), their team's pain points, or their goals, acknowledge that context "
                "directly and tailor your answers to solve their specific business problem.\n"
                "5. TONE & FORMAT: Warm, sharp, professional, consultative, and concise (use structured markdown bullet points). "
                "Never invent non-existent clients or features.\n"
                "6. PROJECT PHOTOS & ATTACHMENTS: If 'Uploaded Project Requirement Notes' are present in the prospect profile above, "
                "refer directly to those technical notes to discuss implementation. You already have the technical breakdown of their image. "
                "NEVER say 'I am unable to view images' or 'I cannot view external files' when those notes are present. Answer with confidence, "
                "outlining how Aanandi TechnoSoft will implement the features, flows, and tech stack described in those notes. "
                "If the lead refers to an attached image or diagram but NO requirement notes are present in their profile, "
                "politely invite them to upload or attach the file using the attachment button in the chat.\n"
                "7. CRITICAL AANANDI TIMELINES & DELIVERY BOUNDARIES (STRICT RULE):\n"
                "- You are strictly forbidden from quoting generic software timelines like '3 to 6 months', '6 to 12 months', or '12+ months'.\n"
                "- Aanandi TechnoSoft operates on high-velocity agile sprints with weekly playable builds.\n"
                "- Official Delivery Benchmarks:\n"
                "  * Single Workflow Automations / CRM Integrations: 2 to 3 weeks (a few weeks).\n"
                "  * Multi-System Enterprise Projects with AI Components: 6 to 8 weeks.\n"
                "  * Architectural Assessment SLA: Ballpark estimate delivered within 4 to 6 business hours.\n"
                "- When asked about timelines: State the official 2–3 weeks (single) or 6–8 weeks (multi-system) benchmark, highlight the weekly playable builds, and offer to confirm exact delivery dates during a discovery call.\n\n"
                "CRITICAL: At the very end of your response, generate exactly 2 to 3 dynamic, context-specific follow-up questions "
                "that the lead can ask next in this chat. Format the end strictly as:\n"
                "FOLLOW_UPS:\n"
                "- [Dynamic Question 1]\n"
                "- [Dynamic Question 2]\n"
                "- [Dynamic Question 3]"
            )

            messages_to_send = [SystemMessage(content=sys_prompt)]

            # Inject recent chat history (up to last 6 messages) for conversational continuity
            if chat_history:
                recent_msgs = [m for m in chat_history if isinstance(m, (HumanMessage, AIMessage))][-6:]
                # Avoid duplicating the current message if it's already the last element in chat_history
                if recent_msgs and recent_msgs[-1].content.strip() == user_query.strip():
                    messages_to_send.extend(recent_msgs)
                else:
                    messages_to_send.extend(recent_msgs)
                    messages_to_send.append(HumanMessage(content=user_query))
            else:
                messages_to_send.append(HumanMessage(content=user_query))

            res = llm.invoke(messages_to_send)
            if res and res.content:
                raw_text = res.content.strip()
                
                # Extract FOLLOW_UPS if present
                if "FOLLOW_UPS:" in raw_text:
                    parts = raw_text.split("FOLLOW_UPS:")
                    main_answer = parts[0].strip()
                    follow_up_lines = [line.strip().lstrip("-*•0123456789. ") for line in parts[1].strip().split("\n") if line.strip()]
                    parsed_followups = [f for f in follow_up_lines if len(f) > 5 and len(f) < 90]
                    if len(parsed_followups) >= 2:
                        return main_answer, parsed_followups[:3]
                
                return raw_text, generate_dynamic_followups(user_query)
        except Exception as e:
            print(f"[DYNAMIC CONVERSATION NOTICE] LLM generation notice: {e}")

    # Fallback response with domain-mapped followups
    default_answer = (
        f"Here is information regarding our technical capabilities and solutions:\n\n{kb_data}\n\n"
        "What specific business workflow or digital platform would you like to explore?"
    )
    return default_answer, generate_dynamic_followups(user_query)

def generate_ai_answer(user_query: str, kb_data: str) -> str:
    """Backward compatible wrapper returning only the textual answer."""
    answer, _ = generate_ai_answer_with_followups(user_query, kb_data)
    return answer

# ── Graph Nodes Definition ─────────────────────────────────────────────────────
def triage_node(state: AgentState):
    """Assesses lead qualification and lifecycle stage."""
    current_stage = state.get("lead_stage") or "QUALIFYING"
    current_bant = state.get("bant_score") or 5
    return {
        "lead_stage": current_stage,
        "bant_score": current_bant,
    }

def reasoning_node(state: AgentState):
    """Generates next response or tool call based on current state."""
    messages = state["messages"]
    last_msg = messages[-1].content.strip() if messages else ""
    
    user_name = state.get("user_name", "")
    if user_name and user_name.strip().lower() in GREETING_WORDS:
        user_name = ""
    user_email = state.get("user_email", "")
    user_phone = state.get("user_phone", "")
    otp_code = state.get("otp_code", "")
    photo_ctx = state.get("photo_context", "")
    lead_stage = state.get("lead_stage") or "PENDING_VERIFICATION"
    pending_step = state.get("pending_step") or "COLLECT_NAME"
    unverified_questions_count = state.get("unverified_questions_count", 0)

    # Integrity guard: A lead is ONLY verified if a valid email is recorded and is_verified is True!
    is_verified = bool(state.get("is_verified", False)) and bool(user_email)
    if is_verified:
        unverified_questions_count = 0
        if lead_stage == "PENDING_VERIFICATION":
            lead_stage = "QUALIFYING"

    if not user_name and pending_step in ["COLLECT_EMAIL", "COLLECT_PHONE"]:
        pending_step = "COLLECT_NAME"
    if not user_email and pending_step == "VERIFIED":
        pending_step = "COLLECT_EMAIL" if user_name else "COLLECT_NAME"
    if user_name and pending_step == "COLLECT_NAME":
        pending_step = "COLLECT_EMAIL"
    if user_email and pending_step == "COLLECT_EMAIL":
        pending_step = "COLLECT_PHONE"
    if user_phone and pending_step == "COLLECT_PHONE":
        pending_step = "VERIFY_OTP"

    # ── 0. Payment Confirmation Success & Follow-ups (Top Priority) ──────────────
    if "payment" in last_msg.lower() and "confirmed" in last_msg.lower():
        date_time_str = last_msg.split(" on ")[-1].strip(" .") if " on " in last_msg else "your scheduled time"
        dest_inbox = f"to **{user_email}**" if user_email else "to your inbox"
        return {
            "messages": [
                AIMessage(content=f"🎉 **Your booking is fully confirmed for {date_time_str}!** We have dispatched the calendar invite {dest_inbox} and notified our team.\n\nWhile you wait for our meeting, would you like to explore anything else?")
            ],
            "lead_stage": "CALL_BOOKED",
            "pending_step": "VERIFIED",
            "is_verified": is_verified,
            "user_name": user_name,
            "user_email": user_email,
            "user_phone": user_phone,
            "photo_context": photo_ctx,
            "unverified_questions_count": 0,
            "tool_payload": {
                "type": "mcq",
                "data": {
                    "title": "Suggested Follow-ups",
                    "options": [
                        "Tell me about your 9 live portfolio apps (Uclean, Jotno, etc.)",
                        "Tell me about Custom CRM Integrations",
                        "How do AI Voice & Support Agents work?",
                        "Talk to AI (Live Voice Demo)"
                    ]
                }
            }
        }

    # ── 1. Check for Active OTP Verification or Escape Hatches ──────────────────
    cleaned_digits = "".join(filter(str.isdigit, last_msg))

    # Check for escape hatch requests (Resend OTP or Change Email)
    if any(k in last_msg.lower() for k in ["resend", "resend_otp", "resend code", "didn't receive", "didnt receive"]):
        target_mail = user_email.strip() if (user_email and "@" in user_email) else os.getenv("SMTP_EMAIL", "pyashkumar0312@gmail.com")
        new_otp = str(random.randint(100000, 999999))
        print(f"\n==================================================", flush=True)
        print(f"🔑 RESENT SECURITY OTP FOR {target_mail}: {new_otp}", flush=True)
        print(f"==================================================\n", flush=True)
        from dispatch import send_email_dispatch
        send_email_dispatch(
            to_email=target_mail,
            subject="Your Aanandi Security Verification Code (Resent)",
            text_content=f"Hello {user_name or 'Valued Customer'},\n\nYour new 6-digit security code is: {new_otp}\nValid for 10 minutes."
        )
        try:
            from db import _in_memory_otps
            from datetime import datetime, timezone, timedelta
            _in_memory_otps[target_mail.lower()] = {
                "email": target_mail.lower(),
                "otp_code": str(new_otp),
                "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                "is_verified": False,
                "updated_at": datetime.now(timezone.utc)
            }
        except Exception:
            pass
        return {
            "messages": [AIMessage(content=f"🔄 **New verification code sent!**\n\nPlease check your inbox & spam folder (**{target_mail}**) and enter the 6-digit code below.")],
            "user_name": user_name,
            "user_email": target_mail,
            "user_phone": user_phone,
            "otp_code": new_otp,
            "lead_stage": lead_stage,
            "pending_step": "VERIFY_OTP",
            "is_verified": False,
            "photo_context": photo_ctx,
            "unverified_questions_count": unverified_questions_count,
            "tool_payload": {
                "type": "otp_options",
                "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}
            }
        }

    if any(k in last_msg.lower() for k in ["change email", "change_email", "wrong email", "different email"]):
        return {
            "messages": [AIMessage(content="Sure! Please fill in your updated email address below to receive a new code:")],
            "user_name": user_name,
            "user_email": "",
            "user_phone": user_phone,
            "otp_code": "",
            "lead_stage": lead_stage,
            "pending_step": "COLLECT_EMAIL",
            "is_verified": False,
            "photo_context": photo_ctx,
            "unverified_questions_count": unverified_questions_count,
            "tool_payload": {
                "type": "lead_form",
                "data": {"title": "Update Email Address", "fields": ["email"]}
            }
        }

    # Handle 10-digit phone number sent while waiting for OTP
    if pending_step == "VERIFY_OTP" and len(cleaned_digits) in [10, 11, 12] and not is_user_query(last_msg):
        target_mail = user_email.strip() if (user_email and "@" in user_email) else os.getenv("SMTP_EMAIL", "pyashkumar0312@gmail.com")
        return {
            "messages": [AIMessage(content=f"🔐 **We've dispatched your 6-digit verification code to {target_mail}!**\n\nPlease check your inbox and enter the 6-digit code below to complete session verification.")],
            "user_name": user_name,
            "user_phone": last_msg.strip(),
            "user_email": target_mail,
            "otp_code": otp_code,
            "lead_stage": lead_stage,
            "pending_step": "VERIFY_OTP",
            "is_verified": False,
            "photo_context": photo_ctx,
            "unverified_questions_count": unverified_questions_count,
            "tool_payload": {
                "type": "otp_options",
                "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}
            }
        }

    # Check for 6-digit OTP code entry (checks whenever user submits a 6-digit number and is unverified or in VERIFY_OTP)
    if len(cleaned_digits) == 6 and not is_user_query(last_msg) and not is_verified:
        target_mail = user_email.strip() if (user_email and "@" in user_email) else os.getenv("SMTP_EMAIL", "pyashkumar0312@gmail.com")
        
        # Verify against active otp_code or fallback in-memory OTP storage
        otp_matches = (cleaned_digits == otp_code) if otp_code else False
        if not otp_matches and target_mail:
            try:
                from db import _in_memory_otps
                mem = _in_memory_otps.get(target_mail.lower())
                if mem and mem.get("otp_code") == cleaned_digits:
                    otp_matches = True
            except Exception:
                pass

        if otp_matches:
            # If verified in a booking flow, immediately display call routing options!
            if lead_stage == "BOOKING_OFFERED" or "book" in last_msg.lower():
                return {
                    "messages": [AIMessage(content=f"✅ **Session & Email Verified Successfully!**\n\nThank you, **{user_name or 'there'}**. How would you like to connect with our team for your session?")],
                    "is_verified": True,
                    "pending_step": "VERIFIED",
                    "lead_stage": "BOOKING_OFFERED",
                    "user_name": user_name,
                    "user_email": target_mail,
                    "user_phone": user_phone,
                    "otp_code": "",
                    "photo_context": photo_ctx,
                    "unverified_questions_count": 0,
                    "tool_payload": {
                        "type": "call_routing",
                        "data": {}
                    }
                }
            else:
                return {
                    "messages": [AIMessage(content=f"✅ **Email Verified Successfully!**\n\nWelcome aboard, **{user_name or 'there'}**! How can I help you today with custom AI agents, workflow automation, or enterprise solutions?")],
                    "is_verified": True,
                    "pending_step": "VERIFIED",
                    "lead_stage": "QUALIFYING",
                    "user_name": user_name,
                    "user_email": target_mail,
                    "user_phone": user_phone,
                    "otp_code": "",
                    "photo_context": photo_ctx,
                    "unverified_questions_count": 0,
                    "tool_payload": {
                        "type": "mcq",
                        "data": {
                            "title": "Suggested Follow-ups",
                            "options": [
                                "Tell me about your 9 live portfolio apps (Uclean, Jotno, etc.)",
                                "Tell me about Custom CRM Integrations",
                                "How do AI Voice & Support Agents work?",
                                "Book a Discovery Call with Senior Technical Team"
                            ]
                        }
                    }
                }
        else:
            return {
                "messages": [AIMessage(content=f"❌ Invalid verification code. Please check your inbox (**{target_mail}**) and enter the correct 6-digit code.")],
                "user_name": user_name,
                "user_email": target_mail,
                "user_phone": user_phone,
                "otp_code": otp_code,
                "lead_stage": lead_stage,
                "pending_step": "VERIFY_OTP",
                "is_verified": False,
                "photo_context": photo_ctx,
                "unverified_questions_count": unverified_questions_count,
                "tool_payload": {
                    "type": "otp_options",
                    "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}
                }
            }

    # ── 2. Check for Standalone Greetings (e.g. "hi", "hay", "hello", "heyy") ───
    if is_standalone_greeting(last_msg):
        if is_verified:
            return {
                "messages": [AIMessage(content=f"👋 Welcome back, **{user_name or 'there'}**! How can I help you today? Ask me any question or pick a topic below.")],
                "lead_stage": lead_stage if lead_stage != "PENDING_VERIFICATION" else "QUALIFYING",
                "pending_step": "VERIFIED",
                "is_verified": True,
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "photo_context": photo_ctx,
                "unverified_questions_count": 0,
                "tool_payload": {
                    "type": "mcq",
                    "data": {
                        "title": "Quick Questions",
                        "options": [
                            "Tell me about your 9 live portfolio apps (Uclean, Jotno, etc.)",
                            "Tell me about Custom CRM Integrations",
                            "How do AI Voice & Support Agents work?",
                            "Book a Discovery Call with Senior Technical Team"
                        ]
                    }
                }
            }
        else:
            if user_name and user_name.strip().lower() not in GREETING_WORDS:
                if not user_email:
                    prompt_text = f"👋 Hello again, **{user_name}**! What is your email address so we can secure your session and send you detailed project briefs?"
                    next_step = "COLLECT_EMAIL"
                    payload = {"type": "lead_form", "data": {"title": "Submit Email Address", "fields": ["email"]}}
                elif not user_phone:
                    prompt_text = f"👋 Hello again, **{user_name}**! What is your contact phone number to finalize your session verification?"
                    next_step = "COLLECT_PHONE"
                    payload = {"type": "lead_form", "data": {"title": "Provide Contact Phone", "fields": ["phone"]}}
                else:
                    prompt_text = f"👋 Welcome back, **{user_name}**! Please enter your 6-digit verification code below to complete session verification."
                    next_step = "VERIFY_OTP"
                    payload = {"type": "otp_options", "data": {"user_email": user_email, "can_resend": True, "can_change_email": True}}
                return {
                    "messages": [AIMessage(content=prompt_text)],
                    "lead_stage": "PENDING_VERIFICATION",
                    "pending_step": next_step,
                    "is_verified": False,
                    "user_name": user_name,
                    "user_email": user_email,
                    "user_phone": user_phone,
                    "photo_context": photo_ctx,
                    "unverified_questions_count": unverified_questions_count,
                    "tool_payload": payload
                }
            else:
                return {
                    "messages": [AIMessage(content="👋 Welcome to Aanandi TechnoSoft! I'm Aanandi, your AI Sales Engineer.\n\nMay I please have your full name to start our conversation?")],
                    "lead_stage": "PENDING_VERIFICATION",
                    "pending_step": "COLLECT_NAME",
                    "is_verified": False,
                    "user_name": "",
                    "user_email": user_email,
                    "user_phone": user_phone,
                    "photo_context": photo_ctx,
                    "unverified_questions_count": unverified_questions_count,
                    "tool_payload": {
                        "type": "lead_form",
                        "data": {
                            "title": "Provide Your Name",
                            "fields": ["name"]
                        }
                    }
                }

    # ── 3. Parse & Ingest Lead Contact Details (Name, Email, Phone) ────────────
    parsed_info = parse_lead_info(last_msg)
    details_updated = False

    if parsed_info.get("name") and not user_name:
        user_name = parsed_info["name"]
        details_updated = True
    if parsed_info.get("email"):
        user_email = parsed_info["email"]
        details_updated = True
    if parsed_info.get("phone"):
        user_phone = parsed_info["phone"]
        details_updated = True

    # If both email and phone are present and user is unverified, trigger OTP dispatch!
    if user_email and user_phone and not is_verified:
        if pending_step != "VERIFY_OTP" or details_updated:
            new_otp = str(random.randint(100000, 999999))
            print(f"\n==================================================", flush=True)
            print(f"[SECURITY OTP] GENERATED FOR {user_email}: {new_otp}", flush=True)
            print(f"==================================================\n", flush=True)

            from dispatch import send_email_dispatch
            dispatch_res = send_email_dispatch(
                to_email=user_email,
                subject="Your Aanandi Security Verification Code",
                text_content=f"Hello {user_name or 'Valued Customer'},\n\nYour 6-digit security code is: {new_otp}\nValid for 10 minutes."
            )
            try:
                from db import _in_memory_otps
                from datetime import datetime, timezone, timedelta
                _in_memory_otps[user_email.strip().lower()] = {
                    "email": user_email.strip().lower(),
                    "otp_code": str(new_otp),
                    "otp_expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
                    "is_verified": False,
                    "updated_at": datetime.now(timezone.utc)
                }
            except Exception:
                pass
            is_mock = dispatch_res.get("mock", False)
            if is_mock:
                msg_text = (
                    f"🔐 We've dispatched a 6-digit verification code to **{user_email}**.\n\n"
                    f"*(Demo Mode: Your security code is `{new_otp}`)*\n\n"
                    "Please enter the 6-digit code below to verify your session."
                )
            else:
                msg_text = (
                    f"🔐 We've sent a 6-digit verification code to **{user_email}**!\n\n"
                    "Please check your inbox (and spam folder) and enter the 6-digit code below to verify your session."
                )

            return {
                "messages": [AIMessage(content=msg_text)],
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "otp_code": new_otp,
                "lead_stage": lead_stage,
                "pending_step": "VERIFY_OTP",
                "is_verified": False,
                "photo_context": photo_ctx,
                "unverified_questions_count": unverified_questions_count,
                "tool_payload": {
                    "type": "otp_options",
                    "data": {"user_email": user_email, "can_resend": True, "can_change_email": True}
                }
            }

    # If the user is submitting contact details WITHOUT asking a consultative query:
    if not is_user_query(last_msg):
        # If email is provided but phone is missing:
        if user_email and not user_phone:
            display_name = user_name if user_name else "there"
            return {
                "messages": [AIMessage(content=f"Thank you, **{display_name}**! What is your contact phone number to finalize your session verification?")],
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": "",
                "lead_stage": lead_stage,
                "pending_step": "COLLECT_PHONE",
                "is_verified": False,
                "photo_context": photo_ctx,
                "unverified_questions_count": unverified_questions_count,
                "tool_payload": {
                    "type": "lead_form",
                    "data": {"title": "Provide Contact Phone", "fields": ["phone"]}
                }
            }

        # If name is provided but email is missing:
        if user_name and not user_email:
            return {
                "messages": [AIMessage(content=f"Nice to meet you, **{user_name}**! What is your email address so we can secure your session and send you detailed project briefs?")],
                "user_name": user_name,
                "user_email": "",
                "user_phone": user_phone,
                "lead_stage": lead_stage,
                "pending_step": "COLLECT_EMAIL",
                "is_verified": False,
                "photo_context": photo_ctx,
                "unverified_questions_count": unverified_questions_count,
                "tool_payload": {
                    "type": "lead_form",
                    "data": {"title": "Submit Email Address", "fields": ["email"]}
                }
            }

    # ── 4. Check for Call / Booking Request (Gated by Email Verification) ───────
    lower_msg = last_msg.lower()
    is_explicit_booking = (
        any(b in lower_msg for b in ["book", "schedule", "reserve", "arrange"])
        and any(c in lower_msg for c in ["call", "meeting", "appointment", "discovery", "slot", "calendar"])
    ) or any(k in lower_msg for k in [
        "talk to a human", "talk to human", "talk to sales", "talk to expert",
        "talk to an expert", "speak to an expert", "speak with team", "speak to sales"
    ]) or (
        any(k in lower_msg for k in ["book", "schedule", "appointment"])
        and not is_user_query(last_msg)
    )

    if is_explicit_booking:
        # If user is already verified with a verified email:
        if is_verified and user_email:
            display_name = user_name if user_name else "there"
            return {
                "messages": [AIMessage(content=f"I'd be glad to arrange a meeting for you, **{display_name}**! How would you like to connect with our team?")],
                "lead_stage": "BOOKING_OFFERED",
                "pending_step": "VERIFIED",
                "is_verified": True,
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "photo_context": photo_ctx,
                "unverified_questions_count": 0,
                "tool_payload": {
                    "type": "call_routing",
                    "data": {}
                }
            }
        else:
            # Unverified lead: enforce collection of required booking details!
            missing_fields = []
            if not user_name: missing_fields.append("name")
            if not user_email: missing_fields.append("email")
            if not user_phone: missing_fields.append("phone")
            if not missing_fields: missing_fields = ["name", "email", "phone"]

            display_name = user_name if user_name else "there"
            prompt_msg = (
                f"I'd love to connect you with our senior engineering team, **{display_name}**! "
                "To reserve your meeting and dispatch your official Google Meet invitation, please confirm your contact details below:"
            )
            return {
                "messages": [AIMessage(content=prompt_msg)],
                "lead_stage": "BOOKING_OFFERED",
                "pending_step": "COLLECT_PHONE" if (user_name and user_email) else ("COLLECT_EMAIL" if user_name else "COLLECT_NAME"),
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "is_verified": False,
                "photo_context": photo_ctx,
                "unverified_questions_count": unverified_questions_count,
                "tool_payload": {
                    "type": "lead_form",
                    "data": {
                        "title": "Contact Details for Meeting Invite",
                        "fields": missing_fields
                    }
                }
            }

    # ── 5. Product / Knowledge Base Q&A & 3-Question Gating Rule ─────────────
    # If lead is unverified, check the 3-question consultative threshold
    if not is_verified:
        current_q_count = unverified_questions_count + 1
        display_name = user_name if user_name else "there"

        # ── Turn 4 onwards: HARD GATED (Pauses open-ended answers) ───────────
        if current_q_count >= 4:
            payload = None
            if not user_name:
                gate_msg = (
                    "🔒 To protect our engineering team's consultation availability and discuss your project, "
                    "please provide your full name below to continue our consultation."
                )
                next_step = "COLLECT_NAME"
                payload = {"type": "lead_form", "data": {"title": "Provide Your Name", "fields": ["name"]}}
            elif not user_email:
                gate_msg = (
                    f"🔒 To protect our engineering team's consultation availability and discuss solutions for your project, "
                    f"**{display_name}**, please provide your email address below to verify your session."
                )
                next_step = "COLLECT_EMAIL"
                payload = {"type": "lead_form", "data": {"title": "Provide Email Address", "fields": ["email"]}}
            elif not user_phone:
                gate_msg = (
                    f"🔒 To protect our engineering team's consultation availability and discuss solutions for your project, "
                    f"**{display_name}**, please provide your contact phone number below to verify your session."
                )
                next_step = "COLLECT_PHONE"
                payload = {"type": "lead_form", "data": {"title": "Provide Contact Phone", "fields": ["phone"]}}
            else:
                target_mail = user_email or "your email"
                gate_msg = (
                    f"🔒 To protect our engineering team's consultation availability and continue our consultation, "
                    f"**{display_name}**, please enter the 6-digit verification code sent to **{target_mail}**."
                )
                next_step = "VERIFY_OTP"
                payload = {"type": "otp_options", "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}}

            return {
                "messages": [AIMessage(content=gate_msg)],
                "lead_stage": "PENDING_VERIFICATION",
                "pending_step": next_step,
                "is_verified": False,
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "photo_context": photo_ctx,
                "unverified_questions_count": current_q_count,
                "tool_payload": payload
            }

        # ── Turns 1, 2, 3: Answer question thoroughly using Knowledge Base ────
        kb_res = query_knowledge_base.invoke({"query": last_msg})
        lead_ctx = {
            "user_name": user_name,
            "user_email": user_email,
            "user_phone": user_phone,
            "lead_stage": "PENDING_VERIFICATION",
            "photo_context": photo_ctx
        }
        ai_answer, _ = generate_ai_answer_with_followups(
            user_query=last_msg,
            kb_data=kb_res,
            chat_history=messages,
            lead_context=lead_ctx
        )

        # ── Turn 3: Final free question + Warning Notice ─────────────────────
        if current_q_count == 3:
            payload = None
            if not user_name:
                notice = (
                    "\n\n---\n*(Notice: 3 questions answered)* 👤 **Before we continue our consultation, "
                    "please provide your full name below.**"
                )
                next_step = "COLLECT_NAME"
                payload = {"type": "lead_form", "data": {"title": "Provide Your Name", "fields": ["name"]}}
            elif not user_email:
                notice = (
                    f"\n\n---\n*(Notice: 3 questions answered)* 📧 **{display_name}, to continue our consultation, "
                    "please provide your email address (and phone number) below so we can verify your session.**"
                )
                next_step = "COLLECT_EMAIL"
                payload = {"type": "lead_form", "data": {"title": "Provide Email Address", "fields": ["email"]}}
            elif not user_phone:
                notice = (
                    f"\n\n---\n*(Notice: 3 questions answered)* 📱 **{display_name}, to continue our consultation, "
                    "please provide your contact phone number below so we can verify your session.**"
                )
                next_step = "COLLECT_PHONE"
                payload = {"type": "lead_form", "data": {"title": "Provide Contact Phone", "fields": ["phone"]}}
            else:
                target_mail = user_email or "your email"
                notice = (
                    f"\n\n---\n*(Notice: 3 questions answered)* 🔐 **{display_name}, please enter the 6-digit "
                    f"verification code sent to {target_mail} to continue our consultation.**"
                )
                next_step = "VERIFY_OTP"
                payload = {"type": "otp_options", "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}}

            ai_answer += notice
            return {
                "messages": [AIMessage(content=ai_answer)],
                "lead_stage": "PENDING_VERIFICATION",
                "pending_step": next_step,
                "is_verified": False,
                "user_name": user_name,
                "user_email": user_email,
                "user_phone": user_phone,
                "photo_context": photo_ctx,
                "unverified_questions_count": current_q_count,
                "tool_payload": payload
            }

        # ── Turns 1 & 2: Progressive detail collection prompt ────────────────
        payload = None
        if not user_name:
            ai_answer += "\n\n---\n👤 **Before we proceed further, may I know your full name?**"
            next_step = "COLLECT_NAME"
            payload = {"type": "lead_form", "data": {"title": "Provide Your Name", "fields": ["name"]}}
        elif not user_email:
            ai_answer += f"\n\n---\n📧 **To secure your session, {display_name}, what is your email address?**"
            next_step = "COLLECT_EMAIL"
            payload = {"type": "lead_form", "data": {"title": "Provide Email Address", "fields": ["email"]}}
        elif not user_phone:
            ai_answer += f"\n\n---\n📱 **{display_name}, what is your contact phone number to complete verification?**"
            next_step = "COLLECT_PHONE"
            payload = {"type": "lead_form", "data": {"title": "Provide Contact Phone", "fields": ["phone"]}}
        else:
            target_mail = user_email or "your email"
            ai_answer += f"\n\n---\n🔐 **Please check your inbox and enter the 6-digit verification code sent to {target_mail}.**"
            next_step = "VERIFY_OTP"
            payload = {"type": "otp_options", "data": {"user_email": target_mail, "can_resend": True, "can_change_email": True}}

        return {
            "messages": [AIMessage(content=ai_answer)],
            "lead_stage": "PENDING_VERIFICATION",
            "pending_step": next_step,
            "is_verified": False,
            "user_name": user_name,
            "user_email": user_email,
            "user_phone": user_phone,
            "photo_context": photo_ctx,
            "unverified_questions_count": current_q_count,
            "tool_payload": payload
        }

    # ── If already verified, full consultative flow is unlocked! ─────────────
    kb_res = query_knowledge_base.invoke({"query": last_msg})
    lead_ctx = {
        "user_name": user_name,
        "user_email": user_email,
        "user_phone": user_phone,
        "lead_stage": lead_stage if lead_stage != "PENDING_VERIFICATION" else "QUALIFYING",
        "photo_context": photo_ctx
    }
    ai_answer, dynamic_followups = generate_ai_answer_with_followups(
        user_query=last_msg,
        kb_data=kb_res,
        chat_history=messages,
        lead_context=lead_ctx
    )

    return {
        "messages": [AIMessage(content=ai_answer)],
        "lead_stage": lead_stage if lead_stage != "PENDING_VERIFICATION" else "QUALIFYING",
        "pending_step": "VERIFIED",
        "is_verified": True,
        "user_name": user_name,
        "user_email": user_email,
        "user_phone": user_phone,
        "photo_context": photo_ctx,
        "unverified_questions_count": 0,
        "tool_payload": {
            "type": "mcq",
            "data": {
                "title": "Suggested Follow-ups",
                "options": dynamic_followups
            }
        }
    }

def should_continue(state: AgentState):
    return "end"

# Construct the StateGraph
workflow = StateGraph(AgentState)
workflow.add_node("triage", triage_node)
workflow.add_node("reasoner", reasoning_node)

workflow.set_entry_point("triage")
workflow.add_edge("triage", "reasoner")
workflow.add_edge("reasoner", END)

class BoundedMemorySaver(MemorySaver):
    """
    Production-safe in-memory checkpointer that bounds retained threads to prevent memory leaks on Render.
    Caps in-memory state to the most recent 50 active sessions, preventing unbounded RAM accumulation.
    """
    def __init__(self, max_threads: int = 50):
        super().__init__()
        self._max_threads = max_threads
        self._thread_order: list[str] = []

    def _track_and_evict(self, thread_id: str):
        if not thread_id:
            return
        if thread_id in self._thread_order:
            self._thread_order.remove(thread_id)
        self._thread_order.append(thread_id)
        while len(self._thread_order) > self._max_threads:
            oldest = self._thread_order.pop(0)
            self.storage.pop(oldest, None)
            if hasattr(self, "blobs") and isinstance(self.blobs, dict):
                self.blobs = {k: v for k, v in self.blobs.items() if not (isinstance(k, tuple) and k and k[0] == oldest)}

    def put(self, config, checkpoint, metadata, new_versions):
        thread_id = config.get("configurable", {}).get("thread_id")
        self._track_and_evict(thread_id)
        return super().put(config, checkpoint, metadata, new_versions)

    async def aput(self, config, checkpoint, metadata, new_versions):
        thread_id = config.get("configurable", {}).get("thread_id")
        self._track_and_evict(thread_id)
        return await super().aput(config, checkpoint, metadata, new_versions)

checkpointer = BoundedMemorySaver(max_threads=50)
app = workflow.compile(checkpointer=checkpointer)

