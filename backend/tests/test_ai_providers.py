"""Provider layer: env-based selection, OpenAI-compatible request format, retries, no key leaks."""
import io
import json
import unittest
import urllib.error
from unittest import mock

from engine.ai import MockProvider, OpenAICompatibleProvider, ProviderError, ProviderRequest, provider_from_env
from engine.ai.providers import GEMINI_BASE_URL

REQ = ProviderRequest([{"role": "user", "content": "hi"}], ("E001-W00000-03000",))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def ok(content='{"judgments": []}'):
    return FakeResponse(json.dumps({"model": "m", "choices": [{"message": {"content": content}}], "usage": {"total_tokens": 5}}).encode())


def http_error(code, headers=None):
    return urllib.error.HTTPError("u", code, "err", headers or {}, io.BytesIO(b"{}"))


class FactoryTests(unittest.TestCase):
    def test_default_is_mock(self):
        self.assertIsInstance(provider_from_env(env={}), MockProvider)

    def test_gemini_preset_and_key_required(self):
        p = provider_from_env(env={"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "k", "LLM_MODEL": "some-flash"})
        self.assertEqual((p.name, p.base_url, p.model), ("gemini", GEMINI_BASE_URL, "some-flash"))
        with self.assertRaises(ProviderError):
            provider_from_env(env={"LLM_PROVIDER": "gemini", "LLM_MODEL": "x"})
        with self.assertRaises(ProviderError):
            provider_from_env(env={"LLM_PROVIDER": "nope"})

    def test_model_required(self):
        with self.assertRaises(ProviderError):
            provider_from_env(env={"LLM_PROVIDER": "gemini", "LLM_API_KEY": "k"})


class OpenAICompatibleTests(unittest.TestCase):
    def make(self, **kw):
        return OpenAICompatibleProvider(GEMINI_BASE_URL, "some-flash", "SECRET-KEY", sleep=lambda s: None, **kw)

    def test_request_format(self):
        with mock.patch("urllib.request.urlopen", return_value=ok()) as urlopen:
            out = self.make().complete(REQ)
        req = urlopen.call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(req.full_url, GEMINI_BASE_URL + "chat/completions")
        self.assertEqual(req.get_header("Authorization"), "Bearer SECRET-KEY")
        self.assertEqual((body["model"], body["temperature"], body["response_format"]), ("some-flash", 0, {"type": "json_object"}))
        self.assertEqual((out.text, out.usage), ('{"judgments": []}', {"total_tokens": 5}))

    def test_retries_on_rate_limit_then_succeeds(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(429), http_error(503), ok()]):
            p = self.make()
            self.assertEqual(p.complete(REQ).text, '{"judgments": []}')
            self.assertEqual(p.calls, 3)

    def test_gives_up_without_leaking_the_key(self):
        with mock.patch("urllib.request.urlopen", side_effect=http_error(429)):
            with self.assertRaises(ProviderError) as ctx:
                self.make(max_retries=2).complete(REQ)
        self.assertNotIn("SECRET-KEY", str(ctx.exception))

    def test_drops_json_mode_if_model_rejects_it(self):
        with mock.patch("urllib.request.urlopen", side_effect=[http_error(400), ok()]) as urlopen:
            self.make().complete(REQ)
        self.assertNotIn("response_format", json.loads(urlopen.call_args[0][0].data))

    def test_list_models(self):
        payload = FakeResponse(json.dumps({"data": [{"id": "models/b"}, {"id": "models/a"}]}).encode())
        with mock.patch("urllib.request.urlopen", return_value=payload):
            self.assertEqual(self.make().list_models(), ["models/a", "models/b"])
