import sys
import os
import logging
import time
import re
import base64
from typing import Dict, Any, List, cast

# Ensure project root directory is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
from utils.secrets import get_secret
from agents.graph import run_career_advisor
from agents.state import CareerAdvisorState
from utils.pdf_generator import generate_academic_pdf

# Configure console logger for debugging runtime errors
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CareerAdvisorUI")


def get_asset_base64(filename: str) -> str:
    """Reads a local image asset and returns a base64 Data URI string for HTML embedding."""
    candidates = [filename]
    
    # Auto-detect variations like WS02.png vs WSO2.jpg, Virtusa.png vs Virtusa.jpg
    lower_f = filename.lower()
    if "wso2" in lower_f or "ws02" in lower_f:
        candidates.extend(["WS02.png", "WSO2.png", "WSO2.jpg", "WS02.jpg"])
    elif "virtusa" in lower_f:
        candidates.extend(["Virtusa.png", "virtusa.png", "Virtusa.jpg", "virtusa.jpg"])
    elif "lseg" in lower_f:
        candidates.extend(["LSEG.png", "LSEG.jpg", "LSEG.jpeg"])
    elif "ifs" in lower_f:
        candidates.extend(["IFS.png", "IFS.jpg", "IFS.jpeg"])
        
    for cand in candidates:
        file_path = os.path.join(PROJECT_ROOT, "assets", cand)
        if os.path.exists(file_path):
            ext = os.path.splitext(cand)[1].lower().lstrip(".")
            mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            try:
                with open(file_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    return f"data:{mime_type};base64,{encoded}"
            except Exception as e:
                logger.warning(f"Error loading asset '{cand}': {e}")
    return ""


def toggle_cert_status(cert_key: str) -> None:
    """Callback function to reliably toggle certification achievement status in Streamlit session state."""
    if "achieved_certs" not in st.session_state:
        st.session_state["achieved_certs"] = set()
    if cert_key in st.session_state["achieved_certs"]:
        st.session_state["achieved_certs"].discard(cert_key)
    else:
        st.session_state["achieved_certs"].add(cert_key)


# ------------------------------------------------------------------------------
# Helper Functions for Parsing & Formatting Professional Text
# ------------------------------------------------------------------------------
def sanitize_markdown_text(text: str) -> str:
    """Sanitize raw markdown formatting into clean, professional HTML bold tags."""
    if not text:
        return ""
    
    s = text.strip()
    
    # Clean up broken/mismatched asterisks around label keys (e.g., *Target Position** -> **Target Position**)
    s = re.sub(r'^\*+([^*]+?)\*+:\s*', r'**\1**: ', s)
    s = re.sub(r'\*+([^*]+?)\*+:\s*', r'**\1**: ', s)

    # Convert **bold** to <b>bold</b>
    s = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', s)

    # Convert single *italic* or leftover *text* to <b>text</b>
    s = re.sub(r'\*(.*?)\*', r'<b>\1</b>', s)

    # Clean up remaining quotes inside b tags or double quotes
    s = s.replace('<b>"', '<b>').replace('"</b>', '</b>').replace('""', '"')
    
    # Clean up any leftover lone asterisks
    s = re.sub(r'\*+:\s*', ': ', s)
    s = s.replace('*', '')

    return s


def clean_text_formatting(text: str) -> str:
    """Sanitize raw markdown formatting into clean HTML with consistent, prominent subheaders and aligned list items."""
    if not text:
        return ""
    
    cleaned = text.strip()
    
    # Insert newlines before inline numbered list items (e.g., " 2. ", " 3. ")
    cleaned = re.sub(r'(\s+)(\d+\.\s+)', r'\n\2', cleaned)
    # Insert newlines before inline bullet points (e.g., " - ", " * ")
    cleaned = re.sub(r'(\s+)([-\*•]\s+)', r'\n\2', cleaned)

    lines = cleaned.split("\n")
    formatted_lines = []
    first_header_skipped = False
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Check if line is a top-level section header (e.g. ## Step-by-Step... or # Target Career...)
        if (stripped.startswith("#") or stripped.startswith("##")) and not stripped.startswith("###") and not first_header_skipped:
            first_header_skipped = True
            continue
            
        clean_header = re.sub(r'^\s*#{1,6}\s*', '', stripped)
        clean_header_text = clean_header.replace('**', '').replace('*', '').strip()
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
            continue

        # Check for numbered list items (e.g. "1. Stay Updated...")
        numbered_match = re.match(r'^(\d+\.)\s*(.*)', stripped)
        if numbered_match:
            num_prefix = numbered_match.group(1)
            item_body = sanitize_markdown_text(numbered_match.group(2))
            formatted_lines.append(
                f'<div style="margin-top: 0.55rem; margin-bottom: 0.55rem; line-height: 1.6; display: flex; align-items: flex-start; gap: 0.6rem;">'
                f'<span style="color: #34d399; font-weight: 700; min-width: 1.6rem; font-size: 1rem;">{num_prefix}</span>'
                f'<div style="color: #cbd5e1; flex: 1;">{item_body}</div>'
                f'</div>'
            )
            continue

        # Check for bullet list items (e.g. "- Focus on...", "* Build...")
        bullet_match = re.match(r'^[-\*•]\s*(.*)', stripped)
        if bullet_match:
            item_body = sanitize_markdown_text(bullet_match.group(1))
            formatted_lines.append(
                f'<div style="margin-top: 0.45rem; margin-bottom: 0.45rem; line-height: 1.6; display: flex; align-items: flex-start; gap: 0.6rem;">'
                f'<span style="color: #818cf8; font-weight: 700;">•</span>'
                f'<div style="color: #cbd5e1; flex: 1;">{item_body}</div>'
                f'</div>'
            )
            continue

        # Normal text paragraph
        formatted = sanitize_markdown_text(stripped)
        formatted_lines.append(
            f'<div style="margin-top: 0.45rem; margin-bottom: 0.45rem; line-height: 1.6; color: #cbd5e1;">{formatted}</div>'
        )
            
    return "\n".join(formatted_lines)




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
    clean_input = re.sub(r'</?[^>]+>', '', cert_text)
    
    lines = clean_input.split("\n")
    current_cert = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        clean = stripped.lstrip("#*- ").rstrip("*").strip()
        clean = re.sub(r'</?[^>]+>', '', clean).strip()
        
        if not clean or clean.lower() in ["div", "/div", "</div>", "<div>", "</div"]:
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
            if clean_desc and clean_desc.lower() not in ["div", "/div", "</div>", "<div>", "</div"]:
                if current_cert["desc"]:
                    current_cert["desc"] += " " + clean_desc
                else:
                    current_cert["desc"] = clean_desc
                    
    if current_cert and current_cert["title"]:
        certs.append(current_cert)
        
    # Final sanitization pass
    final_certs = []
    for c in certs:
        c_title = re.sub(r'</?[^>]+>', '', c["title"]).replace('div', '').replace('/div', '').strip()
        c_desc = re.sub(r'</?[^>]+>', '', c["desc"]).strip()
        c_desc = re.sub(r'(?i)\b/?div\b', '', c_desc).strip()
        c_desc = c_desc.replace('</div>', '').replace('<div>', '').replace('</div', '').strip()
        if c_title and c_title.lower() != "div":
            final_certs.append({"title": c_title, "desc": c_desc})
            
    return final_certs


def get_month_card_metadata(title_text: str, details_list: List[str], idx: int) -> Dict[str, str]:
    """Extract visual design metadata for photo-style monthly career ladder timeline cards with 3D icons."""
    clean_title = title_text.replace('**', '').replace('##', '').replace('###', '').strip()
    
    default_icons = ["💻", "🐳", "⚙️", "☸️", "☁️", "💼", "🧠", "📊"]
    default_3d_urls = [
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Laptop.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Animals/Spouting%20Whale.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Gear.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Anchor.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Cloud.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Briefcase.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Robot.png",
        "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Bar%20Chart.png"
    ]
    default_nodes = ["🎓", "⚡", "🔄", "🏛️", "🌐", "🏆", "🎯", "🚀"]
    
    icon = default_icons[(idx - 1) % len(default_icons)]
    icon_3d_url = default_3d_urls[(idx - 1) % len(default_3d_urls)]
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
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Laptop.png"
        node = "🎓"
        subtitle = "Linux CLI, System Administration & Bash"
    elif "docker" in lower_t or "container" in lower_t:
        icon = "🐳"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Animals/Spouting%20Whale.png"
        node = "⚡"
        subtitle = "Containerization & Multi-Container Deployment"
    elif "ci/cd" in lower_t or "jenkins" in lower_t or "github action" in lower_t or "automation" in lower_t or "pipeline" in lower_t:
        icon = "⚙️"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Gear.png"
        node = "🔄"
        subtitle = "Automated Delivery Pipelines & Workflow Automation"
    elif "kubernetes" in lower_t or "k8s" in lower_t or "orchestr" in lower_t:
        icon = "☸️"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Anchor.png"
        node = "🏛️"
        subtitle = "Container Orchestration, Clusters & Helm"
    elif "terraform" in lower_t or "cloud" in lower_t or "aws" in lower_t or "iac" in lower_t or "azure" in lower_t:
        icon = "☁️"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Travel%20and%20places/Cloud.png"
        node = "🌐"
        subtitle = "Infrastructure as Code & Cloud Computing"
    elif "sri lanka" in lower_t or "interview" in lower_t or "career" in lower_t or "portfolio" in lower_t or "cert" in lower_t:
        icon = "💼"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Briefcase.png"
        node = "🏆"
        subtitle = "Sri Lanka IT Industry Execution & Certification"
    elif "python" in lower_t or "programming" in lower_t or "backend" in lower_t:
        icon = "🐍"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Animals/Snake.png"
        node = "💻"
        subtitle = "Backend Development & Software Architecture"
    elif "react" in lower_t or "frontend" in lower_t or "web" in lower_t or "js" in lower_t:
        icon = "⚛️"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Activities/Artist%20Palette.png"
        node = "🎨"
        subtitle = "Modern Web Frontend & UI Applications"
    elif "data" in lower_t or "sql" in lower_t or "database" in lower_t:
        icon = "📊"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Bar%20Chart.png"
        node = "🗄️"
        subtitle = "Database Engineering & Data Management"
    elif "ai" in lower_t or "machine learning" in lower_t or "llm" in lower_t or "agent" in lower_t:
        icon = "🧠"
        icon_3d_url = "https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Robot.png"
        node = "🤖"
        subtitle = "Artificial Intelligence & Agentic AI Architecture"
        
    return {
        "badge": badge,
        "main_title": main_title,
        "subtitle": subtitle,
        "icon": icon,
        "icon_3d_url": icon_3d_url,
        "node_icon": node
    }


def render_interactive_agent_progress(current_phase: int) -> str:
    """Renders an ultra-modern glassmorphic multi-agent live execution progress UI."""
    phases = [
        {"num": 1, "name": "Intent & Goal Parsing Agent", "desc": "Analyzing profile, extracting technical skills & target career goal..."},
        {"num": 2, "name": "RAG Vector Store Retrieval Agent", "desc": "Querying local ChromaDB knowledge base for 2026 Sri Lanka IT market standards..."},
        {"num": 3, "name": "Skills Gap Evaluator Agent", "desc": "Cross-referencing current skills vs missing industry requirements..."},
        {"num": 4, "name": "Strategic Roadmap & Advice Agent", "desc": "Synthesizing monthly elevation ladder, certifications & market advice..."}
    ]
    
    pct = min(int((current_phase / 4.0) * 100), 100)
    
    cards_html = ""
    for p in phases:
        p_num = int(p["num"])
        if current_phase > p_num:
            card_class = "agent-step-card agent-step-card-completed"
            tag_html = '<span class="agent-tag-completed">COMPLETED</span>'
            title_color = "#34d399"
        elif current_phase == p_num:
            card_class = "agent-step-card agent-step-card-active"
            tag_html = '<span class="agent-tag-active"><span class="agent-spinner"></span>EXECUTING...</span>'
            title_color = "#818cf8"
        else:
            card_class = "agent-step-card"
            tag_html = '<span class="agent-tag-waiting">QUEUED</span>'
            title_color = "#94a3b8"
            
        cards_html += (
            f'<div class="{card_class}">'
            f'<div class="agent-step-info">'
            f'<div>'
            f'<div class="agent-step-title" style="color: {title_color};">{p["name"]}</div>'
            f'<div class="agent-step-desc">{p["desc"]}</div>'
            f'</div>'
            f'</div>'
            f'<div>{tag_html}</div>'
            f'</div>'
        )
        
    status_label = "ANALYSIS COMPLETE (100%)" if current_phase > 4 else f"ORCHESTRATION ACTIVE ({pct}%)"
    badge_class = "agent-badge-completed" if current_phase > 4 else "agent-badge-live"
    dot_html = '<span class="agent-pulse-dot"></span>' if current_phase <= 4 else '<span></span>'

    return f"""
    <div class="agent-workflow-container">
        <div class="agent-header-row">
            <div class="agent-title-text">
                <span>Multi-Agent Workflow Engine Active</span>
            </div>
            <div class="{badge_class}">
                {dot_html}
                <span>{status_label}</span>
            </div>
        </div>
        <div style="margin-bottom: 1.1rem;">
            <div style="background: rgba(255, 255, 255, 0.08); border-radius: 10px; height: 8px; overflow: hidden; width: 100%;">
                <div style="background: linear-gradient(90deg, #6366f1, #06b6d4, #10b981); height: 100%; width: {pct}%; transition: width 0.4s ease;"></div>
            </div>
        </div>
        <div>{cards_html}</div>
    </div>
    """



# ------------------------------------------------------------------------------
# 1. Page Configuration & Modern Glassmorphic Custom CSS Design System
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Talent Navigator | Sri Lanka IT Edition",
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
        margin-bottom: 1.25rem;
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
    .preset-tag-qa { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .preset-tag-ba { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    .preset-tag-sys { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }

    .preset-card-desc {
        font-size: 0.85rem;
        color: #94a3b8;
        line-height: 1.45;
        margin-bottom: 0.4rem;
    }

    /* Company Career Portals Showcase Cards */
    .company-showcase-container {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.8) 100%);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-radius: 24px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(16px);
        box-shadow: 0 15px 35px -10px rgba(0, 0, 0, 0.5);
    }
    
    .company-card-glass {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 20px;
        padding: 1.25rem 1rem;
        text-align: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;
        min-height: 170px;
        height: 100%;
        text-decoration: none !important;
        box-sizing: border-box;
        backdrop-filter: blur(12px);
        position: relative;
        margin-bottom: 1.25rem;
    }

    .company-card-glass:hover {
        border-color: var(--card-border-hover);
        transform: translateY(-3px);
        box-shadow: 0 15px 30px -10px rgba(99, 102, 241, 0.25);
    }

    .company-logo-img {
        height: 42px !important;
        max-height: 42px !important;
        width: 140px !important;
        max-width: 140px !important;
        object-fit: contain !important;
        display: block !important;
        margin: 0 auto 0.4rem auto !important;
        filter: drop-shadow(0 4px 8px rgba(0,0,0,0.4));
        transition: transform 0.3s ease;
    }

    .company-card-glass:hover .company-logo-img {
        transform: scale(1.08);
    }

    .company-badge-tag {
        font-size: 0.7rem;
        font-weight: 700;
        padding: 0.2rem 0.6rem;
        border-radius: 12px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.5rem;
    }

    .company-link-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        width: 100%;
        padding: 0.45rem 0.75rem;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.3) 0%, rgba(139, 92, 246, 0.3) 100%);
        border: 1px solid rgba(139, 92, 246, 0.5);
        color: #f8fafc !important;
        font-size: 0.8rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.25s ease;
    }

    .company-card-glass:hover .company-link-btn {
        background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
        border-color: #00f2fe;
        box-shadow: 0 4px 15px rgba(6, 182, 212, 0.4);
    }

    /* Button Instant Processing Loading Indicator */
    .button-loading-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0.55rem 1.1rem;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(139, 92, 246, 0.25) 100%);
        border: 1px solid rgba(139, 92, 246, 0.5);
        border-radius: 14px;
        color: #c084fc;
        font-size: 0.88rem;
        font-weight: 700;
        backdrop-filter: blur(10px);
        margin-top: 0.2rem;
        animation: pulseGlow 2s infinite alternate;
    }

    /* Autofill Profile Banner */
    .autofill-info-banner {
        display: flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0.75rem 1.1rem;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(6, 182, 212, 0.2) 100%);
        border: 1px solid rgba(52, 211, 153, 0.5);
        border-radius: 14px;
        color: #34d399;
        font-size: 0.92rem;
        font-weight: 700;
        margin-top: 0.85rem;
        margin-bottom: 0.75rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 15px rgba(52, 211, 153, 0.25);
    }

    .btn-spinner {
        width: 18px;
        height: 18px;
        border: 2.5px solid rgba(192, 132, 252, 0.25);
        border-top-color: #38bdf8;
        border-right-color: #c084fc;
        border-radius: 50%;
        animation: spin 0.75s linear infinite;
        flex-shrink: 0;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    @keyframes pulseGlow {
        0% { box-shadow: 0 0 10px rgba(139, 92, 246, 0.25); }
        100% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.55); }
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
        margin-bottom: 0.85rem;
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
        max-width: 1480px;
        width: 98%;
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
        z-index: 6;
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

    /* Horizontal Connector Cyan Line - Extends from Circle Node Edge to Card Border */
    .career-timeline-connector {
        position: absolute;
        top: calc(1.8rem + 21px);
        height: 2px;
        background: #00f2fe;
        box-shadow: 0 0 10px #00f2fe;
        z-index: 5;
    }

    .career-timeline-row.row-left .career-timeline-connector {
        right: 22px;
        width: 14px;
    }

    .career-timeline-row.row-right .career-timeline-connector {
        left: 22px;
        width: 14px;
    }

    /* Card Styling - Positioned in Front of Connector Line */
    .photo-month-card {
        background: #0d0e15;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.65);
        backdrop-filter: blur(14px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        z-index: 5;
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
        position: absolute;
        top: 1.25rem;
        right: 1.35rem;
        background: #251343;
        border: 1px solid rgba(139, 92, 246, 0.5);
        color: #00f2fe;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 0.35rem 0.95rem;
        border-radius: 20px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        z-index: 5;
        white-space: nowrap;
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

    /* 3D Icon Container - Transparent 3D Glassmorphism (NO WHITE BACKGROUND) */
    .photo-card-3d-square, .photo-card-white-square {
        width: 64px;
        height: 64px;
        min-width: 64px;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(6, 182, 212, 0.18) 100%) !important;
        border: 1px solid rgba(0, 242, 254, 0.4) !important;
        border-radius: 18px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 10px 25px -5px rgba(0, 242, 254, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(16px) !important;
        box-sizing: border-box !important;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
        transform: perspective(600px) rotateX(8deg) rotateY(-8deg);
    }

    .photo-month-card:hover .photo-card-3d-square,
    .photo-month-card:hover .photo-card-white-square {
        transform: perspective(600px) rotateX(0deg) rotateY(0deg) scale(1.08) !important;
        border-color: rgba(0, 242, 254, 0.75) !important;
        box-shadow: 0 15px 35px -5px rgba(0, 242, 254, 0.55), inset 0 1px 2px rgba(255, 255, 255, 0.4) !important;
    }

    .photo-card-3d-icon-img {
        width: 46px;
        height: 46px;
        object-fit: contain;
        filter: drop-shadow(0 6px 12px rgba(0, 242, 254, 0.45));
        transition: transform 0.3s ease;
    }

    .photo-card-titles-wrap {
        flex-grow: 1;
        padding-right: 7.5rem;
    }

    .photo-card-main-title {
        font-size: 1.28rem;
        font-weight: 800;
        color: #ffffff;
        line-height: 1.25;
        margin: 0 0 0.2rem 0;
        font-family: 'Plus Jakarta Sans', sans-serif;
        word-break: normal;
        overflow-wrap: break-word;
        hyphens: manual;
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
        .career-timeline-wrapper {
            padding: 0.5rem 0;
            margin: 1rem auto;
        }
        .career-timeline-line {
            left: 18px !important;
        }
        .career-timeline-row {
            width: 100% !important;
            left: 0 !important;
            padding-left: 55px !important;
            padding-right: 0px !important;
            margin-bottom: 1.5rem !important;
        }
        .career-timeline-row.row-left .career-timeline-node,
        .career-timeline-row.row-right .career-timeline-node {
            left: -3px !important;
            right: auto !important;
            width: 38px !important;
            height: 38px !important;
            font-size: 1.05rem !important;
        }
        .career-timeline-row.row-left .career-timeline-connector,
        .career-timeline-row.row-right .career-timeline-connector {
            left: 35px !important;
            right: auto !important;
            width: 20px !important;
            height: 2px !important;
            z-index: 5 !important;
        }
        .photo-month-card {
            padding: 1.15rem 1.1rem !important;
            border-radius: 16px !important;
            position: relative !important;
            z-index: 5 !important;
        }
        .photo-card-titles-wrap {
            padding-right: 0 !important;
        }
        .photo-card-pill {
            position: static !important;
            float: none !important;
            display: inline-block !important;
            margin-bottom: 0.75rem !important;
            font-size: 0.68rem !important;
            padding: 0.25rem 0.75rem !important;
        }
        .photo-card-header-flex {
            gap: 0.85rem !important;
            align-items: flex-start !important;
        }
        .photo-card-white-square {
            width: 46px !important;
            height: 46px !important;
            min-width: 46px !important;
            font-size: 1.45rem !important;
            border-radius: 12px !important;
        }
        .photo-card-main-title {
            font-size: 1.1rem !important;
            line-height: 1.3 !important;
            word-break: normal !important;
            overflow-wrap: break-word !important;
            hyphens: manual !important;
        }
        .photo-card-subtitle-cyan {
            font-size: 0.86rem !important;
            line-height: 1.35 !important;
        }
    }

    /* Multi-Agent Live Execution Dashboard */
    .agent-workflow-container {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.92) 100%);
        border: 1px solid rgba(139, 92, 246, 0.45);
        border-radius: 22px;
        padding: 1.6rem 1.8rem;
        margin: 1.5rem 0;
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.65), 0 0 30px rgba(99, 102, 241, 0.2);
        backdrop-filter: blur(16px);
    }

    .agent-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-bottom: 1.25rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 1rem;
    }

    .agent-title-text {
        font-size: 1.25rem;
        font-weight: 800;
        color: #ffffff;
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    .agent-badge-live {
        background: rgba(139, 92, 246, 0.18);
        color: #c084fc;
        border: 1px solid rgba(139, 92, 246, 0.45);
        font-size: 0.78rem;
        font-weight: 800;
        padding: 0.35rem 0.9rem;
        border-radius: 16px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    .agent-badge-completed {
        background: rgba(16, 185, 129, 0.18);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.45);
        font-size: 0.78rem;
        font-weight: 800;
        padding: 0.35rem 0.9rem;
        border-radius: 16px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }

    .agent-pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #34d399;
        border-radius: 50%;
        box-shadow: 0 0 10px #34d399;
        animation: agentPulse 1.4s infinite ease-in-out;
    }

    @keyframes agentPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.35; transform: scale(0.85); }
    }

    /* Individual Agent Step Card */
    .agent-step-card {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 14px;
        padding: 0.95rem 1.2rem;
        margin-bottom: 0.75rem;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }

    .agent-step-card-active {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.22) 0%, rgba(139, 92, 246, 0.18) 100%);
        border: 1px solid rgba(139, 92, 246, 0.65);
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.25);
    }

    .agent-step-card-completed {
        background: rgba(6, 182, 212, 0.06);
        border: 1px solid rgba(16, 185, 129, 0.4);
    }

    .agent-step-info {
        display: flex;
        align-items: center;
        gap: 0.9rem;
    }

    .agent-step-icon {
        font-size: 1.45rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .agent-step-title {
        font-weight: 700;
        font-size: 0.98rem;
        color: #ffffff;
    }

    .agent-step-desc {
        font-size: 0.83rem;
        color: #94a3b8;
        margin-top: 0.15rem;
        line-height: 1.4;
    }

    .agent-tag-waiting {
        background: rgba(148, 163, 184, 0.1);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.2);
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.25rem 0.75rem;
        border-radius: 12px;
        white-space: nowrap;
    }

    .agent-tag-active {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 800;
        padding: 0.28rem 0.8rem;
        border-radius: 12px;
        box-shadow: 0 0 12px rgba(99, 102, 241, 0.5);
        white-space: nowrap;
        display: inline-flex;
        align-items: center;
    }

    .agent-spinner {
        display: inline-block;
        width: 10px;
        height: 10px;
        border: 2px solid rgba(255, 255, 255, 0.35);
        border-radius: 50%;
        border-top-color: #ffffff;
        animation: agentSpin 0.75s linear infinite;
        margin-right: 0.45rem;
    }

    @keyframes agentSpin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .agent-tag-completed {
        background: rgba(16, 185, 129, 0.2);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.5);
        font-size: 0.72rem;
        font-weight: 800;
        padding: 0.28rem 0.8rem;
        border-radius: 12px;
        white-space: nowrap;
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
        border-radius: 16px;
        padding: 0.85rem 1.25rem;
        margin-bottom: 0.85rem;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.3);
    }

    .report-card-box:hover {
        border-color: rgba(99, 102, 241, 0.45);
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -10px rgba(99, 102, 241, 0.3);
    }

    .sl-strategic-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(6, 182, 212, 0.08) 100%);
        border: 1px solid rgba(16, 185, 129, 0.35);
        border-radius: 16px;
        padding: 0.85rem 1.25rem;
        margin-top: 0.85rem;
        margin-bottom: 0.85rem;
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.65;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.3);
    }

    .sl-strategic-box:hover {
        border-color: rgba(16, 185, 129, 0.6);
        transform: translateY(-2px);
        box-shadow: 0 12px 24px -10px rgba(16, 185, 129, 0.3);
    }

    .report-section-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: none;
        padding-bottom: 0;
    }

    .report-skills-container {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        margin-bottom: 0.8rem;
    }

    .report-strength-item {
        background: rgba(16, 185, 129, 0.08);
        border: 1px solid rgba(16, 185, 129, 0.25);
        border-left: 4px solid #10b981;
        border-radius: 12px;
        padding: 0.5rem 0.85rem;
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.4;
        display: inline-flex;
        align-items: center;
        transition: transform 0.2s ease, background 0.2s ease;
    }
    .report-strength-item:hover {
        transform: translateY(-2px);
        background: rgba(16, 185, 129, 0.16);
    }

    .report-gap-item {
        background: rgba(244, 63, 94, 0.08);
        border: 1px solid rgba(244, 63, 94, 0.25);
        border-left: 4px solid #f43f5e;
        border-radius: 12px;
        padding: 0.5rem 0.85rem;
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.4;
        display: inline-flex;
        align-items: center;
        transition: transform 0.2s ease, background 0.2s ease;
    }
    .report-gap-item:hover {
        transform: translateY(-2px);
        background: rgba(244, 63, 94, 0.16);
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
    /* Ultra-Modern Floating Glass Tab Navigation Bar */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 20px !important;
        padding: 6px 8px !important;
        gap: 8px !important;
        backdrop-filter: blur(16px) !important;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.4) !important;
        margin-bottom: 1.5rem !important;
    }

    /* Individual Tab Buttons */
    .stTabs button[data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        border-radius: 14px !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 0.65rem 1.25rem !important;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    .stTabs button[data-baseweb="tab"]:hover {
        color: #f8fafc !important;
        background: rgba(255, 255, 255, 0.06) !important;
        transform: translateY(-1px) !important;
    }

    /* Active Selected Tab with Vibrant Gradient & Glow */
    .stTabs button[aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 50%, #06b6d4 100%) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 8px 25px -4px rgba(79, 70, 229, 0.5) !important;
        border-radius: 14px !important;
        transform: scale(1.02) !important;
    }

    /* REMOVE default flat underline highlight bar */
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
        background-color: transparent !important;
        height: 0 !important;
    }

    /* Silky-Smooth Hardware-Accelerated Tab Entrance Transition (Zero Glitch / Zero Shift) */
    @keyframes tabEntranceSmooth {
        0% {
            opacity: 0;
            transform: translate3d(0, 8px, 0);
        }
        100% {
            opacity: 1;
            transform: translate3d(0, 0, 0);
        }
    }

    .stTabs div[data-baseweb="tab-panel"] {
        animation: tabEntranceSmooth 0.25s cubic-bezier(0.25, 1, 0.5, 1) forwards !important;
        will-change: opacity, transform !important;
        backface-visibility: hidden !important;
        -webkit-backface-visibility: hidden !important;
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
        .metric-card-glass {
            margin-bottom: 1.25rem !important;
            height: auto;
            min-height: 115px;
            padding: 1.15rem 1rem;
        }
        .company-card-glass {
            margin-bottom: 1.25rem !important;
        }
        .preset-card-container {
            margin-bottom: 1.25rem !important;
        }
        div[data-testid="stColumn"], div[data-testid="column"] {
            margin-bottom: 0.6rem;
        }
    }

    /* -------------------------------------------------------------------------
       Separate Detailed Report Section Styling
       ------------------------------------------------------------------------- */
    .report-divider-container {
        margin-top: 3.5rem;
        margin-bottom: 2rem;
        position: relative;
    }

    .report-divider-line {
        border: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, rgba(99, 102, 241, 0.7) 50%, transparent 100%);
        margin: 0;
    }

    .report-divider-badge {
        position: absolute;
        top: -14px;
        left: 50%;
        transform: translateX(-50%);
        background: #0b0f19;
        padding: 0.25rem 1.4rem;
        border-radius: 20px;
        border: 1px solid rgba(99, 102, 241, 0.5);
        font-size: 0.85rem;
        font-weight: 800;
        color: #a5b4fc;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.35);
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
    }

    .report-placeholder-banner {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.7) 100%);
        border: 2px dashed rgba(99, 102, 241, 0.4);
        border-radius: 24px;
        padding: 2.5rem 2rem;
        text-align: center;
        margin-bottom: 2.5rem;
        backdrop-filter: blur(14px);
        transition: all 0.3s ease;
    }

    .report-placeholder-banner:hover {
        border-color: rgba(99, 102, 241, 0.7);
        box-shadow: 0 12px 30px -10px rgba(99, 102, 241, 0.25);
    }

    .report-placeholder-icon {
        font-size: 2.8rem;
        margin-bottom: 0.75rem;
        display: inline-block;
        filter: drop-shadow(0 4px 12px rgba(99, 102, 241, 0.4));
    }

    .report-placeholder-title {
        font-size: 1.45rem;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }

    .report-placeholder-desc {
        font-size: 0.95rem;
        color: #94a3b8;
        max-width: 680px;
        margin: 0 auto 1.25rem auto;
        line-height: 1.6;
    }

    .report-feature-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: rgba(99, 102, 241, 0.15);
        color: #c084fc;
        border: 1px solid rgba(139, 92, 246, 0.35);
        padding: 0.38rem 0.9rem;
        border-radius: 16px;
        font-size: 0.82rem;
        font-weight: 700;
    }

    .report-section-hero-wrapper {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.75) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(129, 140, 248, 0.45);
        border-radius: 24px;
        padding: 1.75rem 2rem;
        margin-bottom: 1.75rem;
        backdrop-filter: blur(16px);
        box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }

    .report-status-pill-active {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 0.25rem 0.75rem;
        border-radius: 14px;
        font-size: 0.76rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .report-pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #34d399;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px #34d399;
        animation: pulseDot 1.5s infinite;
    }

    @keyframes pulseDot {
        0% { opacity: 0.4; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1.2); }
        100% { opacity: 0.4; transform: scale(0.8); }
    }

    .report-status-pill-meta {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: rgba(99, 102, 241, 0.15);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.3);
        padding: 0.25rem 0.75rem;
        border-radius: 14px;
        font-size: 0.76rem;
        font-weight: 700;
    }

    .report-hero-role-chip {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(56, 189, 248, 0.35);
        padding: 0.55rem 1.1rem;
        border-radius: 16px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 2. Glassmorphic Hero Banner Header
# ------------------------------------------------------------------------------
st.markdown("""
<div class="hero-glass-container">
    <div class="hero-badge-top">
        <span>Agentic AI Platform</span>
    </div>
    <div class="hero-title-text">🎓 Talent Navigator</div>
    <div class="hero-subtitle-text">
        An agentic AI talent navigator designed specifically for Sri Lankan IT undergraduates & fresh graduates. 
        Analyze your technical background, identify skill gaps against market standards, and receive RAG-grounded learning roadmaps.
    </div>
    <div class="hero-chips-grid">
        <span class="hero-chip-item">LangGraph Multi-Agent Engine</span>
        <span class="hero-chip-item">RAG Sri Lanka IT Knowledge Base</span>
        <span class="hero-chip-item">Interactive Elevation Ladder</span>
        <span class="hero-chip-item">Local IT Market Focus 2026</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 3. Interactive Student Profile Input & Skill Quick-Builder
# ------------------------------------------------------------------------------
if "user_prompt_input" not in st.session_state:
    st.session_state["user_prompt_input"] = ""

def set_autofill_prompt(prompt_text: str) -> None:
    """Callback function to safely update session state before widget rendering."""
    st.session_state["user_prompt_input"] = prompt_text
    st.session_state["show_autofill_notice"] = True

st.markdown("### Enter Your Profile & Career Aspiration")

if st.session_state.get("show_autofill_notice", False):
    st.markdown("""
    <div class="autofill-info-banner">
        <span>Profile Query Autofilled! Review prompt in the text box below & click <b>Generate Career Advice & Roadmap</b> ↑</span>
    </div>
    """, unsafe_allow_html=True)
    st.toast("Profile Autofilled! Review the prompt below and click 'Generate Career Advice & Roadmap'")
    st.session_state["show_autofill_notice"] = False

# Form Text Area (Main User Input)
user_input = st.text_area(
    label="Describe your current technical skills, tools, languages, and target IT career role:",
    height=170,
    placeholder="e.g., I'm an IT undergraduate. I know Python, C#, MySQL, and Git. I want to become a Backend Developer.",
    key="user_prompt_input"
)

st.markdown('<div style="margin-top: 0.85rem;"></div>', unsafe_allow_html=True)

submit_col1, submit_col2 = st.columns([1.6, 3.4])
with submit_col1:
    submit_btn = st.button("Generate Career Advice & Roadmap", type="primary", use_container_width=True)

btn_loading_placeholder = submit_col2.empty()

# Spacing
st.markdown('<div style="margin-top: 2rem; margin-bottom: 0.85rem;"></div>', unsafe_allow_html=True)

# Sample Profile Preset Cards (6 Popular IT Career Tracks)
st.markdown("""
<div style="font-size: 1.05rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.85rem;">
    Or Choose a Sample Profile Track to Autofill:
</div>
""", unsafe_allow_html=True)

col_r1_1, col_r1_2, col_r1_3 = st.columns(3)

qa_text = (
    "I have experience in manual software testing, writing test cases, Python, Java, Postman API testing, and basic Selenium. "
    "I want to transition into an Automation QA / Software Test Engineer role. "
    "Please analyze my current background, identify missing automation & performance testing skills, "
    "and create a step-by-step career progression roadmap."
)

ba_text = (
    "I have an IT background with skills in SQL database querying, UML diagramming, requirements gathering, writing user stories, "
    "and working with Jira in Agile/Scrum teams. I aim to become a professional Business Analyst (BA) or Systems Analyst. "
    "Please evaluate my profile, highlight missing business analysis competencies, and generate a learning roadmap."
)

ml_text = (
    "I have a solid foundation in Python, Pandas, SQL database querying, and basic statistics. "
    "I am passionate about discovering patterns in complex datasets, building predictive machine learning models, "
    "and working with intelligent agentic frameworks. I want to transition into an advanced AI & ML role within the next 6 to 9 months. "
    "Please analyze my current profile, highlight missing core skills (such as PyTorch, MLOps, and vector databases), "
    "and build a month-by-month career progression roadmap."
)

devops_text = (
    "I am a 3rd year IT student with experience in Python, Java, SQL, basic Docker containerization, and Git version control. "
    "I enjoy setting up servers, writing deployment scripts, ensuring system uptime, and configuring automated build pipelines. "
    "I prefer system reliability and automation over frontend UI design. Please evaluate my background and preferences, "
    "recommend the best-fit career roles for me, identify my missing technical competencies, and generate a step-by-step learning roadmap."
)

sys_text = (
    "I have hands-on experience in Linux & Windows server administration, bash and PowerShell scripting, "
    "networking fundamentals (TCP/IP, DNS, VPNs, Firewalls), and system troubleshooting. "
    "I want to become a Senior Systems Administrator or Cloud Infrastructure Engineer. "
    "Please analyze my current skills, highlight missing infrastructure & cloud certifications, and provide a career roadmap."
)

fullstack_text = (
    "I am proficient in React, JavaScript, HTML5, CSS3, Node.js, and MongoDB. "
    "I enjoy building end-to-end web applications, designing responsive interfaces, creating RESTful backend APIs, "
    "and scaling database schema designs. I aim to elevate my career towards a Senior Full-Stack Software Architect role. "
    "Please conduct a comprehensive skills gap analysis on my profile, recommend missing industry-standard credentials/certifications, "
    "and create a strategic career development path."
)

with col_r1_1:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>QA & Test Automation</span>
            <span class="preset-card-tag preset-tag-qa">Testing & QA</span>
        </div>
        <div class="preset-card-desc">Manual testing, test cases, Postman, Python/Java & Selenium aiming for Automation QA Engineer.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill QA Profile", key="btn_preset_qa", use_container_width=True, on_click=set_autofill_prompt, args=(qa_text,))

with col_r1_2:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>Business Analyst (BA)</span>
            <span class="preset-card-tag preset-tag-ba">Product & Agile</span>
        </div>
        <div class="preset-card-desc">Requirements gathering, user stories, Jira/Agile, SQL & UML diagrams aiming for BA role.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill BA Profile", key="btn_preset_ba", use_container_width=True, on_click=set_autofill_prompt, args=(ba_text,))

with col_r1_3:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>AI & ML Engineer</span>
            <span class="preset-card-tag preset-tag-ai">AI & Big Data</span>
        </div>
        <div class="preset-card-desc">Python, Pandas, SQL & Statistics background transitioning into Machine Learning.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill ML Profile", key="btn_preset_ml", use_container_width=True, on_click=set_autofill_prompt, args=(ml_text,))

st.markdown('<div style="margin-top: 0.75rem;"></div>', unsafe_allow_html=True)

col_r2_1, col_r2_2, col_r2_3 = st.columns(3)

with col_r2_1:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>DevOps Cloud</span>
            <span class="preset-card-tag preset-tag-hot">High Demand</span>
        </div>
        <div class="preset-card-desc">Python, Java, SQL, Docker & Git student seeking DevOps Cloud Engineer path.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill DevOps Profile", key="btn_preset_devops", use_container_width=True, on_click=set_autofill_prompt, args=(devops_text,))

with col_r2_2:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>Sys Admin & Infra</span>
            <span class="preset-card-tag preset-tag-sys">IT & Network</span>
        </div>
        <div class="preset-card-desc">Linux, Windows Server, Networking (TCP/IP, DNS) & Bash/PowerShell aiming for SysAdmin.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill SysAdmin Profile", key="btn_preset_sysadmin", use_container_width=True, on_click=set_autofill_prompt, args=(sys_text,))

with col_r2_3:
    st.markdown("""
    <div class="preset-card-container">
        <div class="preset-card-title">
            <span>Full-Stack Architect</span>
            <span class="preset-card-tag preset-tag-core">Core Web</span>
        </div>
        <div class="preset-card-desc">React, Node.js, MongoDB & CSS dev aiming for Full-Stack Software Engineer.</div>
    </div>
    """, unsafe_allow_html=True)
    st.button("Autofill Full-Stack Profile", key="btn_preset_fullstack", use_container_width=True, on_click=set_autofill_prompt, args=(fullstack_text,))


# ------------------------------------------------------------------------------
# 3.5 Top Sri Lankan Tech Employers & Live Career Portals Showcase
# ------------------------------------------------------------------------------
st.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)
st.markdown("### Top Sri Lankan Tech Employers & Career Portals")
st.caption("Click any leading tech company logo to explore live open positions & hiring portals:")

st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)

# Load local asset images as base64 Data URIs
wso2_img = get_asset_base64("WSO2.jpg") or "https://wso2.com/files/wso2-dark-logo.svg"
virtusa_img = get_asset_base64("Virtusa.png") or "https://www.virtusa.com/content/dam/virtusa/global/en/images/virtusa-logo.svg"
lseg_img = get_asset_base64("LSEG.png") or "https://www.lseg.com/content/dam/lseg/global/en/images/logos/lseg-logo.svg"
ifs_img = get_asset_base64("IFS.png") or "https://www.ifs.com/assets/images/ifs-logo.svg"

col_c1, col_c2, col_c3, col_c4 = st.columns(4)

with col_c1:
    st.markdown(f"""
    <a href="https://wso2.com/careers" target="_blank" class="company-card-glass">
        <div style="width: 100%; display: flex; flex-direction: column; align-items: center;">
            <span class="company-badge-tag" style="background: rgba(244, 63, 94, 0.18); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4);">
                Middleware & Cloud
            </span>
            <div style="height: 52px; display: flex; align-items: center; justify-content: center; margin: 0.3rem 0;">
                <img src="{wso2_img}" class="company-logo-img" alt="WSO2" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                <span style="display:none; font-size: 1.35rem; font-weight: 800; color: #ffffff;">WSO2</span>
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin-bottom: 0.2rem;">WSO2</div>
        </div>
        <div class="company-link-btn">
            <span>Explore Open Jobs</span>
            <span style="font-size: 0.9rem;">↗</span>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col_c2:
    st.markdown(f"""
    <a href="https://www.virtusa.com/careers" target="_blank" class="company-card-glass">
        <div style="width: 100%; display: flex; flex-direction: column; align-items: center;">
            <span class="company-badge-tag" style="background: rgba(6, 182, 212, 0.18); color: #38bdf8; border: 1px solid rgba(6, 182, 212, 0.4);">
                Digital Engineering & Cloud
            </span>
            <div style="height: 52px; display: flex; align-items: center; justify-content: center; margin: 0.3rem 0;">
                <img src="{virtusa_img}" class="company-logo-img" alt="Virtusa" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                <span style="display:none; font-size: 1.35rem; font-weight: 800; color: #ffffff;">Virtusa</span>
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin-bottom: 0.2rem;">Virtusa</div>
        </div>
        <div class="company-link-btn">
            <span>Explore Open Jobs</span>
            <span style="font-size: 0.9rem;">↗</span>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col_c3:
    st.markdown(f"""
    <a href="https://lseg.wd3.myworkdayjobs.com/Careers" target="_blank" class="company-card-glass">
        <div style="width: 100%; display: flex; flex-direction: column; align-items: center;">
            <span class="company-badge-tag" style="background: rgba(139, 92, 246, 0.18); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.4);">
                FinTech & Trading
            </span>
            <div style="height: 52px; display: flex; align-items: center; justify-content: center; margin: 0.3rem 0;">
                <img src="{lseg_img}" class="company-logo-img" alt="LSEG" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                <span style="display:none; font-size: 1.35rem; font-weight: 800; color: #ffffff;">LSEG</span>
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin-bottom: 0.2rem;">LSEG Sri Lanka</div>
        </div>
        <div class="company-link-btn">
            <span>Explore Open Jobs</span>
            <span style="font-size: 0.9rem;">↗</span>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col_c4:
    st.markdown(f"""
    <a href="https://www.ifs.com/en/about/careers" target="_blank" class="company-card-glass">
        <div style="width: 100%; display: flex; flex-direction: column; align-items: center;">
            <span class="company-badge-tag" style="background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);">
                Enterprise ERP & SaaS
            </span>
            <div style="height: 52px; display: flex; align-items: center; justify-content: center; margin: 0.3rem 0;">
                <img src="{ifs_img}" class="company-logo-img" alt="IFS" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
                <span style="display:none; font-size: 1.35rem; font-weight: 800; color: #ffffff;">IFS</span>
            </div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin-bottom: 0.2rem;">IFS World</div>
        </div>
        <div class="company-link-btn">
            <span>Explore Open Jobs</span>
            <span style="font-size: 0.9rem;">↗</span>
        </div>
    </a>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 3.6 Prominent Visual Section Divider for Detailed Report
# ------------------------------------------------------------------------------
st.markdown("""
<div id="career-report-section" class="report-divider-container">
    <hr class="report-divider-line">
    <div class="report-divider-badge">
        <span></span>
        <span>DETAILED CAREER REPORT</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Render Placeholder Banner if no report has been generated yet
if "career_advice_result" not in st.session_state:
    st.markdown("""
    <div class="report-placeholder-banner">
        <div class="report-placeholder-icon">📑</div>
        <div class="report-placeholder-title">Personalized Career Intelligence Report Section</div>
        <div class="report-placeholder-desc">
            Your detailed multi-agent AI career analysis, personalized career ladder, skills gap matrix, industry certifications, and grounded RAG insights will be generated and displayed right here in this section.
        </div>
        <div style="display: flex; gap: 0.65rem; justify-content: center; flex-wrap: wrap; margin-top: 1.1rem;">
            <span class="report-feature-badge">🗺️ Monthly Career Rungs</span>
            <span class="report-feature-badge">🎯 Live Skill Readiness Score</span>
            <span class="report-feature-badge">🏆 Industry Certifications Grid</span>
            <span class="report-feature-badge">📚 Grounded RAG References</span>
            <span class="report-feature-badge">📄 Exportable PDF Report</span>
        </div>
        <div style="margin-top: 1.4rem; font-size: 0.88rem; color: #34d399; font-weight: 700;">
            Enter your profile & goal above, then click <b>"Generate Career Advice & Roadmap"</b> to populate your report!
        </div>
    </div>
    """, unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# 4. Multi-Agent Pipeline Execution & Animated Progress
# ------------------------------------------------------------------------------
if submit_btn:
    current_input = user_input.strip() if user_input else ""
    if not current_input:
        st.warning("Please enter your current skills and target career goal before submitting.")
    else:
        btn_loading_placeholder.markdown("""
        <div class="button-loading-indicator">
            <div class="btn-spinner"></div>
            <span>Processing AI Workflow... Scroll Down to View Execution ↓</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Load API keys via secrets helper
        groq_key = get_secret("GROQ_API_KEY")
        openrouter_key = get_secret("OPENROUTER_API_KEY")

        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        if openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = openrouter_key

        # Ultra-Modern Interactive Multi-Agent Progress Dashboard
        progress_placeholder = st.empty()
        
        # Phase 1: Intent & Goal Parsing
        progress_placeholder.markdown(render_interactive_agent_progress(1), unsafe_allow_html=True)
        time.sleep(3.0)
        
        # Phase 2: RAG Knowledge Base Retrieval
        progress_placeholder.markdown(render_interactive_agent_progress(2), unsafe_allow_html=True)
        time.sleep(3.0)
        
        # Phase 3: Skills Gap Evaluator
        progress_placeholder.markdown(render_interactive_agent_progress(3), unsafe_allow_html=True)
        time.sleep(3.0)
        
        # Phase 4: Strategic Roadmap Synthesis
        progress_placeholder.markdown(render_interactive_agent_progress(4), unsafe_allow_html=True)
        
        try:
            # Invoke LangGraph Multi-Agent Workflow
            final_state: CareerAdvisorState = cast(CareerAdvisorState, run_career_advisor(current_input))
            st.session_state["career_advice_result"] = final_state
            st.session_state["last_executed_input"] = current_input
            # Reset completed tracker sets on new query execution
            st.session_state["completed_roadmap_steps"] = set()
            st.session_state["learned_skills"] = set()
            
            # Phase 5: Render 100% Completed State
            progress_placeholder.markdown(render_interactive_agent_progress(5), unsafe_allow_html=True)
            time.sleep(0.5)
            progress_placeholder.empty()
            btn_loading_placeholder.empty()
            st.toast("Multi-Agent Career Analysis Completed Successfully!")
            
        except Exception as e:
            logger.error(f"Error executing run_career_advisor: {e}", exc_info=True)
            progress_placeholder.empty()
            btn_loading_placeholder.empty()
            st.error(f"An error occurred while generating your advice: {e}")


# ------------------------------------------------------------------------------
# 5. Modern Structured Results Dashboard (Detailed Report Section)
# ------------------------------------------------------------------------------
if "career_advice_result" in st.session_state:
    result: CareerAdvisorState = st.session_state["career_advice_result"]
    last_executed = st.session_state.get("last_executed_input", "")
    current_input_text = user_input.strip() if 'user_input' in locals() and user_input else ""

    extracted_skills = result.get("skills") or []
    missing_skills = result.get("missing_skills") or []
    raw_goal = result.get("goal")
    target_role = raw_goal.strip() if isinstance(raw_goal, str) and raw_goal.strip() else "Target IT Role"
    recommendation = result.get("final_recommendation") or "No report content generated."

    # Eye-Catching Report Section Hero Header Banner
    st.markdown(f"""
    <div class="report-section-hero-wrapper">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
                <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; flex-wrap: wrap;">
                    <span class="report-status-pill-active">
                        <span class="report-pulse-dot"></span> LIVE ANALYSIS READY
                    </span>
                    <span class="report-status-pill-meta">
                        🇱🇰 SRI LANKA TECH BENCHMARK 2026
                    </span>
                </div>
                <h2 style="margin: 0.2rem 0 0.4rem 0; color: #ffffff; font-size: 1.85rem; font-weight: 800; letter-spacing: -0.02em;">
                    Your Personalized Career Intelligence Report
                </h2>
                <div style="color: #94a3b8; font-size: 0.95rem; line-height: 1.5;">
                    Comprehensive AI multi-agent roadmap, skills gap analysis, certifications, and local Sri Lankan IT market strategy.
                </div>
            </div>
            <div class="report-hero-role-chip">
                <span style="font-size: 0.75rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Target IT Position</span>
                <span style="font-size: 1.15rem; color: #38bdf8; font-weight: 800; margin-top: 0.15rem;">{target_role}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if current_input_text and last_executed and current_input_text != last_executed:
        st.warning("⚠️ **New Input Text Detected!** The report below is from your previous run. Click the blue **`Generate Career Advice & Roadmap`** button above to generate the new report for your updated profile!")

    # High-Level Metric Stat Box Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    with m_col1:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Target IT Role</div>
            <div class="metric-val-num" style="color: #818cf8; font-size: 1.05rem;">{target_role}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col2:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Current Strengths</div>
            <div class="metric-val-num" style="color: #34d399; font-size: 1.7rem;">{len(extracted_skills)}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col3:
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Missing Skills</div>
            <div class="metric-val-num" style="color: #fb7185; font-size: 1.7rem;">{len(missing_skills)}</div>
        </div>
        """, unsafe_allow_html=True)

    with m_col4:
        match_score = "High" if len(missing_skills) <= 2 else ("Medium" if len(missing_skills) <= 4 else "Growth Needed")
        color = "#34d399" if match_score == "High" else ("#fbbf24" if match_score == "Medium" else "#818cf8")
        st.markdown(f"""
        <div class="metric-card-glass">
            <div class="metric-lbl-text">Role Alignment</div>
            <div class="metric-val-num" style="color: {color}; font-size: 1.15rem;">{match_score}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabbed View Navigation
    tab_roadmap, tab_skills, tab_rag = st.tabs([
        "🗺️ Career Roadmap & Elevation Ladder", 
        "🎯 Skills Gap & Readiness Radar", 
        "📚 RAG Knowledge Base References"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: INTERACTIVE CAREER ROADMAP & ELEVATION LADDER
    # --------------------------------------------------------------------------
    with tab_roadmap:
        st.markdown("### Career Elevation Ladder")
        
        parsed_sec = parse_roadmap_sections(recommendation)

        # View Selector
        view_mode = st.radio(
            "Select View Mode:",
            ["Career Ladder", "Live Skill Readiness Tracker", "Full Markdown Report"],
            horizontal=True,
            key="roadmap_view_mode"
        )

        st.markdown("<br>", unsafe_allow_html=True)

        if view_mode == "Career Ladder":
            # Profile & Feasibility Hero Card
            if parsed_sec["profile"]:
                clean_profile = clean_text_formatting(parsed_sec["profile"])
                st.markdown(f"""
                <div class="report-card-box" style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.85) 0%, rgba(15, 23, 42, 0.9) 100%); border-color: rgba(99, 102, 241, 0.35);">
                    <div class="report-section-title">
                        <span>Target Career Profile & Feasibility Assessment</span>
                    </div>
                    <div>{clean_profile}</div>
                </div>
                """, unsafe_allow_html=True)

            steps = extract_timeline_steps(parsed_sec["roadmap"]) if parsed_sec["roadmap"] else []
            if not steps:
                steps = extract_timeline_steps(recommendation)
            if not steps:
                # Build dynamic fallback steps from the user's actual missing skills and goal
                dynamic_steps = []
                if missing_skills:
                    for i, skill in enumerate(missing_skills[:5], 1):
                        dynamic_steps.append({
                            "title": f"Month {i}: {skill}",
                            "details": [f"• Focus on hands-on learning, tutorials, and building mini-projects to develop proficiency in {skill} for {target_role} roles."]
                        })
                    dynamic_steps.append({
                        "title": f"Month {len(dynamic_steps) + 1}: Portfolio Building, Certifications & Interview Prep",
                        "details": [f"• Complete relevant certification prep, build a strong GitHub portfolio showcasing {target_role} projects, and apply for junior {target_role} roles in Sri Lanka."]
                    })
                else:
                    dynamic_steps = [
                        {"title": f"Month 1: Core Fundamentals for {target_role}", "details": [f"• Build foundational skills and domain knowledge required for {target_role} roles."]},
                        {"title": f"Month 2: Intermediate Skills & Tools", "details": [f"• Learn key tools, frameworks, and technologies commonly used by {target_role} professionals."]},
                        {"title": f"Month 3: Hands-on Projects & Practice", "details": [f"• Build real-world projects to strengthen your {target_role} portfolio."]},
                        {"title": f"Month 4: Advanced Concepts & Specialization", "details": [f"• Deep-dive into advanced topics and specializations within {target_role}."]},
                        {"title": f"Month 5: Certifications & Industry Preparation", "details": [f"• Pursue industry certifications valued for {target_role} roles in Sri Lanka."]},
                        {"title": f"Month 6: Job Search, Networking & Interview Prep", "details": [f"• Build your professional network, prepare for technical interviews, and apply for {target_role} positions."]},
                    ]
                steps = dynamic_steps

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
                        <span style="font-size: 1.35rem; font-weight: 800; color: #ffffff;">Ladder Climb Elevation</span>
                        <span style="font-size: 1.05rem; font-weight: 700; color: {tier_color}; background: rgba(0,0,0,0.4); padding: 0.4rem 1.1rem; border-radius: 20px; border: 1px solid {tier_color};">{tier_name}</span>
                    </div>
                    <div style="color: #cbd5e1; font-size: 0.98rem; margin-bottom: 0.6rem;">
                        Climbed <b>{completed_count}</b> of <b>{total_rungs}</b> Rungs ({progress_pct}% Completed)
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.progress(progress_pct / 100.0)
                st.markdown("<br>", unsafe_allow_html=True)

                st.subheader("Monthly Career Ladder Timeline")
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
                    
                    badge_label = f"✓ {meta['badge']}" if chk else meta['badge']
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
                        f'<div class="photo-card-3d-square">'
                        f'<img src="{meta.get("icon_3d_url", "")}" class="photo-card-3d-icon-img" alt="{meta["main_title"]}" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'inline-block\';" />'
                        f'<span style="display:none; font-size: 1.8rem; filter: drop-shadow(0 4px 10px rgba(0,242,254,0.6));">{meta["icon"]}</span>'
                        f'</div>'
                        f'<div class="photo-card-titles-wrap">'
                        f'<h3 class="photo-card-main-title">{meta["main_title"]}</h3>'
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

            # Calculate achieved count specifically for currently displayed cert_items
            achieved_count = sum(
                1 for cert in cert_items
                if f"cert_{cert['title'].strip()}" in st.session_state["achieved_certs"]
            )

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="font-size: 1.25rem; font-weight: 800; color: #ffffff; margin-bottom: 0.85rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
                <span>Industry Certification Cards Grid</span>
                <span style="font-size: 0.9rem; color: #c084fc; font-weight: 700; background: rgba(139, 92, 246, 0.2); padding: 0.3rem 0.85rem; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.4);">
                    Achieved: <b>{achieved_count}</b> of <b>{len(cert_items)}</b> Credentials
                </span>
            </div>
            """, unsafe_allow_html=True)

            # Render row by row in pairs of 2 columns to ensure clean widget layout without column interleaving issues
            for row_idx in range(0, len(cert_items), 2):
                row_items = cert_items[row_idx:row_idx+2]
                cols = st.columns(len(row_items))
                for col_idx, cert in enumerate(row_items):
                    c_idx = row_idx + col_idx
                    clean_title = cert["title"].strip()
                    cert_key = f"cert_{clean_title}"
                    is_achieved = cert_key in st.session_state["achieved_certs"]
                    
                    with cols[col_idx]:
                        card_class = "cert-card-glass cert-card-achieved" if is_achieved else "cert-card-glass"
                        badge_text = "✓ ACHIEVED" if is_achieved else "CREDENTIAL"
                        badge_class = "cert-pill-tag cert-pill-achieved" if is_achieved else "cert-pill-tag"
                        title_color = "#34d399" if is_achieved else "#ffffff"
                        icon = "🏆 " if is_achieved else "🎓 "
                        
                        card_html = (
                            f'<div class="{card_class}">'
                            f'<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem; flex-wrap: wrap; gap: 0.4rem;">'
                            f'<div style="font-weight: 800; font-size: 1.08rem; color: {title_color};">{icon}{cert["title"]}</div>'
                            f'<span class="{badge_class}">{badge_text}</span>'
                            f'</div>'
                            f'<div style="color: #cbd5e1; font-size: 0.92rem; line-height: 1.6; margin-bottom: 0.75rem;">{cert["desc"]}</div>'
                            f'</div>'
                        )
                        st.markdown(card_html, unsafe_allow_html=True)
                        
                        btn_label = "🏆 Achieved!" if is_achieved else "Mark as Achieved"
                        st.button(
                            btn_label,
                            key=f"btn_cert_toggle_{c_idx}_{clean_title[:15]}",
                            use_container_width=True,
                            on_click=toggle_cert_status,
                            args=(cert_key,)
                        )

            if parsed_sec["market_advice"]:
                cleaned_advice = clean_text_formatting(parsed_sec["market_advice"])
                st.markdown(f"""
                <div class="sl-strategic-box">
                    <div style="font-size: 1.05rem; font-weight: 700; color: #34d399; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span>Strategic Advice for Sri Lankan IT Market</span>
                    </div>
                    <div>{cleaned_advice}</div>
                </div>
                """, unsafe_allow_html=True)

        elif view_mode == "Live Skill Readiness Tracker":
            st.subheader("Skill Acquisition & Readiness Score Tracker")
            st.caption("Check off missing technical skills as you learn them to dynamically recalculate your readiness score!")

            if "learned_skills" not in st.session_state:
                st.session_state["learned_skills"] = set()

            total_initial_skills = len(extracted_skills)
            total_missing = len(missing_skills)
            total_required = total_initial_skills + total_missing

            col_tr1, col_tr2 = st.columns(2)

            with col_tr1:
                st.markdown("#### Current Strengths (Already Possessed)")
                if extracted_skills:
                    badges_html = "".join([f"<span class='skill-badge-emerald'>✓ {s}</span>" for s in extracted_skills])
                    st.markdown(f"<div style='display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 0.75rem; margin-bottom: 1rem;'>{badges_html}</div>", unsafe_allow_html=True)
                else:
                    st.caption("No current skills specified.")


            with col_tr2:
                st.markdown("#### Missing Skills to Acquire")
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
            st.markdown(f"### Your Updated Role Readiness: **{readiness_pct}%**")
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
                        <span>Target Career Profile & Feasibility</span>
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
                        <span>Technical Strengths vs Priority Missing Skill Gaps</span>
                    </div>
                """, unsafe_allow_html=True)

                col_rep_str, col_rep_gap = st.columns(2)

                with col_rep_str:
                    st.markdown('<h5 style="color: #34d399; margin-bottom: 0.8rem;">Existing Technical Strengths</h5>', unsafe_allow_html=True)
                    if extracted_skills:
                        str_items = "".join([f'<div class="report-strength-item"><b>{s}</b></div>' for s in extracted_skills])
                        st.markdown(f'<div class="report-skills-container">{str_items}</div>', unsafe_allow_html=True)
                    else:
                        st.info("No specific initial skills provided.")

                with col_rep_gap:
                    st.markdown('<h5 style="color: #fb7185; margin-bottom: 0.8rem;">Priority Skill Gaps to Acquire</h5>', unsafe_allow_html=True)
                    if missing_skills:
                        gap_items = "".join([f'<div class="report-gap-item"><b>{s}</b></div>' for s in missing_skills])
                        st.markdown(f'<div class="report-skills-container">{gap_items}</div>', unsafe_allow_html=True)
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
                        <span>Step-by-Step Short Learning Roadmap</span>
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
                        <span>Recommended Certifications & Industry Qualifications</span>
                    </div>
                    <div>{cleaned_certs}</div>
                </div>
                """, unsafe_allow_html=True)

            # 5. Sri Lanka Strategic Advice Section
            if (sec_filter == "Show All Sections" or "Market Advice" in sec_filter) and matches_kw(parsed_sec["market_advice"]):
                cleaned_advice = clean_text_formatting(parsed_sec["market_advice"]) if parsed_sec["market_advice"] else "Local market advice."
                st.markdown(f"""
                <div class="sl-strategic-box">
                    <div style="font-size: 1.05rem; font-weight: 700; color: #34d399; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;">
                        <span>Strategic Advice for Sri Lankan IT Market</span>
                    </div>
                    <div>{cleaned_advice}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown('<div style="margin-top: 1.5rem;"></div>', unsafe_allow_html=True)

            # Expander for Copyable Raw Markdown Source
            with st.expander("📋 View & Copy Raw Markdown Source Code", expanded=False):
                st.code(recommendation, language="markdown")

        st.markdown("<br>", unsafe_allow_html=True)
        # Download Academic PDF Advice Report Option
        pdf_data = generate_academic_pdf(
            target_role=target_role,
            parsed_sec=parsed_sec,
            raw_recommendation=recommendation,
            extracted_skills=extracted_skills,
            missing_skills=missing_skills
        )
        st.download_button(
            label="📄 Download Official Advice Report (.pdf)",
            data=pdf_data,
            file_name=f"career_advice_{target_role.lower().replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

    # --------------------------------------------------------------------------
    # TAB 2: SKILLS GAP BREAKDOWN
    # --------------------------------------------------------------------------
    with tab_skills:
        col_sk1, col_sk2 = st.columns(2)

        with col_sk1:
            st.markdown("#### Detected Technical Strengths")
            if extracted_skills:
                pills = "".join([f'<span class="skill-badge-emerald">{s}</span>' for s in extracted_skills])
                st.markdown(pills, unsafe_allow_html=True)
            else:
                st.info("No specific technical skills identified in your query.")

        with col_sk2:
            st.markdown("#### Priority Missing Skill Acquisition")
            if missing_skills:
                gaps_html = "".join([f'<span class="skill-badge-rose">{s}</span>' for s in missing_skills])
                st.markdown(gaps_html, unsafe_allow_html=True)
            else:
                st.success("🎉 You possess all primary technical prerequisites for this role!")

    # --------------------------------------------------------------------------
    # TAB 3: RAG KNOWLEDGE BASE REFERENCES
    # --------------------------------------------------------------------------
    with tab_rag:
        st.markdown("#### Grounded Knowledge Base Insights")
        st.caption("Verified curriculum benchmarks and domain knowledge retrieved for your analysis:")
        st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
        
        retrieved_context = result.get("retrieved_context", [])
        if retrieved_context:
            for idx, raw_chunk in enumerate(retrieved_context, 1):
                clean_text = raw_chunk
                display_title = f"Knowledge Insight #{idx}"
                
                # Strip out any raw file path prefix like [data\roadmaps\...]:
                if raw_chunk.startswith("[") and "]:" in raw_chunk:
                    parts = raw_chunk.split("]: ", 1)
                    clean_text = parts[1].strip()
                    filename_no_ext = os.path.splitext(os.path.basename(parts[0].lstrip("[").strip()))[0]
                    display_title = filename_no_ext.replace("_", " ").replace("-", " ").title()

                # Normalize all Markdown headers (# / ## / ###) to a uniform, clean font size (h4)
                lines = clean_text.split("\n")
                normalized_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        normalized_lines.append(f"#### {stripped[2:].strip()}")
                    elif stripped.startswith("## "):
                        normalized_lines.append(f"#### {stripped[3:].strip()}")
                    elif stripped.startswith("### "):
                        normalized_lines.append(f"#### {stripped[4:].strip()}")
                    else:
                        normalized_lines.append(line)
                
                normalized_content = "\n".join(normalized_lines)

                with st.expander(f"📌 {idx}. {display_title}", expanded=(idx <= 2)):
                    st.markdown(normalized_content)
        else:
            st.info("No direct RAG knowledge base insights were retrieved for this query.")