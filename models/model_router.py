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
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

# Load environment variables from .env file
load_dotenv()


def get_model_for_task(task_name: str) -> BaseChatModel:
    """
    Returns a configured LangChain Chat Model client tailored for the specified agent task.
    
    Args:
        task_name (str): Name of agent task ('intent_analysis', 'career_research', 'skills_gap', 'final_recommendation').
        
    Returns:
        BaseChatModel: Configured LangChain chat model instance.
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
        return _get_fallback_model(task_name)

    else:
        raise ValueError(f"Unknown task name '{task_name}'. Valid tasks: intent_analysis, career_research, skills_gap, final_recommendation.")


def _get_fallback_model(task_name: str) -> BaseChatModel:
    """
    Internal helper returning a mock/dummy Runnable or basic ChatOpenAI instance for offline testing.
    """
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    
    # Return contextually sensible fake responses for offline testing
    if task_name == "intent_analysis":
        responses = [AIMessage(content='{"skills": ["Python", "Java"], "goal": "DevOps Engineer"}')]
    elif task_name == "skills_gap":
        responses = [AIMessage(content='["Docker", "Kubernetes", "CI/CD Pipelines", "Linux Administration", "Terraform"]')]
    else:
        responses = [AIMessage(content="### Career Recommendation\n\n**Recommended Role:** DevOps Engineer\n**Missing Skills:** Docker, Kubernetes, CI/CD, Linux\n**Certifications:** AWS Certified Solutions Architect Associate\n**Roadmap:** 1. Master Linux CLI -> 2. Containerization with Docker -> 3. CI/CD with GitHub Actions.")]

    return FakeMessagesListChatModel(responses=responses)
