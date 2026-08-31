"""PhD Career Radar Launcher（V0.1.1）—— 日常使用入口。

双击启动（或 `python launcher/launcher.py`）：
- 以**无 --reload** 方式启动后端（uvicorn 单进程）；
- 后端由 FastAPI 直接托管前端构建产物（frontend/dist），日常运行**不需要 Vite/Node**；
- 保存 PID 文件；停止/关闭时优雅 terminate → 强制 taskkill /T /F 清理整个进程树；
- 启动时检测上次异常残留的 PID 并提示清理；
- stdout/stderr 实时进入日志窗口；启动成功后自动打开默认浏览器。

两种入口：
- `--serve`：仅启动后端（供本文件自身 subprocess 复用，也便于冒烟验证）；
- 无参数：Tkinter GUI 启动器。

开发模式不受影响：`uvicorn --reload` + `npm run dev` 照常使用。
"""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller：app 包与资源在 _MEIPASS（只读），数据与 PID 文件在 exe 旁
    BACKEND_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    PROJECT_ROOT = BACKEND_DIR
    _DATA_ROOT = Path(sys.executable).parent
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
    PROJECT_ROOT = BACKEND_DIR.parent
    _DATA_ROOT = PROJECT_ROOT
PID_FILE = _DATA_ROOT / "data" / "backend.pid"
HEALTH_URL = "http://127.0.0.1:8000/api/health"
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


class ProcessManager:
    """后端进程生命周期管理：启动 / 停止 / 残留检测 / PID 持久化。"""

    def __init__(self, pid_file: Path = PID_FILE, port: int = DEFAULT_PORT):
        self.pid_file = pid_file
        self.port = port
        self.proc: subprocess.Popen | None = None

    # ---- 状态 ----

    def read_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except ValueError:
            return None

    def is_running(self) -> bool:
        pid = self.read_pid()
        return pid is not None and _is_alive(pid)

    def stale_pid(self) -> int | None:
        """上次异常退出可能留下的 PID（pid 文件存在但当前进程不归我们管理）。"""
        pid = self.read_pid()
        if pid is not None and _is_alive(pid):
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
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(self.proc.pid), encoding="utf-8")
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
        elif pid is not None and _is_alive(pid):
            # pid 文件指向存活进程但对象丢失（如重启后的残留）→ 直接清理
            self._kill_tree(pid)
        if self.pid_file.exists():
            self.pid_file.unlink()
        self.proc = None

    def cleanup_stale(self) -> int | None:
        """清理上次异常残留的进程树；返回被清理的 PID 或 None。"""
        pid = self.stale_pid()
        if pid is not None:
            self._kill_tree(pid)
            if self.pid_file.exists():
                self.pid_file.unlink()
        return pid

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
    import tkinter as tk
    from tkinter import ttk

    manager = ProcessManager()
    log_queue: queue.Queue[str] = queue.Queue()
    status_var = tk.StringVar(value="Stopped")
    pid_var = tk.StringVar(value="—")
    url_var = tk.StringVar(value=f"http://127.0.0.1:{manager.port}")
    auto_open = tk.BooleanVar(value=True)

    root = tk.Tk()
    root.title("PhD Career Radar Launcher")
    root.geometry("720x480")
    root.minsize(560, 380)

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

    def start() -> None:
        stale = manager.stale_pid()
        if stale is not None:
            log_box.insert(tk.END, f"[launcher] 检测到上次残留进程 PID {stale}，正在清理…\n")
            manager.cleanup_stale()
        status_var.set("Starting…")
        manager.start()
        threading.Thread(target=read_logs, daemon=True).start()
        log_box.insert(tk.END, f"[launcher] 后端已启动（PID {manager.proc.pid}）\n")
        threading.Thread(target=_after_start, daemon=True).start()

    def _after_start() -> None:
        ok = wait_for_health()
        log_box.insert(tk.END, "[launcher] 后端就绪，页面地址 " + url_var.get() + "\n")
        if ok and auto_open.get():
            webbrowser.open(url_var.get())

    def stop() -> None:
        log_box.insert(tk.END, "[launcher] 正在停止后端…\n")
        manager.stop()
        log_box.insert(tk.END, "[launcher] 已停止，进程树已清理\n")

    def restart() -> None:
        stop()
        start()

    def open_page() -> None:
        webbrowser.open(url_var.get())

    def on_close() -> None:
        if manager.is_running():
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
    ttk.Checkbutton(buttons, text="启动成功后自动打开浏览器", variable=auto_open).pack(side=tk.LEFT, padx=(16, 0))

    log_frame = ttk.LabelFrame(frame, text="实时日志")
    log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
    log_box = tk.Text(log_frame, height=18, font=("Consolas", 9), state=tk.NORMAL)
    log_box.pack(fill=tk.BOTH, expand=True)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(100, pump_logs)
    root.after(1000, refresh_status)
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
