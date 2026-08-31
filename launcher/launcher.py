"""PhD Career Radar Launcher（V0.1.1）—— 日常使用入口。

双击启动（或 `python launcher/launcher.py`）：
- 以**无 --reload** 方式启动后端（uvicorn 单进程）；
- 后端由 FastAPI 直接托管前端构建产物（frontend/dist），日常运行**不需要 Vite/Node**；
- PID 文件为 JSON：{pid, created_at_marker, port}；清理残留前校验进程创建时间
  （PID 被系统重用的防护：不一致只删文件，绝不 kill 无辜进程）；
- 停止/关闭时优雅 terminate → 强制 taskkill /T /F 清理整个进程树；
- stdout/stderr 实时进入日志窗口；health 检查在后台线程完成、
  经 root.after 回主线程更新 UI 并自动打开浏览器；
- 「API 设置」：接口地址/模型写 .env；API Key 用 Windows DPAPI 加密存
  data/llm_secret.bin（无明文，与接口地址绑定），后端启动时自行解密读取，
  launcher 不把 Key 注入环境变量。

两种入口：
- `--serve`：仅启动后端（供本文件自身 subprocess 复用，也便于冒烟验证）；
- 无参数：Tkinter GUI 启动器。

开发模式不受影响：`uvicorn --reload` + `npm run dev` 照常使用。
"""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

if getattr(sys, "frozen", False):
    # PyInstaller：app 包与资源在 _MEIPASS（只读），数据与 PID 文件在 exe 旁
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    PROJECT_ROOT = BACKEND_DIR
    _DATA_ROOT = Path(sys.executable).parent
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
    PROJECT_ROOT = BACKEND_DIR.parent
    _DATA_ROOT = PROJECT_ROOT
    # 开发模式：launcher（GUI）也要能 import app.*（API 设置里的 DPAPI 密钥模块）
    sys.path.insert(0, str(BACKEND_DIR))
PID_FILE = _DATA_ROOT / "data" / "backend.pid"
DEFAULT_PORT = 8000


def _is_alive(pid: int) -> bool:
    """Windows 上检查进程是否存活（无权限时按存在处理）。"""
    if sys.platform == "win32":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _process_creation_time(pid: int) -> float | None:
    """进程创建时间（epoch 秒）。Windows 用 GetProcessTimes；Linux 用 /proc。"""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return None
            try:
                creation = wintypes.FILETIME()
                exit_time = wintypes.FILETIME()
                kernel_time = wintypes.FILETIME()
                user_time = wintypes.FILETIME()
                ok = ctypes.windll.kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel_time),
                    ctypes.byref(user_time),
                )
                if not ok:
                    return None
                # FILETIME: 100ns 步长自 1601-01-01
                ft = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
                return ft / 10_000_000 - 11644473600.0
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        parts = stat.rsplit(")", 1)[1].split()
        return float(parts[19]) / 100.0  # starttime（clock ticks）
    except Exception:
        return None


