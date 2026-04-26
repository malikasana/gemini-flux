"""
gemini-flux — Smart Policy Fetcher
Asks Gemini about its own free tier limits and caches the result.
Also dynamically discovers available models.
"""

import json
import os
import time
from google import genai

CACHE_FILE = ".gemini_flux_policy_cache.json"
CACHE_TTL_DAYS = 7

FALLBACK_POLICY = {
    "pro": {
        "requests_per_day": 100,
        "tokens_per_minute": 250000,
        "requests_per_minute": 2
    },
    "flash": {
        "requests_per_day": 250,
        "tokens_per_minute": 250000,
        "requests_per_minute": 10
    },
    "flash_lite": {
        "requests_per_day": 1000,
        "tokens_per_minute": 250000,
        "requests_per_minute": 15
    },
    "token_cooldown_seconds": 240,
    "daily_reset_time_pt": "00:00"
}

FALLBACK_MODEL_CHAIN = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
]

POLICY_PROMPT = """You are a data provider. Return ONLY a raw JSON object.
No markdown, no backticks, no explanation, no preamble, no trailing text.
Use this exact schema with real current Gemini free tier API limit values:

{
  "pro": {
    "requests_per_day": <integer>,
    "tokens_per_minute": <integer>,
    "requests_per_minute": <integer>
  },
  "flash": {
    "requests_per_day": <integer>,
    "tokens_per_minute": <integer>,
    "requests_per_minute": <integer>
  },
  "flash_lite": {
    "requests_per_day": <integer>,
    "tokens_per_minute": <integer>,
    "requests_per_minute": <integer>
  },
  "token_cooldown_seconds": <integer>,
  "daily_reset_time_pt": "<HH:MM>"
}

Only return the JSON. Nothing else."""

EXCLUDE_KEYWORDS = [
    "embedding", "imagen", "veo", "lyria", "tts", "audio",
    "image", "aqa", "robotics", "computer-use",
    "deep-research", "native-audio", "live"
]


def _is_text_model(name: str) -> bool:
    name = name.lower().replace("models/", "")
    if "gemini" not in name:
        return False
    if "gemma" in name:
        return False
    if any(kw in name for kw in EXCLUDE_KEYWORDS):
        return False
    return True


def _sort_models(models: list) -> list:
    import re
    def priority(name):
        n = name.lower()
        match = re.search(r'(\d+\.?\d*)', n)
        version = float(match.group(1)) if match else 0
        if "pro" in n and "preview" not in n:
            cat = 0
        elif "flash" in n and "lite" not in n and "preview" not in n:
            cat = 1
        elif "lite" in n and "preview" not in n:
            cat = 2
        elif "pro" in n and "preview" in n:
            cat = 3
        elif "flash" in n and "lite" not in n and "preview" in n:
            cat = 4
        elif "lite" in n and "preview" in n:
            cat = 5
        else:
            cat = 6
        return (cat, -version)
    return sorted(models, key=priority)


def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return None, None
    try:
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
        age_days = (time.time() - data.get("fetched_at", 0)) / 86400
        if age_days > CACHE_TTL_DAYS:
            print(f"[POLICY] Cache is {age_days:.1f} days old — refreshing")
            return None, None
        print(f"[POLICY] Using cached policy ({age_days:.1f} days old)")
        return data.get("policy"), data.get("models")
    except Exception:
        return None, None


def _save_cache(policy: dict, models: list):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "fetched_at": time.time(),
                "policy": policy,
                "models": models
            }, f, indent=2)
    except Exception as e:
        print(f"[POLICY] ⚠️  Could not save cache: {e}")


def fetch_models(api_key: str) -> list:
    """Dynamically fetch available text-generation models. FREE — no quota cost."""
    print("[MODELS] Discovering available Gemini models...")
    try:
        client = genai.Client(api_key=api_key)
        all_models = client.models.list()
        text_models = [
            m.name.replace("models/", "")
            for m in all_models
            if _is_text_model(m.name)
        ]
        sorted_models = _sort_models(text_models)
        print(f"[MODELS] ✅ Discovered {len(sorted_models)} text generation models")
        return sorted_models
    except Exception as e:
        print(f"[MODELS] ⚠️  Discovery failed: {e} — using fallback chain")
        return FALLBACK_MODEL_CHAIN


def fetch_policy(api_key: str, force: bool = False) -> tuple:
    """
    Returns (policy_dict, model_chain, used_request).
    used_request=True means 1 real API request was consumed.
    """
    if not force:
        cached_policy, cached_models = _load_cache()
        if cached_policy and cached_models:
            return cached_policy, cached_models, False

    # Fetch models first (FREE)
    models = fetch_models(api_key)

    # Fetch policy (costs 1 request)
    print("[POLICY] Fetching current Gemini free tier limits...")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=POLICY_PROMPT
        )
        raw = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        policy = json.loads(raw)
        _save_cache(policy, models)
        print("[POLICY] ✅ Policy fetched and cached successfully")
        return policy, models, True

    except json.JSONDecodeError as e:
        print(f"[POLICY] ⚠️  Could not parse response: {e} — using fallback policy")
        _save_cache(FALLBACK_POLICY, models)
        return FALLBACK_POLICY, models, True
    except Exception as e:
        print(f"[POLICY] ⚠️  Fetch failed: {e} — using fallback policy")
        _save_cache(FALLBACK_POLICY, models)
        return FALLBACK_POLICY, models, True