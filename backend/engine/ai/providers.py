"""AI providers behind one small interface.

    MockProvider              deterministic fake answers: tests and offline runs (verdicts are NOT meaningful)
    OpenAICompatibleProvider  any /chat/completions API: Gemini, Groq, OpenRouter, local Ollama

Switching model or vendor is configuration, not code:
    LLM_PROVIDER=gemini | openai_compatible | mock
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY (or GEMINI_API_KEY), LLM_MIN_INTERVAL_S, LLM_TIMEOUT_S, LLM_REASONING_EFFORT

Uses only the standard library (urllib), so no extra dependency. The API key is read
from the environment, sent only in the Authorization header, and never logged or saved.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Protocol

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderRequest:
    messages: list[dict]                    # [{"role": "system"|"user", "content": str}]
    candidate_ids: tuple[str, ...] = ()     # used only by MockProvider


@dataclass(frozen=True)
class ProviderResponse:
    text: str                               # raw model output, exactly as returned
    model: str
    usage: dict = field(default_factory=dict)


class Provider(Protocol):
    name: str
    model: str

    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


class MockProvider:
    """Deterministic stand-in. Scores are derived from a hash of the candidate ID, so
    they are stable but carry no judgement. Never use mock output as real results."""

    name, model = "mock", "mock-1"

    def __init__(self):
        self.calls = 0

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        judgments = []
        for cid in request.candidate_ids:
            h = hashlib.sha256(cid.encode()).digest()
            hook, cliff, alone = 3 + h[0] % 7, 3 + h[1] % 7, 3 + h[2] % 7
            verdict = "post" if hook + cliff >= 14 else "maybe" if hook + cliff >= 10 else "skip"
            judgments.append({
                "candidate_id": cid, "hook_score": hook, "cliffhanger_score": cliff, "standalone_score": alone,
                "verdict": verdict, "hook": "[mock] opening moment", "cliffhanger": "[mock] unresolved ending",
                "why": "[mock] placeholder judgement, not a real assessment",
                "suggested_start_block_id": None, "suggested_end_block_id": None,
            })
        return ProviderResponse(json.dumps({"judgments": judgments}), self.model)


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, model: str, api_key: Optional[str], *, name: str = "openai_compatible",
                 timeout_s: float = 120.0, max_retries: int = 4, min_interval_s: float = 0.0,
                 json_mode: bool = True, reasoning_effort: Optional[str] = None, sleep=time.sleep):
        if not model:
            raise ProviderError("LLM_MODEL is not set. Run with --list-models to see what your key can use.")
        self.base_url = base_url.rstrip("/") + "/"
        self.model, self.name = model, name
        self._key = api_key
        self.timeout_s, self.max_retries, self.min_interval_s = timeout_s, max_retries, min_interval_s
        self.json_mode, self.reasoning_effort = json_mode, reasoning_effort
        self._sleep, self._last_call = sleep, 0.0
        self.calls = 0

    # ---- HTTP -------------------------------------------------------------
    def _http(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _pace(self) -> None:
        wait = self.min_interval_s - (time.monotonic() - self._last_call)
        if self._last_call and wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def list_models(self) -> list[str]:
        try:
            data = self._http("GET", "models")
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"Listing models failed: HTTP {exc.code}") from None
        return sorted(m.get("id", "") for m in data.get("data", []))

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        body = {"model": self.model, "messages": request.messages, "temperature": 0}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort

        attempt = 0
        while True:
            attempt += 1
            self._pace()
            self.calls += 1
            try:
                data = self._http("POST", "chat/completions", body)
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 400 and "response_format" in body:
                    body.pop("response_format")          # some models reject JSON mode: retry once without it
                    continue
                if exc.code in RETRYABLE_STATUS and attempt <= self.max_retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    self._sleep(float(retry_after) if retry_after and retry_after.isdigit() else min(60.0, 5.0 * 2 ** (attempt - 1)))
                    continue
                raise ProviderError(f"{self.name} returned HTTP {exc.code} after {attempt} attempt(s)") from None
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt <= self.max_retries:
                    self._sleep(min(60.0, 5.0 * 2 ** (attempt - 1)))
                    continue
                raise ProviderError(f"{self.name} unreachable: {getattr(exc, 'reason', exc)}") from None

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ProviderError(f"{self.name} returned no message content") from None
        return ProviderResponse(text, data.get("model", self.model), data.get("usage") or {})


def provider_from_env(override_name: Optional[str] = None, override_model: Optional[str] = None, env=os.environ):
    name = (override_name or env.get("LLM_PROVIDER") or "mock").strip().lower()
    if name == "mock":
        return MockProvider()
    if name not in ("gemini", "openai_compatible"):
        raise ProviderError(f"Unknown LLM_PROVIDER {name!r}; use gemini, openai_compatible or mock")
    base_url = env.get("LLM_BASE_URL") or (GEMINI_BASE_URL if name == "gemini" else "")
    if not base_url:
        raise ProviderError("LLM_BASE_URL is required for openai_compatible")
    key = env.get("LLM_API_KEY") or (env.get("GEMINI_API_KEY") if name == "gemini" else None)
    if name == "gemini" and not key:
        raise ProviderError("Set LLM_API_KEY (or GEMINI_API_KEY) in .env to use Gemini")
    return OpenAICompatibleProvider(
        base_url, override_model or env.get("LLM_MODEL", ""), key, name=name,
        timeout_s=float(env.get("LLM_TIMEOUT_S", "120")),
        min_interval_s=float(env.get("LLM_MIN_INTERVAL_S", "6.5")),
        reasoning_effort=env.get("LLM_REASONING_EFFORT") or None,
    )
