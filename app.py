# Career Advisor AI - Streamlit Web Application (Ultra-Modern & Interactive Edition)
# Course Assignment: IT41043 Agentic AI Assignment

import sys
import os
import logging
import time
import re
from typing import Dict, Any, List, cast

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
# Helper Functions for Parsing & Formatting Professional Text
# ------------------------------------------------------------------------------
def clean_text_formatting(text: str) -> str:
    """Sanitize raw markdown formatting into clean HTML with consistent, prominent subheaders."""
    if not text:
        return ""
    
    cleaned = text.strip()
    lines = cleaned.split("\n")
    formatted_lines = []
    first_header_skipped = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append("<br>")
            continue
            
        # Check if line is a top-level section header (e.g. ## Step-by-Step... or # Target Career...)
        if (stripped.startswith("#") or stripped.startswith("##")) and not stripped.startswith("###") and not first_header_skipped:
            first_header_skipped = True
            continue
            
        clean_header = re.sub(r'^\s*#{1,6}\s*', '', stripped)
        clean_header_text = clean_header.replace('**', '').strip()
        lower_header = clean_header_text.lower()
        
        # Identify month/phase/step subheaders or ### markdown headers
        is_subheading = (
            stripped.startswith("###") or 
            stripped.startswith("####") or 
            lower_header.startswith("month ") or 
            lower_header.startswith("phase ") or 
            lower_header.startswith("step ") or 
            bool(re.match(r'^(month|phase|step)\s*\d+', lower_header))
        )
        
        if is_subheading:
            formatted_lines.append(
                f'<h4 style="color: #818cf8; font-size: 1.2rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: 0.55rem; display: flex; align-items: center; gap: 0.4rem; font-family: inherit;">'
                f'📍 {clean_header_text}</h4>'
            )
        else:
            # Convert **bold** to <b>bold</b>
            formatted = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', stripped)
            formatted = formatted.replace('<b>"', '<b>').replace('"</b>', '</b>').replace('""', '"')
            formatted_lines.append(formatted)
            
    result_html = "\n".join(formatted_lines)
    
    # Strip leading <br> tags if any
    while result_html.startswith('<br>') or result_html.startswith('<br/>'):
        result_html = re.sub(r'^(<br\s*/?>)+', '', result_html).strip()
        
    return result_html


def clean_bullet_item(item: str) -> str:
    """Format an individual rung detail bullet point into clean HTML without raw markdown."""
    if not item:
        return ""
        
    cleaned = item.strip()
    
    # Strip leading bullet dashes, asterisks, or numbers
    cleaned = re.sub(r'^[-\*\•\d+\.\)]+\s*', '', cleaned)
    
    # Convert **bold** to <b>bold</b>
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', cleaned)
    
    # Remove quotes inside bold tags
    cleaned = cleaned.replace('<b>"', '<b>').replace('"</b>', '</b>')
    cleaned = cleaned.replace('""', '"')
    
    return f'• {cleaned}'


def parse_roadmap_sections(text: str) -> Dict[str, str]:
    """Parse raw markdown recommendation into key logical sections."""
    sections = {
        "profile": "",
        "strengths_gaps": "",
        "certifications": "",
        "roadmap": "",
        "market_advice": ""
    }
    
    current_key = "profile"
    lines = text.split("\n")
    buffer = []
    
    for line in lines:
        stripped = line.strip()
        lower_line = stripped.lower()
        clean_h = re.sub(r'^\s*#{1,6}\s*', '', lower_line)
        
        # Check if header is a section boundary (starts with # or ## or numbered section header)
        is_section_header = (
            stripped.startswith("## ") or 
            stripped.startswith("# ") or 
            bool(re.match(r'^\s*#{1,2}\s+\d+[\.\)]', stripped))
        )
        
        # Ensure it's not a step/month header like "## Month 4: ..." or "## Phase 2: ..."
        is_month_or_step_header = (
            ("month " in clean_h or "phase " in clean_h or bool(re.match(r'^(month|phase|step)\s*\d+', clean_h))) and
            ("step-by-step" not in clean_h) and ("learning roadmap" not in clean_h)
        )
        
        if is_section_header and not is_month_or_step_header:
            if "target career" in clean_h or "feasibility" in clean_h or "profile" in clean_h:
                if buffer and current_key:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = "profile"
                buffer = [line]
                continue
            elif "strengths" in clean_h or "missing skills" in clean_h or "gap" in clean_h:
                if buffer and current_key:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = "strengths_gaps"
                buffer = [line]
                continue
            elif "roadmap" in clean_h or "step-by-step" in clean_h or "learning" in clean_h:
                if buffer and current_key:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = "roadmap"
                buffer = [line]
                continue
            elif ("certifications" in clean_h or "credentials" in clean_h or "qualification" in clean_h):
                if buffer and current_key:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = "certifications"
                buffer = [line]
                continue
            elif "strategic advice" in clean_h or "sri lanka" in clean_h or "market" in clean_h:
                if buffer and current_key:
                    sections[current_key] = "\n".join(buffer).strip()
                current_key = "market_advice"
                buffer = [line]
                continue
                
        buffer.append(line)
            
    if buffer and current_key:
        sections[current_key] = "\n".join(buffer).strip()
        
    return sections


def extract_timeline_steps(roadmap_text: str) -> List[Dict[str, Any]]:
    """Extract individual month-wise ladder step rungs from the roadmap section ONLY."""
    steps = []
    if not roadmap_text:
        return steps
        
    lines = roadmap_text.split("\n")
    current_step = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        clean = stripped.lstrip("#*- ").rstrip("*").strip()
        lower = clean.lower()
        
        # Skip section titles/topics
        if (
            "step-by-step" in lower or 
            "learning roadmap" in lower or 
            "career profile" in lower or 
            "current strengths" in lower or 
            "missing skills" in lower or
            "strategic advice" in lower or
            "recommended cert" in lower
        ):
            continue
            
        # STRICTLY match month or phase headers ONLY (e.g. "Month 1: ...", "Month 1-2: ...", "Phase 1: ...")
        is_month_header = (
            lower.startswith("month ") or
            lower.startswith("phase ") or
            bool(re.match(r'^(month|phase)\s*[\d\-]+', lower))
        )
        
        if is_month_header:
            if current_step:
                steps.append(current_step)
            current_step = {"title": clean.replace('**', '').replace('##', '').replace('###', '').strip(), "details": []}
        elif current_step:
            # Only append details if line doesn't start a new section header
            if not stripped.startswith("## ") and not stripped.startswith("# "):
                if isinstance(current_step.get("details"), list):
                    current_step["details"].append(stripped)
            
    if current_step:
        steps.append(current_step)
        
    return steps


