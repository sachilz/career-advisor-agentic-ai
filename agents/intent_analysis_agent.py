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
from typing import Optional, List, Dict, Any
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
        "2. 'goal': The desired target IT career role implied or mentioned by the student.\n"
        "Determine the EXACT real IT role accurately from context clues:\n"
        "- Predictive systems, predictive modeling, discovering patterns, datasets, machine learning, PyTorch, TensorFlow, Pandas -> 'AI/ML Engineer'.\n"
        "- Data pipelines, ETL, data engineering, big data, Spark, Kafka -> 'Data Engineer'.\n"
        "- Docker, Kubernetes, Terraform, Jenkins, CI/CD, infrastructure automation -> 'DevOps Engineer'.\n"
        "- SQL, database management, relational databases, data querying, analytics -> 'Data Analyst' or 'Database Administrator'.\n"
        "- React, HTML, CSS, JavaScript, frontend -> 'Frontend Developer'.\n"
        "- Node.js, Express, Spring Boot, REST API, microservices (without data analytics/predictive focus) -> 'Backend Developer'.\n"
        "- Wireshark, penetration testing, networking, ethical hacking -> 'Cybersecurity Analyst'.\n"
        "Do NOT default to Full-Stack Developer or Software Engineer when specific domain keywords exist.\n\n"
        "Return ONLY a valid JSON object in this exact format, with no Markdown wrapping or conversational text:\n"
        '{"skills": ["Python", "Pandas", "SQL"], "goal": "AI/ML Engineer"}'
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]

    try:
        response = model.invoke(messages)
        content = response.content
        # Handle case where content is a list (e.g. tool calls / content blocks)
        if isinstance(content, list):
            content = " ".join(c for c in content if isinstance(c, str))
        content = content.strip()

        # Extract JSON object from content robustly
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            content = json_match.group(0)

        parsed = json.loads(content)
        extracted_skills = parsed.get("skills", [])
        extracted_goal = parsed.get("goal", "Software Engineer")

    except Exception as e:
        print(f"[Agent 1: Intent Analysis] Warning parsing LLM response: {e}. Applying fallback extraction.")
        extracted_skills, extracted_goal = _heuristic_extraction(user_input)

    # Post-validation: Enforce domain matrix role if LLM output is generic or misclassified without explicit mention
    matrix_role = _classify_role_by_domain_matrix(user_input)
    if matrix_role:
        # Check if user explicitly wrote a target role title in text
        explicit_mention = re.search(
            r"(?:goal is to become|become a|become an|aspiring|seeking|target role|target is|work as a|transition into an|transition into a|aiming for|path for)\s+([a-zA-Z0-9\s\/\-\+]+)",
            user_input, re.IGNORECASE
        )
        if explicit_mention:
            pass
        elif extracted_goal in ["Software Engineer", "Full-Stack Developer", "Target IT Role"]:
            extracted_goal = matrix_role
        elif not extracted_goal:
            extracted_goal = matrix_role

    print(f"  [+] Extracted Skills: {extracted_skills}")
    print(f"  [+] Extracted Goal:   {extracted_goal}")


    return {
        **state,
        "skills": extracted_skills,
        "goal": extracted_goal
    }


