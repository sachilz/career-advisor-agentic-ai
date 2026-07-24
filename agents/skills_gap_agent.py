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

        # Robust JSON array extraction
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

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
    """Fallback skill gap calculator with role-aware requirements."""
    skills_lower = [s.lower() for s in skills]
    goal_lower = goal.lower()
    
    # Role-specific requirement maps
    role_requirements = {
        "devops": ["Linux Administration", "Docker & Containerization", "Kubernetes Orchestration", "CI/CD Pipelines (GitHub Actions/Jenkins)", "Terraform IaC", "AWS/Azure Cloud Fundamentals"],
        "data analyst": ["SQL & Complex Queries", "Data Visualization (Power BI / Tableau)", "Python/R for Analytics (Pandas/NumPy)", "Excel & Spreadsheet Modeling", "Statistics & Business Intelligence", "Data Warehousing & ETL Basics"],
        "data analytics": ["SQL & Complex Queries", "Data Visualization (Power BI / Tableau)", "Python/R for Analytics (Pandas/NumPy)", "Excel & Spreadsheet Modeling", "Statistics & Business Intelligence", "Data Warehousing & ETL Basics"],
        "data scien": ["Python (NumPy/Pandas)", "Machine Learning (Scikit-learn)", "Deep Learning (TensorFlow/PyTorch)", "SQL & Database Querying", "Data Visualization (Matplotlib/Seaborn)", "Statistics & Probability"],
        "data engineer": ["SQL & Database Design", "Python/Scala for Data Pipelines", "Apache Spark/Kafka", "ETL & Data Warehousing", "Cloud Data Services (AWS Redshift/GCP BigQuery)", "Airflow/dbt"],
        "database": ["SQL (Advanced Queries, Joins, Indexing)", "Database Design & Normalization", "PostgreSQL / MySQL Administration", "Performance Tuning & Query Optimization", "NoSQL Databases (MongoDB/Redis)", "Database Backup, Security & Disaster Recovery"],
        "sql": ["SQL (Advanced Queries, Joins, Indexing)", "Database Design & Normalization", "PostgreSQL / MySQL Administration", "Performance Tuning & Query Optimization", "NoSQL Databases (MongoDB/Redis)", "Data Warehousing Basics"],
        "backend": ["Python/Java/Node.js", "REST API Design", "SQL & Database Management", "Authentication & Security", "Docker & Deployment", "System Design Fundamentals"],
        "frontend": ["HTML/CSS/JavaScript", "React or Angular or Vue.js", "TypeScript", "Responsive Design & CSS Frameworks", "State Management (Redux/Zustand)", "Testing (Jest/Cypress)"],
        "full-stack": ["Frontend (React/Angular)", "Backend (Node.js/Python)", "REST API & GraphQL", "SQL & NoSQL Databases", "Docker & CI/CD", "Cloud Deployment (AWS/Vercel)"],
        "full stack": ["Frontend (React/Angular)", "Backend (Node.js/Python)", "REST API & GraphQL", "SQL & NoSQL Databases", "Docker & CI/CD", "Cloud Deployment (AWS/Vercel)"],
        "cloud": ["AWS/Azure/GCP Core Services", "Infrastructure as Code (Terraform)", "Networking & Security", "Containerization (Docker/K8s)", "Monitoring & Logging", "Cost Optimization"],
        "mobile": ["React Native or Flutter", "iOS/Android Native Development", "Mobile UI/UX Design", "REST API Integration", "App Store Deployment", "Push Notifications & Analytics"],
        "machine learning": ["Python (NumPy/Pandas/Scikit-learn)", "Deep Learning Frameworks", "Model Training & Evaluation", "Feature Engineering", "MLOps & Model Deployment", "Mathematics (Linear Algebra/Statistics)"],
        "ai": ["Python Programming", "Machine Learning Fundamentals", "Deep Learning (PyTorch/TensorFlow)", "NLP & Computer Vision", "LLM & Prompt Engineering", "MLOps & Model Deployment"],
        "cyber": ["Network Security Fundamentals", "Penetration Testing", "Security Information & Event Management (SIEM)", "Ethical Hacking Tools (Burp Suite/Metasploit)", "Compliance & Governance", "Incident Response"],
        "security": ["Network Security Fundamentals", "Penetration Testing", "Security Information & Event Management (SIEM)", "Ethical Hacking Tools (Burp Suite/Metasploit)", "Compliance & Governance", "Incident Response"],
        "qa": ["Manual Testing Fundamentals", "Test Automation (Selenium/Cypress)", "API Testing (Postman/RestAssured)", "CI/CD Integration Testing", "Performance Testing (JMeter)", "Test Planning & Bug Tracking"],
        "ui": ["Figma & Wireframing", "User Research & Usability Testing", "Design Systems & Prototyping", "Information Architecture", "HTML/CSS Basics"],
        "ux": ["Figma & Wireframing", "User Research & Usability Testing", "Design Systems & Prototyping", "Information Architecture", "HTML/CSS Basics"],
        "software engineer": ["Data Structures & Algorithms", "System Design", "Version Control (Git)", "Testing & Debugging", "API Design & Integration", "Cloud Deployment Basics"],
    }
    
    # Find matching role requirements
    reqs = None
    for role_key, role_reqs in role_requirements.items():
        if role_key in goal_lower:
            reqs = role_reqs
            break
    
    # Default generic requirements if no role match
    if reqs is None:
        reqs = ["Data Structures & Algorithms", "System Design", "Version Control (Git)", "Testing & Debugging", "API Design & Integration", "Cloud Deployment Basics"]
    
    missing = [req for req in reqs if not any(kw in req.lower() for kw in skills_lower)]
    return missing if missing else ["Advanced System Design", "Production Best Practices"]

