"""V0.2.3 启动器 API 设置对话框：真实 Tk 驱动测试（Windows 桌面环境）。

直接创建对话框 → 填表 → 点「保存」→ 校验 .env 与加密文件；
再打开 → 点「清除密钥」→ 校验密钥删除。Tk 窗口 withdraw 隐藏，不打扰屏幕。
"""

import importlib.util
import sys

import pytest

from app.core.config import PROJECT_ROOT
from app.core.secrets import load_secret

win32_only = pytest.mark.skipif(sys.platform != "win32", reason="Tk 对话框测试仅 Windows")


def _load_launcher() -> object:
    path = PROJECT_ROOT / "launcher" / "launcher.py"
    spec = importlib.util.spec_from_file_location("pcr_launcher_mod2", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _find_widgets(dlg) -> tuple[list, list]:
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


@win32_only
def test_api_settings_dialog_save_and_clear(monkeypatch, tmp_path):
    import tkinter as tk

    mod = _load_launcher()
    env_path = tmp_path / ".env"
    secret_f = tmp_path / "llm_secret.bin"
    env_path.write_text("LLM_BASE_URL=https://old.example.com/v1\nLLM_MODEL=old-model\n", encoding="utf-8")

    root = tk.Tk()
    root.withdraw()
    try:
        log_box = tk.Text(root)
        # ---- 打开对话框：预填旧值 ----
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        dlg = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"]
        assert len(dlg) == 1
        dlg = dlg[0]
        entries, buttons = _find_widgets(dlg)
        assert set(buttons) == {"保存", "清除密钥", "取消"}
        assert entries[0].get() == "https://old.example.com/v1"  # 预填接口地址
        assert entries[1].get() == "old-model"                    # 预填模型

        # ---- 填新值并保存 ----
        entries[0].delete(0, tk.END)
        entries[0].insert(0, "https://api.new.com/v1")
        entries[1].delete(0, tk.END)
        entries[1].insert(0, "new-model")
        entries[2].insert(0, "sk-dialog-secret-xyz")
        buttons["保存"].invoke()

        env = env_path.read_text(encoding="utf-8")
        assert "sk-dialog-secret-xyz" not in env           # .env 无明文
        assert "LLM_API_KEY" not in env
        assert "LLM_BASE_URL=https://api.new.com/v1" in env
        assert "LLM_MODEL=new-model" in env
        assert load_secret(secret_f) == "sk-dialog-secret-xyz"  # 加密文件可解密

        # ---- 再次打开：密钥输入框留空保存 → 保留已存密钥 ----
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        dlg2 = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
        entries2, buttons2 = _find_widgets(dlg2)
        buttons2["保存"].invoke()
        assert load_secret(secret_f) == "sk-dialog-secret-xyz"  # 未被清掉

        # ---- 清除密钥（确认框返回 True）----
        monkeypatch.setattr(mod.messagebox, "askyesno", lambda *a, **k: True)
        mod._open_api_settings_dialog(root, log_box, env_path, secret_f)
        dlg3 = [w for w in root.winfo_children() if w.winfo_class() == "Toplevel"][-1]
        _, buttons3 = _find_widgets(dlg3)
        buttons3["清除密钥"].invoke()
        assert not secret_f.exists()
        assert load_secret(secret_f) is None
    finally:
        root.destroy()
