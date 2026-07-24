"""
Career Advisor Agent State Schema.

This module defines the shared state data structure passed between all agents
in the LangGraph orchestration pipeline.

State Schema:
    - user_input (str): Raw text input provided by the student.
    - skills (list[str]): List of current technical skills extracted from user_input.
    - goal (str): Target IT career role or goal extracted from user_input.
    - retrieved_context (list[str]): Relevant job description & roadmap text chunks fetched from RAG knowledge base.
    - missing_skills (list[str]): Skills identified as missing when comparing current skills against retrieved context.
    - final_recommendation (str): Synthesized career advice, learning roadmap, and certification guidance.
"""

from typing import TypedDict, List


class CareerAdvisorState(TypedDict):
    """
    Shared state object passed sequentially between LangGraph worker nodes.
    Each agent node reads from this state and returns a dict with updated keys.
    """
    user_input: str
    skills: List[str]
    goal: str
    retrieved_context: List[str]
    missing_skills: List[str]
    final_recommendation: str
