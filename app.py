"""
Career Advisor Agentic AI - Streamlit Web Application.

This is the primary user interface for the Sri Lankan IT Student Career Guidance System.
It integrates our LangGraph multi-agent orchestration pipeline with RAG document retrieval
and displays structured career guidance, skill gap analysis, and learning roadmaps.

Usage:
    streamlit run app.py
"""

import sys
import os
import time

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from agents.graph import run_career_advisor
from agents.state import CareerAdvisorState


# ------------------------------------------------------------------------------
# 1. Page Configuration & Custom CSS Styling
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Career Advisor Agentic AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Rich Aesthetics & Glassmorphism UI
st.markdown("""
<style>
    /* Global Fonts & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Gradient Banner */
    .header-banner {
        background: linear-gradient(135deg, #1e1e2f 0%, #0f172a 50%, #1e293b 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .header-title {
        color: #F8FAFC;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    
    .header-subtitle {
        color: #94A3B8;
        font-size: 1.05rem;
        margin-top: 0.5rem;
        font-weight: 400;
    }
    
    /* Badge Pills for Skills */
    .skill-pill {
        display: inline-block;
        background-color: #1E293B;
        color: #38BDF8;
        border: 1px solid #0284C7;
        padding: 0.35rem 0.8rem;
        border-radius: 20px;
        font-size: 0.88rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    .missing-skill-pill {
        display: inline-block;
        background-color: #311213;
        color: #FCA5A5;
        border: 1px solid #DC2626;
        padding: 0.35rem 0.8rem;
        border-radius: 20px;
        font-size: 0.88rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    
    /* Card Container */
    .card-box {
        background-color: #0F172A;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #1E293B;
        margin-bottom: 1.5rem;
    }

    /* Metric Box */
    .metric-card {
        background: #1E293B;
        padding: 1.2rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #334155;
    }
    
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38BDF8;
    }
    
    .metric-lbl {
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. Sidebar Navigation & Configuration
# ------------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/color/96/artificial-intelligence.png", width=64)
    st.title("Career Advisor AI")
    st.caption("Agentic Guidance System for Sri Lankan IT Students")
    st.markdown("---")

    # API Keys Expander
    with st.expander("🔑 API Key Settings", expanded=False):
        groq_key = st.text_input("GROQ_API_KEY", value=os.getenv("GROQ_API_KEY", ""), type="password")
        openrouter_key = st.text_input("OPENROUTER_API_KEY", value=os.getenv("OPENROUTER_API_KEY", ""), type="password")
        
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = openrouter_key
            
        st.info("Keys are loaded from `.env` or set above for model routing.")

    st.markdown("### 💡 Quick Sample Profiles")
    st.caption("Click any button below to pre-fill a student profile:")

    sample_prompt_1 = "I'm an IT student. I know Python and Java. I want to become a DevOps Engineer."
    sample_prompt_2 = "I'm a Computer Science undergraduate. I know Python, SQL, and HTML. I want to become a Data Scientist."
    sample_prompt_3 = "I know C#, Linux, and Networking basics. I want to become a Cloud Engineer."

    if st.button("🚀 DevOps Engineer Path", use_container_width=True):
        st.session_state["user_input_text"] = sample_prompt_1
    if st.button("📊 Data Scientist Path", use_container_width=True):
        st.session_state["user_input_text"] = sample_prompt_2
    if st.button("☁️ Cloud Engineer Path", use_container_width=True):
        st.session_state["user_input_text"] = sample_prompt_3

    st.markdown("---")
    st.markdown("#### ⚙️ LangGraph Multi-Agent Pipeline")
    st.markdown("""
    1. **Intent Analysis Agent** *(Groq Llama-3.1)*
    2. **Career Research Agent** *(RAG Tool)*
    3. **Skills Gap Agent** *(Groq Llama-3.1)*
    4. **Recommendation Agent** *(OpenRouter)*
    """)


# ------------------------------------------------------------------------------
# 3. Main Interface Header
# ------------------------------------------------------------------------------
st.markdown("""
<div class="header-banner">
    <div class="header-title">🎓 Career Advisor Agentic AI</div>
    <div class="header-subtitle">Empowering Sri Lankan IT Students with AI-Driven Career Recommendations, RAG Knowledge Base Insights, and Skill Roadmaps</div>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 4. Student Profile Input Area
# ------------------------------------------------------------------------------
if "user_input_text" not in st.session_state:
    st.session_state["user_input_text"] = "I'm an IT student. I know Python and Java. I want to become a DevOps Engineer."

st.subheader("📝 Tell Us About Your IT Background & Goal")

user_input = st.text_area(
    label="Describe your current technical skills, languages, tools, and target IT career role:",
    value=st.session_state["user_input_text"],
    height=120,
    placeholder="e.g. I am in my 3rd year at SLIIT. I know React, Node.js, and SQL. I want to become a Full-Stack Developer."
)

col_submit, col_clear = st.columns([1, 4])
with col_submit:
    analyze_btn = st.button("🚀 Analyze Career Path", type="primary", use_container_width=True)


# ------------------------------------------------------------------------------
# 5. Pipeline Execution & Multi-Agent Status Display
# ------------------------------------------------------------------------------
if analyze_btn:
    if not user_input.strip():
        st.warning("Please enter your technical skills and career goal before running analysis.")
    else:
        st.markdown("---")
        st.subheader("⚡ Multi-Agent Orchestration Execution")
        
        # Interactive Status Container
        status_box = st.status("Executing LangGraph Multi-Agent Workflow...", expanded=True)
        
        try:
            with status_box:
                st.write("🔍 **Agent 1 (Intent Analysis)**: Extracting skills and target career goal...")
                time.sleep(0.3)
                
                st.write("📚 **Agent 2 (Career Research)**: Invoking RAG vector store for job requirements & roadmaps...")
                time.sleep(0.3)
                
                st.write("⚖️ **Agent 3 (Skills Gap Analysis)**: Comparing user skills against industry standards...")
                time.sleep(0.3)
                
                st.write("🎓 **Agent 4 (Recommendation Agent)**: Synthesizing final structured roadmap & report...")
                
                # Execute LangGraph Pipeline
                start_time = time.time()
                final_state = run_career_advisor(user_input)
                elapsed = round(time.time() - start_time, 2)
                
                status_box.update(label=f"✅ All 4 Agents Executed Successfully! ({elapsed}s)", state="complete", expanded=False)
                
            st.session_state["last_result"] = final_state
            
        except Exception as e:
            status_box.update(label="❌ Error during Agent Execution", state="error")
            st.error(f"Execution Error: {e}")


# ------------------------------------------------------------------------------
# 6. Output Dashboard & Results Display
# ------------------------------------------------------------------------------
if "last_result" in st.session_state:
    res: CareerAdvisorState = st.session_state["last_result"]
    
    st.markdown("---")
    st.subheader("📊 Career Recommendation Dashboard")

    # Metrics Summary Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{res.get("goal", "N/A")}</div><div class="metric-lbl">Target Role</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(res.get("skills", []))}</div><div class="metric-lbl">Known Skills</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(res.get("missing_skills", []))}</div><div class="metric-lbl">Missing Skills</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card"><div class="metric-val">{len(res.get("retrieved_context", []))}</div><div class="metric-lbl">RAG Chunks</div></div>', unsafe_allow_html=True)

    st.write("")

    # Display Output Tabs
    tab_roadmap, tab_profile, tab_rag = st.tabs([
        "🎓 Structured Career Roadmap",
        "🎯 Profile & Skills Gap",
        "📚 RAG Knowledge Base Citations"
    ])

    # Tab 1: Final Recommendation Report
    with tab_roadmap:
        st.markdown("### 🏆 Personalized Learning & Career Plan")
        st.markdown(res.get("final_recommendation", "No recommendation generated."))

    # Tab 2: Profile & Skills Gap Visualization
    with tab_profile:
        col_known, col_gap = st.columns(2)
        
        with col_known:
            st.markdown("#### ✅ Current Known Skills")
            skills_list = res.get("skills", [])
            if skills_list:
                pills_html = "".join([f'<span class="skill-pill">✓ {s}</span>' for s in skills_list])
                st.markdown(pills_html, unsafe_allow_html=True)
            else:
                st.info("No specific technical skills were detected in the input.")
                
        with col_gap:
            st.markdown("#### 🚨 Identified Missing Skills Gap")
            missing_list = res.get("missing_skills", [])
            if missing_list:
                gap_pills_html = "".join([f'<span class="missing-skill-pill">⚠ {s}</span>' for s in missing_list])
                st.markdown(gap_pills_html, unsafe_allow_html=True)
            else:
                st.success("Great job! No major skill gaps identified for your target role.")

    # Tab 3: RAG Knowledge Base Citations
    with tab_rag:
        st.markdown("#### 📚 Retrieved RAG Knowledge Base Context")
        st.caption("These document chunks were retrieved from ChromaDB to ground your recommendation:")
        
        context_chunks = res.get("retrieved_context", [])
        if context_chunks:
            for idx, snippet in enumerate(context_chunks, 1):
                with st.expander(f"Chunk #{idx} Source Citation", expanded=(idx == 1)):
                    st.markdown(f"```text\n{snippet}\n```")
        else:
            st.info("No RAG chunks retrieved. (Ensure documents are in `/data` and `python rag/ingest.py` has been executed).")
