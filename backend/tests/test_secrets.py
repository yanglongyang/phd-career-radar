"""V0.2.3 API Key 安全存储：DPAPI 加密回环、文件读写、config 集成、launcher .env 工具。"""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT, Settings, _apply_llm_secret
from app.core.secrets import (
    delete_secret,
    load_secret,
    protect_bytes,
    save_secret,
    secret_path,
    unprotect_bytes,
)

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI 仅 Windows")


@win32_only
def test_dpapi_roundtrip():
    """加密 → 解密 得到原文；密文不等于明文。"""
    blob = protect_bytes("sk-test-1234567890".encode("utf-8"))
    assert blob != b"sk-test-1234567890"
    assert unprotect_bytes(blob) == b"sk-test-1234567890"


@win32_only
def test_save_load_roundtrip_no_plaintext_on_disk(tmp_path):
    path = secret_path(tmp_path)
    save_secret("sk-super-secret-abcdef", path)
    raw = path.read_bytes()
    assert b"sk-super-secret-abcdef" not in raw  # 磁盘上无明文
    assert raw.startswith(b"PCRSEC1\x00")
    assert load_secret(path) == "sk-super-secret-abcdef"


@win32_only
def test_load_secret_missing_or_corrupt(tmp_path):
    path = secret_path(tmp_path)
    assert load_secret(path) is None  # 文件不存在
    path.write_bytes(b"garbage-no-magic")
    assert load_secret(path) is None  # 格式不对
    path.write_bytes(b"PCRSEC1\x00too-short")
    assert load_secret(path) is None  # 只有 magic 无密文


@win32_only
def test_delete_secret(tmp_path):
    path = secret_path(tmp_path)
    save_secret("sk-x", path)
    delete_secret(path)
    assert not path.exists()
    assert load_secret(path) is None


def test_apply_llm_secret_prefers_env_key():
    """环境变量已有 key → 不读取密钥文件（环境变量优先级最高）。"""
    settings = Settings(llm_api_key="sk-from-env", _env_file=None)
    out = _apply_llm_secret(settings, secret_file=Path("does-not-matter"))
    assert out.llm_api_key == "sk-from-env"


@win32_only
def test_apply_llm_secret_loads_encrypted_file(tmp_path):
    """环境变量为空 + 密钥文件存在 → 自动解密填充（直接 uvicorn 启动也能用）。"""
    path = secret_path(tmp_path)
    save_secret("sk-file-secret", path)
    settings = Settings(llm_api_key="", _env_file=None)
    out = _apply_llm_secret(settings, secret_file=path)
    assert out.llm_api_key == "sk-file-secret"


@win32_only
def test_apply_llm_secret_missing_file_stays_unset(tmp_path):
    settings = Settings(llm_api_key="", _env_file=None)
    out = _apply_llm_secret(settings, secret_file=secret_path(tmp_path))
    assert out.llm_api_key == ""


# ---------- launcher 的 .env 读写工具 ----------

def _load_launcher() -> object:
    path = PROJECT_ROOT / "launcher" / "launcher.py"
    spec = importlib.util.spec_from_file_location("pcr_launcher_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_launcher_env_read_write(tmp_path):
    mod = _load_launcher()
    env = tmp_path / ".env"
    env.write_text(
        "# 注释行\nLLM_PROVIDER=openai_compatible\nLLM_API_KEY=sk-old-plain\nLLM_MODEL=gpt-4o\n",
        encoding="utf-8",
    )
    assert mod._read_env(env) == {
        "LLM_PROVIDER": "openai_compatible",
        "LLM_API_KEY": "sk-old-plain",
        "LLM_MODEL": "gpt-4o",
    }
    mod._write_env(
        env,
        {"LLM_BASE_URL": "https://api.example.com/v1", "LLM_MODEL": "new-model"},
        ["LLM_API_KEY"],
    )
    content = env.read_text(encoding="utf-8")
    assert "sk-old-plain" not in content  # 明文密钥行被移除
    assert "LLM_API_KEY" not in content
    assert "LLM_BASE_URL=https://api.example.com/v1" in content
    assert "LLM_MODEL=new-model" in content
    assert "LLM_PROVIDER=openai_compatible" in content  # 无关行保留
    assert "# 注释行" in content  # 注释保留
    assert mod._read_env(env)["LLM_BASE_URL"] == "https://api.example.com/v1"