def _classify_role_by_domain_matrix(text: str) -> Optional[str]:
    """Score matching domain keyword clusters to deterministically identify the exact IT job role."""
    text_lower = text.lower()

    domain_matrix = {
        "DevOps Engineer": [
            "devops", "docker", "kubernetes", "k8s", "terraform", "jenkins", "github actions",
            "ci/cd", "infrastructure automation", "containerized", "system reliability", "sre",
            "deployment efficiency", "automate deployments", "ansible", "cloud platforms",
            "provision infrastructure", "prometheus", "grafana"
        ],
        "AI/ML Engineer": [
            "ai/ml", "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn",
            "mlops", "neural networks", "nlp", "computer vision", "llm", "pandas", "numpy",
            "predictive", "predictive systems", "discovering patterns", "patterns in complex datasets",
            "predictive modeling", "dataset", "datasets"
        ],
        "Data Analyst": [
            "data analyst", "data analytics", "analyze data", "power bi", "tableau", "excel",
            "sql queries", "relational databases", "data manipulation", "business intelligence"
        ],
        "Data Engineer": [
            "data engineer", "data pipeline", "data pipelines", "apache spark", "spark", "kafka", "etl",
            "data warehousing", "snowflake", "bigquery", "airflow", "dbt"
        ],
        "Frontend Developer": [
            "frontend", "front-end", "react", "angular", "vue", "html", "css", "javascript",
            "typescript", "next.js", "tailwind", "responsive design", "ui component"
        ],
        "Backend Developer": [
            "backend", "back-end", "node.js", "express", "spring boot", "django", "flask",
            "fastapi", "rest api", "graphql", "microservices", "authentication"
        ],
        "Cybersecurity Analyst": [
            "cybersecurity", "cyber", "penetration testing", "ethical hacking", "wireshark",
            "siem", "metasploit", "burp suite", "network security", "firewall", "incident response"
        ],
        "Mobile App Developer": [
            "mobile app", "flutter", "react native", "swift", "kotlin", "android", "ios developer"
        ],
        "QA Engineer": [
            "qa engineer", "quality assurance", "test automation", "selenium", "cypress",
            "postman", "jmeter", "manual testing"
        ],
        "UI/UX Designer": [
            "ui/ux", "ux design", "ui design", "figma", "wireframing", "usability testing", "prototyping"
        ],
        "Database Administrator": [
            "database admin", "dba", "database administrator", "pl/sql", "database tuning", "indexing"
        ],
        "Cloud Engineer": [
            "cloud engineer", "aws certified", "azure engineer", "cloud architecture", "gcp"
        ]
    }

    scores = {}
    for role, keywords in domain_matrix.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[role] = score

    if scores:
        best_role = max(scores.items(), key=lambda x: x[1])[0]
        return best_role

    return None


