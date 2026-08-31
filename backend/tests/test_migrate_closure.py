"""V0.2.5 追加测试：迁移"旧加密 A + 新明文 B"覆盖分支。"""

import sys

import pytest

from app.core.secrets import load_secret, save_secret
from tests.test_launcher_gui import _load_launcher

# 注意：不复用 test_launcher_gui 的 win32_only（它带 CI 跳过 —— GUI 需要桌面）。
# 迁移测试只需要 Windows DPAPI，不碰 Tk 窗口，CI（windows runner）必须真实执行。
windows_dpapi_only = pytest.mark.skipif(
    sys.platform != "win32",
    reason="DPAPI 仅 Windows",
)

# launcher 的密钥文件路径：_DATA_ROOT/data/llm_secret.bin
SECRET_F = "data/llm_secret.bin"


def _migrate_with(monkeypatch, tmp_path, env_text: str, existing_payload=None):
    mod = _load_launcher()
    monkeypatch.setattr(mod, "_DATA_ROOT", tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text(env_text, encoding="utf-8")
    if existing_payload is not None:
        save_secret(existing_payload, tmp_path / SECRET_F)
    mod._migrate_plaintext_key(log_box=None)
    return env_path, tmp_path / SECRET_F


@windows_dpapi_only
def test_migrate_overwrites_different_existing_secret(monkeypatch, tmp_path):
    """P2 closure：加密文件是旧 Key A，.env 是新的 Key B →
    迁移后加密文件必须是 B（A 被覆盖），明文 B 被删除 —— B 不丢。"""
    env_path, secret_f = _migrate_with(
        monkeypatch, tmp_path,
        "LLM_BASE_URL=https://api.example.com/v1\nLLM_API_KEY=sk-new-key-b\n",
        existing_payload={"api_key": "sk-old-key-a", "base_url": "https://api.example.com/v1"},
    )
    env = env_path.read_text(encoding="utf-8")
    assert "sk-new-key-b" not in env            # 明文已删
    assert "LLM_API_KEY" not in env
    assert load_secret(secret_f) == {
        "api_key": "sk-new-key-b",              # 新 Key 被保留并加密
        "base_url": "https://api.example.com/v1",
    }


@windows_dpapi_only
def test_migrate_same_secret_just_deletes_plain(monkeypatch, tmp_path):
    """加密副本与明文是同一个 Key → 只删明文，加密文件不变。"""
    env_path, secret_f = _migrate_with(
        monkeypatch, tmp_path,
        "LLM_BASE_URL=https://api.example.com/v1\nLLM_API_KEY=sk-same-key\n",
        existing_payload={"api_key": "sk-same-key", "base_url": "https://old.example.com/v1"},
    )
    env = env_path.read_text(encoding="utf-8")
    assert "sk-same-key" not in env
    assert load_secret(secret_f) == {
        "api_key": "sk-same-key",
        "base_url": "https://old.example.com/v1",   # 加密文件原样保留
    }


@windows_dpapi_only
def test_migrate_existing_secret_write_failure_keeps_plain(monkeypatch, tmp_path):
    """已有加密文件但内容不同，覆盖写入失败 → 明文保留，旧加密文件不动。"""
    import app.core.secrets as secrets_mod

    mod = _load_launcher()
    monkeypatch.setattr(mod, "_DATA_ROOT", tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_API_KEY=sk-new-key-b\n", encoding="utf-8")
    save_secret({"api_key": "sk-old-key-a", "base_url": "https://api.example.com/v1"},
                tmp_path / SECRET_F)

    def boom(payload, path):
        raise OSError("磁盘满")

    monkeypatch.setattr(secrets_mod, "save_secret", boom)
    mod._migrate_plaintext_key()
    assert "sk-new-key-b" in env_path.read_text(encoding="utf-8")   # 明文仍在
    assert load_secret(tmp_path / SECRET_F)["api_key"] == "sk-old-key-a"  # 旧文件未动