class ProcessManager:
    """后端进程生命周期管理：启动 / 停止 / 残留检测 / PID 持久化。

    PID 文件为 JSON：{pid, created_at_marker, port}。清理残留前**必须**验证
    进程创建时间与记录一致（PID 被系统重用的防护 —— 不一致只删文件，绝不 kill）。
    """

    def __init__(self, pid_file: Path = PID_FILE, port: int = DEFAULT_PORT):
        self.pid_file = pid_file
        self.port = port
        self.proc: subprocess.Popen | None = None

    # ---- PID 记录 ----

    def _write_pid(self, pid: int) -> None:
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "pid": pid,
            "created_at_marker": _process_creation_time(pid),
            "port": self.port,
        }
        self.pid_file.write_text(json.dumps(record), encoding="utf-8")

    def _read_record(self) -> dict | None:
        if not self.pid_file.exists():
            return None
        try:
            data = json.loads(self.pid_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (ValueError, TypeError):
            return None

    def read_pid(self) -> int | None:
        """兼容旧纯数字格式；返回记录中的 pid。"""
        record = self._read_record()
        if record is not None and record.get("pid") is not None:
            try:
                return int(record["pid"])
            except (TypeError, ValueError):
                return None
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    def _verify_identity(self, pid: int) -> bool:
        """进程创建时间与记录一致才算同一进程（PID 复用防护）。"""
        record = self._read_record()
        marker = record.get("created_at_marker") if record else None
        if not marker:
            return False  # 旧格式无身份信息 → 保守：不 kill
        now = _process_creation_time(pid)
        if now is None:
            return False
        return abs(now - float(marker)) < 2.0

    def is_running(self) -> bool:
        pid = self.read_pid()
        return pid is not None and _is_alive(pid) and self._verify_identity(pid)

    def stale_pid(self) -> int | None:
        """上次异常退出留下的 PID：进程存活且身份校验通过才算残留。"""
        pid = self.read_pid()
        if pid is not None and _is_alive(pid) and self._verify_identity(pid):
            return pid
        return None

    # ---- 启动 / 停止 ----

    def start(self) -> subprocess.Popen:
        """无 --reload 启动后端；stdout/stderr 走管道供 GUI 读取。"""
        if self.proc is not None and self.proc.poll() is None:
            return self.proc
        cmd = [sys.executable, str(Path(__file__).resolve()), "--serve", "--port", str(self.port)]
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._write_pid(self.proc.pid)
        return self.proc

    def stop(self, timeout: float = 6.0) -> None:
        """优雅 terminate → 等待 → 强制清理整个进程树 → 删除 pid 文件。"""
        pid = self.read_pid()
        proc = self.proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._kill_tree(proc.pid)
                proc.wait(timeout=5)
        elif pid is not None and _is_alive(pid) and self._verify_identity(pid):
            # pid 文件指向存活进程但对象丢失（如重启后的残留）→ 身份校验通过才清理
            self._kill_tree(pid)
        if self.pid_file.exists():
            self.pid_file.unlink()
        self.proc = None

    def cleanup_stale(self) -> int | None:
        """清理上次异常残留的进程树；返回被清理的 PID 或 None。

        身份校验失败（PID 已被系统复用）→ 只删除 pid 文件，绝不 kill 无辜进程。"""
        pid = self.read_pid()
        if pid is None:
            return None
        identity_ok = _is_alive(pid) and self._verify_identity(pid)
        if identity_ok:
            self._kill_tree(pid)
        if self.pid_file.exists():
            self.pid_file.unlink()
        return pid if identity_ok else None

    @staticmethod
    def _kill_tree(pid: int) -> None:
        """Windows：taskkill /T /F 连子进程一起清理；其他平台：SIGKILL 组。"""
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
            )
        else:
            try:
                os.killpg(pid, signal.SIGKILL)
            except OSError:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass


def wait_for_health(port: int = DEFAULT_PORT, timeout: float = 30.0) -> bool:
    """轮询 /api/health 直到后端就绪（按实际端口）。"""
    import urllib.request

    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# API Key 安全存储（V0.2.3 → V0.2.4）
#   - 密钥用 Windows DPAPI 加密存 data/llm_secret.bin（绑定当前账户+本机），
#     磁盘上无明文；.env 只放接口地址/模型名（非机密）；
#   - V0.2.4：密钥载荷 {api_key, base_url} 与 endpoint 绑定；接口地址必须
#     https（本地模型可 http://127.0.0.1）；后端自行解密密钥文件，
#     launcher 不再把 Key 注入环境变量（缩小明文驻留范围）；
#   - 旧版 .env 里的明文 LLM_API_KEY 自动迁移：先加密保存并验证成功，
#     才删除明文行（失败则保留明文，绝不丢 Key）。
# ---------------------------------------------------------------------------

def _secret_file() -> Path:
    from app.core.secrets import SECRET_FILE_NAME

    return _DATA_ROOT / "data" / SECRET_FILE_NAME


def _read_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, _, value = stripped.partition("=")
                result[key.strip()] = value.strip()
    return result


