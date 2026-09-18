#!/usr/bin/env python3
"""
bump_version.py —— 一条命令同步项目里的版本号（防止发版时漏改）

版本号散落在代码、打包配置、README、徽章、文档里，手动改容易漏。
这个脚本以 `inklimner.py` 的 `__version__` 为唯一「当前版本」，
把它统一替换成新版本。

用法：
    python tools/bump_version.py            # 只检查：列出版本号出现在哪些文件
    python tools/bump_version.py 3.4.2      # 同步：把当前版本替换成 3.4.2

注意：CHANGELOG 与 docs/releases/ 是**历史记录**，故意不在同步范围内
（否则会把历史版本的链接一起改坏）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 需要跟着版本号走的文件
TARGETS = [
    'inklimner.py',
    'pyproject.toml',
    'README.md',
    'README.en.md',
    'docs/BUILD.md',
    '.github/workflows/build.yml',
    'tools/make_release.py',
]
SCAN_SUFFIX = {'.py', '.toml', '.md', '.yml', '.yaml', '.txt', '.cfg', '.json'}
SKIP_DIRS = {'.git', '__pycache__', 'build', 'dist', 'release', '.venv'}


def current_version() -> str:
    text = (ROOT / 'inklimner.py').read_text(encoding='utf-8')
    m = re.search(r"__version__\s*=\s*'([^']+)'", text)
    if not m:
        raise SystemExit('读不到 inklimner.py 里的 __version__')
    return m.group(1)


def scan(ver: str):
    """列出还有哪些文件里出现当前版本号"""
    pat = re.compile(re.escape(ver))
    hits = []
    for p in sorted(ROOT.rglob('*')):
        if p.is_dir() or p.suffix not in SCAN_SUFFIX:
            continue
        if SKIP_DIRS & set(p.relative_to(ROOT).parts):
            continue
        try:
            n = len(pat.findall(p.read_text(encoding='utf-8')))
        except Exception:                              # noqa: BLE001
            continue
        if n:
            hits.append((p.relative_to(ROOT).as_posix(), n))
    return hits


def bump(old: str, new: str) -> int:
    if not re.fullmatch(r'\d+(\.\d+)+', new):
        raise SystemExit(f'版本号格式不对：{new}（应形如 3.4.2 或 3.4.2.1）')
    total = 0
    for rel in TARGETS:
        p = ROOT / rel
        if not p.exists():
            print(f'  · 跳过（不存在）：{rel}')
            continue
        text = p.read_text(encoding='utf-8')
        n = text.count(old)
        if not n:
            continue
        p.write_text(text.replace(old, new), encoding='utf-8')
        print(f'  ✓ {rel}：{n} 处')
        total += n
    print(f'共替换 {total} 处：{old} → {new}')
    print('别忘了：在 CHANGELOG.md 顶部新增一节，并新建 docs/releases/v'
          f'{new}.md')
    return total


def main(argv=None) -> int:
    args = [a for a in (argv if argv is not None else sys.argv[1:])]
    ver = current_version()
    print(f'当前版本（来自 inklimner.py 的 __version__）：{ver}')
    hits = scan(ver)
    if not hits:
        print('  没找到任何出现位置？检查一下 __version__ 是否正确')
    for rel, n in hits:
        tag = '会同步' if rel in TARGETS else '历史/其它（不动）'
        print(f'  [{tag}] {rel}  ×{n}')
    if not args:
        print('\n（加一个版本号参数即可同步，例如：python tools/bump_version.py 3.4.2）')
        return 0
    print(f'\n同步到 {args[0]} …')
    bump(ver, args[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
