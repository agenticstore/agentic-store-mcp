import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from mitmproxy.test import tflow
from starlette.testclient import TestClient as ProxyClient

from agentic_store_mcp.firewall import proxy, tls_proxy, rules
from agentic_store_mcp.firewall.sanitizers.deterministic import sanitize
from agentic_store_mcp.webapp import app as webapp


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(rules, "CONFIG_FILE", tmp_path / "firewall.json")
    monkeypatch.setattr(proxy, "log_event", lambda *a, **kw: None)
    monkeypatch.setattr(tls_proxy, "log_event", lambda *a, **kw: None)


@pytest.mark.parametrize(
    "body",
    [
        {
            "system": "Contact a@example.com",
            "messages": [{"role": "user", "content": "Call b@example.com"}],
        },
        {"instructions": "Email a@example.com", "input": "Email b@example.com"},
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "a@example.com"},
                        {
                            "type": "input_image",
                            "image_url": "data:image/png;base64,AAAA",
                        },
                    ],
                },
                {
                    "type": "function_call_output",
                    "call_id": "keep",
                    "output": "b@example.com",
                },
                {
                    "type": "function_call",
                    "call_id": "keep",
                    "arguments": '{"email":"c@example.com"}',
                },
            ]
        },
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "keep",
                            "name": "lookup",
                            "input": {"email": "a@example.com"},
                        }
                    ],
                }
            ]
        },
    ],
)
def test_field_redaction_both_transports(body):
    original = json.dumps(body)
    redacted, findings, safe = asyncio.run(proxy._sanitize(body, rules.DEFAULT_CONFIG))
    assert findings and safe
    assert "@example.com" not in json.dumps(redacted)
    assert json.dumps(body) == original
    flow = tflow.tflow()
    flow.request.host = "api.openai.com"
    flow.request.path = "/v1/responses"
    flow.request.content = original.encode()
    asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
    assert json.loads(flow.request.content) == redacted
    if "input" in redacted and isinstance(redacted["input"], list):
        assert (
            redacted["input"][0]["content"][1]["image_url"]
            == "data:image/png;base64,AAAA"
        )
        assert (
            json.loads(redacted["input"][2]["arguments"])["email"] == "[REDACTED_EMAIL]"
        )


def test_literal_replacement_no_rescan():
    replacement = r"private@example.com\1"
    out, findings = sanitize("a@example.com 10.1.2.3", {"redaction_text": replacement})
    assert out == replacement + " " + replacement
    assert len(findings) == 2


def test_settings_roundtrip_and_validation():
    client = TestClient(webapp.app)
    assert (
        client.post(
            "/api/firewall/config", json={"redaction_text": "[PRIVATE]"}
        ).status_code
        == 200
    )
    assert client.get("/api/firewall/config").json()["redaction_text"] == "[PRIVATE]"
    assert (
        client.post(
            "/api/firewall/config", json={"redaction_text": "a" * 201}
        ).status_code
        == 422
    )
    client.post("/api/firewall/config", json={"redaction_text": None})
    assert client.get("/api/firewall/config").json()["redaction_text"] is None


def test_block_before_upstream():
    rules.save_config({**rules.DEFAULT_CONFIG, "mode": "block"})
    with patch.object(
        proxy.httpx, "AsyncClient", side_effect=AssertionError("must not forward")
    ):
        response = ProxyClient(proxy._proxy_app).post(
            "/v1/responses", json={"input": "a@example.com"}
        )
    assert response.status_code == 400
    flow = tflow.tflow()
    flow.request.host = "api.openai.com"
    flow.request.content = b'{"input":"a@example.com"}'
    asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
    assert flow.response.status_code == 400


