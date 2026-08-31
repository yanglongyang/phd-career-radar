"""CI secret scan：扫描 git 追踪文件中的常见凭据模式（V0.2.4 供应链硬化）。

在 push/PR 时运行：一旦任何被追踪的文件出现疑似密钥，CI 直接失败。
真实密钥永远不应该出现在仓库里 —— .env 与 data/llm_secret.bin 已在 .gitignore。

注意：测试里出现的假密钥（sk-fake-key-...）故意带连字符且长度 < 20，
不会命中 sk-[A-Za-z0-9-]{20,} 模式（V0.2.5 起允许 sk- 后出现连字符，
以覆盖 sk-proj-... 形态的真实 Key）。
"""

import re
import subprocess
import sys

PATTERNS = [
    # OpenAI-compatible：sk- 后允许连字符（真实 Key 形如 sk-proj-xxxxx...）
    re.compile(r"sk-[A-Za-z0-9-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),          # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),       # GitHub personal access token
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),     # Google API key
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
]


def main() -> None:
    files = subprocess.check_output(["git", "ls-files"], text=True).splitlines()
    bad: list[tuple[str, str]] = []
    for name in files:
        try:
            with open(name, encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue
        for pattern in PATTERNS:
            if pattern.search(content):
                bad.append((name, pattern.pattern))
    if bad:
        print("❌ 疑似密钥泄漏：")
        for name, pattern in bad:
            print(f"  {name}  匹配 {pattern}")
        sys.exit(1)
    print(f"✅ secret scan OK（{len(files)} 个追踪文件，无凭据模式）")


if __name__ == "__main__":
    main()
