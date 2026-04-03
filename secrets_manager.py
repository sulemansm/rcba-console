"""
secrets_manager.py - Handle environment variables and Streamlit secrets
Works both locally (.env) and on Streamlit Cloud (secrets.toml)
"""

import os
import json
import streamlit as st
from dotenv import load_dotenv

# Load .env file for local development
load_dotenv()


def get_secret(key: str, default: str = "") -> str:
    """
    Get secret from Streamlit Cloud or .env file
    
    Priority:
    1. Streamlit secrets (st.secrets)
    2. Environment variables (.env)
    3. Default value
    """
    try:
        # Try Streamlit secrets first (runs on Streamlit Cloud)
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except:
        pass
    
    # Fall back to environment variables (.env)
    value = os.getenv(key)
    if value:
        return value
    
    # Return default
    return default


def get_secret_dict(key: str, default: dict = None) -> dict:
    """Get a dictionary secret (e.g., JSON credentials)"""
    if default is None:
        default = {}
    
    try:
        # Try Streamlit secrets first
        if hasattr(st, 'secrets') and key in st.secrets:
            val = st.secrets[key]
            if isinstance(val, dict):
                return val
            elif isinstance(val, str):
                return json.loads(val)
    except:
        pass
    
    # Fall back to environment variable
    val = os.getenv(key)
    if val:
        try:
            return json.loads(val) if isinstance(val, str) else val
        except:
            return default
    
    return default


def get_oauth_redirect_uri() -> str:
    """
    Get OAuth redirect URI
    - For local: http://localhost:8501/
    - For Streamlit Cloud: https://your-app.streamlit.app/
    """
    # Try from secrets/env first (for manual override)
    override = get_secret("OAUTH_REDIRECT_URI")
    if override and override != "http://localhost:8501/":
        return override
    
    # Auto-detect from Streamlit's URL
    try:
        # This is available when running on Streamlit Cloud
        if hasattr(st, 'session_state') and hasattr(st, '_get_script_run_ctx'):
            ctx = st._get_script_run_ctx()
            if ctx:
                return f"{ctx.session_state.get('base_url', 'http://localhost:8501/')}"
    except:
        pass
    
    # Fallback to localhost
    return "http://localhost:8501/"


def load_google_credentials() -> dict:
    """
    Load Google OAuth credentials from multiple sources:
    1. GOOGLE_CREDENTIALS_JSON secret (Streamlit Cloud)
    2. google_credentials.json file (local)
    3. Empty dict if neither available
    """
    # Try from Streamlit secrets (JSON as string)
    try:
        creds_json = get_secret("GOOGLE_CREDENTIALS_JSON")
        if creds_json and isinstance(creds_json, str):
            try:
                data = json.loads(creds_json)
                return data.get("web") or data.get("installed") or {}
            except:
                pass
    except:
        pass
    
    # Try from environment variable (JSON as string)
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            try:
                data = json.loads(creds_json)
                return data.get("web") or data.get("installed") or {}
            except:
                pass
    except:
        pass
    
    # Try from file (local development)
    try:
        creds_file = get_secret("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        if os.path.exists(creds_file):
            with open(creds_file) as f:
                data = json.load(f)
            return data.get("web") or data.get("installed") or {}
    except:
        pass
    
    return {}


def get_whitelisted_emails() -> set:
    raw = get_secret("WHITELISTED_EMAILS", "")

    # If already a list (Streamlit secrets)
    if isinstance(raw, list):
        return {e.strip().lower() for e in raw if e.strip()}

    # If string (local .env)
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def has_google_credentials() -> bool:
    """
    Check if Google OAuth credentials are available from any source
    Returns True if credentials can be found (file or JSON string)
    """
    # Check if GOOGLE_CREDENTIALS_JSON is available (Streamlit Cloud or .env)
    try:
        creds_json = get_secret("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            try:
                data = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
                if data.get("web") or data.get("installed"):
                    return True
            except:
                pass
    except:
        pass
    
    # Check if google_credentials.json file exists (local)
    try:
        creds_file = get_secret("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")
        if os.path.exists(creds_file):
            return True
    except:
        pass
    
    return False


def is_running_on_streamlit_cloud() -> bool:
    """Check if app is running on Streamlit Cloud"""
    return "STREAMLIT_SERVER_HEADLESS" in os.environ or "streamlit" in os.getenv("PATH", "")
