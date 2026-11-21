"""Probe LLM_BASE_URL and print which API it speaks: "anthropic" or "openai".

Sends a 1-token request to each format, using the same URLs LiteLLM will use.
Anthropic is tried first: when an endpoint speaks both, passing calls through
beats translating them. Exits non-zero if neither works.
"""
import json
import os
import sys
import urllib.error
import urllib.request

base = os.environ["LLM_BASE_URL"].rstrip("/")
root = base[:-3] if base.endswith("/v1") else base
key = os.environ["LLM_API_KEY"]
model = os.environ["MODEL_NAME"]
ping = [{"role": "user", "content": "ping"}]

PROBES = [
    ("anthropic", f"{root}/v1/messages",
     {"x-api-key": key, "Authorization": f"Bearer {key}", "anthropic-version": "2023-06-01"}),
    ("openai", f"{base}/chat/completions",
     {"Authorization": f"Bearer {key}"}),
]


def status(url: str, headers: dict) -> str:
    body = json.dumps({"model": model, "max_tokens": 1, "messages": ping}).encode()
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return str(r.status)
    except urllib.error.HTTPError as e:
        return str(e.code)
    except Exception as e:  # DNS, TLS, timeout: report it, do not crash the probe
        return type(e).__name__


results = []
for fmt, url, headers in PROBES:
    code = status(url, headers)
    print(f"probe {fmt}: POST {url} -> {code}", file=sys.stderr)
    if code.startswith("2"):
        print(fmt)
        sys.exit(0)
    results.append(f"{fmt}={code}")

print(f"endpoint answered neither API format ({', '.join(results)}); "
      "check LLM_BASE_URL, LLM_API_KEY and MODEL_NAME", file=sys.stderr)
sys.exit(1)
