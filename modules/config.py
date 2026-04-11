"""
Credential loader.
- Local: reads from secrets.json in the project root
- Deployed (Streamlit Cloud): reads from st.secrets
"""

import json
import os

_secrets = None


def _load():
    global _secrets
    if _secrets is not None:
        return _secrets

    # Try local secrets.json first
    json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "secrets.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            _secrets = json.load(f)
        return _secrets

    # Fall back to Streamlit secrets (when deployed)
    try:
        import streamlit as st
        _secrets = {k: str(st.secrets[k]) for k in st.secrets}
        # DEBUG — remove after fix
        import streamlit as _st
        _st.write("DEBUG secrets keys:", list(_secrets.keys()))
        _st.write("DEBUG SUPABASE_KEY prefix:", _secrets.get("SUPABASE_KEY", "NOT FOUND")[:20])
    except Exception as e:
        _secrets = {}
        import streamlit as _st
        _st.write("DEBUG secrets load error:", str(e))

    return _secrets


def get(key, default=None):
    return _load().get(key, default)
