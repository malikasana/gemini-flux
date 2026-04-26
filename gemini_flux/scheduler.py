"""
gemini-flux — Token-Aware Sliding Window Scheduler
The brain: figures out WHEN to send each request and on WHICH key + model.
"""

import time
from typing import Optional
from .key_pool import KeyState, KeyStatus


# Map model name to policy key
def _get_policy_key(model: str) -> str:
    if "lite" in model:
        return "flash_lite"
    if "flash" in model:
        return "flash"
    return "pro"


class Scheduler:
    def __init__(self, policy: dict, model_chain: list, mode: str = "both"):
        self.policy = policy
        self.model_chain = model_chain  # dynamic, not hardcoded
        self.mode = mode

    def _get_tpm(self, model: str) -> int:
        key = _get_policy_key(model)
        return self.policy.get(key, {}).get("tokens_per_minute", 250000)

    def _get_rpd(self, model: str) -> int:
        key = _get_policy_key(model)
        return self.policy.get(key, {}).get("requests_per_day", 100)

    def _allowed_models(self) -> list:
        """Filter model chain based on current mode."""
        if self.mode == "pro_only":
            return [m for m in self.model_chain if "pro" in m]
        elif self.mode == "flash_only":
            return [m for m in self.model_chain if "flash" in m and "lite" not in m]
        elif self.mode == "flash_lite_only":
            return [m for m in self.model_chain if "lite" in m]
        else:
            return self.model_chain

    def _select_model(self, key: KeyState) -> Optional[str]:
        """Pick first model in chain that still has quota for this key."""
        for model in self._allowed_models():
            rpd = self._get_rpd(model)
            used = key.requests_today.get(model, 0)
            if used < rpd:
                return model
        return None

    def pick_key(self, pool: list, needed_tokens: int) -> tuple:
        """
        Find best key + model for this request.
        Returns (key, model, wait_seconds).
        """
        best_key = None
        best_model = None
        best_wait = float("inf")

        for key in pool:
            if key.status == KeyStatus.INVALID:
                continue
            if key.status == KeyStatus.EXHAUSTED:
                continue

            model = self._select_model(key)
            if model is None:
                key.status = KeyStatus.EXHAUSTED
                print(f"[KEY {key.index}] ⚠️  All models exhausted for today")
                continue

            tpm = self._get_tpm(model)
            wait = key.seconds_until_available(needed_tokens, tpm)

            if wait < best_wait:
                best_wait = wait
                best_key = key
                best_model = model

        return best_key, best_model, best_wait

    def count_tokens(self, key: KeyState, prompt_parts: list) -> int:
        """Count tokens using FREE count_tokens API."""
        from google import genai
        try:
            client = genai.Client(api_key=key.api_key)
            response = client.models.count_tokens(
                model="gemini-2.5-flash",
                contents=prompt_parts
            )
            return response.total_tokens
        except Exception as e:
            print(f"[SCHEDULER] ⚠️  Token count failed: {e} — estimating")
            total_chars = sum(len(str(p)) for p in prompt_parts)
            return total_chars // 4