def extract_certification_items(cert_text: str) -> List[Dict[str, str]]:
    """Parse raw certifications text into individual structured certification card dicts."""
    certs = []
    if not cert_text:
        return certs
        
    # Strip raw div and html tags
    clean_input = re.sub(r'</?(div|p|span|code|pre)[^>]*>', '', cert_text)
    
    lines = clean_input.split("\n")
    current_cert = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        clean = stripped.lstrip("#*- ").rstrip("*").strip()
        clean = re.sub(r'</?[^>]+>', '', clean).strip()
        
        if not clean or clean.lower() == "div" or clean.startswith("</"):
            continue
        
        # Check if line is a cert title like "1. AWS Certified...", "**Docker Certified...**", "CKAD: ..."
        is_cert_title = (
            bool(re.match(r'^\d+[\.\)]\s+', clean)) or
            stripped.startswith("###") or
            stripped.startswith("####") or
            (stripped.startswith("**") and stripped.endswith("**"))
        )
        
        if is_cert_title:
            if current_cert and current_cert["title"]:
                certs.append(current_cert)
            title = clean.replace('**', '').replace('###', '').replace('####', '').strip()
            title = re.sub(r'^\d+[\.\)]\s*', '', title)
            current_cert = {"title": title, "desc": ""}
        elif current_cert:
            clean_desc = clean_bullet_item(stripped)
            clean_desc = re.sub(r'</?[^>]+>', '', clean_desc).strip()
            if clean_desc and clean_desc.lower() != "div":
                if current_cert["desc"]:
                    current_cert["desc"] += " " + clean_desc
                else:
                    current_cert["desc"] = clean_desc
                    
    if current_cert and current_cert["title"]:
        certs.append(current_cert)
        
    # Final sanitization pass
    final_certs = []
    for c in certs:
        c_title = re.sub(r'</?[^>]+>', '', c["title"]).strip()
        c_desc = re.sub(r'</?[^>]+>', '', c["desc"]).strip()
        if c_title and c_title.lower() != "div":
            final_certs.append({"title": c_title, "desc": c_desc})
            
    return final_certs


def get_month_card_metadata(title_text: str, details_list: List[str], idx: int) -> Dict[str, str]:
    """Extract visual design metadata for photo-style monthly career ladder timeline cards."""
    clean_title = title_text.replace('**', '').replace('##', '').replace('###', '').strip()
    
    default_icons = ["💻", "🐳", "⚙️", "☸️", "☁️", "💼", "🧠", "📊"]
    default_nodes = ["🎓", "⚡", "🔄", "🏛️", "🌐", "🏆", "🎯", "🚀"]
    
    icon = default_icons[(idx - 1) % len(default_icons)]
    node = default_nodes[(idx - 1) % len(default_nodes)]
    badge = f"MONTH {idx:02d}" if idx <= 99 else f"STEP {idx}"
    
    # Try parsing title format like "Month 1: Linux Administration..."
    parts = clean_title.split(":", 1)
    if len(parts) == 2:
        badge_part = parts[0].strip().upper()
        if "MONTH" in badge_part or "PHASE" in badge_part or "STEP" in badge_part:
            badge = badge_part
        main_title = parts[1].strip()
    else:
        main_title = clean_title
        
    lower_t = main_title.lower()
    subtitle = "Core Skills & Practical Mastery Phase"
    
    if "linux" in lower_t or "system" in lower_t or "os" in lower_t:
        icon = "💻"
        node = "🎓"
        subtitle = "Linux CLI, System Administration & Bash"
    elif "docker" in lower_t or "container" in lower_t:
        icon = "🐳"
        node = "⚡"
        subtitle = "Containerization & Multi-Container Deployment"
    elif "ci/cd" in lower_t or "jenkins" in lower_t or "github action" in lower_t or "automation" in lower_t or "pipeline" in lower_t:
        icon = "⚙️"
        node = "🔄"
        subtitle = "Automated Delivery Pipelines & Workflow Automation"
    elif "kubernetes" in lower_t or "k8s" in lower_t or "orchestr" in lower_t:
        icon = "☸️"
        node = "🏛️"
        subtitle = "Container Orchestration, Clusters & Helm"
    elif "terraform" in lower_t or "cloud" in lower_t or "aws" in lower_t or "iac" in lower_t or "azure" in lower_t:
        icon = "☁️"
        node = "🌐"
        subtitle = "Infrastructure as Code & Cloud Computing"
    elif "sri lanka" in lower_t or "interview" in lower_t or "career" in lower_t or "portfolio" in lower_t or "cert" in lower_t:
        icon = "💼"
        node = "🏆"
        subtitle = "Sri Lanka IT Industry Execution & Certification"
    elif "python" in lower_t or "programming" in lower_t or "backend" in lower_t:
        icon = "🐍"
        node = "💻"
        subtitle = "Backend Development & Software Architecture"
    elif "react" in lower_t or "frontend" in lower_t or "web" in lower_t or "js" in lower_t:
        icon = "⚛️"
        node = "🎨"
        subtitle = "Modern Web Frontend & UI Applications"
    elif "data" in lower_t or "sql" in lower_t or "database" in lower_t:
        icon = "📊"
        node = "🗄️"
        subtitle = "Database Engineering & Data Management"
    elif "ai" in lower_t or "machine learning" in lower_t or "llm" in lower_t or "agent" in lower_t:
        icon = "🧠"
        node = "🤖"
        subtitle = "Artificial Intelligence & Agentic AI Architecture"
        
    return {
        "badge": badge,
        "main_title": main_title,
        "subtitle": subtitle,
        "icon": icon,
        "node_icon": node
    }



