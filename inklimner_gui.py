#!/usr/bin/env python3
"""
inklimner_gui.py —— InkLimner 图形界面**统一入口**

自动挑选当前环境里可用的界面，优先现代外观的 Qt 版：

    1) PySide6 / Qt   → inklimner_gui_qt.py   （推荐：暗色卡片式，原生拖拽）
    2) Tkinter        → inklimner_gui_tk.py   （零第三方依赖回退方案）

共享的参数规格、预设、CLI 命令互转、批量执行逻辑都在 inklimner_gui_core.py，
两个界面共用同一份，参数永不漂移。

启动方式（任选其一）：
    python inklimner_gui.py
    python inklimner.py --gui
    inklimner-gui                       # pip install . 之后

强制指定后端：
    python inklimner_gui.py --tk        # 用 Tkinter 版
    python inklimner_gui.py --qt        # 用 Qt 版
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# 共享核心层（零 GUI 依赖），在这里 re-export 便于外部直接引用
from inklimner_gui_core import (  # noqa: E402, F401
    APP_TAGLINE,
    APP_TITLE,
    COMMON_KEYS,
    GROUPS,
    MODE_EXTRA,
    MODE_TIPS,
    PRESETS,
    SETTINGS_PATH,
    QueueLogHandler,
    active_keys,
    all_keys,
    build_command,
    default_values,
    env_summary,
    load_settings,
    parse_command,
    plan_pairs,
    run_batch,
    safe_name,
    save_settings,
    values_to_namespace,
)

QT_HINT = 'pip install "inklimner[gui]"      # 即 PySide6-Essentials'
TK_HINT = '使用带 tkinter 的官方 Python，或 Linux 下 sudo apt install python3-tk'


def has_pyside6() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except Exception:                                 # noqa: BLE001
        return False


def has_tkinter() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:                                 # noqa: BLE001
        return False


def pick_backend(forced: str = '') -> str:
    """决定用哪个后端：显式指定优先，其次 Qt，最后 Tk"""
    if forced in ('qt', 'tk'):
        return forced
    if has_pyside6():
        return 'qt'
    if has_tkinter():
        return 'tk'
    return ''


def run_qt(args) -> int:
    import inklimner_gui_qt as mod
    return mod.run(args, selftest='--selftest' in args)


def run_tk() -> int:
    import inklimner_gui_tk as mod
    return mod.main()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    forced = os.environ.get('INKLIMNER_GUI', '').strip().lower()
    for flag, name in (('--qt', 'qt'), ('--tk', 'tk')):
        if flag in args:
            forced = name
            args = [a for a in args if a != flag]

    backend = pick_backend(forced)
    if backend == 'qt':
        try:
            return run_qt(args)
        except ImportError as e:
            print(f'[警告] Qt 界面无法加载（{e}），尝试回退到 Tkinter…', file=sys.stderr)
            if has_tkinter():
                return run_tk()
    elif backend == 'tk':
        try:
            return run_tk()
        except ImportError as e:
            print(f'[警告] Tkinter 界面无法加载（{e}）', file=sys.stderr)

    print('没有可用的图形界面后端。', file=sys.stderr)
    print(f'  · 想要现代外观：{QT_HINT}', file=sys.stderr)
    print(f'  · 想要零依赖　：{TK_HINT}', file=sys.stderr)
    print('  · 也可以直接用命令行：inklimner --help', file=sys.stderr)
    return 3


if __name__ == '__main__':
    sys.exit(main())
