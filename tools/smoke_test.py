#!/usr/bin/env python3
"""
smoke_test.py —— 冒烟测试 PyInstaller 产物：确认打出来的东西真的能跑

跨平台（Windows / macOS / Linux 都能用），CI 里用来拦住"能打包但一运行就崩"。

用法：
    python tools/smoke_test.py              # CLI 必须通过；GUI 尽力而为
    python tools/smoke_test.py --strict     # GUI 也必须通过
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = os.name == 'nt'


def _force_utf8_output() -> None:
    """Windows 终端默认 cp1252，本脚本自己也会 print 中文，先兜住"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except Exception:                              # noqa: BLE001
            pass


def _exe(directory: Path, stem: str) -> Path:
    return directory / f'{stem}.exe' if WINDOWS else directory / stem


def find_cli(dist: Path) -> Path | None:
    """产物可能在 dist/ 下，也可能在 dist/cli（CI 的布局）。

    CI 之所以分开存放，是因为 macOS 文件系统不区分大小写 ——
    inklimner(CLI) 与 InkLimner(GUI) 算同一个名字，放同一个目录会互相顶掉。
    """
    for base in (dist, dist / 'cli'):
        p = _exe(base, 'inklimner')
        if p.is_file():                 # is_file：目录不算数（曾因此误判）
            return p
    return None


def find_gui(dist: Path) -> Path | None:
    for base in (dist, dist / 'gui'):
        app = base / 'InkLimner.app' / 'Contents' / 'MacOS' / 'InkLimner'
        if app.is_file():
            return app
        p = _exe(base / 'InkLimner', 'InkLimner')
        if p.is_file():
            return p
    return None


def ensure_executable(p: Path) -> None:
    """Unix 下补上可执行位 —— zip / artifact 流转时权限位常常会丢"""
    if os.name != 'nt':
        try:
            p.chmod(p.stat().st_mode | 0o755)
        except OSError:
            pass


def gui_env() -> dict:
    """GUI 自检的运行环境。

    Linux / macOS 的 CI runner 没有显示器，必须走 offscreen；
    Windows runner 自带桌面会话，直接用默认平台更贴近真实运行环境。
    （无论哪种，子进程都会被强制 UTF-8 —— 见 run()。）
    """
    return {} if os.name == 'nt' else {'QT_QPA_PLATFORM': 'offscreen'}


def run(cmd, env_extra=None, timeout=900) -> int:
    env = dict(os.environ)
    # Windows 终端默认 cp1252，被调用程序一旦 print 中文就会崩 —— 强制 UTF-8
    env['PYTHONIOENCODING'] = 'utf-8'
    env.update(env_extra or {})
    print('$', ' '.join(str(c) for c in cmd), flush=True)
    try:
        r = subprocess.run([str(c) for c in cmd], env=env, timeout=timeout,
                           capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print('  ✗ 超时')
        return 1
    tail = (r.stdout or '').strip().splitlines()[-6:]
    for line in tail:
        print('  ', line)
    if r.returncode:
        print('  stderr:', (r.stderr or '').strip()[-500:])
    return r.returncode


def main(argv=None) -> int:
    _force_utf8_output()
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', default='dist')
    ap.add_argument('--strict', action='store_true',
                    help='GUI 自检失败也判为失败（默认只警告）')
    a = ap.parse_args(argv)
    dist = ROOT / a.dist

    failures = []
    cli, gui = find_cli(dist), find_gui(dist)

    if cli is None:
        print('[smoke] 没找到 CLI 产物')
        failures.append('cli-missing')
    else:
        ensure_executable(cli)
        print('[smoke] CLI --version')
        if run([cli, '--version']):
            failures.append('cli-version')

    if gui is None:
        print('[smoke] 没找到 GUI 产物')
    else:
        ensure_executable(gui)
        print('[smoke] GUI 自检（--selftest）')
        code = run([gui, '--selftest'], gui_env())
        if code and os.name == 'nt':
            print('  默认平台没起来，改用 offscreen 再试一次…')
            code = run([gui, '--selftest'], {'QT_QPA_PLATFORM': 'offscreen'})
        if code:
            print('  ! GUI 自检未通过（无显示器环境偶发，仅供参考）')
            if a.strict:
                failures.append('gui-selftest')

    if failures:
        print('[smoke] 失败 ✗', failures)
        return 1
    print('[smoke] 通过 ✓')
    return 0


if __name__ == '__main__':
    sys.exit(main())
