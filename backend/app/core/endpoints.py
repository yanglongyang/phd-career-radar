"""LLM 接口地址安全策略（V0.2.4）。

凭据（API Key）只能发给受信任的目标：
- 非本机接口强制 https://（Key 不以明文经过网络）；
- 仅 http://127.0.0.1 / http://localhost / http://[::1] 放行明文（本地模型）；
- 拒绝 userinfo（user:pass@）、fragment、空主机名、其他 scheme。

本模块只依赖标准库，launcher 与后端共用。
"""

from __future__ import annotations

from urllib.parse import urlsplit

# 允许 http 明文的本机地址（本地模型服务，如 Ollama/LM Studio）
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def validate_llm_base_url(url: str) -> str | None:
    """校验 AI 接口地址。合法返回 None；非法返回中文错误说明（可直接展示给用户）。"""
    try:
        parts = urlsplit((url or "").strip())
    except ValueError as e:
        return f"接口地址无法解析：{e}"
    if parts.scheme == "https":
        pass
    elif parts.scheme == "http":
        host = (parts.hostname or "").casefold()
        if host not in LOCAL_HOSTS:
            return "非本机接口必须使用 https://，禁止 http 明文传输 API Key"
    else:
        return "接口地址必须使用 https://（本地模型可例外使用 http://127.0.0.1 或 http://localhost）"
    if not parts.hostname:
        return "接口地址缺少主机名"
    if parts.username or parts.password:
        return "接口地址不允许包含用户名/密码"
    if parts.fragment:
        return "接口地址不允许包含 #fragment"
    return None


def normalize_base_url(url: str) -> str:
    """规范化接口地址用于绑定比对：scheme/host 小写、去尾斜杠、保留端口与路径。"""
    parts = urlsplit((url or "").strip())
    port = f":{parts.port}" if parts.port else ""
    path = parts.path.rstrip("/")
    return f"{parts.scheme.lower()}://{(parts.hostname or '').casefold()}{port}{path}"
