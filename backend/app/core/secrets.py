"""Windows DPAPI 密钥加密存储（V0.2.3 → V0.2.4）。

桌面版安全要求：API Key 不以明文落盘、不上传 GitHub。方案：
- 用 Windows 自带 DPAPI（CryptProtectData / CryptUnprotectData，ctypes 调用，
  无第三方依赖）加密后写入 data/llm_secret.bin；
- 密文默认绑定「当前 Windows 账户 + 本机」：文件被别人拿到、复制到别的机器、
  换账户登录通常无法解密（load 返回 None，不崩溃，不泄露）；
  个别域环境/漫游配置文件可能跟随账户迁移（文档措辞见 README）。
- 载荷为 JSON：{api_key, base_url} —— 把 Key 与用户确认过的接口地址绑定，
  防止 .env 被篡改后自动把 Key 发给新 host（credential destination integrity）；
- 写入采用 临时文件 + fsync + os.replace 原子替换，崩溃不产生半截密文；
- 非 Windows 平台（CI/Linux 开发机）不可用：load 返回 None，功能降级为"未配置密钥"。

文件格式：MAGIC(8B) + DPAPI(JSON)。兼容 V0.2.3 的旧格式（MAGIC_V1 + DPAPI(裸字符串)），
旧格式无 endpoint 绑定信息 → base_url=None，后端按"未绑定"处理（拒绝发送 Key）。
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

MAGIC = b"PCRSEC2\x00"
MAGIC_V1 = b"PCRSEC1\x00"
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


def save_secret(payload: dict, path: Path) -> None:
    """加密写入密钥载荷 {api_key, base_url}；磁盘上只有 MAGIC + 密文，无明文。

    原子写入：临时文件 + flush/fsync + os.replace —— 中途退出只会留下
    旧文件或完整新文件，不会得到半截密文。"""
    blob = protect_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(MAGIC + blob)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_secret(path: Path) -> dict | None:
    """读取并解密。文件缺失 / 格式不对 / 换机器换账户解密失败 → None（不抛异常）。

    返回 {"api_key": str, "base_url": str | None}；base_url 为 None 表示
    旧版格式无 endpoint 绑定（后端按"未绑定"处理，不发送 Key）。"""
    if not path.exists():
        return None
    raw = path.read_bytes()
    if raw.startswith(MAGIC):
        payload_bytes = raw[len(MAGIC):]
        is_v1 = False
    elif raw.startswith(MAGIC_V1):
        payload_bytes = raw[len(MAGIC_V1):]
        is_v1 = True
    else:
        return None
    try:
        plain = unprotect_bytes(payload_bytes).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if is_v1:
        return {"api_key": plain, "base_url": None}
    try:
        data = json.loads(plain)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return {"api_key": data.get("api_key"), "base_url": data.get("base_url")}


def delete_secret(path: Path) -> None:
    """删除密钥文件（含可能的残留 .tmp）。"""
    for p in (path, path.with_name(path.name + ".tmp")):
        if p.exists():
            p.unlink()
