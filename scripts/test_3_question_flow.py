import asyncio
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

from langchain_core.messages import HumanMessage
from agent import app as sales_agent

async def run_test():
    session_id = "test_3_q_session_99"
    config = {"configurable": {"thread_id": session_id}}

    print("\n--- TURN 1: User asks question without details ---")
    state_turn1 = {
        "messages": [HumanMessage(content="What services do you offer?")],
        "lead_stage": "PENDING_VERIFICATION",
        "bant_score": 3,
        "user_email": "",
        "user_name": "",
        "user_phone": "",
        "is_verified": False,
        "otp_code": "",
        "pending_step": "COLLECT_NAME",
        "needs_human": False,
        "photo_context": "",
        "unverified_questions_count": 0
    }
    res1 = await sales_agent.ainvoke(state_turn1, config=config)
    ans1 = res1["messages"][-1].content
    print("Turn 1 Response snippet:", ans1[:150], "...")
    assert "full name" in ans1.lower(), "Turn 1 must prompt for full name!"
    assert res1["unverified_questions_count"] == 1, f"Expected count 1, got {res1['unverified_questions_count']}"
    assert res1["is_verified"] is False
    assert res1["lead_stage"] == "PENDING_VERIFICATION"
    print("[PASS] Turn 1 PASSED!")

    print("\n--- TURN 2: User gives name AND asks about Jotno EHR app ---")
    res2 = await sales_agent.ainvoke({"messages": [HumanMessage(content="I am Hiral. Can you tell me about the Jotno EHR app?")]}, config=config)
    ans2 = res2["messages"][-1].content
    print("Turn 2 Response snippet:", ans2[:150], "...")
    assert res2["user_name"] == "Hiral", f"Expected user_name 'Hiral', got {res2.get('user_name')}"
    assert "jotno" in ans2.lower() or "ehr" in ans2.lower() or "healthcare" in ans2.lower(), "Turn 2 must answer about Jotno EHR!"
    assert "email" in ans2.lower(), "Turn 2 must prompt for email!"
    assert res2["unverified_questions_count"] == 2, f"Expected count 2, got {res2['unverified_questions_count']}"
    assert res2["is_verified"] is False
    print("[PASS] Turn 2 PASSED!")

    print("\n--- TURN 3: User ignores email and asks about mobile tech stack ---")
    res3 = await sales_agent.ainvoke({"messages": [HumanMessage(content="What is your tech stack for mobile apps?")]}, config=config)
    ans3 = res3["messages"][-1].content
    print("Turn 3 Response snippet:", ans3[:150], "...")
    assert "notice: 3 questions answered" in ans3.lower(), "Turn 3 must include the 3 questions answered notice!"
    assert res3["unverified_questions_count"] == 3, f"Expected count 3, got {res3['unverified_questions_count']}"
    assert res3["is_verified"] is False
    print("[PASS] Turn 3 PASSED!")

    print("\n--- TURN 4: User asks 4th question without verifying (HARD GATED) ---")
    res4 = await sales_agent.ainvoke({"messages": [HumanMessage(content="How much does a CRM integration cost?")]}, config=config)
    ans4 = res4["messages"][-1].content
    print("Turn 4 Response:", ans4)
    assert "protect our engineering" in ans4.lower() or "lock" in ans4.lower() or "verify" in ans4.lower(), "Turn 4 must gate with consultation protection message!"
    assert "email" in ans4.lower(), "Turn 4 must request email!"
    assert res4["unverified_questions_count"] >= 4, f"Expected count >= 4, got {res4['unverified_questions_count']}"
    assert res4["is_verified"] is False
    print("[PASS] Turn 4 PASSED!")

    print("\n--- TURN 5: User provides email and phone ---")
    res5 = await sales_agent.ainvoke({"messages": [HumanMessage(content="hiral@example.com 9876543210")]}, config=config)
    ans5 = res5["messages"][-1].content
    print("Turn 5 Response snippet:", ans5[:150], "...")
    assert "verification code" in ans5.lower() or "code" in ans5.lower(), "Turn 5 must send OTP!"
    assert res5["pending_step"] == "VERIFY_OTP"
    otp_code = res5["otp_code"]
    assert len(otp_code) == 6, f"Expected 6-digit OTP, got {otp_code}"
    print(f"[PASS] Turn 5 PASSED! Dispatched OTP: {otp_code}")

    print("\n--- TURN 6: User submits OTP code ---")
    res6 = await sales_agent.ainvoke({"messages": [HumanMessage(content=otp_code)]}, config=config)
    ans6 = res6["messages"][-1].content
    print("Turn 6 Response snippet:", ans6[:150], "...")
    assert res6["is_verified"] is True, "Turn 6 must verify session!"
    assert res6["lead_stage"] in ["QUALIFYING", "BOOKING_OFFERED"]
    assert res6["unverified_questions_count"] == 0, f"Expected count 0, got {res6['unverified_questions_count']}"
    print("[PASS] Turn 6 PASSED! User is verified.")

    print("\n--- TURN 7: User asks consultative question after verification (UNLOCKED) ---")
    res7 = await sales_agent.ainvoke({"messages": [HumanMessage(content="Can you tell me more about your CRM integration workflows?")]}, config=config)
    ans7 = res7["messages"][-1].content
    print("Turn 7 Response snippet:", ans7[:150], "...")
    assert "protect our engineering" not in ans7.lower(), "Turn 7 must not be gated!"
    assert "notice: 3 questions answered" not in ans7.lower(), "Turn 7 must not contain 3-question warning!"
    assert "before we proceed further" not in ans7.lower(), "Turn 7 must not contain onboarding prompt!"
    assert res7["is_verified"] is True
    assert res7["unverified_questions_count"] == 0
    print("[PASS] Turn 7 PASSED! Verified user has unrestricted access.")

    print("\n===========================================")
    print("ALL 7 TURNS PASSED THE 3-QUESTION RULE & PROGRESSIVE STAGING TEST!")
    print("===========================================\n")

if __name__ == "__main__":
    asyncio.run(run_test())
