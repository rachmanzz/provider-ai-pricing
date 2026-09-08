#!/usr/bin/env python3
"""Info about the LLM endpoint for debugging.

Usage:
    python scripts/debug_llm.py
"""
import os

import requests

BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
AI_MODEL = os.environ.get("AI_MODEL", "").strip()
AI_KEY = os.environ.get("AI_KEY", "").strip()

endpoint = BASE_URL if BASE_URL.endswith("/chat/completions") else f"{BASE_URL}/chat/completions"
print(f"BASE_URL ends with /chat/completions: {BASE_URL.endswith('/chat/completions')}")
print(f"Resolved endpoint (host masked): {endpoint.replace(endpoint.split('://')[1].split('/')[0], '***', 1)}")
print(f"AI_MODEL: {AI_MODEL}")
print(f"AI_KEY set: {bool(AI_KEY)}")

resp = requests.post(
    endpoint,
    headers={"Authorization": f"Bearer {AI_KEY}", "Content-Type": "application/json"},
    json={"model": AI_MODEL, "messages": [{"role": "user", "content": "hi"}], "temperature": 0},
    timeout=60,
)
print(f"HTTP {resp.status_code}")
print(f"Body: {resp.text[:800]}")