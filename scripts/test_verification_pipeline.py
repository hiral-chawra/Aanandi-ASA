import os
import sys
import asyncio

# Set stdout/stderr to UTF-8
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))
# Force mock email mode during automated test suites
os.environ["MOCK_EMAIL"] = "true"


from langchain_core.messages import HumanMessage
from agent import app as sales_agent, parse_lead_info

async def run_verification_tests():
    print("=================================================================")
    print("[DRY RUN] TESTING LEAD INTAKE, OTP VERIFICATION & BOOKING GATING")
    print("=================================================================\n")

    # -------------------------------------------------------------
    # UNIT TEST: parse_lead_info helper
    # -------------------------------------------------------------
    print("[TEST 0] Testing parse_lead_info helper...")
    sample_1 = "My details - Name: Ramesh Patel, Email: ramesh@patel.com, Phone: 9876543210"
    p1 = parse_lead_info(sample_1)
    assert p1.get("name") == "Ramesh Patel", f"Failed name: {p1}"
    assert p1.get("email") == "ramesh@patel.com", f"Failed email: {p1}"
    assert p1.get("phone") == "9876543210", f"Failed phone: {p1}"
    print("  ✓ parse_lead_info successfully parsed multi-field formatted string.")

    sample_2 = "Hey I'm Priya, priya123@gmail.com and +91 9123456789"
    p2 = parse_lead_info(sample_2)
    assert p2.get("name") == "Priya", f"Failed name: {p2}"
    assert p2.get("email") == "priya123@gmail.com", f"Failed email: {p2}"
    assert "9123456789" in p2.get("phone", ""), f"Failed phone: {p2}"
    print("  ✓ parse_lead_info successfully parsed natural language string.")

    # -------------------------------------------------------------
    # TEST 1: Unverified User Requests "Book a Discovery Call"
    # Expected: MUST NOT show call_routing or calendar. MUST show lead_form.
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing 'Book a Discovery Call' on fresh unverified session...")
    session_1 = f"test_booking_unverified_{int(asyncio.get_event_loop().time() * 1000)}"
    config_1 = {"configurable": {"thread_id": session_1}}

    state_1 = {
        "messages": [HumanMessage(content="Book a Discovery Call with Senior Technical Team")],
        "lead_stage": "QUALIFYING",
        "bant_score": 3,
        "user_email": "",
        "user_name": "",
        "user_phone": "",
        "is_verified": False,
        "otp_code": "",
        "pending_step": "COLLECT_NAME",
        "needs_human": False,
        "photo_context": ""
    }

    res_1 = await sales_agent.ainvoke(state_1, config=config_1)
    payload_1 = res_1.get("tool_payload") or {}
    print(f"  AI Response: {res_1['messages'][-1].content[:120]}...")
    print(f"  Tool Payload Type: {payload_1.get('type')}")
    print(f"  Lead Stage: {res_1.get('lead_stage')}")
    print(f"  Pending Step: {res_1.get('pending_step')}")
    print(f"  Is Verified: {res_1.get('is_verified')}")

    assert payload_1.get("type") == "lead_form", f"Expected lead_form, got {payload_1.get('type')}"
    assert res_1.get("lead_stage") == "BOOKING_OFFERED", "Expected lead_stage BOOKING_OFFERED"
    assert res_1.get("is_verified") is False, "is_verified must be False"
    print("  [PASS] Unverified booking request correctly prompted for lead details via lead_form.")

    # -------------------------------------------------------------
    # TEST 2: Ingest Multi-Field Details (Name, Email, Phone)
    # Expected: Generates OTP, dispatches email, sets pending_step="VERIFY_OTP", returns otp_options
    # -------------------------------------------------------------
    print("\n[TEST 2] Submitting multi-field contact details...")
    state_2 = {
        "messages": [HumanMessage(content="My details - Name: Ramesh Patel, Email: ramesh@testcompany.com, Phone: 9876543210")],
        "lead_stage": res_1.get("lead_stage"),
        "bant_score": 3,
        "user_email": "",
        "user_name": "",
        "user_phone": "",
        "is_verified": False,
        "otp_code": "",
        "pending_step": res_1.get("pending_step"),
        "needs_human": False,
        "photo_context": ""
    }

    res_2 = await sales_agent.ainvoke(state_2, config=config_1)
    payload_2 = res_2.get("tool_payload") or {}
    print(f"  AI Response: {res_2['messages'][-1].content[:120]}...")
    print(f"  Tool Payload Type: {payload_2.get('type')}")
    print(f"  Pending Step: {res_2.get('pending_step')}")
    print(f"  OTP Code Generated: {res_2.get('otp_code')}")
    print(f"  User Email Recorded: {res_2.get('user_email')}")
    print(f"  User Phone Recorded: {res_2.get('user_phone')}")

    assert payload_2.get("type") == "otp_options", f"Expected otp_options, got {payload_2.get('type')}"
    assert res_2.get("pending_step") == "VERIFY_OTP", f"Expected VERIFY_OTP, got {res_2.get('pending_step')}"
    assert len(res_2.get("otp_code", "")) == 6, f"Invalid OTP code: {res_2.get('otp_code')}"
    assert res_2.get("is_verified") is False, "Must remain unverified until OTP entered"
    generated_otp = res_2.get("otp_code")
    print("  [PASS] Contact details captured and 6-digit OTP dispatched successfully.")

    # -------------------------------------------------------------
    # TEST 3: Entering Wrong OTP
    # Expected: Rejects with error, keeps pending_step="VERIFY_OTP", returns otp_options
    # -------------------------------------------------------------
    print("\n[TEST 3] Submitting incorrect OTP...")
    state_3 = {
        "messages": [HumanMessage(content="000000")],
        "lead_stage": res_2.get("lead_stage"),
        "bant_score": 3,
        "user_email": res_2.get("user_email"),
        "user_name": res_2.get("user_name"),
        "user_phone": res_2.get("user_phone"),
        "is_verified": False,
        "otp_code": generated_otp,
        "pending_step": "VERIFY_OTP",
        "needs_human": False,
        "photo_context": ""
    }

    res_3 = await sales_agent.ainvoke(state_3, config=config_1)
    payload_3 = res_3.get("tool_payload") or {}
    print(f"  AI Response: {res_3['messages'][-1].content}")
    print(f"  Pending Step: {res_3.get('pending_step')}")
    print(f"  Is Verified: {res_3.get('is_verified')}")

    assert "Invalid verification code" in res_3["messages"][-1].content or "invalid" in res_3["messages"][-1].content.lower()
    assert res_3.get("is_verified") is False
    assert res_3.get("pending_step") == "VERIFY_OTP"
    print("  [PASS] Invalid OTP correctly rejected with retry prompt.")

    # -------------------------------------------------------------
    # TEST 4: Entering Correct OTP in Booking Flow
    # Expected: Verifies session, returns call_routing card!
    # -------------------------------------------------------------
    print(f"\n[TEST 4] Submitting correct OTP ({generated_otp}) in Booking Flow...")
    state_4 = {
        "messages": [HumanMessage(content=generated_otp)],
        "lead_stage": res_3.get("lead_stage"),
        "bant_score": 3,
        "user_email": res_3.get("user_email"),
        "user_name": res_3.get("user_name"),
        "user_phone": res_3.get("user_phone"),
        "is_verified": False,
        "otp_code": generated_otp,
        "pending_step": "VERIFY_OTP",
        "needs_human": False,
        "photo_context": ""
    }

    res_4 = await sales_agent.ainvoke(state_4, config=config_1)
    payload_4 = res_4.get("tool_payload") or {}
    print(f"  AI Response: {res_4['messages'][-1].content}")
    print(f"  Tool Payload Type: {payload_4.get('type')}")
    print(f"  Is Verified: {res_4.get('is_verified')}")
    print(f"  Pending Step: {res_4.get('pending_step')}")

    assert res_4.get("is_verified") is True, "Must be verified"
    assert res_4.get("pending_step") == "VERIFIED", "Pending step must be VERIFIED"
    assert payload_4.get("type") == "call_routing", f"Expected call_routing after booking OTP, got {payload_4.get('type')}"
    print("  [PASS] Correct OTP in booking flow verified and immediately presented call_routing card!")

    # -------------------------------------------------------------
    # TEST 5: Integrity Guard: Inconsistent state (is_verified=True but email="")
    # Expected: Integrity guard resets is_verified to False and pending_step to COLLECT_NAME/COLLECT_EMAIL
    # -------------------------------------------------------------
    print("\n[TEST 5] Testing integrity guard against corrupt session (is_verified=True, email='')...")
    session_5 = f"test_corrupt_{int(asyncio.get_event_loop().time() * 1000)}"
    config_5 = {"configurable": {"thread_id": session_5}}

    corrupt_state = {
        "messages": [HumanMessage(content="Book a call")],
        "lead_stage": "QUALIFYING",
        "bant_score": 3,
        "user_email": "",       # Empty email!
        "user_name": "",
        "user_phone": "",
        "is_verified": True,   # Corrupted flag from legacy session
        "otp_code": "",
        "pending_step": "VERIFIED",
        "needs_human": False,
        "photo_context": ""
    }

    res_5 = await sales_agent.ainvoke(corrupt_state, config=config_5)
    payload_5 = res_5.get("tool_payload") or {}
    print(f"  Is Verified after guard: {res_5.get('is_verified')}")
    print(f"  Pending Step after guard: {res_5.get('pending_step')}")
    print(f"  Tool Payload: {payload_5.get('type')}")

    assert res_5.get("is_verified") is False, "Integrity guard failed: is_verified must be False when email is empty"
    assert payload_5.get("type") == "lead_form", "Integrity guard must force lead_form intake"
    print("  [PASS] Corrupted state was sanitized; unverified booking without email blocked successfully.")

    # -------------------------------------------------------------
    # TEST 6: Q&A Question on Unverified Session
    # Expected: Answers the question AND appends prompt for name/email.
    # -------------------------------------------------------------
    print("\n[TEST 6] Testing consultative Q&A on fresh unverified session...")
    session_6 = f"test_qa_{int(asyncio.get_event_loop().time() * 1000)}"
    config_6 = {"configurable": {"thread_id": session_6}}

    qa_state = {
        "messages": [HumanMessage(content="What projects has your company built in healthcare?")],
        "lead_stage": "QUALIFYING",
        "bant_score": 3,
        "user_email": "",
        "user_name": "",
        "user_phone": "",
        "is_verified": False,
        "otp_code": "",
        "pending_step": "COLLECT_NAME",
        "needs_human": False,
        "photo_context": ""
    }

    res_6 = await sales_agent.ainvoke(qa_state, config=config_6)
    content_6 = res_6["messages"][-1].content
    payload_6 = res_6.get("tool_payload") or {}
    print(f"  AI Response snippet: {content_6[:180]}...")
    print(f"  Payload Type: {payload_6.get('type')}")
    print(f"  Pending Step: {res_6.get('pending_step')}")

    assert "jotno" in content_6.lower() or "health" in content_6.lower() or "ehr" in content_6.lower(), "Must answer healthcare question"
    assert "name" in content_6.lower(), "Must prompt for user name"
    assert payload_6.get("type") == "lead_form", "Must attach lead_form for name"
    print("  [PASS] Consultative Q&A provides informative answer and politely prompts for contact name.")

    print("\n=================================================================")
    print("[ALL TESTS PASSED] LEAD INTAKE & OTP VERIFICATION VERIFIED 100%")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(run_verification_tests())