def _write_env(path: Path, updates: dict[str, str], removes: list[str]) -> None:
    """更新 .env：updates 覆盖 KEY=VALUE；removes 删除键（如明文 LLM_API_KEY）。
    保留注释与其余行；新键追加到文件末尾。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in updates or key in removes:
                seen.add(key)
                if key in updates:
                    out.append(f"{key}={updates[key]}")
                continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _migrate_plaintext_key(log_box=None) -> None:
    """旧工作流遗留：.env 里有明文 LLM_API_KEY → 迁移为 DPAPI 加密存储。

    顺序（V0.2.4 安全要求）：先加密写入 + 回读验证成功，才删除 .env 明文行；
    任何一步失败都保留明文 —— Key 绝不因迁移失败而丢失。

    V0.2.5（P2 closure）：已存在可解密的密钥文件时，必须核对明文与加密载荷
    是否同一个 Key：一致才允许只删明文；不一致（旧加密文件 A + 新明文 B）
    则用 B + 当前 base_url 覆盖写入并验证，防止新 Key 被误删。"""
    from app.core.endpoints import normalize_base_url
    from app.core.secrets import load_secret, save_secret

    env_path = _DATA_ROOT / ".env"
    env = _read_env(env_path)
    plain = env.get("LLM_API_KEY", "")
    if not plain:
        return
    base = env.get("LLM_BASE_URL", "")
    secret_f = _secret_file()
    existing = load_secret(secret_f)
    if existing is not None and existing.get("api_key") == plain:
        # 加密副本与明文是同一个 Key → 只删明文行，不动加密文件
        _write_env(env_path, {}, ["LLM_API_KEY"])
        if log_box is not None:
            log_box.insert(tk.END, "[launcher] 已移除 .env 中的明文密钥（加密副本已存在且一致）\n")
        return
    try:
        save_secret({"api_key": plain, "base_url": base or None}, secret_f)
    except OSError as e:
        if log_box is not None:
            log_box.insert(tk.END, f"[launcher] 密钥迁移失败（明文已保留，未删除）：{e}\n")
        return
    saved = load_secret(secret_f)
    if (
        saved is None
        or saved.get("api_key") != plain
        or normalize_base_url(saved.get("base_url") or "")
        != normalize_base_url(base or "")
    ):
        if log_box is not None:
            log_box.insert(tk.END, "[launcher] 密钥迁移校验失败（明文已保留，未删除）\n")
        return
    _write_env(env_path, {}, ["LLM_API_KEY"])
    if log_box is not None:
        log_box.insert(tk.END, "[launcher] 检测到 .env 明文密钥，已迁移为加密存储（Windows 账户绑定）\n")


def _backend_running() -> bool:
    return ProcessManager().is_running()


def _open_api_settings_dialog(root, log_box, env_path: Path, secret_f: Path) -> None:
    """API 设置对话框：接口地址/模型名写 .env（非机密）；API Key 走 DPAPI 加密存储。

    V0.2.4：接口地址强制 https（本地模型 http://127.0.0.1 例外）；密钥与接口地址
    一起加密绑定，.env 被改后后端拒绝发送 Key。独立成模块级函数以便 GUI 测试
    直接驱动（填表 → 保存 → 清除密钥）。"""
    from app.core.endpoints import validate_llm_base_url
    from app.core.secrets import delete_secret, load_secret, save_secret
    from tkinter import ttk

    env = _read_env(env_path)
    has_secret = load_secret(secret_f) is not None

    dlg = tk.Toplevel(root)
    dlg.title("API 设置")
    dlg.geometry("600x340")
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    base_var = tk.StringVar(value=env.get("LLM_BASE_URL", ""))
    model_var = tk.StringVar(value=env.get("LLM_MODEL", ""))
    key_var = tk.StringVar()
    status_var2 = tk.StringVar(
        value="已加密保存（Windows 账户绑定）" if has_secret else "未设置"
    )

    frm = ttk.Frame(dlg, padding=16)
    frm.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frm, text="API 接口地址").grid(row=0, column=0, sticky="w", pady=(0, 8))
    ttk.Entry(frm, textvariable=base_var, width=64).grid(row=0, column=1, sticky="we", pady=(0, 8))

    ttk.Label(frm, text="模型名称").grid(row=1, column=0, sticky="w", pady=(0, 8))
    ttk.Entry(frm, textvariable=model_var, width=64).grid(row=1, column=1, sticky="we", pady=(0, 8))

    ttk.Label(frm, text="API Key").grid(row=2, column=0, sticky="w", pady=(0, 8))
    ttk.Entry(frm, textvariable=key_var, width=64, show="*").grid(row=2, column=1, sticky="we", pady=(0, 8))
    ttk.Label(
        frm,
        text="密钥输入框留空 = 保留已保存的密钥；密钥与接口地址一起加密存储，\n"
             "默认绑定当前 Windows 账户与电脑（个别域/漫游配置存在例外）；\n"
             "非本机接口必须 https://。换机器/换账户后需重新输入。",
        foreground="#666",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 4))
    ttk.Label(frm, textvariable=status_var2, foreground="#0a7d33").grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(0, 12)
    )

    btn_row = ttk.Frame(frm)
    btn_row.grid(row=5, column=0, columnspan=2, sticky="e")

    def do_save() -> None:
        base = base_var.get().strip()
        model = model_var.get().strip()
        key = key_var.get().strip()
        url_err = validate_llm_base_url(base)
        if url_err:
            messagebox.showerror("接口地址不合法", url_err, parent=dlg)
            return
        # 密钥载荷：输入了新 Key 用新 Key；留空沿用已保存 Key，
        # 绑定地址始终以本次确认的为准（.env 被改后须在此重新确认）
        if key:
            payload = {"api_key": key, "base_url": base or None}
        else:
            existing = load_secret(secret_f)
            if existing is None or not existing.get("api_key"):
                _write_env(env_path, {"LLM_BASE_URL": base, "LLM_MODEL": model}, ["LLM_API_KEY"])
                log_box.insert(tk.END, "[launcher] 未输入 API Key：AI 功能保持未配置状态\n")
                dlg.destroy()
                return
            payload = {"api_key": existing["api_key"], "base_url": base or None}
        try:
            save_secret(payload, secret_f)
        except OSError as e:
            messagebox.showerror("保存失败", f"密钥加密保存失败：{e}", parent=dlg)
            return
        saved = load_secret(secret_f)
        if saved is None or saved.get("api_key") != payload["api_key"]:
            messagebox.showerror("保存失败", "密钥写入后校验失败，未修改任何配置", parent=dlg)
            return
        _write_env(env_path, {"LLM_BASE_URL": base, "LLM_MODEL": model}, ["LLM_API_KEY"])
        if key:
            log_box.insert(
                tk.END,
                "[launcher] API Key 已加密保存（data/llm_secret.bin，Windows 账户绑定）\n",
            )
        hint = "请点击「重启」使配置生效" if _backend_running() else "下次启动自动生效"
        log_box.insert(tk.END, f"[launcher] 接口地址/模型已写入 .env；{hint}\n")
        dlg.destroy()

    def do_clear() -> None:
        if load_secret(secret_f) is None:
            log_box.insert(tk.END, "[launcher] 当前没有已保存的密钥\n")
            return
        if not messagebox.askyesno("清除密钥", "确定清除已保存的 API Key 吗？", parent=dlg):
            return
        delete_secret(secret_f)
        status_var2.set("未设置")
        key_var.set("")
        log_box.insert(
            tk.END,
            "[launcher] API Key 已清除（运行中的后端需重启后完全生效）\n",
        )

    ttk.Button(btn_row, text="保存", command=do_save).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="清除密钥", command=do_clear).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="取消", command=dlg.destroy).pack(side=tk.LEFT, padx=4)

    frm.columnconfigure(1, weight=1)


# ---------------------------------------------------------------------------
# 后端服务入口（--serve）：供 launcher 自身 subprocess 复用
# ---------------------------------------------------------------------------

def serve(port: int = DEFAULT_PORT) -> None:
    if not getattr(sys, "frozen", False):
        os.chdir(BACKEND_DIR)
        sys.path.insert(0, str(BACKEND_DIR))
    import uvicorn

    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)


# ---------------------------------------------------------------------------
# Tkinter GUI
# ---------------------------------------------------------------------------

def _build_gui() -> None:
    from tkinter import ttk

    manager = ProcessManager()
    log_queue: queue.Queue[str] = queue.Queue()

    root = tk.Tk()
    root.title("PhD Career Radar Launcher")
    root.geometry("720x480")
    root.minsize(560, 380)

    # Tk 变量必须在 root 创建之后初始化（否则 "Too early to create variable"）
    status_var = tk.StringVar(value="Stopped")
    pid_var = tk.StringVar(value="—")
    url_var = tk.StringVar(value=f"http://127.0.0.1:{manager.port}")
    auto_open = tk.BooleanVar(value=True)

    def read_logs() -> None:
        """把子进程输出搬进队列，再由 GUI 线程刷新。"""
        proc = manager.proc
        if proc is not None and proc.stdout is not None:
            try:
                for line in proc.stdout:
                    log_queue.put(line)
            except Exception:
                pass

    def pump_logs() -> None:
        while True:
            try:
                line = log_queue.get_nowait()
            except queue.Empty:
                break
            log_box.insert(tk.END, line)
            log_box.see(tk.END)
        root.after(100, pump_logs)

    def refresh_status() -> None:
        if manager.is_running():
            pid = manager.read_pid()
            status_var.set("Running")
            pid_var.set(str(pid) if pid else "?")
            start_btn.config(state=tk.DISABLED)
            stop_btn.config(state=tk.NORMAL)
        else:
            status_var.set("Stopped")
            pid_var.set("—")
            start_btn.config(state=tk.NORMAL)
            stop_btn.config(state=tk.DISABLED)
        root.after(1000, refresh_status)

    def _on_health_result(ok: bool) -> None:
        """health 检查结果（主线程回调）：只在这里操作 Tk 控件。"""
        if ok:
            log_box.insert(tk.END, "[launcher] 后端就绪，页面地址 " + url_var.get() + "\n")
            status_var.set("Running")
            if auto_open.get():
                webbrowser.open(url_var.get())
        else:
            log_box.insert(tk.END, "[launcher] 启动失败：/api/health 超时未响应\n")
            status_var.set("Error")
            stop_btn.config(state=tk.NORMAL)

    def start() -> None:
        stale = manager.stale_pid()
        if stale is not None:
            log_box.insert(tk.END, f"[launcher] 检测到上次残留进程 PID {stale}，正在清理…\n")
            manager.cleanup_stale()
        _migrate_plaintext_key(log_box)
        status_var.set("Starting…")
        manager.start()
        threading.Thread(target=read_logs, daemon=True).start()
        log_box.insert(tk.END, f"[launcher] 后端已启动（PID {manager.proc.pid}）\n")
        threading.Thread(target=_health_worker, daemon=True).start()

    def _health_worker() -> None:
        """后台线程只做 health 检查；结果经 root.after 回主线程更新 UI。"""
        ok = wait_for_health(port=manager.port)
        root.after(0, lambda: _on_health_result(ok))

    def stop() -> None:
        log_box.insert(tk.END, "[launcher] 正在停止后端…\n")
        manager.stop()
        log_box.insert(tk.END, "[launcher] 已停止，进程树已清理\n")

    def restart() -> None:
        stop()
        start()

    def open_page() -> None:
        webbrowser.open(url_var.get())

    def _open_api_settings() -> None:
        _open_api_settings_dialog(root, log_box, _DATA_ROOT / ".env", _secret_file())

    def on_close() -> None:
        # 无条件 stop：manager.stop() 对"Launcher 自己持有的活进程"直接 terminate，
        # 不依赖 PID 身份验证 —— 关掉启动器就绝不残留后端。
        manager.stop()
        root.destroy()

    # ---- 布局 ----
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    status_row = ttk.Frame(frame)
    status_row.pack(fill=tk.X)
    ttk.Label(status_row, text="状态：").pack(side=tk.LEFT)
    ttk.Label(status_row, textvariable=status_var, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
    ttk.Label(status_row, text="   PID：").pack(side=tk.LEFT, padx=(16, 0))
    ttk.Label(status_row, textvariable=pid_var).pack(side=tk.LEFT)
    ttk.Label(status_row, text="   地址：").pack(side=tk.LEFT, padx=(16, 0))
    ttk.Label(status_row, textvariable=url_var).pack(side=tk.LEFT)

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X, pady=(10, 4))
    start_btn = ttk.Button(buttons, text="启动", command=start)
    start_btn.pack(side=tk.LEFT)
    stop_btn = ttk.Button(buttons, text="停止", command=stop, state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="重启", command=restart).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="打开页面", command=open_page).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="API 设置", command=_open_api_settings).pack(side=tk.LEFT, padx=4)
    ttk.Checkbutton(buttons, text="启动成功后自动打开浏览器", variable=auto_open).pack(side=tk.LEFT, padx=(16, 0))

    log_frame = ttk.LabelFrame(frame, text="实时日志")
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
    log_box = tk.Text(log_frame, height=18, font=("Consolas", 9), state=tk.NORMAL)
    log_box.pack(fill=tk.BOTH, expand=True)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(100, pump_logs)
    root.after(1000, refresh_status)
    # V0.1.1 UX：双击 exe → 自动启动后端 → health OK → 自动打开浏览器
    root.after(200, start)
    root.mainloop()


def main() -> None:
    args = [a for a in sys.argv[1:]]
    if "--serve" in args:
        port = DEFAULT_PORT
        if "--port" in args:
            port = int(args[args.index("--port") + 1])
        serve(port)
        return
    _build_gui()


if __name__ == "__main__":
    # PyInstaller 打包后 multiprocessing/subprocess 复用同一 exe 时需要
    if getattr(sys, "frozen", False):
        from multiprocessing import freeze_support

        freeze_support()
    main()
