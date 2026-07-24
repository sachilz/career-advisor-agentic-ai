"""
Model Router Module for Hybrid LLM Orchestration.

This module provides dynamic model routing across two LLM providers:
1. Groq (llama-3.1-8b-instant):
   - Tasks: 'intent_analysis', 'career_research', 'skills_gap'
   - Why: Ultra-fast inference latency (<300ms) and zero/low token costs make Llama-3.1-8b ideal for
     high-frequency extraction, classification, and gap comparison tasks.

2. OpenRouter (OpenAI / Claude class models via OpenRouter endpoint):
   - Tasks: 'final_recommendation'
   - Why: Generating nuanced, empathetic, structured career roadmaps requires advanced reasoning,
     instruction following, and synthesis capabilities typical of frontier models (GPT-4o-mini / Claude 3.5 Sonnet).

Environment Variables Required:
   - GROQ_API_KEY
   - OPENROUTER_API_KEY
"""

import os
from typing import Any, Union
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

# Load environment variables from .env file
load_dotenv()


def get_model_for_task(task_name: str) -> Any:
    """
    Returns a configured LangChain Chat Model client tailored for the specified agent task.
    
    Args:
        task_name (str): Name of agent task ('intent_analysis', 'career_research', 'skills_gap', 'final_recommendation').
        
    Returns:
        BaseChatModel | Any: Configured LangChain chat model or fallback model instance.
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()

    # Task Router Logic
    if task_name in ["intent_analysis", "career_research", "skills_gap"]:
        """
        TRADE-OFF RATIONALE FOR GROQ (llama-3.1-8b-instant):
        - Latency: Sub-second token generation speeds keep agent workflow responsive.
        - Cost: Highly economical for standard JSON extraction and list comparisons.
        - Precision: Llama-3.1 8B excels at following JSON schemas and concise list outputs.
        """
        if groq_api_key and groq_api_key != "your_key_here":
            try:
                from langchain_groq import ChatGroq
                return ChatGroq(
                    model="llama-3.1-8b-instant",
                    groq_api_key=groq_api_key,
                    temperature=0.1
                )
            except Exception as e:
                print(f"[ModelRouter] Warning initializing ChatGroq: {e}. Falling back...")
        
        # Fallback if Groq API key is placeholder or missing
        print(f"[ModelRouter] Using default fallback LLM for task '{task_name}' (No valid GROQ_API_KEY provided).")
        return _get_fallback_model(task_name)

    elif task_name == "final_recommendation":
        """
        TRADE-OFF RATIONALE FOR OPENROUTER (openai/gpt-4o-mini or Claude):
        - Reasoning: Deep synthesis of student skills, gap analysis, and RAG context into an actionable career roadmap.
        - Quality: High creative formatting, professional tone, and multi-step reasoning capabilities.
        - Cost: Moderately higher cost per token, justified because it is called only ONCE at the final stage.
        """
        if openrouter_api_key and openrouter_api_key != "your_key_here":
            try:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model="openai/gpt-4o-mini",
                    openai_api_key=openrouter_api_key,
                    openai_api_base="https://openrouter.ai/api/v1",
                    temperature=0.3
                )
            except Exception as e:
                print(f"[ModelRouter] Warning initializing ChatOpenAI for OpenRouter: {e}. Falling back...")

        # Fallback if OpenRouter API key is placeholder or missing
        print(f"[ModelRouter] Using default fallback LLM for task '{task_name}' (No valid OPENROUTER_API_KEY provided).")
        return DynamicFallbackChatModel(task_name)

    else:
        raise ValueError(f"Unknown task name '{task_name}'. Valid tasks: intent_analysis, career_research, skills_gap, final_recommendation.")


class DynamicFallbackChatModel:
    """
    Dynamic fallback runnable when LLM API keys (Groq/OpenRouter) are missing or offline.
    Extracts the user input contextually and generates dynamic, role-appropriate responses
    instead of returning static hardcoded fallback data.
    """
    def __init__(self, task_name: str):
        self.task_name = task_name

    def invoke(self, input_messages, config=None, **kwargs):
        import json
        import re
        from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

        # Extract only user / human text content to prevent system prompt pollution
        user_text = ""
        full_text = ""
        if isinstance(input_messages, list):
            for m in input_messages:
                if isinstance(m, BaseMessage):
                    if isinstance(m.content, str):
                        content_str = m.content
                    elif isinstance(m.content, list):
                        content_str = " ".join(str(c) for c in m.content)
                    else:
                        content_str = str(m.content)
                else:
                    content_str = str(m)

                full_text += content_str + "\n"
                is_human = False
                if hasattr(m, "type") and getattr(m, "type", "") in ["human", "user"]:
                    is_human = True
                elif isinstance(m, HumanMessage):
                    is_human = True

                if is_human:
                    user_text += content_str + "\n"

            if not user_text.strip():
                user_text = full_text
        else:
            user_text = str(input_messages)
            full_text = user_text

        if self.task_name == "intent_analysis":
            from agents.intent_analysis_agent import _heuristic_extraction
            skills, goal = _heuristic_extraction(user_text)
            content = json.dumps({"skills": skills, "goal": goal})

        elif self.task_name == "skills_gap":
            from agents.skills_gap_agent import _fallback_gap_analysis
            goal_match = re.search(r"Target Role Goal:\s*(.+)", full_text)
            skills_match = re.search(r"Student's Current Skills:\s*\[(.*?)\]", full_text)

            goal = goal_match.group(1).strip() if goal_match else "Software Engineer"
            skills_raw = skills_match.group(1) if skills_match else ""
            skills = [s.strip("'\" ") for s in skills_raw.split(",") if s.strip("'\" ")]

            missing = _fallback_gap_analysis(skills, goal)
            content = json.dumps(missing)

        else: # final_recommendation
            from agents.recommendation_agent import _fallback_recommendation_report
            goal_match = re.search(r"Target Goal:\s*(.+)", full_text)
            skills_match = re.search(r"Student's Current Known Skills:\s*\[(.*?)\]", full_text)
            missing_match = re.search(r"Identified Missing Skills \(Gap\):\s*\[(.*?)\]", full_text)

            goal = goal_match.group(1).strip() if goal_match else "Software Engineer"
            skills_raw = skills_match.group(1) if skills_match else ""
            missing_raw = missing_match.group(1) if missing_match else ""
            skills = [s.strip("'\" ") for s in skills_raw.split(",") if s.strip("'\" ")]
            missing = [m.strip("'\" ") for m in missing_raw.split(",") if m.strip("'\" ")]

            content = _fallback_recommendation_report(goal, skills, missing)

        return AIMessage(content=content)


def _get_fallback_model(task_name: str):
    return DynamicFallbackChatModel(task_name)