"""
Agent 4: Career Recommendation Agent (Synthesizer).

This agent uses an advanced reasoning model via OpenRouter (GPT-4o-mini / Claude 3.5 Sonnet)
to synthesize all state findings (goal, current skills, RAG context, missing skills)
into a structured, personalized career guidance roadmap tailored for Sri Lankan IT students.

Input State:  {"user_input": str, "skills": List[str], "goal": str, "retrieved_context": List[str], "missing_skills": List[str]}
Output State: {"final_recommendation": str}
"""

import sys
import os

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from langchain_core.messages import SystemMessage, HumanMessage
from agents.state import CareerAdvisorState
from models.model_router import get_model_for_task


def recommendation_agent(state: CareerAdvisorState) -> CareerAdvisorState:
    """
    Worker Node 4: Synthesizes all gathered data into a structured final career recommendation report.
    
    Args:
        state (CareerAdvisorState): Complete pipeline state.
        
    Returns:
        CareerAdvisorState: Updated state dictionary with 'final_recommendation'.
    """
    goal = state.get("goal", "DevOps Engineer")
    skills = state.get("skills", [])
    missing_skills = state.get("missing_skills", [])
    retrieved_context = state.get("retrieved_context", [])

    print(f"\n[Agent 4: Recommendation Agent] Synthesizing final career roadmap for: \"{goal}\"")

    model = get_model_for_task("final_recommendation")

    context_text = "\n\n".join(retrieved_context) if retrieved_context else "Standard Sri Lankan IT market standards."

    system_prompt = (
        "You are the Lead Career Advisor AI for Sri Lankan IT undergraduates and job seekers. "
        "Synthesize the provided information into a highly structured, encouraging, and actionable career roadmap.\n\n"
        "Your response MUST include the following sections formatted in clean Markdown:\n"
        "1. ## Target Career Profile & Feasibility\n"
        "2. ## Current Strengths & Identified Missing Skills\n"
        "3. ## Recommended Certifications\n"
        "4. ## Step-by-Step Short Learning Roadmap (3-6 Months)\n"
        "5. ## Strategic Advice for the Sri Lankan IT Market\n"
    )

    user_prompt = (
        f"Target Goal: {goal}\n"
        f"Student's Current Known Skills: {skills}\n"
        f"Identified Missing Skills (Gap): {missing_skills}\n\n"
        f"Retrieved Domain Knowledge Context:\n{context_text}"
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
        final_text = content.strip()
    except Exception as e:
        print(f"[Agent 4: Recommendation Agent] Warning generating LLM recommendation: {e}. Generating fallback report.")
        final_text = _fallback_recommendation_report(goal, skills, missing_skills)

    print(f"  [+] Final Recommendation Generated ({len(final_text)} characters).")

    return {
        **state,
        "final_recommendation": final_text
    }


def _fallback_recommendation_report(goal: str, skills: list, missing_skills: list) -> str:
    """Fallback markdown report generator when LLM client is offline."""
    skills_str = ", ".join(skills) if skills else "General IT Fundamentals"
    missing_str = ", ".join(missing_skills) if missing_skills else "Cloud Architecture & Containerization"

    return f"""## Target Career Profile & Feasibility
- **Recommended Role:** {goal}
- **Assessment:** Your current foundation in `{skills_str}` provides a strong starting point for transitioning into a {goal} role in Sri Lanka.

## Current Strengths & Identified Missing Skills
- **Existing Strengths:** {skills_str}
- **Critical Missing Skills:** {missing_str}

## Recommended Certifications
1. **AWS Certified Solutions Architect – Associate** (Highly valued in Sri Lankan tech companies like Sysco LABS, Virtusa, WSO2)
2. **Docker Certified Associate (DCA)** or **CKAD (Kubernetes Developer)**

## Step-by-Step Short Learning Roadmap (3-6 Months)
1. **Month 1 (Fundamentals & Linux):** Master Linux command line, Bash scripting, and Git workflows.
2. **Month 2 (Containerization):** Learn Docker, build custom container images, and set up Docker Compose.
3. **Month 3 (CI/CD & Cloud):** Build automated CI/CD pipelines with GitHub Actions and deploy sample apps to AWS.

## Strategic Advice for the Sri Lankan IT Market
- Focus on practical hands-on GitHub projects over passive video tutorials.
- Connect with local DevOps communities (e.g. SLASSCOM, AWS User Group Sri Lanka).
"""
