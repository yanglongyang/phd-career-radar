"""公开网页正文获取（Phase 3 方法 3：URL 导入）。

原则与边界（Phase 3.1 收紧）：
- 只做最简单的公开网页下载与正文粗提取，不编写任何反爬对抗。
- **SSRF 防护**：目标主机必须解析到公网可路由 IP（拒绝 loopback/私网/链路本地/
  组播/保留地址），且**每一跳重定向都重新校验**。
- **大小限制**：响应体最多 MAX_BODY_BYTES，超出明确报错。
- 失败一律抛 PageFetchError，由 API 层转成明确提示"请粘贴公告全文"。
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx

USER_AGENT = "Mozilla/5.0 (compatible; PhDCareerRadar/0.1; personal research tool)"
MIN_TEXT_LENGTH = 50
MAX_BODY_BYTES = 5 * 1024 * 1024  # 网页下载上限
MAX_REDIRECTS = 5

_SCRIPT_STYLE = re.compile(
    r"<(script|style|noscript|template)\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"</(p|div|li|tr|h[1-6]|section|article|table)>", re.IGNORECASE)
_BLANK_LINES = re.compile(r"\n{3,}")


class PageFetchError(ValueError):
    """URL 抓取或正文提取失败。"""


def html_to_text(html: str) -> str:
    """粗糙但可预测的 HTML → 纯文本：去脚本/样式/注释，块级标签转换行，压缩空白。"""
    text = _COMMENTS.sub("", html)
    text = _SCRIPT_STYLE.sub("", text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAGS.sub("", text)
    lines = [line.strip() for line in text.splitlines()]
    return _BLANK_LINES.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def assert_public_host(host: str) -> None:
    """目标主机必须解析到公网可路由 IP，否则拒绝（SSRF 边界）。"""
    if not host:
        raise PageFetchError("链接缺少主机名")
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        raise PageFetchError("拒绝访问本地/内网地址")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise PageFetchError("域名解析失败，请检查链接") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise PageFetchError(
                f"拒绝访问非公网地址（{host} → {ip}）；如需导入内网公告请直接粘贴正文"
            )


def _fetch_once(url: str, timeout: float) -> tuple[int, str, str, str, bytes]:
    """单次 GET（不跟随重定向），流式读取并限制大小。
    返回 (status, content_type, location, final_url, body)。"""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
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
                        if len(body) > MAX_BODY_BYTES:
                            raise PageFetchError("网页内容过大（超过 5MB），请直接粘贴公告全文")
                        if len(body) == MAX_BODY_BYTES:
                            break
                return status, content_type, location, str(resp.url), body
    except httpx.HTTPError as e:
        raise PageFetchError(f"网页访问失败（{e.__class__.__name__}），请直接粘贴公告全文") from e


def fetch_url_text(url: str, timeout: float = 20.0) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise PageFetchError("仅支持 http/https 链接")

    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        host = urlparse(current_url).hostname
        # 每一跳都重新校验目标地址（防重定向进入内网）
        assert_public_host(host)
        status, content_type, location, resp_url, body = _fetch_once(current_url, timeout)
        if status in (301, 302, 303, 307, 308):
            if not location:
                raise PageFetchError("重定向缺少目标地址")
            current_url = urljoin(resp_url or current_url, location)
            continue
        if status >= 400:
            raise PageFetchError(f"网页返回 HTTP {status}，可能需要登录或已失效，请直接粘贴公告全文")
        if "html" not in content_type and "text" not in content_type and content_type:
            raise PageFetchError(
                f"链接不是网页（{content_type.split(';')[0]}），请直接粘贴公告全文"
            )
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            html = body.decode("utf-8", errors="replace")
        text = html_to_text(html)
        if len(text) < MIN_TEXT_LENGTH:
            raise PageFetchError("网页正文过短或提取失败，请直接粘贴公告全文")
        return text
    raise PageFetchError(f"重定向次数过多（>{MAX_REDIRECTS}），请直接粘贴公告全文")
