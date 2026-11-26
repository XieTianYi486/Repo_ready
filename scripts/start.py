#!/usr/bin/env python3
"""RepoReady one-command launcher (cross-platform).

Creates/uses .venv, installs Python dependencies, installs/builds the frontend,
then starts uvicorn and opens the browser when /api/health is ready.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
FRONTEND = ROOT / "frontend"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def step(message: str) -> None:
    print(f"\n[RepoReady] {message}", flush=True)


def fail(message: str) -> None:
    print(f"\n[RepoReady][ERROR] {message}", flush=True)
    raise SystemExit(1)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_python() -> None:
    if sys.version_info < (3, 11):
        fail(
            f"需要 Python 3.11+，当前为 {sys.version.split()[0]}。"
            "请安装 Python 3.12 后重试（Windows 推荐 py -3.12）。"
        )
    if not VENV.exists():
        step(f"创建虚拟环境：{VENV}")
        result = subprocess.run([sys.executable, "-m", "venv", str(VENV)])
        if result.returncode != 0:
            fail("创建虚拟环境失败。请确认 Python venv 模块可用。")


def run_checked(command: list[str], *, cwd: Path, env: dict | None = None) -> None:
    print("  $ " + " ".join(str(part) for part in command), flush=True)
    result = subprocess.run(command, cwd=str(cwd), env=env)
    if result.returncode != 0:
        fail(f"命令执行失败（退出码 {result.returncode}）")


def ensure_python_deps() -> None:
    python = venv_python()
    if not python.exists():
        fail("虚拟环境 Python 不存在，请删除 .venv 后重试。")
    try:
        check = subprocess.run(
            [str(python), "-c", "import fastapi, httpx, pydantic"],
            capture_output=True,
            text=True,
        )
        imports_ok = check.returncode == 0
    except OSError:
        imports_ok = False
    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    marker = VENV / ".repoready-requirements-hash"
    if imports_ok and marker.exists() and marker.read_text(encoding="utf-8").strip() == digest:
        return
    step("安装后端依赖（首次运行或 requirements 有变化）")
    base = [
        str(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--timeout",
        "60",
        "--retries",
        "3",
        "-r",
        str(REQUIREMENTS),
    ]
    result = subprocess.run(base)
    if result.returncode != 0:
        step("官方 PyPI 连接失败，切换到清华镜像重试")
        result = subprocess.run(base + ["-i", MIRROR])
    if result.returncode != 0:
        fail("后端依赖安装失败。请检查网络，或手动执行 pip install -r backend/requirements.txt。")
    marker.write_text(digest, encoding="utf-8")


def find_node() -> tuple[Path, Path]:
    candidates: list[Path] = []
    which_node = shutil.which("node")
    if which_node:
        candidates.append(Path(which_node))
    if os.name == "nt":
        for raw in (
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            r"E:\nodejs\node.exe",
        ):
            candidates.append(Path(raw))
    for node in candidates:
        if not node.exists():
            continue
        directory = node.parent
        npm_candidates = [
            directory / ("npm.cmd" if os.name == "nt" else "npm"),
            directory / "npm",
            directory / "npm.exe",
        ]
        for npm in npm_candidates:
            if npm.exists():
                return node, npm
        which_npm = shutil.which("npm")
        if which_npm:
            return node, Path(which_npm)
    fail(
        "未找到 Node.js（需要 20.19+）。请安装 Node.js 后重试；"
        "Windows 也可从 https://nodejs.org 安装 LTS 版本。"
    )
    raise AssertionError("unreachable")


def _frontend_needs_build(rebuild: bool) -> bool:
    dist_index = FRONTEND / "dist" / "index.html"
    if rebuild or not dist_index.exists():
        return True
    dist_mtime = dist_index.stat().st_mtime
    candidates = [
        FRONTEND / "package.json",
        FRONTEND / "vite.config.ts",
        FRONTEND / "tsconfig.json",
        FRONTEND / "index.html",
    ]
    src = FRONTEND / "src"
    if src.exists():
        candidates.extend(path for path in src.rglob("*") if path.is_file())
    return any(path.exists() and path.stat().st_mtime > dist_mtime for path in candidates)


def ensure_frontend(node: Path, npm: Path, rebuild: bool) -> None:
    env = os.environ.copy()
    env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
    node_modules = FRONTEND / "node_modules"
    lockfile = FRONTEND / "package-lock.json"
    marker = node_modules / ".repoready-install-hash"
    lock_hash = (
        hashlib.sha256(lockfile.read_bytes()).hexdigest() if lockfile.exists() else ""
    )
    if not node_modules.exists() or not marker.exists() or marker.read_text(encoding="utf-8").strip() != lock_hash:
        step("安装前端依赖（首次运行或 package-lock 有变化）")
        run_checked([str(npm), "install", "--no-audit", "--no-fund"], cwd=FRONTEND, env=env)
        marker.write_text(lock_hash, encoding="utf-8")

    if _frontend_needs_build(rebuild):
        step("构建前端产物")
        tsc = FRONTEND / "node_modules" / "typescript" / "bin" / "tsc"
        vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
        if tsc.exists() and vite.exists():
            run_checked([str(node), str(tsc), "--noEmit"], cwd=FRONTEND, env=env)
            run_checked([str(node), str(vite), "build"], cwd=FRONTEND, env=env)
        else:
            run_checked([str(npm), "run", "build"], cwd=FRONTEND, env=env)


def pick_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    fail(f"端口 {preferred}–{preferred + 19} 均被占用，请用 --port 指定其他端口。")


def ensure_env_file() -> None:
    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if not env_file.exists() and example.exists():
        shutil.copyfile(example, env_file)
        print(
            "  已从 .env.example 创建 .env（所有 Key 为空，可稍后填写；不会提交到 Git）",
            flush=True,
        )


def open_browser_when_ready(url: str) -> None:
    for _ in range(120):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:
            continue
    print(f"[RepoReady] 服务可能仍在启动，请手动打开 {url}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="RepoReady one-command launcher")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--rebuild", action="store_true", help="强制重新构建前端")
    args = parser.parse_args()

    os.chdir(ROOT)
    step("检查 Python 与虚拟环境")
    ensure_python()
    ensure_python_deps()
    ensure_env_file()

    step("检查 Node.js 与前端构建")
    node, npm = find_node()
    print(f"  Node: {node}")
    ensure_frontend(node, npm, args.rebuild)

    port = pick_port(args.port)
    url = f"http://127.0.0.1:{port}"
    step(f"启动 RepoReady：{url}")
    print("  按 Ctrl+C 停止服务。\n", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PORT"] = str(port)
    command = [
        str(venv_python()),
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "info",
    ]
    try:
        subprocess.run(command, cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print("\n[RepoReady] 已停止。", flush=True)


if __name__ == "__main__":
    main()
