"""Pluggable LLM adapter. Uses the first configured key: XAI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY.
The model is only ever given data we fetched, and told to use nothing else. If no key is set,
callers fall back to rule-based narratives (clearly labeled)."""
import json, os, hashlib
from . import cache
from .config import TTL_LLM
from .http import client

SYSTEM = ("You are a careful equity research analyst. Use ONLY the JSON data provided. Never invent prices, "
          "financial figures, analyst targets, customers, products or news that are not in the data. If something is "
          "unknown, say it is unknown. Never guarantee outcomes; use probabilistic language. Plain English first. "
          "Return strictly valid JSON matching the requested keys.")


def provider():
    if os.getenv("XAI_API_KEY"):
        return {"name": "xAI", "model": os.getenv("XAI_MODEL", "grok-4-latest"), "kind": "openai",
                "base": "https://api.x.ai/v1", "key": os.getenv("XAI_API_KEY")}
    if os.getenv("OPENAI_API_KEY"):
        return {"name": "OpenAI", "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "kind": "openai",
                "base": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"), "key": os.getenv("OPENAI_API_KEY")}
    if os.getenv("ANTHROPIC_API_KEY"):
        return {"name": "Anthropic", "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"), "kind": "anthropic",
                "key": os.getenv("ANTHROPIC_API_KEY")}
    return None


def status():
    p = provider()
    return {"configured": bool(p), "provider": p and p["name"], "model": p and p["model"]}


async def complete_json(task: str, data: dict, keys: list[str]) -> dict | None:
    p = provider()
    if not p:
        return None
    payload = json.dumps(data, default=str)[:60000]
    prompt = f"{task}\n\nReturn a JSON object with keys: {', '.join(keys)}. Each value is a string (markdown allowed) or list of strings.\n\nDATA:\n{payload}"
    key = "llm:" + hashlib.sha1((p["model"] + prompt).encode()).hexdigest()

    async def fetch():
        if p["kind"] == "openai":
            r = await client().post(f"{p['base']}/chat/completions", timeout=90,
                                    headers={"Authorization": f"Bearer {p['key']}"},
                                    json={"model": p["model"], "temperature": 0.2, "response_format": {"type": "json_object"},
                                          "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"]
        else:
            r = await client().post("https://api.anthropic.com/v1/messages", timeout=90,
                                    headers={"x-api-key": p["key"], "anthropic-version": "2023-06-01"},
                                    json={"model": p["model"], "max_tokens": 2500, "system": SYSTEM,
                                          "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            txt = "".join(b.get("text", "") for b in r.json()["content"])
        s, e = txt.find("{"), txt.rfind("}")
        return json.loads(txt[s:e + 1])
    try:
        val, *_ = await cache.cached(key, TTL_LLM, fetch)
        return {"content": val, "provider": p["name"], "model": p["model"]}
    except Exception as ex:
        return {"error": str(ex)[:200], "provider": p["name"], "model": p["model"]}
