"""Natural-language spend insights, backed by a real LLM call.

Hard rule (same invariant as costing_engine.py): this module NEVER produces or
alters a cost figure. It only takes numbers the deterministic costing engine
already computed (handed in as `context` by the caller) and asks an LLM to
summarize/answer questions about them in plain English. The answer is
advisory commentary, not authoritative data -- callers must label it as such.

Uses a separate credential (`settings.anthropic_api_key`, a normal Messages
API key) from `settings.anthropic_admin_api_key` (the Admin/Usage-Cost API
key used by AnthropicConnector) -- different scope, different key.
"""

import json

import httpx

API_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-haiku-4-5"  # cheap/fast: this is a summarization task, not hard reasoning

SYSTEM_PROMPT = (
    "You are a spend-insights assistant for an internal AI-billing tool. "
    "You will be given a JSON object of already-computed, authoritative cost "
    "and budget figures, and a user's question about them. Answer using ONLY "
    "the numbers in that JSON -- never invent or estimate a figure that isn't "
    "there. If the JSON doesn't contain what's needed to answer, say so "
    "plainly instead of guessing. Keep answers short and concrete."
)


class InsightsUnavailableError(RuntimeError):
    pass


def ask(question: str, context: dict, api_key: str | None, client: httpx.Client | None = None) -> str:
    if not api_key:
        raise InsightsUnavailableError("ANTHROPIC_API_KEY not configured")

    http_client = client or httpx.Client(base_url=API_BASE_URL, timeout=30.0)
    resp = http_client.post(
        "/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        json={
            "model": MODEL,
            "max_tokens": 512,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Context:\n{json.dumps(context, default=str)}\n\nQuestion: {question}",
                }
            ],
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    return "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
