"""
Career Advisor AI - Streamlit Web Application.

This Streamlit application acts as the interactive user interface for the Sri Lankan IT
student career advisor system, connecting student input to our multi-agent LangGraph workflow.

Course Assignment: IT41043 Agentic AI Assignment
"""

import sys
import os
import logging
from typing import Dict, Any

# Ensure project root directory is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from utils.secrets import get_secret
from agents.graph import run_career_advisor
from agents.state import CareerAdvisorState

# Configure console logger for debugging runtime errors
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CareerAdvisorUI")


# ------------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS Styling
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Career Advisor AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for clean layout & badge tags
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .main-description {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .skill-badge {
        display: inline-block;
        background-color: #E0F2FE;
        color: #0369A1;
        border: 1px solid #BAE6FD;
        padding: 0.3rem 0.75rem;
        border-radius: 16px;
        font-size: 0.88rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .missing-badge {
        display: inline-block;
        background-color: #FEE2E2;
        color: #B91C1C;
        border: 1px solid #FCA5A5;
        padding: 0.3rem 0.75rem;
        border-radius: 16px;
        font-size: 0.88rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .footer-text {
        font-size: 0.85rem;
        color: #94A3B8;
        text-align: center;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #E2E8F0;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. Main Header & Description
# ------------------------------------------------------------------------------
st.markdown('<div class="main-header">🎓 Career Advisor AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-description">'
    'An agentic AI system for Sri Lankan IT undergraduates and fresh graduates. '
    'Describe your current technical background and target career goals to receive personalized, RAG-grounded career advice, skill gap analysis, and learning roadmaps.'
    '</div>',
    unsafe_allow_html=True
)


# ------------------------------------------------------------------------------
# 3. Student Input Form & Validation
# ------------------------------------------------------------------------------
st.subheader("📝 Your Technical Profile & Career Goal")

placeholder_text = "I'm an IT student. I know Python and Java. I want to become a DevOps Engineer."

user_input = st.text_area(
    label="Describe your current technical skills, languages, tools, and your target IT career role:",
    value="",
    height=120,
    placeholder=placeholder_text
)

submit_btn = st.button("Get My Career Advice", type="primary")


# ------------------------------------------------------------------------------
# 4. Agent Pipeline Execution & Error Handling
# ------------------------------------------------------------------------------
if submit_btn:
    # INPUT VALIDATION: Check if text area is empty
    if not user_input or not user_input.strip():
        st.warning("Please enter your current skills and target career goal before submitting.")
    else:
        # Load API keys via secrets helper (supports st.secrets and local .env)
        groq_key = get_secret("GROQ_API_KEY")
        openrouter_key = get_secret("OPENROUTER_API_KEY")

        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = openrouter_key

        # SPINNER: Show loading state during multi-agent execution
        with st.spinner("Analyzing your profile and generating career advice..."):
            try:
                # Invoke LangGraph Multi-Agent Workflow
                final_state: CareerAdvisorState = run_career_advisor(user_input)
                st.session_state["career_advice_result"] = final_state
                
            except Exception as e:
                # Log full error to console for developer debugging
                logger.error(f"Error executing run_career_advisor: {e}", exc_info=True)
                print(f"[CONSOLE LOG - ERROR]: {e}")
                
                # Friendly error message for student user (no raw stack trace)
                st.error("An error occurred while generating your career advice. Please try again or check your configuration.")


# ------------------------------------------------------------------------------
# 5. Results Section Layout & Display
# ------------------------------------------------------------------------------
if "career_advice_result" in st.session_state:
    result: CareerAdvisorState = st.session_state["career_advice_result"]
    
    st.markdown("---")
    st.header("📊 Your Personalized Career Report")

    # Column Layout for Overview
    col_role, col_skills, col_gaps = st.columns([1.5, 2, 2])

    with col_role:
        st.markdown("### 🎯 Recommended Career")
        st.success(f"**{result.get('goal', 'Target Role')}**")

    with col_skills:
        st.markdown("### ✅ Extracted Current Skills")
        extracted_skills = result.get("skills", [])
        if extracted_skills:
            pills = "".join([f'<span class="skill-badge">✓ {s}</span>' for s in extracted_skills])
            st.markdown(pills, unsafe_allow_html=True)
        else:
            st.info("No specific technical skills detected in prompt.")

    with col_gaps:
        st.markdown("### 🚨 Identified Missing Skills")
        missing_skills = result.get("missing_skills", [])
        if missing_skills:
            gaps_html = "".join([f'<span class="missing-badge">⚠ {s}</span>' for s in missing_skills])
            st.markdown(gaps_html, unsafe_allow_html=True)
        else:
            st.success("No major skill gaps identified!")

    st.markdown("---")

    # Detailed Structured Sections
    st.markdown("### 🎓 Learning Roadmap & Certification Advice")
    st.markdown(result.get("final_recommendation", "No recommendation report available."))

    # Optional Expandable RAG Citations
    retrieved_context = result.get("retrieved_context", [])
    if retrieved_context:
        with st.expander("📚 View RAG Knowledge Base Sources Used"):
            for idx, chunk in enumerate(retrieved_context, 1):
                st.markdown(f"**Source Chunk #{idx}:**")
                st.code(chunk, language="text")


# ------------------------------------------------------------------------------
# 6. Student Assignment Footer
# ------------------------------------------------------------------------------
st.markdown("""
<div class="footer-text">
    IT41043 Agentic AI Assignment | Built with LangGraph, RAG, and Streamlit<br>
    <a href="https://github.com/your-username/career-advisor-agentic-ai" target="_blank">🔗 GitHub Repository</a>
</div>
""", unsafe_allow_html=True)
