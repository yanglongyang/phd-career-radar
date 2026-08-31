"""V0.2.4 Provider 安全：错误回显 scrub、endpoint 合规、Key 与 endpoint 绑定。"""

import sys

import pytest

from app.ai.provider import (
    OpenAICompatibleProvider,
    _http_error_message,
    get_provider,
)
from app.core.config import Settings
from app.core.secrets import save_secret, secret_path

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI 仅 Windows")


class _FakeResp:
    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    def json(self):
        import json

        if isinstance(self._body, str):
            return json.loads(self._body)
        return self._body


def test_http_error_scrubs_remote_body():
    """远端错误正文不回显：不得包含敏感内容/原始 body。"""
    msg = _http_error_message(
        _FakeResp(
            401,
            '{"error": {"type": "invalid_request_error",'
            ' "message": "Incorrect API key: sk-super-secret-abcdef123456"}}',
        )
    )
    assert "HTTP 401" in msg
    assert "invalid_request_error" in msg      # 受控 error.type 保留
    assert "sk-super-secret" not in msg        # body 里的敏感内容不回流
    assert "Incorrect API key" not in msg


def test_http_error_non_json_body_only_status():
    msg = _http_error_message(_FakeResp(500, "<html>Internal Server Error</html>"))
    assert msg == "AI 返回 HTTP 500"


def test_http_error_request_id_sanitized():
    ok = _http_error_message(_FakeResp(429, '{"error":{"type":"rate_limit"}}',
                                       {"x-request-id": "req_abc123"}))
    assert "req_abc123" in ok
    bad = _http_error_message(_FakeResp(429, "", {"x-request-id": "<script>alert(1)</script>"}))
    assert "<script>" not in bad


# ---------- get_provider：URL 合规 + endpoint 绑定 ----------

def _settings(key="sk-x", base_url="https://api.example.com/v1", model="m"):
    return Settings(llm_api_key=key, llm_base_url=base_url, llm_model=model, _env_file=None)


def test_get_provider_rejects_insecure_http_url():
    s = _settings(base_url="http://evil.example/v1")
    assert get_provider(s) is None


def test_get_provider_rejects_userinfo_url():
    s = _settings(base_url="https://user:pass@api.example.com/v1")
    assert get_provider(s) is None


def test_get_provider_allows_local_http():
    s = _settings(base_url="http://127.0.0.1:11434")
    # 无密钥文件 → 无绑定校验，直接放行
    assert isinstance(get_provider(s), OpenAICompatibleProvider)


def test_get_provider_not_configured():
    assert get_provider(Settings(_env_file=None)) is None


@win32_only
def test_get_provider_binding_mismatch_blocks_key(monkeypatch, tmp_path):
    """密钥绑定 endpoint A，当前 .env 指向 B → 拒绝发送 Key（返回 None）。"""
    import app.core.secrets as secrets_mod

    path = secret_path(tmp_path)
    save_secret({"api_key": "sk-bound", "base_url": "https://api.a.com/v1"}, path)
    monkeypatch.setattr(secrets_mod, "secret_path", lambda _dir: path)
    s = _settings(key="sk-bound", base_url="https://api.b.com/v1")  # 被改成 B
    assert get_provider(s) is None


@win32_only
def test_get_provider_binding_match_allows(monkeypatch, tmp_path):
    """绑定一致（含尾斜杠差异）→ 正常放行。"""
    import app.core.secrets as secrets_mod

    path = secret_path(tmp_path)
    save_secret({"api_key": "sk-bound", "base_url": "https://api.a.com/v1"}, path)
    monkeypatch.setattr(secrets_mod, "secret_path", lambda _dir: path)
    s = _settings(key="sk-bound", base_url="https://api.a.com/v1/")  # 尾斜杠
    assert isinstance(get_provider(s), OpenAICompatibleProvider)


@win32_only
def test_get_provider_v1_unbound_secret_blocks(monkeypatch, tmp_path):
    """旧格式密钥（无绑定信息）→ 保守拒绝，要求重新确认。"""
    import app.core.secrets as secrets_mod
    from app.core.secrets import MAGIC_V1, protect_bytes

    path = secret_path(tmp_path)
    path.write_bytes(MAGIC_V1 + protect_bytes(b"sk-legacy"))
    monkeypatch.setattr(secrets_mod, "secret_path", lambda _dir: path)
    s = _settings(key="sk-legacy", base_url="https://api.a.com/v1")
    assert get_provider(s) is None
