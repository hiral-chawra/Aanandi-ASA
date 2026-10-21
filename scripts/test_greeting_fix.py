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

from langchain_core.messages import HumanMessage
from agent import app as sales_agent, parse_lead_info, extract_name, is_standalone_greeting, GREETING_WORDS

async def test_greetings():
    print("=================================================================")
    print("[TEST SUITE] TESTING GREETINGS & NAME EXTRACTION FIX")
    print("=================================================================\n")

    # 1. Test unit helper functions
    print("[TEST 1] Testing is_standalone_greeting...")
    for g in ["hay", "Hay", "hi", "Hi", "hello", "Hey", "heyy", "hii", "heya", "yo", "namaste", "hi!"]:
        assert is_standalone_greeting(g), f"Expected '{g}' to be recognized as greeting"
    assert not is_standalone_greeting("Rahul"), "Expected 'Rahul' not to be greeting"
    assert not is_standalone_greeting("John Doe"), "Expected 'John Doe' not to be greeting"
    print("  ✓ All greeting variations recognized correctly.")

    print("\n[TEST 2] Testing extract_name helper...")
    assert extract_name("hay") is None, f"extract_name('hay') must be None, got: {extract_name('hay')}"
    assert extract_name("hi") is None, f"extract_name('hi') must be None, got: {extract_name('hi')}"
    assert extract_name("heyy") is None, f"extract_name('heyy') must be None, got: {extract_name('heyy')}"
    assert extract_name("Rahul Sharma") == "Rahul Sharma", f"Failed: {extract_name('Rahul Sharma')}"
    assert extract_name("My name is Rahul") == "Rahul", f"Failed: {extract_name('My name is Rahul')}"
    print("  ✓ extract_name correctly rejects greetings and accepts real names.")

    print("\n[TEST 3] Testing parse_lead_info helper...")
    assert parse_lead_info("hay") == {}, f"parse_lead_info('hay') must be empty, got: {parse_lead_info('hay')}"
    assert parse_lead_info("hi") == {}, f"parse_lead_info('hi') must be empty, got: {parse_lead_info('hi')}"
    assert parse_lead_info("heyy") == {}, f"parse_lead_info('heyy') must be empty, got: {parse_lead_info('heyy')}"
    p_real = parse_lead_info("Rahul Sharma")
    assert p_real.get("name") == "Rahul Sharma", f"Expected 'Rahul Sharma', got: {p_real}"
    print("  ✓ parse_lead_info correctly ignores greetings.")

    # 2. Integration test: Sending "hay" on fresh unverified session
    print("\n[TEST 4] Testing sending 'hay' into LangGraph agent on fresh session...")
    session_id = f"test_hay_{int(asyncio.get_event_loop().time() * 1000)}"
    config = {"configurable": {"thread_id": session_id}}

    state_hay = {
        "messages": [HumanMessage(content="hay")],
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

    res_hay = await sales_agent.ainvoke(state_hay, config=config)
    ai_msg = res_hay["messages"][-1].content
    payload = res_hay.get("tool_payload") or {}

    print(f"  AI Response: {ai_msg[:120]}...")
    print(f"  User Name in state: '{res_hay.get('user_name')}'")
    print(f"  Pending Step: {res_hay.get('pending_step')}")
    print(f"  Tool Payload Type: {payload.get('type')}")
    print(f"  Tool Payload Fields: {payload.get('data', {}).get('fields')}")

    assert res_hay.get("user_name") == "", f"user_name must be empty, got: '{res_hay.get('user_name')}'"
    assert res_hay.get("pending_step") == "COLLECT_NAME", f"pending_step must be COLLECT_NAME, got: {res_hay.get('pending_step')}"
    assert payload.get("data", {}).get("fields") == ["name"], f"Expected fields ['name'], got {payload.get('data', {}).get('fields')}"
    assert "Nice to meet you, Hay" not in ai_msg, "Must not greet by name 'Hay'!"
    assert "May I please have your full name" in ai_msg, "Must ask for full name!"
    print("  ✓ 'hay' correctly prompted for name via lead_form without capturing 'Hay' as name!")

    # 3. Test corrupted state recovery: what if user_name is already 'Hay'?
    print("\n[TEST 5] Testing self-healing when session previously had user_name='Hay'...")
    state_corrupted = {
        "messages": [HumanMessage(content="hay")],
        "lead_stage": "QUALIFYING",
        "bant_score": 3,
        "user_email": "",
        "user_name": "Hay",
        "user_phone": "",
        "is_verified": False,
        "otp_code": "",
        "pending_step": "COLLECT_EMAIL",
        "needs_human": False,
        "photo_context": ""
    }

    res_corrupted = await sales_agent.ainvoke(state_corrupted, config=config)
    assert res_corrupted.get("user_name") == "", f"Corrupted name 'Hay' should be cleared, got '{res_corrupted.get('user_name')}'"
    assert res_corrupted.get("pending_step") == "COLLECT_NAME", f"Step should reset to COLLECT_NAME, got {res_corrupted.get('pending_step')}"
    print("  ✓ Corrupted 'Hay' session successfully healed back to COLLECT_NAME!")

    print("\n=================================================================")
    print("[ALL TESTS PASSED] GREETINGS FIX VERIFIED 100%")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(test_greetings())
