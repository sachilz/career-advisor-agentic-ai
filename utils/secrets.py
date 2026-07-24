"""
Environment Secrets Helper Utility.

WHY BOTH ARE NEEDED (VIVA EXPLANATION):
----------------------------------------
1. Streamlit Cloud Deployment:
   When deployed on Streamlit Cloud (https://share.streamlit.io), environment variables 
   are stored securely in Streamlit's managed secrets manager, accessed via `st.secrets["KEY"]`.
   `os.getenv()` will NOT find these secrets in a cloud environment unless explicitly injected.

2. Local Development (.env):
   During local development, developers store API keys in a local `.env` file (loaded via python-dotenv).
   `st.secrets` will raise a FileNotFoundError if `.streamlit/secrets.toml` does not exist locally.

By checking `st.secrets` first and falling back to `os.getenv(key)`, `get_secret()` enables seamless
execution both locally and in cloud production environments without code changes.
"""

import os
from typing import Optional
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Load local .env file if present
load_dotenv()


def get_secret(key: str, default: Optional[str] = "") -> str:
    """
    Retrieves a secret or configuration value by key.
    Checks Streamlit Cloud secrets manager (`st.secrets`) first, then falls back to `os.getenv()`.
    
    Args:
        key (str): Secret variable key (e.g. 'GROQ_API_KEY', 'OPENROUTER_API_KEY').
        default (str): Fallback default value if key is missing in both sources.
        
    Returns:
        str: Secret value or default string.
    """
    # 1. Try Streamlit Cloud secrets (st.secrets)
    try:
        # type: ignore # pyrefly: ignore [missing-import]
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            val = st.secrets[key]
            if val:
                return str(val)
    except Exception:
        # Ignore exception if Streamlit is not initialized or secrets.toml is missing
        pass

    # 2. Fall back to local environment variables (os.getenv)
    env_val = os.getenv(key, default)
    return env_val if env_val is not None else default