def _heuristic_extraction(text: str):
    """Fallback extraction when LLM returns non-JSON format or offline."""
    text_lower = text.lower()

    # Skill regex pattern map to avoid false substring matches (e.g. 'java' inside 'javascript')
    skill_patterns = {
        "python": r"\bpython\b",
        "java": r"\bjava\b(?![\s\-]*script)",
        "javascript": r"\bjava[\s\-]*script\b|\bjs\b",
        "typescript": r"\btype[\s\-]*script\b|\bts\b",
        "c++": r"\bc\+\+\b",
        "c#": r"\bc\#\b",
        "react": r"\breact(?:\.js)?\b",
        "angular": r"\bangular(?:\.js)?\b",
        "vue": r"\bvue(?:\.js)?\b",
        "node": r"\bnode(?:\.js)?\b",
        "sql": r"\bsql\b",
        "mysql": r"\bmysql\b",
        "postgresql": r"\bpostgres(?:ql)?\b",
        "mongodb": r"\bmongo(?:db)?\b",
        "redis": r"\bredis\b",
        "aws": r"\baws\b",
        "azure": r"\bazure\b",
        "gcp": r"\bgcp\b",
        "docker": r"\bdocker\b",
        "kubernetes": r"\bkubernetes\b|\bk8s\b",
        "git": r"\bgit\b",
        "linux": r"\blinux\b",
        "html": r"\bhtml5?\b",
        "css": r"\bcss3?\b",
        "django": r"\bdjango\b",
        "flask": r"\bflask\b",
        "spring": r"\bspring(?:\s*boot)?\b",
        "tensorflow": r"\btensorflow\b",
        "pytorch": r"\bpytorch\b",
        "pandas": r"\bpandas\b",
        "numpy": r"\bnumpy\b",
        "scikit-learn": r"\bscikit[\s\-]*learn\b|\bsklearn\b",
        "flutter": r"\bflutter\b",
        "react native": r"\breact[\s\-]*native\b",
        "swift": r"\bswift\b",
        "kotlin": r"\bkotlin\b",
        "go": r"\bgo\b|\bgolang\b",
        "rust": r"\brust\b",
        "php": r"\bphp\b",
        "laravel": r"\blaravel\b",
        "ruby": r"\bruby\b",
        "rails": r"\brails\b",
        "terraform": r"\bterraform\b",
        "jenkins": r"\bjenkins\b",
        "github actions": r"\bgithub[\s\-]*actions\b",
        "figma": r"\bfigma\b",
        "selenium": r"\bselenium\b",
        "jira": r"\bjira\b",
        "jest": r"\bjest\b",
        "cypress": r"\bcypress\b",
        "postman": r"\bpostman\b",
        "jmeter": r"\bjmeter\b",
        "manual testing": r"\bmanual[\s\-]*testing\b",
        "qa": r"\bqa\b|\bquality[\s\-]*assurance\b",
        "graphql": r"\bgraphql\b",
        "kafka": r"\bkafka\b",
        "spark": r"\bspark\b",
        "hadoop": r"\bhadoop\b",
        "airflow": r"\bairflow\b",
        "dbt": r"\bdbt\b",
        "tableau": r"\btableau\b",
        "power bi": r"\bpower[\s\-]*bi\b",
        "excel": r"\bexcel\b",
        "r": r"\b(?!in\b)r\b",
        "matlab": r"\bmatlab\b",
        "scala": r"\bscala\b",
        "dart": r"\bdart\b",
        "firebase": r"\bfirebase\b",
        "supabase": r"\bsupabase\b",
        "next.js": r"\bnext(?:\.js)?\b",
        "nuxt": r"\bnuxt(?:\.js)?\b",
        "tailwind": r"\btailwind\b",
        "bootstrap": r"\bbootstrap\b",
        "sass": r"\bsass\b",
        "webpack": r"\bwebpack\b",
        "vite": r"\bvite\b"
    }

    display_names = {
        "python": "Python",
        "java": "Java",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "c++": "C++",
        "c#": "C#",
        "react": "React",
        "angular": "Angular",
        "vue": "Vue.js",
        "node": "Node.js",
        "sql": "SQL",
        "mysql": "MySQL",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "GCP",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "git": "Git",
        "linux": "Linux",
        "html": "HTML",
        "css": "CSS",
        "django": "Django",
        "flask": "Flask",
        "spring": "Spring Boot",
        "tensorflow": "TensorFlow",
        "pytorch": "PyTorch",
        "pandas": "Pandas",
        "numpy": "NumPy",
        "scikit-learn": "Scikit-Learn",
        "flutter": "Flutter",
        "react native": "React Native",
        "swift": "Swift",
        "kotlin": "Kotlin",
        "go": "Go",
        "rust": "Rust",
        "php": "PHP",
        "laravel": "Laravel",
        "ruby": "Ruby",
        "rails": "Ruby on Rails",
        "terraform": "Terraform",
        "jenkins": "Jenkins",
        "github actions": "GitHub Actions",
        "figma": "Figma",
        "selenium": "Selenium",
        "jira": "Jira",
        "jest": "Jest",
        "cypress": "Cypress",
        "postman": "Postman",
        "jmeter": "JMeter",
        "manual testing": "Manual Testing",
        "qa": "QA / Quality Assurance",
        "graphql": "GraphQL",
        "kafka": "Kafka",
        "spark": "Apache Spark",
        "hadoop": "Hadoop",
        "airflow": "Airflow",
        "dbt": "dbt",
        "tableau": "Tableau",
        "power bi": "Power BI",
        "excel": "Excel",
        "r": "R",
        "matlab": "MATLAB",
        "scala": "Scala",
        "dart": "Dart",
        "firebase": "Firebase",
        "supabase": "Supabase",
        "next.js": "Next.js",
        "nuxt": "Nuxt.js",
        "tailwind": "Tailwind CSS",
        "bootstrap": "Bootstrap",
        "sass": "Sass",
        "webpack": "Webpack",
        "vite": "Vite"
    }

    found_skills = []
    for skill_key, pattern in skill_patterns.items():
        if re.search(pattern, text_lower):
            disp = display_names.get(skill_key, skill_key.title())
            if disp not in found_skills:
                found_skills.append(disp)

    # 1. Try explicit role extraction using intent regex
    extracted_role = None
    role_intent_match = re.search(
        r"(?:goal is to become|become a|become an|aspiring|seeking|target role|target is|work as a|transition into an|transition into a|aiming for|path for)\s+([a-zA-Z0-9\s\/\-\+]+?)(?:\.|\,|\;|$|\n|in Sri Lanka)",
        text, re.IGNORECASE
    )
    if role_intent_match:
        cand = role_intent_match.group(1).strip()
        # Clean candidates
        if len(cand) > 2 and len(cand) < 40 and cand.lower() not in ["a", "an", "the", "my"]:
            extracted_role = cand.title()

    # 2. Use Domain Matrix Classification
    if not extracted_role:
        extracted_role = _classify_role_by_domain_matrix(text)

    goal = extracted_role if extracted_role else "Software Engineer"
    return found_skills, goal



