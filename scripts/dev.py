#!/usr/bin/env python3
"""Development launcher: uvicorn --reload on :8000 + Vite on :5173."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
FRONTEND = ROOT / "frontend"


def find_node() -> tuple[str, str] | None:
    node = shutil.which("node") or shutil.which("node.exe")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if node and npm:
        return node, npm
    if os.name == "nt":
        for raw in (r"C:\Program Files\nodejs", r"E:\nodejs"):
            node_path = Path(raw) / "node.exe"
            npm_path = Path(raw) / "npm.cmd"
            if node_path.exists() and npm_path.exists():
                return str(node_path), str(npm_path)
    return None


def main() -> int:
    if not VENV_PYTHON.exists():
        print("请先运行 start.bat 或 scripts/start.py 完成初始化。", file=sys.stderr)
        return 1
    node_info = find_node()
    if node_info is None:
        print("未找到 Node.js。", file=sys.stderr)
        return 1
    node, npm = node_info
    env = os.environ.copy()
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONUTF8"] = "1"

    backend = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ],
        cwd=str(ROOT),
        env=env,
    )
    vite_js = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if vite_js.exists():
        frontend = subprocess.Popen([node, str(vite_js)], cwd=str(FRONTEND), env=env)
    else:
        frontend = subprocess.Popen([npm, "run", "dev"], cwd=str(FRONTEND), env=env)

    print("\n  Backend: http://127.0.0.1:8000")
    print("  Frontend: http://127.0.0.1:5173")
    print("  Ctrl+C 停止两个进程\n", flush=True)

    try:
        while True:
            time.sleep(0.5)
            if backend.poll() is not None or frontend.poll() is not None:
                break
    except KeyboardInterrupt:
        pass
    finally:
        for process in (frontend, backend):
            if process.poll() is None:
                try:
                    if os.name == "nt":
                        process.terminate()
                    else:
                        process.send_signal(signal.SIGINT)
                except OSError:
                    pass
        time.sleep(0.3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
