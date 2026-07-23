"""
Agent 1: Intent Analysis Agent.

This agent receives the raw user text input and uses the Groq model (llama-3.1-8b-instant)
to extract structured JSON containing:
- skills: List of current programming languages, frameworks, or tools the user knows.
- goal: The target IT career role or goal mentioned by the student.

Input State:  {"user_input": str}
Output State: {"skills": List[str], "goal": str}
"""

import sys
import os
import json
import re

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import CareerAdvisorState
from models.model_router import get_model_for_task


def intent_analysis_agent(state: CareerAdvisorState) -> CareerAdvisorState:
    """
    Worker Node 1: Analyzes raw user text to extract current technical skills and career goal.
    
    Args:
        state (CareerAdvisorState): Current pipeline state.
        
    Returns:
        CareerAdvisorState: Updated state dictionary with 'skills' and 'goal'.
    """
    user_input = state.get("user_input", "")
    print(f"\n[Agent 1: Intent Analysis] Processing input: \"{user_input}\"")

    if not user_input or not user_input.strip():
        return {
            **state,
            "skills": [],
            "goal": "Software Engineer"
        }

    # Fetch model client from router (Groq / Llama-3.1-8b)
    model = get_model_for_task("intent_analysis")

    system_prompt = (
        "You are an expert IT career intake assistant for Sri Lankan IT students. "
        "Analyze the student's text and extract:\n"
        "1. 'skills': A JSON list of technical skills, languages, or tools the student currently knows.\n"
        "2. 'goal': The desired target IT career role (e.g. 'DevOps Engineer', 'Data Scientist', 'Full-Stack Developer').\n\n"
        "Return ONLY a valid JSON object in this exact format, with no Markdown wrapping or conversational text:\n"
        '{"skills": ["Python", "Java"], "goal": "DevOps Engineer"}'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]

    try:
        response = model.invoke(messages)
        content = response.content.strip()

        # Clean potential markdown code blocks (```json ... ```)
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content).strip()

        parsed = json.loads(content)
        extracted_skills = parsed.get("skills", [])
        extracted_goal = parsed.get("goal", "Software Engineer")

    except Exception as e:
        print(f"[Agent 1: Intent Analysis] Warning parsing LLM response: {e}. Applying regex/fallback extraction.")
        extracted_skills, extracted_goal = _heuristic_extraction(user_input)

    print(f"  [+] Extracted Skills: {extracted_skills}")
    print(f"  [+] Extracted Goal:   {extracted_goal}")

    return {
        "skills": extracted_skills,
        "goal": extracted_goal
    }


def _heuristic_extraction(text: str):
    """Fallback extraction when LLM returns non-JSON format."""
    known_skills = ["python", "java", "c++", "c#", "javascript", "typescript", "react", "node", "sql", "aws", "docker", "git", "linux", "html", "css"]
    text_lower = text.lower()
    
    found_skills = [s.title() for s in known_skills if s in text_lower]
    
    goal = "Software Engineer"
    if "devops" in text_lower:
        goal = "DevOps Engineer"
    elif "data scient" in text_lower or "data engineer" in text_lower:
        goal = "Data Scientist"
    elif "cloud" in text_lower:
        goal = "Cloud Engineer"
    elif "full stack" in text_lower or "full-stack" in text_lower:
        goal = "Full-Stack Developer"

    return found_skills, goal
