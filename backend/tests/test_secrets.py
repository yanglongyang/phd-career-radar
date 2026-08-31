"""V0.2.3→V0.2.4 API Key 安全存储：DPAPI 加密回环、载荷绑定、原子写入、
endpoint 策略、config 集成、launcher .env 工具。"""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT, Settings, _apply_llm_secret
from app.core.endpoints import normalize_base_url, validate_llm_base_url
from app.core.secrets import (
    MAGIC,
    MAGIC_V1,
    delete_secret,
    load_secret,
    protect_bytes,
    save_secret,
    secret_path,
    unprotect_bytes,
)

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI 仅 Windows")

PAYLOAD = {"api_key": "sk-super-secret-abcdef", "base_url": "https://api.example.com/v1"}


@win32_only
def test_dpapi_roundtrip():
    """加密 → 解密 得到原文；密文不等于明文。"""
    blob = protect_bytes(b"sk-test-1234567890")
    assert blob != b"sk-test-1234567890"
    assert unprotect_bytes(blob) == b"sk-test-1234567890"


@win32_only
def test_save_load_roundtrip_no_plaintext_on_disk(tmp_path):
    path = secret_path(tmp_path)
    save_secret(PAYLOAD, path)
    raw = path.read_bytes()
    assert b"sk-super-secret-abcdef" not in raw  # 磁盘上无明文
    assert b"api.example.com" not in raw         # endpoint 绑定也不明文
    assert raw.startswith(MAGIC)
    assert load_secret(path) == PAYLOAD
    # 原子写入：无 .tmp 残留
    assert not path.with_name(path.name + ".tmp").exists()


@win32_only
def test_save_secret_atomic_replace(tmp_path):
    """连续保存两次，文件始终是完整新内容（无半截密文），tmp 清理干净。"""
    path = secret_path(tmp_path)
    save_secret(PAYLOAD, path)
    save_secret({"api_key": "sk-new", "base_url": "https://api.new.com/v1"}, path)
    assert load_secret(path) == {"api_key": "sk-new", "base_url": "https://api.new.com/v1"}
    assert not path.with_name(path.name + ".tmp").exists()


@win32_only
def test_load_secret_missing_or_corrupt(tmp_path):
    path = secret_path(tmp_path)
    assert load_secret(path) is None  # 文件不存在
    path.write_bytes(b"garbage-no-magic")
    assert load_secret(path) is None  # 格式不对
    path.write_bytes(MAGIC + b"too-short")
    assert load_secret(path) is None  # 只有 magic 无密文


@win32_only
def test_load_secret_v1_fallback_unbound(tmp_path):
    """V0.2.3 旧格式（裸字符串载荷）→ 可解密但 base_url=None（未绑定，拒绝发送 Key）。"""
    path = secret_path(tmp_path)
    path.write_bytes(MAGIC_V1 + protect_bytes(b"sk-legacy-key"))
    payload = load_secret(path)
    assert payload == {"api_key": "sk-legacy-key", "base_url": None}


@win32_only
def test_delete_secret_cleans_tmp(tmp_path):
    path = secret_path(tmp_path)
    save_secret(PAYLOAD, path)
    (path.with_name(path.name + ".tmp")).write_bytes(b"leftover")
    delete_secret(path)
    assert not path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
    assert load_secret(path) is None


# ---------- endpoint 策略（P1：Key 只发给可信目标） ----------

def test_validate_llm_base_url_cases():
    assert validate_llm_base_url("https://api.openai.com/v1") is None
    assert validate_llm_base_url("https://api.example.com/v1/") is None
    # 非本机 http → 拒绝（Key 明文过网）
    assert validate_llm_base_url("http://evil.example/v1") is not None
    assert "https" in validate_llm_base_url("http://evil.example/v1")
    # 本机 http → 放行
    assert validate_llm_base_url("http://127.0.0.1:11434") is None
    assert validate_llm_base_url("http://localhost:8080/v1") is None
    assert validate_llm_base_url("http://[::1]:11434") is None
    # userinfo / fragment / 其他 scheme / 空
    assert validate_llm_base_url("https://user:pass@example.com") is not None
    assert validate_llm_base_url("https://example.com/v1#frag") is not None
    assert validate_llm_base_url("ftp://example.com/v1") is not None
    assert validate_llm_base_url("") is not None


def test_normalize_base_url_ignores_trailing_slash_and_case():
    assert normalize_base_url("HTTPS://API.Example.com/v1/") == "https://api.example.com/v1"
    assert normalize_base_url("https://api.example.com/v1") == "https://api.example.com/v1"
    assert normalize_base_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"


# ---------- config 集成 ----------

def test_apply_llm_secret_prefers_env_key():
    """环境变量已有 key → 不读取密钥文件（环境变量优先级最高）。"""
    settings = Settings(llm_api_key="sk-from-env", _env_file=None)
    out = _apply_llm_secret(settings, secret_file=Path("does-not-matter"))
    assert out.llm_api_key == "sk-from-env"


@win32_only
def test_apply_llm_secret_loads_encrypted_file(tmp_path):
    """环境变量为空 + 密钥文件存在 → 自动解密填充（直接 uvicorn 启动也能用）。"""
    path = secret_path(tmp_path)
    save_secret(PAYLOAD, path)
    settings = Settings(llm_api_key="", _env_file=None)
    out = _apply_llm_secret(settings, secret_file=path)
    assert out.llm_api_key == PAYLOAD["api_key"]


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