# ------------------------------------------------------------------------------
# 1. Page Configuration & Modern Glassmorphic Custom CSS Design System
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Career Advisor AI | Sri Lanka IT Edition",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject Modern CSS for Glassmorphism, Micro-Animations, Micro-Interactions & Responsiveness
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --bg-dark: #080c14;
        --card-bg: rgba(15, 23, 42, 0.75);
        --card-border: rgba(255, 255, 255, 0.08);
        --card-border-hover: rgba(99, 102, 241, 0.4);
        --accent-primary: #6366f1;
        --accent-secondary: #8b5cf6;
        --accent-cyan: #06b6d4;
        --accent-emerald: #10b981;
        --accent-rose: #f43f5e;
        --text-bright: #f8fafc;
        --text-muted: #94a3b8;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: var(--bg-dark);
        color: var(--text-bright);
    }

    /* Hide default Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {background: transparent;}
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1240px;
    }

    /* Keyframe Animations */
    @keyframes meshGlow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 20px rgba(99, 102, 241, 0.3); }
        50% { box-shadow: 0 0 35px rgba(139, 92, 246, 0.6); }
    }

    /* Hero Banner Container */
    .hero-glass-container {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 27, 75, 0.85) 50%, rgba(49, 16, 75, 0.9) 100%);
        background-size: 200% 200%;
        animation: meshGlow 12s ease infinite;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 28px;
        padding: 2.75rem 2.25rem;
        margin-bottom: 2rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(16px);
    }

    .hero-glass-container::before {
        content: '';
        position: absolute;
        top: -40%;
        right: -10%;
        width: 350px;
        height: 350px;
        background: radial-gradient(circle, rgba(6, 182, 212, 0.25) 0%, rgba(0, 0, 0, 0) 70%);
        border-radius: 50%;
        pointer-events: none;
    }

    .hero-badge-top {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.2));
        border: 1px solid rgba(139, 92, 246, 0.35);
        color: #c084fc;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 0.3rem 0.85rem;
        border-radius: 20px;
        margin-bottom: 1rem;
    }

    .hero-title-text {
        font-size: clamp(2.2rem, 4vw, 3.2rem);
        font-weight: 800;
        line-height: 1.15;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 40%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.75rem;
    }

    .hero-subtitle-text {
        font-size: clamp(0.95rem, 1.5vw, 1.125rem);
        color: #94a3b8;
        max-width: 820px;
        line-height: 1.65;
        margin-bottom: 1.5rem;
    }

    .hero-chips-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
    }

    .hero-chip-item {
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #e2e8f0;
        padding: 0.4rem 0.95rem;
        border-radius: 20px;
        font-size: 0.84rem;
        font-weight: 600;
        transition: all 0.25s ease;
    }

    .hero-chip-item:hover {
        background: rgba(99, 102, 241, 0.15);
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateY(-1px);
    }

    /* Preset Profile Inspiration Cards */
    .preset-card-container {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 20px;
        padding: 1.25rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        margin-bottom: 0.85rem;
        backdrop-filter: blur(12px);
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }

    .preset-card-container:hover {
        border-color: var(--card-border-hover);
        transform: translateY(-3px);
        box-shadow: 0 15px 30px -10px rgba(99, 102, 241, 0.25);
    }

    .preset-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.3rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .preset-card-tag {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.2rem 0.55rem;
        border-radius: 12px;
        text-transform: uppercase;
    }

    .preset-tag-hot { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
    .preset-tag-ai { background: rgba(139, 92, 246, 0.15); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }
    .preset-tag-core { background: rgba(6, 182, 212, 0.15); color: #38bdf8; border: 1px solid rgba(6, 182, 212, 0.3); }

    .preset-card-desc {
        font-size: 0.85rem;
        color: #94a3b8;
        line-height: 1.45;
        margin-bottom: 0.4rem;
    }

    /* Metric Stat Box */
    .metric-card-glass {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.6) 0%, rgba(15, 23, 42, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 1rem 0.85rem;
        text-align: center;
        backdrop-filter: blur(12px);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        height: 130px;
        min-height: 130px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        box-sizing: border-box;
    }

    .metric-card-glass:hover {
        transform: translateY(-3px);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 12px 24px -8px rgba(99, 102, 241, 0.25);
    }

    .metric-val-num {
        font-size: clamp(1.2rem, 2vw, 1.7rem);
        font-weight: 800;
        line-height: 1.25;
        margin-top: 0.35rem;
        margin-bottom: 0;
        word-break: break-word;
        max-width: 100%;
    }

    .metric-lbl-text {
        font-size: 0.78rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    /* Skill Badges */
    .skill-badge-emerald {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.2) 100%);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
        padding: 0.45rem 0.95rem;
        border-radius: 20px;
        font-size: 0.86rem;
        font-weight: 600;
        margin-right: 0.45rem;
        margin-bottom: 0.55rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }

    .skill-badge-rose {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: linear-gradient(135deg, rgba(244, 63, 94, 0.15) 0%, rgba(225, 29, 72, 0.2) 100%);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.35);
        padding: 0.45rem 0.95rem;
        border-radius: 20px;
        font-size: 0.86rem;
        font-weight: 600;
        margin-right: 0.45rem;
        margin-bottom: 0.55rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    }

    /* Interactive Career Ladder Styling */
    .ladder-banner-glass {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
        border: 1px solid rgba(139, 92, 246, 0.35);
        border-radius: 22px;
        padding: 1.6rem;
        margin-bottom: 2rem;
        backdrop-filter: blur(12px);
    }

    .ladder-rung-card-glass {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left: 6px solid #6366f1;
        border-radius: 20px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.35rem;
        box-shadow: 0 12px 30px -10px rgba(0, 0, 0, 0.4);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .ladder-rung-card-glass:hover {
        transform: translateX(4px) translateY(-2px);
        border-color: rgba(99, 102, 241, 0.5);
    }

    .ladder-rung-completed-glass {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(6, 182, 212, 0.1) 100%);
        border: 1px solid rgba(16, 185, 129, 0.4);
        border-left: 6px solid #10b981;
    }

    .rung-header-flex {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.85rem;
        flex-wrap: wrap;
    }

    .rung-title-heading {
        font-size: 1.22rem;
        font-weight: 700;
        color: #ffffff;
    }

    .rung-step-pill {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        color: #ffffff;
        font-weight: 700;
        font-size: 0.78rem;
        padding: 0.3rem 0.85rem;
        border-radius: 14px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
    }

    .rung-step-pill-done {
        background: linear-gradient(135deg, #10b981, #059669);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }

    .rung-detail-bullet {
        color: #cbd5e1;
        font-size: 0.96rem;
        line-height: 1.65;
        margin-bottom: 0.4rem;
    }

    /* -------------------------------------------------------------------------
       Photo-Style Career Ladder Monthly Divider & Alternating Timeline Cards
       ------------------------------------------------------------------------- */
    .career-timeline-wrapper {
        position: relative;
        max-width: 1080px;
        margin: 2.5rem auto;
        padding: 1rem 0;
    }

    /* Central Multi-Color Glowing Vertical Line */
    .career-timeline-line {
        position: absolute;
        top: 0;
        bottom: 0;
        left: 50%;
        width: 4px;
        background: linear-gradient(180deg, #d946ef 0%, #a855f7 35%, #06b6d4 70%, #00f2fe 100%);
        transform: translateX(-50%);
        box-shadow: 0 0 16px rgba(0, 242, 254, 0.8), 0 0 25px rgba(217, 70, 239, 0.5);
        border-radius: 4px;
        z-index: 1;
    }

    /* Timeline Row Container */
    .career-timeline-row {
        position: relative;
        width: 50%;
        padding: 0.5rem 2.2rem;
        box-sizing: border-box;
        z-index: 2;
        margin-bottom: 2.2rem;
    }

    .career-timeline-row.row-left {
        left: 0;
    }

    .career-timeline-row.row-right {
        left: 50%;
    }

    /* Circular Node Badge on Central Vertical Line */
    .career-timeline-node {
        position: absolute;
        top: 1.8rem;
        width: 44px;
        height: 44px;
        background: #080c14;
        border: 2px solid #00f2fe;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        color: #ffffff;
        box-shadow: 0 0 18px rgba(0, 242, 254, 0.9);
        z-index: 4;
        transition: all 0.3s ease;
    }

    .career-timeline-node-completed {
        border-color: #10b981 !important;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.9) !important;
        background: #042f2e !important;
    }

    .career-timeline-node:hover {
        transform: scale(1.15);
        box-shadow: 0 0 25px rgba(0, 242, 254, 1);
    }

    .career-timeline-row.row-left .career-timeline-node {
        right: -22px;
    }

    .career-timeline-row.row-right .career-timeline-node {
        left: -22px;
    }

    /* Horizontal Connector Cyan Line */
    .career-timeline-connector {
        position: absolute;
        top: calc(1.8rem + 21px);
        height: 2px;
        background: #00f2fe;
        box-shadow: 0 0 10px #00f2fe;
        z-index: 3;
    }

    .career-timeline-row.row-left .career-timeline-connector {
        right: 22px;
        width: 20px;
    }

    .career-timeline-row.row-right .career-timeline-connector {
        left: 22px;
        width: 20px;
    }

    /* Card Styling Matching Photo */
    .photo-month-card {
        background: #0d0e15;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(14px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }

    .photo-month-card:hover {
        border-color: rgba(0, 242, 254, 0.45);
        transform: translateY(-4px);
        box-shadow: 0 20px 40px rgba(0, 242, 254, 0.18);
    }

    .photo-month-card-completed {
        background: rgba(8, 25, 23, 0.95);
        border: 1px solid rgba(16, 185, 129, 0.5);
        box-shadow: 0 15px 35px rgba(16, 185, 129, 0.25);
    }

    /* Top Pill Tag Badge */
    .photo-card-pill {
        float: right;
        background: #251343;
        border: 1px solid rgba(139, 92, 246, 0.5);
        color: #00f2fe;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 0.35rem 0.95rem;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .photo-card-pill-completed {
        background: rgba(16, 185, 129, 0.2);
        border-color: rgba(16, 185, 129, 0.6);
        color: #34d399;
    }

    /* Card Top Header & White Logo Square */
    .photo-card-header-flex {
        display: flex;
        align-items: center;
        gap: 1.1rem;
        margin-bottom: 0.85rem;
    }

    .photo-card-white-square {
        width: 58px;
        height: 58px;
        min-width: 58px;
        background: #ffffff;
        border-radius: 14px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 20px rgba(255, 255, 255, 0.25);
        font-size: 1.85rem;
        line-height: 1;
        box-sizing: border-box;
    }

    .photo-card-titles-wrap {
        flex-grow: 1;
    }

    .photo-card-main-title {
        font-size: 1.28rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.25;
        margin: 0 0 0.2rem 0;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    .photo-card-subtitle-cyan {
        font-size: 0.94rem;
        font-weight: 600;
        color: #00f2fe;
        margin: 0;
    }

    /* Card Body Description */
    .photo-card-body-desc {
        color: #94a3b8;
        font-size: 0.91rem;
        line-height: 1.65;
        margin-top: 0.85rem;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        padding-top: 0.85rem;
    }

    /* Responsive Mobile Layout */
    @media (max-width: 768px) {
        .career-timeline-line {
            left: 20px;
        }
        .career-timeline-row {
            width: 100% !important;
            left: 0 !important;
            padding-left: 55px;
            padding-right: 10px;
        }
        .career-timeline-row.row-left .career-timeline-node,
        .career-timeline-row.row-right .career-timeline-node {
            left: -2px !important;
            right: auto !important;
        }
        .career-timeline-row.row-left .career-timeline-connector,
        .career-timeline-row.row-right .career-timeline-connector {
            left: 20px !important;
            right: auto !important;
            width: 15px !important;
        }
    }

    /* Sri Lanka Strategic Advice Box */
    .sl-strategic-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.08) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: 22px;
        padding: 1.75rem;
        margin-top: 2rem;
        color: #e2e8f0;
        font-size: 0.98rem;
        line-height: 1.7;
    }

    /* Footer Container */
    .footer-glass {
        text-align: center;
        padding: 2.25rem 1rem 1.25rem 1rem;
        margin-top: 3.5rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        color: #94a3b8;
        font-size: 0.9rem;
    }

    .footer-glass a {
        color: #818cf8;
        text-decoration: none;
        font-weight: 600;
        transition: color 0.2s ease;
    }

    .footer-glass a:hover {
        color: #c084fc;
        text-decoration: underline;
    }

    /* Streamlit Input & Button Overrides */
    .stTextArea textarea {
        background: rgba(15, 23, 42, 0.8) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 16px !important;
        color: #f8fafc !important;
        font-size: 0.98rem !important;
        padding: 1rem !important;
        transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
    }

    .stTextArea textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 15px rgba(99, 102, 241, 0.35) !important;
    }

    /* Style Streamlit secondary buttons (autofill profile & skill chips) */
    div.stButton > button:not([kind="primary"]) {
        background: rgba(30, 41, 59, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 14px !important;
        color: #e2e8f0 !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 0.55rem 0.85rem !important;
        transition: all 0.25s ease !important;
        margin-top: 0.2rem !important;
    }

    div.stButton > button:not([kind="primary"]):hover {
        background: rgba(99, 102, 241, 0.25) !important;
        border-color: rgba(99, 102, 241, 0.5) !important;
        color: #ffffff !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 15px rgba(99, 102, 241, 0.2) !important;
    }

    /* Style Streamlit primary button */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #06b6d4 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        padding: 0.75rem 1.75rem !important;
        box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.5) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 15px 30px -5px rgba(124, 58, 237, 0.6) !important;
    }

    div.stButton > button[kind="primary"]:active {
        transform: translateY(0) scale(0.99) !important;
    }

    /* Modern Interactive Report Styling */
    .report-hero-header {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 22px;
        padding: 1.35rem 1.6rem;
        margin-bottom: 1.25rem;
        backdrop-filter: blur(14px);
        box-shadow: 0 15px 35px -10px rgba(0, 0, 0, 0.5);
    }

    .report-card-box {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.8) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 1.35rem 1.6rem;
        margin-bottom: 1.25rem;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.3);
    }

    .report-card-box:hover {
        border-color: rgba(99, 102, 241, 0.45);
        transform: translateY(-3px);
        box-shadow: 0 15px 30px -10px rgba(99, 102, 241, 0.3);
    }

    .sl-strategic-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.08) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: 20px;
        padding: 1.35rem 1.6rem;
        margin-top: 1.25rem;
        margin-bottom: 1.25rem;
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.65;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.3);
    }

    .sl-strategic-box:hover {
        border-color: rgba(16, 185, 129, 0.6);
        transform: translateY(-3px);
        box-shadow: 0 15px 30px -10px rgba(16, 185, 129, 0.3);
    }

    .report-section-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.85rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 0.6rem;
    }

    .report-strength-item {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.25);
        border-left: 5px solid #10b981;
        border-radius: 14px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.6rem;
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    .report-gap-item {
        background: rgba(244, 63, 94, 0.08);
        border: 1px solid rgba(244, 63, 94, 0.25);
        border-left: 5px solid #f43f5e;
        border-radius: 14px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.6rem;
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    /* Certification Cards Styling */
    .cert-card-glass {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.8) 0%, rgba(15, 23, 42, 0.85) 100%);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 20px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 0.85rem;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.4);
        box-sizing: border-box;
        height: 165px;
        min-height: 165px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        overflow: hidden;
    }

    .cert-card-glass:hover {
        border-color: rgba(192, 132, 252, 0.65);
        transform: translateY(-4px);
        box-shadow: 0 16px 32px -8px rgba(139, 92, 246, 0.35);
    }

    .cert-card-achieved {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.18) 0%, rgba(6, 182, 212, 0.15) 100%) !important;
        border: 1px solid rgba(16, 185, 129, 0.55) !important;
        box-shadow: 0 10px 25px rgba(16, 185, 129, 0.25) !important;
    }

    .cert-pill-tag {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(99, 102, 241, 0.25));
        border: 1px solid rgba(139, 92, 246, 0.4);
        color: #c084fc;
        font-weight: 700;
        font-size: 0.72rem;
        padding: 0.2rem 0.65rem;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .cert-pill-achieved {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        color: #ffffff !important;
        border: none !important;
    }

    /* Modern Glass Segmented Control Overrides for Streamlit Radio Widgets */
    div[data-testid="stRadio"] > label {
        color: #94a3b8 !important;
        font-weight: 700 !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-bottom: 0.5rem !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.65rem !important;
        background: rgba(15, 23, 42, 0.7) !important;
        padding: 0.45rem !important;
        border-radius: 18px !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(14px) !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] label {
        background: rgba(30, 41, 59, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 0.55rem 1.1rem !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        cursor: pointer !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
    }

    /* Hide the default radio circle dot completely */
    div[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }

    div[data-testid="stRadio"] div[role="radiogroup"] label:hover {
        background: rgba(99, 102, 241, 0.2) !important;
        border-color: rgba(99, 102, 241, 0.45) !important;
        color: #ffffff !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.25) !important;
    }

    /* Selected Active State */
    div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked),
    div[data-testid="stRadio"] div[role="radiogroup"] label[aria-checked="true"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        border-color: rgba(139, 92, 246, 0.6) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 8px 20px rgba(79, 70, 229, 0.4) !important;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(15, 23, 42, 0.6);
        padding: 0.4rem;
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 14px;
        color: #94a3b8;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.6rem 1.25rem;
        border: none !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3) !important;
    }

    /* Media Queries for Mobile Responsiveness */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1rem;
        }
        .hero-glass-container {
            padding: 1.75rem 1.25rem;
            border-radius: 20px;
        }
        .rung-header-flex {
            flex-direction: column;
            align-items: flex-start;
        }
        .ladder-rung-card-glass {
            padding: 1.25rem 1rem;
        }
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. Glassmorphic Hero Banner Header
# ------------------------------------------------------------------------------
st.markdown("""
<div class="hero-glass-container">
    <div class="hero-badge-top">
        <span>⚡ IT41043 Agentic AI Platform</span>
    </div>
    <div class="hero-title-text">🎓 Career Advisor AI</div>
    <div class="hero-subtitle-text">
        An agentic AI advisor designed specifically for Sri Lankan IT undergraduates & fresh graduates. 
        Analyze your technical background, identify skill gaps against market standards, and receive RAG-grounded learning roadmaps.
    </div>
    <div class="hero-chips-grid">
        <span class="hero-chip-item">⚡ LangGraph Multi-Agent Engine</span>
        <span class="hero-chip-item">📚 RAG Sri Lanka IT Knowledge Base</span>
        <span class="hero-chip-item">🎯 Interactive Elevation Ladder</span>
        <span class="hero-chip-item">🇱🇰 Local IT Market Focus 2026</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 3. Interactive Student Profile Input & Skill Quick-Builder
# ------------------------------------------------------------------------------
if "user_prompt_input" not in st.session_state:
    st.session_state["user_prompt_input"] = ""

st.markdown("### 📝 Enter Your Profile & Career Aspiration")
st.caption("✨ **Choose a sample profile or click skill chips below to autofill your query:**")

st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

# Sample Profile Preset Cards
col_p1, col_p2, col_p3 = st.columns(3)

with col_p1:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>🚀 DevOps Cloud</span>
            <span class="preset-card-tag preset-tag-hot">High Demand</span>
        </div>
        <div class="preset-card-desc">Python, Java, SQL, Docker & Git student seeking DevOps Cloud Engineer path.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Autofill DevOps Profile", key="btn_preset_1", use_container_width=True):
        st.session_state["user_prompt_input"] = (
            "I am a 3rd year IT student in Sri Lanka. I know Python, Java, SQL, basic Docker, and Git. "
            "My goal is to become a DevOps Cloud Engineer."
        )

with col_p2:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>📊 AI & ML Engineer</span>
            <span class="preset-card-tag preset-tag-ai">AI & Big Data</span>
        </div>
        <div class="preset-card-desc">Python, Pandas, SQL & Statistics background transitioning into Machine Learning.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Autofill ML Profile", key="btn_preset_2", use_container_width=True):
        st.session_state["user_prompt_input"] = (
            "I know Python, Pandas, SQL, and basic Statistics. "
            "I want to transition into an AI/ML Engineer role in Sri Lanka."
        )

with col_p3:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>🌐 Full-Stack Architect</span>
            <span class="preset-card-tag preset-tag-core">Core Tech</span>
        </div>
        <div class="preset-card-desc">React, Node.js, MongoDB & CSS dev aiming for Full-Stack Software Engineer.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Autofill Full-Stack Profile", key="btn_preset_3", use_container_width=True):
        st.session_state["user_prompt_input"] = (
            "I am proficient in React, HTML, CSS, JavaScript, and Node.js with MongoDB. "
            "I want to become a Senior Full-Stack Software Engineer."
        )

# Generous Spacing between Profile Cards and Quick-Add Section
st.markdown('<div style="margin-top: 2.25rem; margin-bottom: 0.85rem;"></div>', unsafe_allow_html=True)

# Quick-Add Skill Pills Bar
st.markdown("""
<div style="font-size: 1.02rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.85rem;">
    ⚡ Quick-Add Technical Skills to your prompt:
</div>
""", unsafe_allow_html=True)

col_chips = st.columns(6)
quick_skills = ["Python", "React", "Docker", "SQL", "AWS", "FastAPI"]
for idx, skill in enumerate(quick_skills):
    with col_chips[idx % 6]:
        if st.button(f"+ {skill}", key=f"chip_skill_{skill}", use_container_width=True):
            current_text = st.session_state.get("user_prompt_input", "").strip()
            if skill not in current_text:
                if current_text:
                    st.session_state["user_prompt_input"] = f"{current_text}, {skill}"
                else:
                    st.session_state["user_prompt_input"] = f"I know {skill}."

# Generous Spacing between Quick-Add Skills and Text Area
st.markdown('<div style="margin-top: 1.85rem;"></div>', unsafe_allow_html=True)

# Form Text Area
user_input = st.text_area(
    label="Describe your current technical skills, tools, languages, and target IT career role:",
    height=130,
    placeholder="e.g., I'm an IT undergraduate. I know Python, C#, MySQL, and Git. I want to become a Backend Developer.",
    key="user_prompt_input"
)

st.markdown('<div style="margin-top: 0.85rem;"></div>', unsafe_allow_html=True)

submit_col1, submit_col2 = st.columns([1.5, 3.5])
with submit_col1:
    submit_btn = st.button("Generate Career Advice & Roadmap", type="primary", use_container_width=True)


# ------------------------------------------------------------------------------
# 4. Multi-Agent Pipeline Execution & Animated Progress
# ------------------------------------------------------------------------------
if submit_btn:
    current_input = user_input.strip() if user_input else ""
    if not current_input:
        st.warning("Please enter your current skills and target career goal before submitting.")
    else:
        # Load API keys via secrets helper
        groq_key = get_secret("GROQ_API_KEY")
        openrouter_key = get_secret("OPENROUTER_API_KEY")

        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = openrouter_key

        # Interactive Multistage Step Progress Status Box
        status_box = st.status("**Multi-Agent Workflow Engine Active...**", expanded=True)
        with status_box:
            st.write("**Phase 1 (Intent Agent):** Parsing skills & extracting target goal...")
            time.sleep(0.3)
            st.write("**Phase 2 (RAG Agent):** Querying Sri Lanka IT Knowledge Base...")
            time.sleep(0.3)
            st.write("**Phase 3 (Gap Agent):** Calculating skills gap & market requirements...")
            time.sleep(0.3)
            st.write("**Phase 4 (Recommendation Agent):** Synthesizing career roadmap...")
            
            try:
                # Invoke LangGraph Multi-Agent Workflow
                final_state: CareerAdvisorState = cast(CareerAdvisorState, run_career_advisor(current_input))
                st.session_state["career_advice_result"] = final_state
                # Reset completed tracker sets on new query execution
                st.session_state["completed_roadmap_steps"] = set()
                st.session_state["learned_skills"] = set()
                status_box.update(label=" **Multi-Agent Career Analysis Complete!**", state="complete", expanded=False)
                
            except Exception as e:
                logger.error(f"Error executing run_career_advisor: {e}", exc_info=True)
                status_box.update(label=" **Analysis Error**", state="error", expanded=True)
                st.error(f"An error occurred while generating your advice: {e}")


# ------------------------------------------------------------------------------
# 5. Modern Structured Results Dashboard
# ------------------------------------------------------------------------------
if "career_advice_result" in st.session_state:
    result: CareerAdvisorState = st.session_state["career_advice_result"]
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("## Your Personalized Career Intelligence Report")

    extracted_skills = result.get("skills") or []
    missing_skills = result.get("missing_skills") or []
    raw_goal = result.get("goal")
    target_role = raw_goal.strip() if isinstance(raw_goal, str) and raw_goal.strip() else "Target IT Role"
    recommendation = result.get("final_recommendation") or "No report content generated."

    # High-Level Metric Stat Box Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Target IT Role</div>
            <div class="metric-val-num" style="color: #818cf8; font-size: 1.05rem;">🎯 {target_role}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col2:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Current Strengths</div>
            <div class="metric-val-num" style="color: #34d399; font-size: 1.7rem;">💪 {len(extracted_skills)}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col3:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Missing Skills</div>
            <div class="metric-val-num" style="color: #fb7185; font-size: 1.7rem;">🚨 {len(missing_skills)}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col4:
        match_score = "High" if len(missing_skills) <= 2 else ("Medium" if len(missing_skills) <= 4 else "Growth Needed")
        color = "#34d399" if match_score == "High" else ("#fbbf24" if match_score == "Medium" else "#818cf8")
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Role Alignment</div>
            <div class="metric-val-num" style="color: {color}; font-size: 1.15rem;">⚡ {match_score}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabbed View Navigation
    tab_roadmap, tab_skills, tab_rag = st.tabs([
        "🪜 Career Roadmap & Elevation Ladder", 
        "🎯 Skills Gap & Readiness Radar", 
        "📚 RAG Knowledge Base References"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: INTERACTIVE CAREER ROADMAP & ELEVATION LADDER
    # --------------------------------------------------------------------------
    with tab_roadmap:
        st.markdown("### 🪜 Interactive Career Elevation Ladder")
        
        parsed_sec = parse_roadmap_sections(recommendation)

        # View Selector
        view_mode = st.radio(
            "Select View Mode:",
            ["🪜 Interactive Career Ladder", "🎯 Live Skill Readiness Tracker", "📄 Full Markdown Report"],
            horizontal=True,
            key="roadmap_view_mode"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if view_mode == "🪜 Interactive Career Ladder":
            # Profile & Feasibility Hero Card
            if parsed_sec["profile"]:
                clean_profile = clean_text_formatting(parsed_sec["profile"])
                st.markdown(f"""
                <div class="report-card-box" style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.85) 0%, rgba(15, 23, 42, 0.9) 100%); border-color: rgba(99, 102, 241, 0.35);">
                    <div class="report-section-title">
                        <span>🎯 Target Career Profile & Feasibility Assessment</span>
                    </div>
                    <div>{clean_profile}</div>
                </div>
                """, unsafe_allow_html=True)

            steps = extract_timeline_steps(parsed_sec["roadmap"]) if parsed_sec["roadmap"] else []
            if not steps:
                steps = extract_timeline_steps(recommendation)
            if not steps:
                steps = [
                    {"title": "Month 1: Linux Administration & Systems Fundamentals", "details": ["• Master Linux CLI, user permissions, systemd services, bash scripting, and core networking tools (netstat, curl, ssh)."]},
                    {"title": "Month 2: Containerization with Docker", "details": ["• Learn Dockerfile optimization, multi-stage builds, container networking, volumes, and Docker Compose for multi-container apps."]},
                    {"title": "Month 3: Continuous Integration & CI/CD Pipelines", "details": ["• Build automated build, test, scan, and release workflows using GitHub Actions and Jenkins."]},
                    {"title": "Month 4: Container Orchestration with Kubernetes", "details": ["• Understand Pods, Deployments, Services, Ingress controllers, Helm charts, and cluster management on Minikube or EKS."]},
                    {"title": "Month 5: Infrastructure as Code (Terraform) & Cloud Fundamentals", "details": ["• Provision cloud infrastructure using Terraform HCL scripts, manage AWS EC2, S3, VPCs, and IAM policies."]},
                    {"title": "Month 6: Sri Lanka IT Market Execution, Certifications & Interview Prep", "details": ["• Complete LPIC-1/AWS cert prep, build GitHub portfolio, and apply for junior DevOps/SDET roles at Sysco LABS, Virtusa, and WSO2."]}
                ]

            if "completed_roadmap_steps" not in st.session_state:
                st.session_state["completed_roadmap_steps"] = set()

            if steps:
                completed_count = len(st.session_state["completed_roadmap_steps"])
                total_rungs = len(steps)
                progress_pct = int((completed_count / total_rungs) * 100)

                # Career Elevation Tier logic
                if completed_count == 0:
                    tier_name = "🌱 Tier 0: Career Aspirant"
                    tier_color = "#94a3b8"
                elif completed_count < total_rungs // 2:
                    tier_name = "🧱 Tier 1: Foundation Built"
                    tier_color = "#818cf8"
                elif completed_count < total_rungs:
                    tier_name = "⚡ Tier 2: Practitioner Level"
                    tier_color = "#fbbf24"
                else:
                    tier_name = "🏆 Tier 3: Industry Job-Ready"
                    tier_color = "#34d399"

                # Ladder Top Progress Banner
                st.markdown(f"""
                <div class="ladder-banner-glass">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem; flex-wrap: wrap; gap: 0.5rem;">
                        <span style="font-size: 1.35rem; font-weight: 800; color: #ffffff;">🪜 Ladder Climb Elevation</span>
                        <span style="font-size: 1.05rem; font-weight: 700; color: {tier_color}; background: rgba(0,0,0,0.4); padding: 0.4rem 1.1rem; border-radius: 20px; border: 1px solid {tier_color};">{tier_name}</span>
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.98rem; margin-bottom: 0.6rem;">
                        Climbed <b>{completed_count}</b> of <b>{total_rungs}</b> Rungs ({progress_pct}% Completed)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(progress_pct / 100.0)
                st.markdown("<br>", unsafe_allow_html=True)

                st.subheader("🪜 Monthly Career Ladder Timeline")
                st.caption("Check off each month phase as you master skills to climb your career ladder!")

                # Quick Interactive Checkbox Toolbar for Monthly Rung Completion
                st.markdown("**Quick Step Progress Checklist:**")
                chk_cols = st.columns(min(len(steps), 6))
                for idx, step_item in enumerate(steps, 1):
                    step_key = f"step_chk_{idx}"
                    is_checked = step_key in st.session_state["completed_roadmap_steps"]
                    with chk_cols[(idx - 1) % min(len(steps), 6)]:
                        chk = st.checkbox(f"Month {idx}", value=is_checked, key=step_key)
                        if chk:
                            st.session_state["completed_roadmap_steps"].add(step_key)
                        else:
                            st.session_state["completed_roadmap_steps"].discard(step_key)

                st.markdown("<br>", unsafe_allow_html=True)

                # Render Photo-Style Monthly Timeline Divider & Cards
                timeline_html_list = [
                    '<div class="career-timeline-wrapper">',
                    '<div class="career-timeline-line"></div>'
                ]

                for idx, step_item in enumerate(steps, 1):
                    step_key = f"step_chk_{idx}"
                    chk = step_key in st.session_state["completed_roadmap_steps"]
                    
                    title_text = step_item["title"]
                    details_list = step_item["details"]
                    
                    meta = get_month_card_metadata(title_text, details_list, idx)
                    
                    row_side_class = "row-left" if (idx % 2 != 0) else "row-right"
                    card_completed_class = "photo-month-card-completed" if chk else ""
                    pill_completed_class = "photo-card-pill-completed" if chk else ""
                    node_completed_class = "career-timeline-node-completed" if chk else ""
                    
                    badge_label = f"✓ {meta['badge']} COMPLETED" if chk else meta['badge']
                    node_icon_display = "✅" if chk else meta['node_icon']
                    
                    details_html = ""
                    for item in details_list:
                        cleaned_bullet = clean_bullet_item(item)
                        if cleaned_bullet:
                            details_html += f'<div class="rung-detail-bullet">{cleaned_bullet}</div>'

                    row_html = (
                        f'<div class="career-timeline-row {row_side_class}">'
                        f'<div class="career-timeline-node {node_completed_class}">{node_icon_display}</div>'
                        f'<div class="career-timeline-connector"></div>'
                        f'<div class="photo-month-card {card_completed_class}">'
                        f'<span class="photo-card-pill {pill_completed_class}">{badge_label}</span>'
                        f'<div class="photo-card-header-flex">'
                        f'<div class="photo-card-white-square">{meta["icon"]}</div>'
                        f'<div class="photo-card-titles-wrap">'
                        f'<h3 class="photo-card-main-title">{"✅ " if chk else ""}{meta["main_title"]}</h3>'
                        f'<div class="photo-card-subtitle-cyan">{meta["subtitle"]}</div>'
                        f'</div>'
                        f'</div>'
                        f'<div class="photo-card-body-desc">{details_html}</div>'
                        f'</div>'
                        f'</div>'
                    )
                    timeline_html_list.append(row_html)

                timeline_html_list.append('</div>')
                
                st.markdown("".join(timeline_html_list), unsafe_allow_html=True)



                # Celebration Balloons upon 100% completion
                if completed_count == total_rungs and total_rungs > 0:
                    st.balloons()
                    st.success(f"🏆 **CONGRATULATIONS! You have climbed all {total_rungs} rungs of your Career Ladder and are fully ready for {target_role} roles!**")

            # Recommended Certifications Cards Grid
            if "achieved_certs" not in st.session_state:
                st.session_state["achieved_certs"] = set()

            cert_items = extract_certification_items(parsed_sec["certifications"]) if parsed_sec["certifications"] else []
            if not cert_items:
                cert_items = [
                    {"title": "Linux Professional Institute Certification (LPIC-1)", "desc": "Fundamental Linux system administration certification for DevOps engineers in Sri Lanka."},
                    {"title": "Docker Certified Associate (DCA)", "desc": "Official containerization credential validating enterprise Docker management skills."},
                    {"title": "Certified Kubernetes Application Developer (CKAD / CKA)", "desc": "Cloud Native Computing Foundation (CNCF) certification for Kubernetes container orchestration."},
                    {"title": "CI/CD & Automation Specialist (Jenkins / GitHub Actions)", "desc": "Credential validating automated software delivery pipelines and continuous integration practices."},
                    {"title": "HashiCorp Certified: Terraform Associate", "desc": "Infrastructure as Code (IaC) credential highly demanded by Sysco LABS, Virtusa, & WSO2."},
                    {"title": "AWS Certified Solutions Architect – Associate", "desc": "Top-tier cloud architecture certification for Sri Lankan IT undergraduates transitioning into Cloud & DevOps."}
                ]

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 0.85rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
                <span>Industry Certification Cards Grid</span>
                <span style="font-size: 0.9rem; color: #c084fc; font-weight: 700; background: rgba(139, 92, 246, 0.2); padding: 0.3rem 0.85rem; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.4);">
                    Achieved: <b>{len(st.session_state["achieved_certs"])}</b> of <b>{len(cert_items)}</b> Credentials
                </span>
            </div>
            """, unsafe_allow_html=True)

            cert_cols = st.columns(min(len(cert_items), 2))
            for c_idx, cert in enumerate(cert_items):
                cert_key = f"cert_achieved_{c_idx}"
                is_achieved = cert_key in st.session_state["achieved_certs"]
                
                with cert_cols[c_idx % min(len(cert_items), 2)]:
                    card_class = "cert-card-glass cert-card-achieved" if is_achieved else "cert-card-glass"
                    badge_text = "✓ ACHIEVED" if is_achieved else "CREDENTIAL"
                    badge_class = "cert-pill-tag cert-pill-achieved" if is_achieved else "cert-pill-tag"
                    title_color = "#34d399" if is_achieved else "#ffffff"
                    icon = "🏆 " if is_achieved else "🎓 "
                    
                    st.markdown(f"""
                    <div class="{card_class}">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.4rem;">
                            <div style="font-weight: 800; font-size: 1.08rem; color: {title_color};">
                                {icon}{cert['title']}
                            </div>
                            <span class="{badge_class}">{badge_text}</span>
                        </div>
                        <div style="color: #cbd5e1; font-size: 0.92rem; line-height: 1.6; margin-bottom: 0.75rem;">
                            {cert['desc']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    btn_label = "🏆 Achieved!" if is_achieved else "Mark as Achieved"
                    if st.button(btn_label, key=f"btn_cert_toggle_{c_idx}", use_container_width=True):
                        if is_achieved:
                            st.session_state["achieved_certs"].discard(cert_key)
                        else:
                            st.session_state["achieved_certs"].add(cert_key)

            if parsed_sec["market_advice"]:
                cleaned_advice = clean_text_formatting(parsed_sec["market_advice"])
                st.markdown(f"""
                <div class="sl-strategic-box">
                    <div style="font-size: 1.2rem; font-weight: 700; color: #34d399; margin-bottom: 0.85rem; display: flex; align-items: center; gap: 0.5rem; border-bottom: 1px solid rgba(16, 185, 129, 0.25); padding-bottom: 0.6rem;">
                        <span>🇱🇰 Strategic Advice for Sri Lankan IT Market</span>
                    </div>
                    <div>{cleaned_advice}</div>
                </div>
                """, unsafe_allow_html=True)

        elif view_mode == "🎯 Live Skill Readiness Tracker":
            st.subheader("🎯 Skill Acquisition & Readiness Score Tracker")
            st.caption("Check off missing technical skills as you learn them to dynamically recalculate your readiness score!")

            if "learned_skills" not in st.session_state:
                st.session_state["learned_skills"] = set()

            total_initial_skills = len(extracted_skills)
            total_missing = len(missing_skills)
            total_required = total_initial_skills + total_missing

            col_tr1, col_tr2 = st.columns(2)

            with col_tr1:
                st.markdown("#### ✅ Current Strengths (Already Possessed)")
                for s in extracted_skills:
                    st.markdown(f"<span class='skill-badge-emerald'>✓ {s}</span>", unsafe_allow_html=True)

            with col_tr2:
                st.markdown("#### 🚨 Missing Skills to Acquire")
                for s in missing_skills:
                    chk_key = f"learned_skill_{s}"
                    checked = st.checkbox(f"I am learning / have mastered **{s}**", key=chk_key)
                    if checked:
                        st.session_state["learned_skills"].add(s)
                    else:
                        st.session_state["learned_skills"].discard(s)

            # Calculate Live Readiness Percentage
            newly_learned = len(st.session_state["learned_skills"])
            current_total_possessed = total_initial_skills + newly_learned
            readiness_pct = int((current_total_possessed / total_required) * 100) if total_required > 0 else 100

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"### 📈 Your Updated Role Readiness: **{readiness_pct}%**")
            st.progress(readiness_pct / 100.0)

            if readiness_pct >= 85:
                st.balloons()
                st.success(f"🚀 **Great job!** You are now {readiness_pct}% ready for **{target_role}** roles in Sri Lanka!")
            elif readiness_pct >= 50:
                st.info("💪 You are making steady progress! Focus on the remaining missing skills.")

        else: # Modern Interactive Full Markdown Report Dashboard Mode
            st.markdown(f"""
            <div class="report-hero-header">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div>
                        <span style="background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(139, 92, 246, 0.25)); border: 1px solid rgba(139, 92, 246, 0.4); color: #c084fc; font-size: 0.78rem; font-weight: 700; padding: 0.25rem 0.75rem; border-radius: 14px; text-transform: uppercase;">
                            📄 Executive Intelligence Report
                        </span>
                        <h3 style="margin-top: 0.6rem; margin-bottom: 0.2rem; color: #ffffff; font-size: 1.45rem; font-weight: 800;">
                            Comprehensive Market Analysis & Strategy
                        </h3>
                        <div style="color: #94a3b8; font-size: 0.9rem;">
                            Target Role: <b style="color: #818cf8;">{target_role}</b> | Local Market Benchmark: <b>Sri Lanka IT 2026</b>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Interactive Controls (Search Filter & Section Jump Dropdown)
            rep_col1, rep_col2 = st.columns([2.5, 1.5])
            with rep_col1:
                search_kw = st.text_input(
                    "🔍 Search within report:",
                    placeholder="Type keywords like Docker, Linux, Certifications, Agile...",
                    key="report_search_input"
                )
            with rep_col2:
                sec_filter_raw = st.selectbox(
                    "🎯 Jump / Filter Section:",
                    ["Show All Sections", "🎯 Target Profile & Feasibility", "⚖️ Technical Strengths vs Missing Gaps", "🗺️ Learning Roadmap", "🏆 Recommended Certifications", "🇱🇰 SL Market Advice"],
                    key="report_sec_select"
                )
                sec_filter: str = str(sec_filter_raw or "Show All Sections")

            st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

            kw = search_kw.strip().lower() if search_kw else ""

            def matches_kw(content_str: str) -> bool:
                if not kw:
                    return True
                return kw in content_str.lower()

            # 1. Target Career Profile Card
            if (sec_filter == "Show All Sections" or "Target Profile" in sec_filter) and matches_kw(parsed_sec["profile"] or target_role):
                st.markdown("""
                <div class="report-card-box">
                    <div class="report-section-title">
                        <span>🎯 Target Career Profile & Feasibility</span>
                    </div>
                """, unsafe_allow_html=True)
                if parsed_sec["profile"]:
                    st.markdown(clean_text_formatting(parsed_sec["profile"]), unsafe_allow_html=True)
                else:
                    st.write(f"Based on your profile, **{target_role}** is a highly feasible career trajectory.")
                st.markdown("</div>", unsafe_allow_html=True)

            # 2. Strengths & Missing Skills Breakdown Grid
            if (sec_filter == "Show All Sections" or "Strengths" in sec_filter) and matches_kw(parsed_sec["strengths_gaps"] or "".join(extracted_skills + missing_skills)):
                st.markdown("""
                <div class="report-card-box">
                    <div class="report-section-title">
                        <span>⚖️ Technical Strengths vs Priority Missing Skill Gaps</span>
                    </div>
                """, unsafe_allow_html=True)

                col_rep_str, col_rep_gap = st.columns(2)

                with col_rep_str:
                    st.markdown('<h5 style="color: #34d399; margin-bottom: 0.8rem;">💪 Existing Technical Strengths</h5>', unsafe_allow_html=True)
                    if extracted_skills:
                        for s in extracted_skills:
                            st.markdown(f'<div class="report-strength-item"><b>✓ {s}</b></div>', unsafe_allow_html=True)
                    else:
                        st.info("No specific initial skills provided.")

                with col_rep_gap:
                    st.markdown('<h5 style="color: #fb7185; margin-bottom: 0.8rem;">🚨 Priority Skill Gaps to Acquire</h5>', unsafe_allow_html=True)
                    if missing_skills:
                        for s in missing_skills:
                            st.markdown(f'<div class="report-gap-item"><b>⚡ {s}</b></div>', unsafe_allow_html=True)
                    else:
                        st.success("No major skill gaps identified!")

                if parsed_sec["strengths_gaps"]:
                    with st.expander("📖 View Detailed Strengths & Gaps Analysis", expanded=False):
                        st.markdown(clean_text_formatting(parsed_sec["strengths_gaps"]), unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

            # 3. Learning Roadmap Section
            if (sec_filter == "Show All Sections" or "Roadmap" in sec_filter) and matches_kw(parsed_sec["roadmap"]):
                cleaned_roadmap = clean_text_formatting(parsed_sec["roadmap"]) if parsed_sec["roadmap"] else "Learning roadmap details."
                st.markdown(f"""
                <div class="report-card-box">
                    <div class="report-section-title">
                        <span>🗺️ Step-by-Step Short Learning Roadmap</span>
                    </div>
                    <div>{cleaned_roadmap}</div>
                </div>
                """, unsafe_allow_html=True)

            # 4. Certifications Section
            if (sec_filter == "Show All Sections" or "Certifications" in sec_filter) and matches_kw(parsed_sec["certifications"]):
                cleaned_certs = clean_text_formatting(parsed_sec["certifications"]) if parsed_sec["certifications"] else "Certification details."
                st.markdown(f"""
                <div class="report-card-box">
                    <div class="report-section-title">
                        <span>🏆 Recommended Certifications & Industry Qualifications</span>
                    </div>
                    <div>{cleaned_certs}</div>
                </div>
                """, unsafe_allow_html=True)

            # 5. Sri Lanka Strategic Advice Section
            if (sec_filter == "Show All Sections" or "Market Advice" in sec_filter) and matches_kw(parsed_sec["market_advice"]):
                cleaned_advice = clean_text_formatting(parsed_sec["market_advice"]) if parsed_sec["market_advice"] else "Local market advice."
                st.markdown(f"""
                <div class="sl-strategic-box">
                    <div style="font-size: 1.2rem; font-weight: 700; color: #34d399; margin-bottom: 0.85rem; display: flex; align-items: center; gap: 0.5rem; border-bottom: 1px solid rgba(16, 185, 129, 0.25); padding-bottom: 0.6rem;">
                        <span>🇱🇰 Strategic Advice for Sri Lankan IT Market</span>
                    </div>
                    <div>{cleaned_advice}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)

            # Expander for Copyable Raw Markdown Source
            with st.expander("📋 View & Copy Raw Markdown Source Code", expanded=False):
                st.code(recommendation, language="markdown")

        st.markdown("<br>", unsafe_allow_html=True)
        # Download Report Option
        st.download_button(
            label="📥 Download Advice Report (.md)",
            data=f"# Career Advice Report for {target_role}\n\n" + recommendation,
            file_name=f"career_advice_{target_role.lower().replace(' ', '_')}.md",
            mime="text/markdown"
        )

    # --------------------------------------------------------------------------
    # TAB 2: SKILLS GAP BREAKDOWN
    # --------------------------------------------------------------------------
    with tab_skills:
        col_sk1, col_sk2 = st.columns(2)

        with col_sk1:
            st.markdown("#### ✅ Detected Technical Strengths")
            if extracted_skills:
                pills = "".join([f'<span class="skill-badge-emerald">✓ {s}</span>' for s in extracted_skills])
                st.markdown(pills, unsafe_allow_html=True)
            else:
                st.info("No specific technical skills identified in your query.")

        with col_sk2:
            st.markdown("#### 🚨 Priority Missing Skill Acquisition")
            if missing_skills:
                gaps_html = "".join([f'<span class="skill-badge-rose">⚡ {s}</span>' for s in missing_skills])
                st.markdown(gaps_html, unsafe_allow_html=True)
            else:
                st.success("🎉 You possess all primary technical prerequisites for this role!")

    # --------------------------------------------------------------------------
    # TAB 3: RAG KNOWLEDGE BASE REFERENCES
    # --------------------------------------------------------------------------
    with tab_rag:
        st.markdown("#### 📖 RAG Knowledge Base References")
        st.caption("Insights retrieved from Sri Lankan IT industry guides and curriculum datasets:")
        
        retrieved_context = result.get("retrieved_context", [])
        if retrieved_context:
            for idx, chunk in enumerate(retrieved_context, 1):
                with st.expander(f"📌 Knowledge Reference #{idx}", expanded=(idx == 1)):
                    st.code(chunk, language="markdown")
        else:
            st.info("No direct external RAG context chunks were attached to this execution.")


# ------------------------------------------------------------------------------
# 6. Student Assignment Footer
# ------------------------------------------------------------------------------
st.markdown("""
<div class="footer-glass">
    🎓 <b>IT41043 Agentic AI Assignment</b> | Built with LangGraph, RAG, and Streamlit<br>
    <a href="https://github.com/your-username/career-advisor-agentic-ai" target="_blank">🔗 View Project Repository on GitHub</a>
</div>
""", unsafe_allow_html=True)

