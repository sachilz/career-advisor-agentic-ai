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

# Ensure project root is in sys.path BEFORE package imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
        "- Docker, Kubernetes, Terraform, Jenkins, CI/CD, infrastructure automation -> 'DevOps Engineer'.\n"
        "- SQL, database management, relational databases, data querying -> 'Data Analyst' or 'Database Administrator'.\n"
        "- PyTorch, TensorFlow, Scikit-learn, deep learning, machine learning -> 'AI/ML Engineer'.\n"
        "- React, HTML, CSS, JavaScript, frontend -> 'Frontend Developer'.\n"
        "- Node.js, Express, Spring Boot, REST API, microservices -> 'Backend Developer'.\n"
        "- Wireshark, penetration testing, networking, ethical hacking -> 'Cybersecurity Analyst'.\n"
        "Do NOT default to Full-Stack Developer or Software Engineer when specific domain keywords exist.\n\n"
        "Return ONLY a valid JSON object in this exact format, with no Markdown wrapping or conversational text:\n"
        '{"skills": ["Linux", "Docker", "Kubernetes"], "goal": "DevOps Engineer"}'
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
            content = " ".join(str(c) for c in content if isinstance(c, str))
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
        if not explicit_mention:
            extracted_goal = matrix_role
        elif extracted_goal in ["Software Engineer", "Full-Stack Developer", "Target IT Role"]:
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
            "mlops", "neural networks", "nlp", "computer vision", "llm", "pandas", "numpy"
        ],
        "Data Analyst": [
            "data analyst", "data analytics", "analyze data", "power bi", "tableau", "excel",
            "sql queries", "relational databases", "data manipulation", "business intelligence"
        ],
        "Data Engineer": [
            "data engineer", "data pipeline", "apache spark", "spark", "kafka", "etl",
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
    known_skills = [
        "python", "java", "c++", "c#", "javascript", "typescript", "react", "angular", "vue",
        "node", "sql", "mysql", "postgresql", "mongodb", "redis", "aws", "azure", "gcp",
        "docker", "kubernetes", "git", "linux", "html", "css", "django", "flask", "spring",
        "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "flutter", "react native",
        "swift", "kotlin", "go", "rust", "php", "laravel", "ruby", "rails", "terraform",
        "jenkins", "github actions", "figma", "selenium", "jest", "cypress", "graphql",
        "kafka", "spark", "hadoop", "airflow", "dbt", "tableau", "power bi", "excel",
        "r", "matlab", "scala", "dart", "firebase", "supabase", "next.js", "nuxt",
        "tailwind", "bootstrap", "sass", "webpack", "vite", "relational databases",
        "database design", "data manipulation", "data analysis", "infrastructure automation",
        "monitoring tools", "containerized environments"
    ]
    text_lower = text.lower()
    
    found_skills = []
    for s in known_skills:
        if s in text_lower:
            found_skills.append(s.title())

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



