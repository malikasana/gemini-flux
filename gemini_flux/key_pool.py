import time
from dataclasses import dataclass, field
from enum import Enum
from google import genai


class KeyStatus(Enum):
    HEALTHY = "healthy"
    EXHAUSTED = "exhausted"
    INVALID = "invalid"


@dataclass
class KeyState:
    index: int
    api_key: str
    status: KeyStatus = KeyStatus.HEALTHY

    # Daily usage per model
    requests_today: dict = field(default_factory=dict)

    # Sliding window: list of (timestamp, token_count) tuples
    token_window: list = field(default_factory=list)

    last_used_at: float = 0.0

    def available_tokens_now(self, tokens_per_minute: int) -> int:
        now = time.time()
        self.token_window = [(t, tok) for t, tok in self.token_window if t > now - 60.0]
        used = sum(tok for _, tok in self.token_window)
        return max(0, tokens_per_minute - used)

    def seconds_until_available(self, needed_tokens: int, tokens_per_minute: int) -> float:
        now = time.time()
        self.token_window = [(t, tok) for t, tok in self.token_window if t > now - 60.0]

        available = self.available_tokens_now(tokens_per_minute)
        if available >= needed_tokens:
            return 0.0

        needed_extra = needed_tokens - available
        accumulated = 0
        for t, tok in sorted(self.token_window):
            accumulated += tok
            if accumulated >= needed_extra:
                wait = (t + 60.0) - now
                return max(0.0, wait)
        return 60.0

    def record_usage(self, token_count: int, model: str):
        now = time.time()
        self.token_window.append((now, token_count))
        self.last_used_at = now
        self.requests_today[model] = self.requests_today.get(model, 0) + 1

    def reset_daily(self):
        self.requests_today = {}
        if self.status == KeyStatus.EXHAUSTED:
            self.status = KeyStatus.HEALTHY
            print(f"[KEY {self.index}] 🔄 Daily reset — back to HEALTHY")


def validate_key(index: int, api_key: str) -> KeyStatus:
    try:
        client = genai.Client(api_key=api_key)
        client.models.count_tokens(
            model="gemini-2.5-flash",
            contents="ping"
        )
        return KeyStatus.HEALTHY
    except Exception as e:
        err = str(e).lower()
        if "api_key_invalid" in err or "invalid" in err or "400" in err:
            return KeyStatus.INVALID
        if "quota" in err or "429" in err or "exhausted" in err:
            return KeyStatus.EXHAUSTED
        return KeyStatus.HEALTHY


def build_key_pool(api_keys: list) -> list:
    print(f"[STARTUP] Checking {len(api_keys)} keys...")
    pool = []
    healthy = exhausted = invalid = 0

    for i, key in enumerate(api_keys):
        status = validate_key(i + 1, key)
        state = KeyState(index=i + 1, api_key=key, status=status)
        pool.append(state)

        if status == KeyStatus.HEALTHY:
            healthy += 1
            print(f"[KEY {i+1}] ✅ Healthy")
        elif status == KeyStatus.EXHAUSTED:
            exhausted += 1
            print(f"[KEY {i+1}] ⚠️  Exhausted — will reset at midnight PT")
        elif status == KeyStatus.INVALID:
            invalid += 1
            print(f"[KEY {i+1}] ❌ Invalid — removed from pool")

    print(f"[STARTUP] Pool ready: {healthy} healthy, {exhausted} exhausted, {invalid} invalid")
    return pool