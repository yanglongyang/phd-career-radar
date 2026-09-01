"""Collector 共享安全 HTTP 组件（V0.2）。

复用 Phase 3 URL Import 的 SSRF 防护思路（assert_public_host + 每跳重定向
校验 + 大小限制），抽取为公共函数供 web.py 与 collectors 共用 —— 不重写
第二套 SSRF 逻辑。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

USER_AGENT_DEFAULT = "phd-career-radar/0.2 (+personal job discovery tool)"
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5


class SafeFetchError(ValueError):
    """抓取失败（SSRF 拒绝 / 网络 / 大小 / 状态码）。"""


def assert_public_host(host: str) -> None:
    """目标主机必须解析到公网可路由 IP，否则拒绝（SSRF 边界，与 web.py 同源）。"""
    if not host:
        raise SafeFetchError("链接缺少主机名")
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        raise SafeFetchError("拒绝访问本地/内网地址")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise SafeFetchError("域名解析失败，请检查链接") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise SafeFetchError(
                f"拒绝访问非公网地址（{host} → {ip}）"
            )


class SafeFetcher:
    """带 SSRF 边界与大小限制的 HTTP 抓取器（不跟随重定向，逐跳校验）。"""

    def __init__(self, user_agent: str = USER_AGENT_DEFAULT, max_bytes: int = MAX_BODY_BYTES):
        self.user_agent = user_agent
        self.max_bytes = max_bytes

    def _once(self, url: str, timeout: float) -> tuple[int, str, str, str, bytes]:
        headers = {"User-Agent": self.user_agent, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
        try:
            with httpx.Client(follow_redirects=False, timeout=timeout, headers=headers) as client:
                with client.stream("GET", url) as resp:
                    status = resp.status_code
                    content_type = resp.headers.get("content-type", "")
                    location = resp.headers.get("location", "")
                    body = b""
                    if status not in (301, 302, 303, 307, 308):
                        for chunk in resp.iter_bytes():
                            body += chunk
                            if len(body) > self.max_bytes:
                                raise SafeFetchError("响应体过大（超过大小限制）")
                            if len(body) == self.max_bytes:
                                break
                    return status, content_type, location, str(resp.url), body
        except httpx.HTTPError as e:
            raise SafeFetchError(f"抓取失败（{e.__class__.__name__}）") from e

    def fetch(
        self, url: str, timeout: float = 15.0, content_types: tuple[str, ...] | None = None
    ) -> tuple[str, str, str]:
        """返回 (final_url, content_type, body_text)。

        - 逐跳校验目标地址（防重定向进入内网）；
        - 可选 Content-Type 基础验证；
        - body 以 utf-8 解码（失败时 errors=replace）。
        """
        if not (url.startswith("http://") or url.startswith("https://")):
            raise SafeFetchError("仅支持 http/https 链接")
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            host = urlparse(current).hostname
            assert_public_host(host)
            status, content_type, location, final_url, body = self._once(current, timeout)
            if status in (301, 302, 303, 307, 308):
                if not location:
                    raise SafeFetchError("重定向缺少目标地址")
                current = urljoin(final_url or current, location)
                continue
            if status >= 400:
                raise SafeFetchError(f"HTTP {status}")
            if content_types and content_type and not any(
                ct in content_type for ct in content_types
            ):
                raise SafeFetchError(f"Content-Type 不符合预期: {content_type.split(';')[0]}")
            try:
                text = body.decode("utf-8")
            except UnicodeDecodeError:
                text = body.decode("utf-8", errors="replace")
            return final_url, content_type, text
        raise SafeFetchError(f"重定向次数过多（>{MAX_REDIRECTS}）")
