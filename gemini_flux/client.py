"""
gemini-flux — Lightweight Client
Use anywhere: Kaggle, scripts, notebooks.
"""

import requests
from typing import Optional


class GeminiFluxClient:
    """
    HTTP client for gemini-flux microservice.
    Use when the Docker service is running somewhere.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def generate(
        self,
        prompt: str,
        images: Optional[list] = None,
        files: Optional[list] = None,
        mode: Optional[str] = None,
        preferred_key: Optional[int] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        retry: bool = True
    ) -> dict:
        payload = {
            "prompt": prompt,
            "images": images or [],
            "files": files or [],
            "mode": mode,
            "preferred_key": preferred_key,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "retry": retry
        }
        resp = requests.post(f"{self.base_url}/generate", json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        resp = requests.get(f"{self.base_url}/status", timeout=30)
        resp.raise_for_status()
        return resp.json()

    def refresh_policy(self) -> dict:
        resp = requests.post(f"{self.base_url}/refresh-policy", timeout=60)
        resp.raise_for_status()
        return resp.json()

    def set_mode(self, mode: str) -> dict:
        resp = requests.post(f"{self.base_url}/config", json={"mode": mode}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def disable_key(self, index: int) -> dict:
        resp = requests.post(f"{self.base_url}/config", json={"disable_key": index}, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def enable_key(self, index: int) -> dict:
        resp = requests.post(f"{self.base_url}/config", json={"enable_key": index}, timeout=30)
        resp.raise_for_status()
        return resp.json()