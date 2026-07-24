"""
Agent 2: Career Research Agent (RAG Tool Integration).

AGENT DESIGN PATTERN NOTE:
This agent demonstrates the "Tool Use Pattern" in agentic AI systems.
Instead of relying solely on parametric LLM memory, the agent acts as an autonomous caller
invoking an external RAG retriever tool (query_knowledge_base) to ground its downstream analysis
in verified domain knowledge base documents.

Input State:  {"goal": str}
Output State: {"retrieved_context": List[str]}
"""

import sys
import os

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import List
from agents.state import CareerAdvisorState
from rag.retrieve import query_knowledge_base


def career_research_agent(state: CareerAdvisorState) -> CareerAdvisorState:
    """
    Worker Node 2: Invokes the RAG retrieval tool to fetch relevant job descriptions,
    certification guides, and roadmap chunks for the target career goal.
    
    Args:
        state (CareerAdvisorState): Current pipeline state containing 'goal'.
        
    Returns:
        CareerAdvisorState: Updated state dictionary with 'retrieved_context'.
    """
    goal = state.get("goal", "Software Engineer")
    print(f"\n[Agent 2: Career Research] Executing RAG tool retrieval for goal: \"{goal}\"")

    # TOOL USE PATTERN: Call external query_knowledge_base tool function from RAG module
    retrieved_results = query_knowledge_base(query=f"Requirements, skills, certifications, and roadmaps for {goal}", k=5)

    context_snippets: List[str] = []

    if retrieved_results:
        for item in retrieved_results:
            source = item.get("source", "Knowledge Base")
            content = item.get("content", "").strip()
            context_snippets.append(f"[{source}]: {content}")
        print(f"  [+] Retrieved {len(retrieved_results)} relevant document chunk(s) from RAG vector store.")
    else:
        print("  [!] RAG vector store returned no chunks (or is unpopulated). Using domain context template.")
        # Provide domain template context if vector store hasn't been ingested yet
        context_snippets = [
            f"[Domain Knowledge]: Core requirements for a {goal} include Linux system administration, CI/CD pipeline automation (GitHub Actions, Jenkins), Containerization (Docker, Kubernetes), Cloud infrastructure (AWS/Azure), and Infrastructure-as-Code (Terraform, Ansible)."
        ]

    return {
        **state,
        "retrieved_context": context_snippets
    }
