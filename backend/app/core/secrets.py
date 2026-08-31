"""Windows DPAPI 密钥加密存储（V0.2.3）。

桌面版安全要求：API Key 不以明文落盘、不上传 GitHub。方案：
- 用 Windows 自带 DPAPI（CryptProtectData / CryptUnprotectData，ctypes 调用，
  无第三方依赖）加密后写入 data/llm_secret.bin；
- 密文绑定「当前 Windows 账户 + 本机」：文件被别人拿到、复制到别的机器、
  换账户登录都无法解密（load 返回 None，不崩溃，不泄露）；
- 非 Windows 平台（CI/Linux 开发机）不可用：load 返回 None，功能降级为"未配置密钥"。

文件格式：MAGIC(8B) + DPAPI 密文。MAGIC 用于区分损坏/外来文件。
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

MAGIC = b"PCRSEC1\x00"
SECRET_FILE_NAME = "llm_secret.bin"

# CryptProtectData 的 CRYPTPROTECT_UI_FORBIDDEN：静默加解密，不弹任何系统对话框
_UI_FORBIDDEN = 0x1


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _require_windows() -> None:
    if sys.platform != "win32":
        raise OSError("DPAPI 仅支持 Windows")


def _make_blob(data: bytes) -> tuple[_DATA_BLOB, object]:
    """构造 DATA_BLOB；返回 (blob, 持有缓冲区的引用) —— 缓冲区必须存活到调用结束。"""
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    return blob, buf


def protect_bytes(data: bytes) -> bytes:
    """DPAPI 加密（当前用户 + 本机绑定）。失败抛 OSError。"""
    _require_windows()
    blob_in, holder = _make_blob(data)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError(f"CryptProtectData 失败 (WinError {ctypes.get_last_error()})")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def unprotect_bytes(blob: bytes) -> bytes:
    """DPAPI 解密。非本机/非本账户/损坏 → 抛 OSError（由调用方转 None）。"""
    _require_windows()
    blob_in, holder = _make_blob(blob)
    blob_out = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, _UI_FORBIDDEN, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError(f"CryptUnprotectData 失败 (WinError {ctypes.get_last_error()})")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def secret_path(data_dir: Path) -> Path:
    """密钥文件位置（data/ 下，随 .gitignore 排除）。"""
    return data_dir / SECRET_FILE_NAME


def save_secret(key: str, path: Path) -> None:
    """加密写入密钥文件；磁盘上只有 MAGIC + 密文，无明文。"""
    blob = protect_bytes(key.encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MAGIC + blob)


def load_secret(path: Path) -> str | None:
    """读取并解密。文件缺失 / 格式不对 / 换机器换账户解密失败 → None（不抛异常）。"""
    if not path.exists():
        return None
    raw = path.read_bytes()
    if not raw.startswith(MAGIC) or len(raw) <= len(MAGIC):
        return None
    try:
        return unprotect_bytes(raw[len(MAGIC):]).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def delete_secret(path: Path) -> None:
    """删除密钥文件（清除密钥）。"""
    if path.exists():
        path.unlink()