@pytest.mark.parametrize(
    "path", ["/v1/responses", "/openai/v1/responses", "/openai/v1/chat/completions"]
)
def test_routes_and_streaming(path):
    real_client = httpx.AsyncClient
    captured = []

    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"data: first\n\n"
            yield b"data: [DONE]\n\n"

    async def upstream(request):
        captured.append(request)
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=Chunks()
        )

    def client(**kwargs):
        return real_client(transport=httpx.MockTransport(upstream), **kwargs)

    with patch.object(proxy.httpx, "AsyncClient", client):
        response = ProxyClient(proxy._proxy_app).post(
            path, json={"input": "a@example.com", "stream": True}
        )
    assert response.status_code == 200
    assert response.content.endswith(b"data: [DONE]\n\n")
    assert captured[0].url.host == "api.openai.com"
    assert captured[0].url.path in ("/v1/responses", "/v1/chat/completions")
    assert json.loads(captured[0].content)["input"] == "[REDACTED_EMAIL]"


def test_sdk_connect_preserves_claude(tmp_path):
    with (
        patch("pathlib.Path.home", return_value=tmp_path),
        patch("subprocess.run") as run,
    ):
        run.return_value.returncode = 0
        client = TestClient(webapp.app)
        client.post("/api/firewall/client/connect", json={"client": "claude_code"})
        run.reset_mock()
        response = client.post(
            "/api/firewall/client/connect", json={"client": "openai_sdk"}
        )
        assert response.json()["vars"] == {
            "OPENAI_BASE_URL": "http://127.0.0.1:8766/openai/v1"
        }
        assert run.call_count == 1
        content = (tmp_path / ".zshrc").read_text()
        assert (
            "export ANTHROPIC_BASE_URL=" in content
            and "export OPENAI_BASE_URL=" in content
        )
        client.post("/api/firewall/client/disconnect", json={"client": "openai_sdk"})
        content = (tmp_path / ".zshrc").read_text()
        assert (
            "export ANTHROPIC_BASE_URL=" in content and "OPENAI_BASE_URL" not in content
        )
        assert (
            client.post(
                "/api/firewall/client/connect", json={"client": "unknown"}
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "path", ["/v1/responses", "/openai/v1/responses", "/openai/v1/chat/completions"]
)
def test_tls_local_routes(path):
    flow = tflow.tflow()
    flow.request.host = "127.0.0.1"
    flow.request.path = path
    flow.request.content = b'{"input":"a@example.com"}'
    asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
    assert flow.request.host == "api.openai.com"
    assert flow.request.path in ("/v1/responses", "/v1/chat/completions")
    assert b"@example.com" not in flow.request.content


def test_reviewer_unavailable_blocks_both():
    config = {
        **rules.DEFAULT_CONFIG,
        "mode": "block",
        "llm": {"enabled": True, "model": "local"},
    }
    rules.save_config(config)

    async def unavailable():
        return False

    with patch.object(proxy, "is_ollama_running", unavailable):
        response = ProxyClient(proxy._proxy_app).post(
            "/v1/responses", json={"input": "Hello"}
        )
        assert response.status_code == 400
        flow = tflow.tflow()
        flow.request.host = "api.openai.com"
        flow.request.content = b'{"input":"Hello"}'
        asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
        assert flow.response.status_code == 400


@pytest.mark.parametrize("content", [b"[]", b"not-json"])
def test_malformed_requests_rejected(content):
    response = ProxyClient(proxy._proxy_app).post("/v1/responses", content=content)
    assert response.status_code == 400
    flow = tflow.tflow()
    flow.request.host = "api.openai.com"
    flow.request.content = content
    asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
    assert flow.response.status_code == 400


def test_codex_subscription_http_recording():
    rules.save_config({**rules.DEFAULT_CONFIG, "recording": True})
    flow = tflow.tflow()
    flow.request.host = "chatgpt.com"
    flow.request.path = "/backend-api/codex/responses"
    flow.request.content = b'{"model":"gpt-test","input":"a@example.com"}'
    with patch("agentic_store_mcp.firewall.recorder.record_prompt") as record:
        asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
        assert b"a@example.com" not in flow.request.content
        assert record.call_args.kwargs["prompt_text"] == "[REDACTED_EMAIL]"
        assert record.call_args.kwargs["recording_content"] == "sanitized"
    flow.request.path = "/backend-api/accounts"
    flow.request.content = b"not-json"
    asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
    assert flow.request.content == b"not-json"


@pytest.mark.parametrize("mode", ["redact", "block"])
def test_codex_websocket(mode):
    from mitmproxy import websocket
    from wsproto.frame_protocol import Opcode

    rules.save_config({**rules.DEFAULT_CONFIG, "mode": mode, "recording": True})
    flow = tflow.tflow()
    flow.request.host = "chatgpt.com"
    flow.request.path = "/backend-api/codex/responses"
    flow.websocket = websocket.WebSocketData()
    message = websocket.WebSocketMessage(
        Opcode.TEXT,
        True,
        b'{"type":"response.create","response":{"model":"gpt-test","input":"a@example.com"}}',
    )
    flow.websocket.messages.append(message)
    with patch("agentic_store_mcp.firewall.recorder.record_prompt") as record:
        asyncio.run(tls_proxy._PromptFirewallAddon().websocket_message(flow))
        if mode == "block":
            assert not record.called
        else:
            assert record.call_args.kwargs["prompt_text"] == "[REDACTED_EMAIL]"
    assert message.dropped == (mode == "block")
    if mode == "redact":
        assert b"a@example.com" not in message.content
    incoming = websocket.WebSocketMessage(Opcode.TEXT, False, b"unchanged")
    flow.websocket.messages.append(incoming)
    asyncio.run(tls_proxy._PromptFirewallAddon().websocket_message(flow))
    assert incoming.content == b"unchanged"


def test_recording_can_opt_into_pre_sanitized_prompt():
    rules.save_config(
        {**rules.DEFAULT_CONFIG, "recording": True, "recording_content": "pre_sanitized"}
    )
    flow = tflow.tflow()
    flow.request.host = "chatgpt.com"
    flow.request.path = "/backend-api/codex/responses"
    flow.request.content = b'{"model":"gpt-test","input":"a@example.com"}'
    with patch("agentic_store_mcp.firewall.recorder.record_prompt") as record:
        asyncio.run(tls_proxy._PromptFirewallAddon().request(flow))
        assert record.call_args.kwargs["prompt_text"] == "a@example.com"
        assert record.call_args.kwargs["recording_content"] == "pre_sanitized"


def test_codex_connect_requires_tls():
    with patch(
        "agentic_store_mcp.firewall.tls_proxy.is_tls_proxy_running", return_value=False
    ):
        response = TestClient(webapp.app).post(
            "/api/firewall/client/connect", json={"client": "codex"}
        )
    assert response.status_code == 409


def test_audit_originals_and_filters(tmp_path, monkeypatch):
    from agentic_store_mcp.firewall import audit

    monkeypatch.setattr(audit, "AUDIT_FILE", tmp_path / "audit.jsonl")
    finding = {
        "type": "pii",
        "original": "<secret@example.com>",
        "replacement": "[PRIVATE]",
    }
    audit.log_event("blocked", "Blocked", [finding], safe=False)
    audit.log_event("redacted", "Sanitized", [finding])
    audit.log_event("upstream_error", "Unavailable", safe=False)
    audit.log_event("clean", "Clean")
    assert all("original" not in f for e in audit.read_logs() for f in e["findings"])
    errors = audit.read_logs(event_filter="errors", show_originals=True)
    assert [e["event"] for e in errors] == ["upstream_error", "blocked"]
    assert errors[1]["findings"][0]["original"] == "<secret@example.com>"
    client = TestClient(webapp.app)
    response = client.get(
        "/api/firewall/logs?event_filter=sanitized&show_originals=true"
    )
    assert response.status_code == 200
    assert (
        response.json()["entries"][0]["findings"][0]["original"]
        == "<secret@example.com>"
    )
    assert (
        "original"
        not in client.get("/api/firewall/logs").json()["entries"][2]["findings"][0]
    )
    assert client.get("/api/firewall/logs?event_filter=unknown").status_code == 422
    audit.clear_logs()
    assert audit.read_logs(show_originals=True) == []


def test_block_response_does_not_disclose_original():
    rules.save_config({**rules.DEFAULT_CONFIG, "mode": "block"})
    response = ProxyClient(proxy._proxy_app).post(
        "/v1/responses", json={"input": "secret@example.com"}
    )
    assert response.status_code == 400
    assert "secret@example.com" not in response.text
    assert "original" not in response.text
