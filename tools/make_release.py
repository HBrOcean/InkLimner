#!/usr/bin/env python3
"""
make_release.py —— 把 PyInstaller 的产物打成便于分发的 zip

CI（GitHub Actions）和本地都能用，跨平台，不依赖 shell 语法。

用法：
    python tools/make_release.py --slug windows --version 3.4.1.1

产出（release/ 目录下）：
    InkLimner-3.4.1.1-windows-cli.zip    ← 命令行单文件版
    InkLimner-3.4.1.1-windows-gui.zip    ← 图形界面版（目录包，双击 exe 即用）
"""

from __future__ import annotations

import argparse
import platform
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUGS = {'Windows': 'windows', 'Darwin': 'macos', 'Linux': 'linux'}
COMPRESS_LEVEL = 6          # 体积 / 时间折中


def zip_dir(src: Path, out_zip: Path) -> None:
    """把整个目录压成 zip（保留最外层目录名，解压即得可直接运行的文件夹）"""
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED,
                         compresslevel=COMPRESS_LEVEL) as z:
        for p in sorted(src.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(src.parent))


def zip_file(src: Path, out_zip: Path) -> None:
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED,
                         compresslevel=COMPRESS_LEVEL) as z:
        z.write(src, src.name)


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):            # Windows 终端编码兜底
        try:
            _s.reconfigure(encoding='utf-8', errors='backslashreplace')
        except Exception:                          # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description='打包 InkLimner 的发行 zip')
    ap.add_argument('--slug', default='',
                    help='平台标识（windows / macos / linux），默认按当前系统')
    ap.add_argument('--version', default='dev', help='版本号，用于文件名')
    ap.add_argument('--dist', default='dist', help='PyInstaller 输出目录')
    ap.add_argument('--out', default='release', help='zip 输出目录')
    a = ap.parse_args(argv)

    slug = a.slug or SLUGS.get(platform.system(), platform.system().lower())
    dist, out = ROOT / a.dist, ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    made = []

    for name in ('inklimner.exe', 'inklimner'):
        exe = dist / name
        if exe.exists():
            z = out / f'InkLimner-{a.version}-{slug}-cli.zip'
            zip_file(exe, z)
            made.append(z)
            break

    for name in ('InkLimner.app', 'InkLimner'):
        bundle = dist / name
        if bundle.exists():
            z = out / f'InkLimner-{a.version}-{slug}-gui.zip'
            zip_dir(bundle, z)
            made.append(z)
            break

    if not made:
        print(f'[release] {dist} 里没找到可打包的产物（先跑 PyInstaller）')
        return 1
    for z in made:
        print(f'[release] {z.name}  {z.stat().st_size / 1048576:.1f} MB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
