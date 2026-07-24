"""
LangGraph Multi-Agent Orchestrator Graph.

ARCHITECTURE PATTERN LABEL: Orchestrator-Worker Pattern
------------------------------------------------------
This module implements the Orchestrator-Worker design pattern using LangGraph.
The state workflow sequentially passes control from worker node to worker node,
accumulating state modifications at each step:

1. intent_analysis  : Extracts skills and target career goal from raw text input.
2. career_research  : Queries RAG knowledge base for job requirements and roadmaps.
3. skills_gap       : Compares user skills against retrieved context to list missing skills.
4. recommendation   : Synthesizes final actionable career roadmap for the student.

Graph Flow:
    START ➔ intent_analysis ➔ career_research ➔ skills_gap ➔ recommendation ➔ END
"""

import sys
import os

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import Dict, Any
from langgraph.graph import StateGraph, START, END

# Import shared state and agent worker functions
from agents.state import CareerAdvisorState
from agents.intent_analysis_agent import intent_analysis_agent
from agents.career_research_agent import career_research_agent
from agents.skills_gap_agent import skills_gap_agent
from agents.recommendation_agent import recommendation_agent


def build_career_advisor_graph():
    """
    Constructs and compiles the sequential LangGraph StateGraph workflow for Career Advisor Agentic AI.
    
    Returns:
        CompiledStateGraph: Compiled runnable LangGraph workflow instance.
    """
    # 1. Initialize StateGraph with CareerAdvisorState schema
    workflow = StateGraph(CareerAdvisorState)

    # 2. Add the 4 agent worker functions as nodes
    workflow.add_node("intent_analysis", intent_analysis_agent)
    workflow.add_node("career_research", career_research_agent)
    workflow.add_node("skills_gap", skills_gap_agent)
    workflow.add_node("recommendation", recommendation_agent)

    # 3. Define sequential execution edges (Orchestrator-Worker Flow)
    workflow.add_edge(START, "intent_analysis")
    workflow.add_edge("intent_analysis", "career_research")
    workflow.add_edge("career_research", "skills_gap")
    workflow.add_edge("skills_gap", "recommendation")
    workflow.add_edge("recommendation", END)

    # 4. Compile workflow graph
    app = workflow.compile()
    return app


# Expose compiled app instance
graph_app = build_career_advisor_graph()


def run_career_advisor(user_input: str) -> Dict[str, Any]:
    """
    Primary entry point to invoke the Career Advisor Agentic AI workflow graph.
    
    Args:
        user_input (str): Natural language text prompt from student.
        
    Returns:
        Dict[str, Any]: Final complete state dictionary containing skills, goal,
                        retrieved_context, missing_skills, and final_recommendation.
    """
    initial_state: CareerAdvisorState = {
        "user_input": user_input,
        "skills": [],
        "goal": "",
        "retrieved_context": [],
        "missing_skills": [],
        "final_recommendation": ""
    }

    print("=" * 70)
    print("EXECUTING CAREER ADVISOR AGENTIC AI WORKFLOW")
    print("=" * 70)

    # Invoke graph
    final_state = graph_app.invoke(initial_state)

    print("\n" + "=" * 70)
    print("WORKFLOW EXECUTION COMPLETED")
    print("=" * 70)

    return final_state


if __name__ == "__main__":
    test_prompt = "I am an IT student. I know Python and Java. I want to become a DevOps Engineer."
    result = run_career_advisor(test_prompt)
    print("\n--- FINAL RECOMMENDATION ---")
    print(result.get("final_recommendation"))
