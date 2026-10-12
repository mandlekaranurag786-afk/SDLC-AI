import json
import os
import re
import time
from typing import Any

from openai import OpenAI, RateLimitError
from dotenv import load_dotenv


class LLMServiceError(RuntimeError):
    pass


load_dotenv()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        endpoint = os.getenv("OPENAI_ENDPOINT")
        if not api_key:
            raise LLMServiceError(
                "OPENAI_API_KEY is not configured. Add it to .env and restart."
            )
        _client = OpenAI(
            api_key=api_key,
            base_url=endpoint,
        )
    return _client


def call_llm(
    prompt: str,
    *,
    expect_json: bool = False,
    max_tokens: int = 2000,
    max_retries: int = 5,
) -> str | dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            print(f"[LLM] {model} | max_tokens={max_tokens} | prompt_len={len(prompt)}")
            response = _get_client().chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert SDLC requirements analyst. Follow output format instructions exactly.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            finish_reason = response.choices[0].finish_reason
            content = response.choices[0].message.content or ""
            content = content.strip()

            if finish_reason == "length":
                raise LLMServiceError(
                    f"Response truncated by max_tokens={max_tokens} before completion. "
                    "Increase max_tokens for this call rather than retrying."
                )

            return parse_json(content) if expect_json else content

        except RateLimitError as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            wait = 65 + (attempt * 20)
            print(f"[LLM] Rate limit hit. Waiting {wait}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait)

        except Exception as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            wait = 2 ** attempt
            print(f"[LLM] Error: {exc}. Retrying in {wait}s...")
            time.sleep(wait)

    raise LLMServiceError(
        f"LLM request failed after {max_retries} attempts: {last_error}"
    ) from last_error


def parse_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise LLMServiceError("LLM did not return valid JSON.")
        return json.loads(match.group(0))
