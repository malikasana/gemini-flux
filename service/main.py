"""
gemini-flux — FastAPI Microservice
Wraps GeminiFlux as an HTTP service.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from gemini_flux import GeminiFlux

app = FastAPI(
    title="gemini-flux",
    description="Smart Gemini API Key Manager",
    version="1.0.0"
)

# Read keys from .env (GEMINI_KEY_1, GEMINI_KEY_2 ... GEMINI_KEY_N)
keys = []
i = 1
while True:
    key = os.environ.get(f"GEMINI_KEY_{i}")
    if not key:
        break
    keys.append(key.strip())
    i += 1

if not keys:
    raise RuntimeError("No keys found! Add GEMINI_KEY_1, GEMINI_KEY_2... to your .env file.")

MODE = os.environ.get("GEMINI_MODE", "both")
LOG = os.environ.get("GEMINI_LOG", "true").lower() == "true"

flux = GeminiFlux(keys=keys, mode=MODE, log=LOG)


class GenerateRequest(BaseModel):
    prompt: str
    images: Optional[list] = []
    files: Optional[list] = []
    mode: Optional[str] = None
    preferred_key: Optional[int] = None
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7
    retry: Optional[bool] = True

class ConfigRequest(BaseModel):
    mode: Optional[str] = None
    disable_key: Optional[int] = None
    enable_key: Optional[int] = None


@app.post("/generate")
async def generate(req: GenerateRequest):
    result = flux.generate(
        prompt=req.prompt,
        images=req.images,
        files=req.files,
        mode=req.mode,
        preferred_key=req.preferred_key,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        retry=req.retry
    )
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@app.get("/status")
async def status():
    return flux.status()


@app.post("/refresh-policy")
async def refresh_policy():
    flux.refresh_policy()
    return {"message": "Policy refreshed", "policy": flux.policy}


@app.post("/config")
async def config(req: ConfigRequest):
    changes = []
    if req.mode:
        flux.set_mode(req.mode)
        changes.append(f"mode set to {req.mode}")
    if req.disable_key is not None:
        flux.disable_key(req.disable_key)
        changes.append(f"key #{req.disable_key} disabled")
    if req.enable_key is not None:
        flux.enable_key(req.enable_key)
        changes.append(f"key #{req.enable_key} enabled")
    return {"changes": changes}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gemini-flux"}