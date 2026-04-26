"""
gemini-flux — Quick Test
Reads keys from .env file automatically.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_flux import GeminiFlux

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
    print("❌ No keys found! Please fill your .env file first.")
    print("   Copy .env.example → .env and add your keys.")
    sys.exit(1)

print(f"✅ Loaded {len(keys)} keys from .env\n")

flux = GeminiFlux(
    keys=keys,
    mode=os.environ.get("GEMINI_MODE", "both"),
    log=os.environ.get("GEMINI_LOG", "true").lower() == "true"
)

print("\n--- Sending test request ---\n")
response = flux.generate("Say hello in 5 different languages. Keep it short.")

print("\n--- Response ---")
print(response["response"])
print(f"\nKey used: #{response['key_used']}")
print(f"Model: {response['model_used']}")
print(f"Tokens: {response['tokens_used']:,}")
print(f"Wait applied: {response['wait_applied']}s")