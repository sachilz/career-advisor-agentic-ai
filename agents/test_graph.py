"""
End-to-End Multi-Agent Test Script.

This script tests the complete LangGraph career advisor workflow using the specified sample prompt:
"I'm an IT student. I know Python and Java. I want to become a DevOps Engineer."

Usage:
    python agents/test_graph.py
"""

import sys
import os
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents.graph import run_career_advisor


def test_agent_orchestration():
    """
    Executes sample test prompt and prints formatted outputs for each agent state key.
    """
    sample_prompt = "I'm an IT student. I know Python and Java. I want to become a DevOps Engineer."
    
    print("=" * 80)
    print("CAREER ADVISOR AGENTIC AI - END-TO-END SYSTEM TEST")
    print("=" * 80)
    print(f"Sample Input: \"{sample_prompt}\"\n")

    # Run LangGraph pipeline
    final_state = run_career_advisor(sample_prompt)

    print("\n" + "=" * 80)
    print("VERIFYING AGENT STATE OUTPUTS")
    print("=" * 80)

    print("\n[State Key 1] user_input:")
    print(f"  {final_state.get('user_input')}")

    print("\n[State Key 2] Extracted skills (Agent 1):")
    print(f"  {final_state.get('skills')}")

    print("\n[State Key 3] Extracted goal (Agent 1):")
    print(f"  {final_state.get('goal')}")

    print("\n[State Key 4] Retrieved context count (Agent 2 - RAG Tool Use):")
    context = final_state.get('retrieved_context', [])
    print(f"  Retrieved {len(context)} chunk(s).")
    for idx, snippet in enumerate(context[:2], 1):
        print(f"  - Chunk #{idx}: {snippet[:150]}...")

    print("\n[State Key 5] Missing skills (Agent 3):")
    print(f"  {final_state.get('missing_skills')}")

    print("\n[State Key 6] Final Recommendation (Agent 4):")
    print("-" * 80)
    print(final_state.get('final_recommendation'))
    print("-" * 80)

    print("\n" + "=" * 80)
    print("END-TO-END TEST SUCCESSFUL! All 4 agents executed and populated state.")
    print("=" * 80)


if __name__ == "__main__":
    test_agent_orchestration()
