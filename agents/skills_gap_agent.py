"""
Agent 3: Skills Gap Analysis Agent.

This agent compares the student's current skills against the requirements extracted
from the RAG retrieved context to produce a list of missing skills.

Input State:  {"skills": List[str], "retrieved_context": List[str], "goal": str}
Output State: {"missing_skills": List[str]}
"""

import sys
import os
import json
import re

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from typing import List
from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import CareerAdvisorState
from models.model_router import get_model_for_task


def skills_gap_agent(state: CareerAdvisorState) -> CareerAdvisorState:
    """
    Worker Node 3: Compares current user skills with retrieved industry job context
    and identifies missing skills required for the target role.
    
    Args:
        state (CareerAdvisorState): Current pipeline state.
        
    Returns:
        CareerAdvisorState: Updated state dictionary with 'missing_skills'.
    """
    current_skills = state.get("skills", [])
    goal = state.get("goal", "Software Engineer")
    retrieved_context = state.get("retrieved_context", [])

    print(f"\n[Agent 3: Skills Gap Analysis] Comparing skills {current_skills} against domain requirements for: \"{goal}\"")

    model = get_model_for_task("skills_gap")

    context_text = "\n\n".join(retrieved_context) if retrieved_context else "Standard industry role requirements apply."

    system_prompt = (
        "You are an expert IT technical recruiter and skills evaluator. "
        "Your task is to compare the student's CURRENT SKILLS against the RETRIEVED JOB CONTEXT for their target role.\n"
        "Identify key missing skills, tools, frameworks, or domain knowledge that the student needs to learn.\n\n"
        "Return ONLY a valid JSON array of strings containing the missing skills. Example format:\n"
        '["Docker", "Kubernetes", "Linux Administration", "CI/CD Pipelines", "Terraform"]'
    )

    user_prompt = (
        f"Target Role Goal: {goal}\n"
        f"Student's Current Skills: {current_skills}\n\n"
        f"Retrieved Job & Domain Context:\n{context_text}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = model.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = " ".join(str(c) for c in content if isinstance(c, str))
        content = content.strip()

        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()

        missing_skills = json.loads(content)
        if not isinstance(missing_skills, list):
            missing_skills = [str(missing_skills)]

    except Exception as e:
        print(f"[Agent 3: Skills Gap] Warning parsing LLM response: {e}. Applying fallback gap calculation.")
        missing_skills = _fallback_gap_analysis(current_skills, goal)

    print(f"  [+] Identified Missing Skills: {missing_skills}")

    return {
        **state,
        "missing_skills": missing_skills
    }


def _fallback_gap_analysis(skills: List[str], goal: str) -> List[str]:
    """Fallback skill gap calculator."""
    skills_lower = [s.lower() for s in skills]
    
    devops_reqs = ["Linux Administration", "Docker & Containerization", "Kubernetes Orchestration", "CI/CD Pipelines (GitHub Actions/Jenkins)", "Terraform IaC", "AWS/Azure Cloud Fundamentals"]
    
    missing = [req for req in devops_reqs if not any(kw in req.lower() for kw in skills_lower)]
    return missing if missing else ["Advanced System Design", "Production Monitoring & Observability"]
