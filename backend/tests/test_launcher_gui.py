"""V0.2.3→V0.2.4 启动器 API 设置对话框与明文迁移：真实 Tk 驱动测试（Windows）。

直接创建对话框 → 填表 → 点「保存」→ 校验 .env 与加密文件；
非法接口地址 → 拒绝保存；再打开 → 点「清除密钥」→ 校验密钥删除。
Tk 窗口 withdraw 隐藏，不打扰屏幕。明文迁移失败时 Key 必须保留。
"""

import importlib.util
import os
import sys

import pytest

from app.core.config import PROJECT_ROOT
from app.core.secrets import load_secret

# Tk 对话框需要交互桌面；CI（无桌面会话）跳过，本地 Windows 全量跑
win32_only = pytest.mark.skipif(
    sys.platform != "win32" or os.environ.get("CI") == "true",
    reason="Tk 对话框测试仅本地 Windows 桌面环境",
)


def _load_launcher() -> object:
    path = PROJECT_ROOT / "launcher" / "launcher.py"
    spec = importlib.util.spec_from_file_location("pcr_launcher_mod2", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_widgets(dlg) -> tuple[list, dict]:
    """返回 (entry 列表按创建顺序, 按钮 dict by text)。"""
    entries: list = []
    buttons: dict[str, object] = {}

    def walk(w):
        for child in w.winfo_children():
            cls = child.winfo_class()
            if cls == "TEntry":
                entries.append(child)
            elif cls == "TButton":
                buttons[child.cget("text")] = child
            walk(child)

    walk(dlg)
    return entries, buttons


def _new_dialog(root) -> tuple[object, list, dict]:
    dialogs = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"]
    dlg = dialogs[-1]
    return dlg, *_find_widgets(dlg)


@win32_only
def test_api_settings_dialog_save_and_clear(monkeypatch, tmp_path):
    import tkinter as tk

    mod = _load_launcher()
    env_path = tmp_path / ".env"
    secret_f = tmp_path / "llm_secret.bin"
    env_path.write_text("LLM_BASE_URL=https://old.example.com/v1\nLLM_MODEL=old-model\n", encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(mod.messagebox, "showerror", lambda *a, **k: errors.append(a[1]))

    root = tk.Tk()
    root.withdraw()
    try:
        log_box = tk.Text(root)
        # ---- 打开对话框：预填旧值 ----
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        dlg, entries, buttons = _new_dialog(root)
        assert set(buttons) == {"保存", "清除密钥", "取消"}
        assert entries[0].get() == "https://old.example.com/v1"  # 预填接口地址
        assert entries[1].get() == "old-model"                    # 预填模型

        # ---- 非法接口地址：拒绝保存，什么都不写 ----
        entries[0].delete(0, tk.END)
        entries[0].insert(0, "http://evil.example/v1")
        entries[2].insert(0, "sk-dialog-secret-xyz")
        buttons["保存"].invoke()
        assert errors, "非法地址应弹出错误"
        assert "https" in errors[0]
        assert not secret_f.exists()            # 未写密钥文件
        assert "LLM_BASE_URL=https://old.example.com/v1" in env_path.read_text(
            encoding="utf-8"
        )                                        # .env 保持原值

        # ---- 合法地址 + 新 Key 保存 ----
        entries[0].delete(0, tk.END)
        entries[0].insert(0, "https://api.new.com/v1")
        entries[1].delete(0, tk.END)
        entries[1].insert(0, "new-model")
        buttons["保存"].invoke()

        env = env_path.read_text(encoding="utf-8")
        assert "sk-dialog-secret-xyz" not in env           # .env 无明文
        assert "LLM_API_KEY" not in env
        assert "LLM_BASE_URL=https://api.new.com/v1" in env
        assert "LLM_MODEL=new-model" in env
        saved = load_secret(secret_f)
        assert saved == {"api_key": "sk-dialog-secret-xyz", "base_url": "https://api.new.com/v1"}
        # 绑定地址也加密在载荷里
        assert b"api.new.com" not in secret_f.read_bytes()

        # ---- 再次打开：密钥输入框留空保存 → 保留已存密钥，绑定地址随确认更新 ----
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        _, entries2, buttons2 = _new_dialog(root)
        entries2[0].delete(0, tk.END)
        entries2[0].insert(0, "https://api.new.com/v1/")    # 尾斜杠差异 → 规范化后相同
        buttons2["保存"].invoke()
        assert load_secret(secret_f)["api_key"] == "sk-dialog-secret-xyz"  # 未被清掉

        # ---- 清除密钥（确认框返回 True）----
        monkeypatch.setattr(mod.messagebox, "askyesno", lambda *a, **k: True)
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        _, _, buttons3 = _new_dialog(root)
        buttons3["清除密钥"].invoke()
        assert not secret_f.exists()
        assert load_secret(secret_f) is None
    finally:
        root.destroy()


@win32_only
def test_migrate_plaintext_key_saves_before_deleting(monkeypatch, tmp_path):
    """正常迁移：先加密保存并验证，再删 .env 明文。"""
    mod = _load_launcher()
    monkeypatch.setattr(mod, "_DATA_ROOT", tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_BASE_URL=https://api.example.com/v1\nLLM_API_KEY=sk-plain-123\n",
        encoding="utf-8",
    )
    mod._migrate_plaintext_key()
    env = env_path.read_text(encoding="utf-8")
    assert "sk-plain-123" not in env            # 明文已删
    assert "LLM_API_KEY" not in env
    assert load_secret(tmp_path / "data" / "llm_secret.bin") == {
        "api_key": "sk-plain-123", "base_url": "https://api.example.com/v1",
    }


@win32_only
def test_migrate_plaintext_key_keeps_plain_on_save_failure(monkeypatch, tmp_path):
    """加密保存失败 → 明文必须保留（先存验证后删）。"""
    import app.core.secrets as secrets_mod

    mod = _load_launcher()
    monkeypatch.setattr(mod, "_DATA_ROOT", tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_API_KEY=sk-plain-123\n", encoding="utf-8")

    def boom(payload, path):
        raise OSError("磁盘满")

    monkeypatch.setattr(secrets_mod, "save_secret", boom)
    mod._migrate_plaintext_key()
    assert "sk-plain-123" in env_path.read_text(encoding="utf-8")  # 明文仍在


@win32_only
def test_migrate_plaintext_key_keeps_plain_on_verify_failure(monkeypatch, tmp_path):
    """写入后回读验证不一致 → 明文保留。"""
    import app.core.secrets as secrets_mod

    mod = _load_launcher()
    monkeypatch.setattr(mod, "_DATA_ROOT", tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_API_KEY=sk-plain-123\n", encoding="utf-8")

    def fake_save(payload, path):
        path.write_bytes(b"PCRSEC2\x00garbage")

    monkeypatch.setattr(secrets_mod, "save_secret", fake_save)
    mod._migrate_plaintext_key()
    assert "sk-plain-123" in env_path.read_text(encoding="utf-8")  # 明文仍在
