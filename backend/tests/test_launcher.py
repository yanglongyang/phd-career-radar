"""V0.1.1：静态托管与 Launcher ProcessManager 测试。"""

import importlib.util
import subprocess
import sys
from pathlib import Path


def _load_launcher():
    """launcher/launcher.py 不在 backend 包内，通过文件路径导入。"""
    launcher_path = Path(__file__).resolve().parents[2] / "launcher" / "launcher.py"
    spec = importlib.util.spec_from_file_location("launcher.launcher", launcher_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------- 静态托管：frontend/dist 存在时由 FastAPI 提供 SPA ----------

def test_spa_served_when_dist_exists(tmp_path):
    """构造临时 frontend/dist，确认 / 与前端路由回退到 index.html、/api 不受影响。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.main import mount_static

    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    html = "<!doctype html><html><head><title>PCR</title></head><body>SPA</body></html>"
    (dist / "index.html").write_text(html, encoding="utf-8")
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    mount_static(app, dist)

    with TestClient(app) as c:
        assert "SPA" in c.get("/").text
        # 前端路由（如 /jobs/1）回退 index.html
        assert "SPA" in c.get("/jobs/1").text
        # 静态资源可访问
        assert c.get("/assets/app.js").status_code == 200
        # API 不受影响
        assert c.get("/api/health").status_code == 200


def test_mount_static_noop_without_dist(tmp_path):
    """dist 不存在时 mount_static 不注册任何 SPA 路由。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.main import mount_static

    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    mount_static(app, tmp_path / "missing-dist")

    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/").status_code == 404  # 无 SPA 时根路径不存在


# ---------- ProcessManager（mock subprocess，不真正启动后端） ----------

def test_process_manager_pid_file_lifecycle(monkeypatch, tmp_path):
    launcher_mod = _load_launcher()
    ProcessManager = launcher_mod.ProcessManager

    pid_file = tmp_path / "backend.pid"
    manager = ProcessManager(pid_file=pid_file, port=8123)

    # 模拟 Popen：记录命令与 pid
    class FakePopen:
        pid = 4242

        def __init__(self, cmd, **kwargs):
            self.cmd = cmd
            self.kwargs = kwargs
            self.poll_result = None
            self.stdout = None

        def poll(self):
            return self.poll_result

        def terminate(self):
            self.poll_result = 0

        def wait(self, timeout=None):
            return 0

    created = {}

    def fake_popen(cmd, **kwargs):
        created["cmd"] = cmd
        created["kwargs"] = kwargs
        return FakePopen(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    proc = manager.start()
    assert created["cmd"][-1] == "8123"
    assert "--serve" in created["cmd"]
    assert "reload" not in " ".join(created["cmd"])  # 无 --reload
    assert proc.pid == 4242
    assert manager.read_pid() == 4242
    assert pid_file.exists()

    # 停止后 pid 文件删除、对象复位
    manager.stop()
    assert not pid_file.exists()
    assert manager.proc is None


def test_process_manager_stale_detection_and_kill(monkeypatch, tmp_path):
    launcher_mod = _load_launcher()
    ProcessManager = launcher_mod.ProcessManager

    pid_file = tmp_path / "backend.pid"
    manager = ProcessManager(pid_file=pid_file, port=8124)
    pid_file.write_text("99999", encoding="utf-8")

    killed = []

    def fake_is_alive(pid):
        return pid == 99999

    def fake_kill_tree(pid):
        killed.append(pid)

    monkeypatch.setattr(launcher_mod, "_is_alive", fake_is_alive)
    monkeypatch.setattr(ProcessManager, "_kill_tree", staticmethod(fake_kill_tree))

    assert manager.stale_pid() == 99999
    cleaned = manager.cleanup_stale()
    assert cleaned == 99999
    assert killed == [99999]
    assert not pid_file.exists()  # 清理后 pid 文件删除


def test_process_manager_kill_tree_uses_taskkill_on_windows(monkeypatch):
    """Windows 上 _kill_tree 使用 taskkill /T /F（连子进程树一起清理）。"""
    launcher_mod = _load_launcher()
    ProcessManager = launcher_mod.ProcessManager

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return None

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", fake_run)
    ProcessManager._kill_tree(1234)
    assert calls and calls[0][:3] == ["taskkill", "/PID", "1234"]
    assert "/T" in calls[0] and "/F" in calls[0]
