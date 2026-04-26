# gemini-flux 🔥

> Smart Gemini API key manager. Give it N keys. It handles the rest.

**Author:** Muhammad Ali — malikasana2810@gmail.com

[![PyPI version](https://badge.fury.io/py/gemini-flux.svg)](https://pypi.org/project/gemini-flux/)
[![GitHub](https://img.shields.io/badge/GitHub-gemini--flux-blue)](https://github.com/malikasana/gemini-flux)

---

## Is this for you?

You're hitting `429 RESOURCE_EXHAUSTED` on Gemini's free tier. You've noticed that creating multiple API keys in the same Google Cloud project doesn't help (because rate limits are per-*project*, not per-key). You don't want to pay yet. You want your request-heavy app to just keep running.

**gemini-flux is for you.** Give it 8 keys from 8 projects and it squeezes ~10,000 free requests/day out of Gemini with zero manual babysitting.

---

## Install

```bash
pip install gemini-flux
```

## 30-second example

```python
from gemini_flux import GeminiFlux

flux = GeminiFlux(keys=["key1", "key2", "key3", "key4", "key5", "key6", "key7", "key8"])

response = flux.generate("Translate this transcript to Spanish...")
print(response["response"])
```

That's it. gemini-flux picks the right key, the right model, waits exactly as long as it has to, and falls back through models when one runs out for the day.

---

## Loading keys from .env (recommended)

Hardcoding keys is fine for testing but not for real use. The recommended way is a `.env` file:

```env
GEMINI_KEY_1=AIza...
GEMINI_KEY_2=AIza...
GEMINI_KEY_3=AIza...
GEMINI_KEY_4=AIza...
GEMINI_KEY_5=AIza...
GEMINI_KEY_6=AIza...
GEMINI_KEY_7=AIza...
GEMINI_KEY_8=AIza...
GEMINI_MODE=both
GEMINI_LOG=true
```

Then load them in code:

```python
import os
from dotenv import load_dotenv
from gemini_flux import GeminiFlux

load_dotenv()

keys = []
i = 1
while True:
    key = os.environ.get(f"GEMINI_KEY_{i}")
    if not key:
        break
    keys.append(key)
    i += 1

flux = GeminiFlux(
    keys=keys,
    mode=os.environ.get("GEMINI_MODE", "both"),
    log=os.environ.get("GEMINI_LOG", "true").lower() == "true"
)

response = flux.generate("your prompt here")
print(response["response"])
```

Copy `.env.example` from the repo as your starting template — it has the right format with instructions.

---

## Who this is built for

- Translation and dubbing pipelines
- Long-running batch jobs over large documents
- RAG systems with high request volume
- Any app that burns through Gemini quota faster than the free tier allows
- Anyone stuck in "can't justify paying yet, but the free tier keeps dying" purgatory

---

## The problem Google doesn't tell you about

Gemini rate limits are **per Google Cloud project, not per API key.** Ten keys in one project = one quota, shared. Useless.

The fix: create multiple projects. Each Google account gets up to 10. Each project has its own independent quota. Two accounts with a few projects each gets you 8 independent rate limits without touching a credit card.

With 8 keys on the free tier:

| Model | RPD per key | × 8 keys | Daily total |
|---|---|---|---|
| gemini-2.5-pro | 100 | × 8 | 800 |
| gemini-2.5-flash | 250 | × 8 | 2,000 |
| gemini-2.5-flash-lite | 1,000 | × 8 | 8,000 |
| **Total** | | | **~10,800/day, free** |

Managing 8 keys manually is hell. That's what gemini-flux automates.

---

## How it schedules — the math

Naive rotators cycle keys on a fixed timer (e.g. "use the next key every 30 seconds"). That's wrong, because the real cooldown depends on how many tokens you sent.

Gemini's free tier allows **250,000 tokens per minute (TPM) per project.** So:

```
cooldown = token_count / 250,000

1M tokens    → 4 min cooldown
500k tokens  → 2 min cooldown
100k tokens  → 24 sec cooldown
10k tokens   → 2.4 sec cooldown
```

With N keys rotating:

```
interval_between_requests = cooldown / N

1M token request, 8 keys  → 30 sec between requests
10k token request, 8 keys → 0.3 sec — nearly instant
```

gemini-flux counts tokens using Google's **free** `count_tokens` endpoint (zero quota cost) before every request, maintains a 60-second sliding window per key, and sends via whichever key has capacity *right now*. No fixed timers. No wasted seconds.

---

## What you get out of the box

**Token-aware scheduling** — Every request routed to the key with real-time capacity. If none are ready, waits precisely as long as needed, not a second more.

**Model exhaustion chain** — When a key hits its daily cap on one model, gemini-flux falls through to the next:

```
1. gemini-2.5-pro                → 100 RPD per key
2. gemini-2.5-flash              → 250 RPD per key ← main workhorse
3. gemini-2.5-flash-lite         → 1000 RPD per key
4. gemini-3.1-pro-preview        → newest pro generation
5. gemini-3-flash-preview        → newest flash generation
6. gemini-3.1-flash-lite-preview → newest lite generation
```

You don't lose the key, just that model on that key, until midnight PT reset.

**Self-updating policy** — On startup, gemini-flux asks Gemini what the current free-tier limits are and caches them for 7 days. When Google changes limits (they do, without warning), gemini-flux catches it.

**Key health report on startup** — Invalid keys removed. Exhausted keys flagged. You know the state of your pool before you send a single request.

**Automatic daily reset** — Exhausted keys come back online at midnight Pacific without any manual intervention.

---

## Setup in 3 steps

**1. Create projects.** Go to [console.cloud.google.com](https://console.cloud.google.com) and create up to 10 projects. Each gets independent quota. Use a second Google account to get more.

**2. Get one API key per project.** APIs & Services → Credentials → Create Credentials → API Key.

**3. Drop them in `.env`:**

```env
GEMINI_KEY_1=AIza...
GEMINI_KEY_2=AIza...
# ... up to as many as you want
GEMINI_MODE=both
GEMINI_LOG=true
```

---

## Full usage

```python
response = flux.generate(
    prompt="Translate this transcript to Urdu with natural dubbing tone...",
    images=["base64_image..."],
    files=["base64_pdf..."],
    mode="flash_only",
    preferred_key=3,
    max_tokens=2000,
    temperature=0.5,
    retry=True
)
```

Every response includes:

```python
{
    "response": "Gemini's reply...",
    "key_used": 3,
    "model_used": "gemini-2.5-flash",
    "tokens_used": 45231,
    "wait_applied": 1.8,
    "retried": False
}
```

### Runtime controls

```python
flux.set_mode("flash_only")    # change mode anytime
flux.disable_key(3)            # disable key #3
flux.enable_key(3)             # re-enable key #3
flux.refresh_policy()          # force re-fetch Gemini policy
flux.status()                  # full key pool status
```

### Modes

| Mode | Description |
|---|---|
| `both` | Full exhaustion chain, pro → lite (default) |
| `pro_only` | Only Pro models |
| `flash_only` | Only Flash models |
| `flash_lite_only` | Only Flash-Lite models |

---

## Other ways to run it

### Git clone (development)

```bash
git clone https://github.com/malikasana/gemini-flux
cd gemini-flux
pip install -r requirements.txt
cp .env.example .env
```

```python
from gemini_flux import GeminiFlux
```

### Docker microservice

```bash
docker build -t gemini-flux .
docker run -p 8000:8000 --env-file .env gemini-flux
```

```python
from gemini_flux import GeminiFluxClient
client = GeminiFluxClient(base_url="http://localhost:8000")
response = client.generate("...")
```

### Kaggle notebook

```python
!pip install gemini-flux

import os
from gemini_flux import GeminiFlux

# paste keys directly or load from Kaggle secrets
keys = ["key1", "key2", ...]
flux = GeminiFlux(keys=keys)
response = flux.generate("your prompt here")
```

### HTTP API (when running as microservice)

| Endpoint | Method | Description |
|---|---|---|
| `/generate` | POST | Send prompt, get response |
| `/status` | GET | Key pool status and usage |
| `/refresh-policy` | POST | Force policy re-fetch |
| `/config` | POST | Change mode, enable/disable keys |
| `/health` | GET | Health check |

---

## What it looks like running

```
==================================================
  gemini-flux 🔥  Starting up with 8 keys
==================================================

[STARTUP] Checking 8 keys...
[KEY 1] ✅ Healthy
[KEY 2] ✅ Healthy
[KEY 3] ⚠️  Exhausted — resets at midnight PT
[KEY 4] ❌ Invalid — removed from pool
[STARTUP] Pool ready: 6 healthy, 1 exhausted, 1 invalid

[POLICY] Using cached policy (1.2 days old)
[STARTUP] Dynamic interval: 240s / 6 keys = 40.0s (worst case)
[STARTUP] ✅ gemini-flux ready! Mode: BOTH

[REQUEST] Incoming — 450,000 tokens detected
[SCHEDULER] Key #2 selected — sending via gemini-2.5-flash
[RESPONSE] ✅ Success via Key #2 (gemini-2.5-flash)
[KEY 2] gemini-2.5-flash: 1/250 requests used today
```

---

## Project structure

```
gemini-flux/
├── gemini_flux/
│   ├── __init__.py           # Package interface
│   ├── flux.py               # Main GeminiFlux class
│   ├── scheduler.py          # Token-aware sliding window brain
│   ├── key_pool.py           # Key validation and tracking
│   ├── policy.py             # Smart policy fetcher
│   └── client.py             # Lightweight HTTP client
├── service/
│   └── main.py               # FastAPI microservice
├── .env.example              # Environment template
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── test.py
└── README.md
```

---

## The backstory

I'm building a video dubbing application. Continuous transcript → LLM → translated transcript, chunk after chunk, video after video. Gemini free tier seemed perfect until I hit the 429 wall.

I created a second key in the same project. Same error. That's when I learned rate limits are per-project, not per-key. Made ten keys — still useless. Then I found the multi-project trick, built a naive rotator, realized *that* was also wrong because it ignored how many tokens I was actually sending.

So I wrote the math down. Then I wrote the code. Then I realized other people are going to hit this exact wall, and nobody should have to lose a weekend to it twice.

That's gemini-flux. Built out of frustration. Powered by math. Open-sourced so the next person doesn't have to rebuild it.

---

## Security

- Never commit your `.env` — it's in `.gitignore` by default
- Use `.env.example` as a template
- Every key validated on startup — invalid ones removed before any request is sent

---

## License

MIT. Use it, fork it, ship it.

---

## Author

**Muhammad Ali** — malikasana2810@gmail.com

*Built out of frustration with rate limits. Powered by math.*