#!/usr/bin/env python3
"""
inklimner_gui_core.py —— InkLimner 图形界面的**共享核心层**

这里只放与界面工具包无关的东西：参数规格、预设、命令行互转、配置读写、
输出规划与批量执行。**不 import tkinter / PySide6**，所以任何界面都能复用，
也能在没有图形环境的机器上直接单元测试。

界面实现：
    · inklimner_gui_qt.py —— PySide6 / Qt（推荐，现代外观，支持拖拽）
    · inklimner_gui_tk.py —— Tkinter（零第三方依赖回退方案）
    · inklimner_gui.py    —— 统一入口（优先 Qt，自动回退 Tk）
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import logging
import queue
import re
import shlex
import sys
import threading
import traceback
from pathlib import Path

try:
    import inklimner as core
except ImportError:                                   # 直接运行本文件时
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import inklimner as core

HERE = Path(__file__).resolve().parent
SETTINGS_PATH = Path.home() / '.inklimner_gui.json'
APP_TITLE = f'InkLimner v{core.__version__} — 位图转 SVG 线稿'
APP_TAGLINE = '位图 → 可直接切割的黑白线稿 SVG'


# ============================= 参数规格 =============================
# (属性名, 显示名, 控件类型, 附加参数, 说明, CLI 参数名)
# 控件类型：combo / spin_f(浮点) / spin_i(整数) / check / entry
GROUPS = [
    ('① 提取模式', '选择用哪种算法把图片拆成线', [
        ('mode', '模式', 'combo', ['linedraw', 'edge', 'multi', 'shape'],
         'linedraw=XDoG线稿+中心线（推荐）；edge=Canny；multi=灰度等值线；shape=色块轮廓',
         '--mode'),
        ('detail', '细节 detail', 'spin_f', (0.0, 1.0, 0.05),
         '越大细节越多（linedraw / multi）', '--detail'),
        ('threshold', '阈值 threshold', 'entry', None,
         'auto 或 0~255（shape 模式）', '--threshold'),
        ('band_max', '灰带上限 band-max', 'spin_i', (1, 255, 1),
         'multi 覆盖上限；255=保留浅灰细节', '--band-max'),
        ('invert', '黑白反转 invert', 'check', None,
         '黑底浅色图请勾选（shape）', '--invert'),
        ('no_potrace', '禁用 potrace', 'check', None,
         '强制用 OpenCV 轮廓（shape / multi）', '--no-potrace'),
    ]),
    ('② 线稿参数', '决定线条的粗细、精度与连贯性', [
        ('canny_low', 'Canny 低阈值', 'spin_i', (0, 255, 5), '仅 edge 模式', '--canny-low'),
        ('canny_high', 'Canny 高阈值', 'spin_i', (0, 255, 5), '仅 edge 模式', '--canny-high'),
        ('dilate', '线条加粗 dilate', 'spin_i', (0, 2, 1),
         '0=不加粗；细线易断可设 1（linedraw / edge）', '--dilate'),
        ('blur', '预模糊 blur', 'spin_i', (1, 15, 2),
         '1=关闭；毛刺多可设 3~5（linedraw / edge）', '--blur'),
        ('min_line_len', '中心线最短长 min-line-len', 'spin_i', (0, 999, 1),
         '过滤毛刺碎线（px，linedraw / edge）', '--min-line-len'),
        ('join_gap', '断线修复 join-gap', 'spin_f', (0.0, 20.0, 0.5),
         '线条莫名断开时调大（px）；0=关闭；建议 3~8（linedraw / edge）', '--join-gap'),
        ('simplify', '简化 simplify', 'spin_f', (0.0, 0.02, 0.0005),
         '越小越精细、点越多', '--simplify'),
        ('smooth', '平滑 smooth', 'spin_f', (0.0, 1.0, 0.05),
         '0=硬朗折线，1=圆滑曲线', '--smooth'),
    ]),
    ('③ 轮廓参数', '只影响「闭合轮廓」类模式（shape / multi）', [
        ('min_len', '轮廓最小周长 min-len', 'spin_i', (0, 9999, 5),
         'shape / multi 无 potrace 时生效', '--min-len'),
        ('min_band', '灰带最小面积 min-band', 'spin_i', (0, 9999, 10),
         '仅 multi', '--min-band'),
    ]),
    ('④ 预处理', '处理前对图片做的整理动作', [
        ('scale', '放大 scale', 'spin_f', (1.0, 8.0, 0.5),
         '小图保细节建议 2（输出坐标自动换算）', '--scale'),
        ('max_size', '最长边上限 max-size', 'spin_i', (0, 20000, 200),
         '大图防卡死；0=不限制', '--max-size'),
        ('trim', '自动裁白边 trim', 'check', None, '去掉四周空白，切割省料', '--trim'),
        ('margin', '留白 margin', 'spin_i', (0, 500, 5),
         '成品四周补白（px）', '--margin'),
        ('no_exif', '不校正 EXIF 方向', 'check', None,
         '默认按 EXIF 自动校正手机照片方向', '--no-exif'),
    ]),
    ('⑤ 尺寸与外观', '毫米换算与 SVG 显示样式', [
        ('dpi', '原图 DPI', 'spin_f', (0.0, 1200.0, 10.0),
         '300=300DPI，自动换算成毫米尺寸', '--dpi'),
        ('px_per_mm', 'px/mm', 'spin_f', (0.0, 100.0, 0.01),
         '直接指定，优先于 DPI（0=像素单位）', '--px-per-mm'),
        ('stroke_width', '描边宽度', 'spin_f', (0.0, 5.0, 0.05),
         '仅 SVG 显示用，不影响切割', '--stroke-width'),
        ('stroke_color', '描边颜色', 'entry', None, '如 #000000', '--stroke-color'),
    ]),
    ('⑥ 输出选项', '产出文件的开关', [
        ('preview', '生成 PNG 预览', 'check', None,
         '额外产出 xxx.preview.png', '--preview'),
        ('force', '覆盖已存在文件', 'check', None,
         '取消勾选 = 跳过已存在的输出', '--no-overwrite'),
        ('quiet', '安静模式', 'check', None, '日志只显示错误', '--quiet'),
    ]),
]

# 与模式无关、始终可用的参数（mode 是模式选择器本身，始终可用）
COMMON_KEYS = {
    'mode',
    'scale', 'max_size', 'trim', 'margin', 'no_exif',
    'dpi', 'px_per_mm', 'stroke_width', 'stroke_color',
    'preview', 'force', 'quiet',
}
# 各模式额外生效的参数
MODE_EXTRA = {
    'linedraw': {'detail', 'dilate', 'blur', 'min_line_len', 'join_gap', 'simplify', 'smooth'},
    'edge': {'canny_low', 'canny_high', 'dilate', 'blur', 'min_line_len',
             'join_gap', 'simplify', 'smooth'},
    'multi': {'detail', 'band_max', 'min_band', 'min_len', 'no_potrace',
              'simplify', 'smooth'},
    'shape': {'threshold', 'invert', 'min_len', 'no_potrace', 'simplify', 'smooth'},
}

MODE_TIPS = {
    'linedraw': '🎯 默认。XDoG 线稿 + 骨架中心线，最像手绘线稿，激光只走单线',
    'edge': '📷 Canny 边缘 + 中心线，适合照片、边缘清晰的物体',
    'multi': '🗺️ 灰度波段等值线，层次分明（类似地形图），适合明暗/渐变',
    'shape': '✂️ 色块轮廓（闭合路径），剪纸风，适合沿边切穿',
}

# 内置参数预设（只覆盖列出的项，其余保持当前值）
PRESETS = {
    '剪纸轮廓（切穿）': {'mode': 'shape', 'threshold': 'auto', 'min_len': 30,
                         'smooth': 0.5, 'trim': True, 'dpi': 300},
    '照片描线': {'mode': 'edge', 'canny_low': 30, 'canny_high': 100,
                 'blur': 3, 'min_line_len': 12, 'simplify': 0.001, 'smooth': 0.4},
    '手绘线稿': {'mode': 'linedraw', 'detail': 0.8, 'simplify': 0.0008,
                 'smooth': 0.5, 'trim': True},
    '印章 / 高对比': {'mode': 'shape', 'threshold': 160, 'min_len': 60,
                      'smooth': 0.3, 'dilate': 1},
    '小图补细节': {'scale': 2, 'detail': 0.9, 'simplify': 0.0005, 'smooth': 0},
    '灰度层次': {'mode': 'multi', 'detail': 0.8, 'band_max': 255, 'min_band': 20},
}

# 布尔型开关（命令导出时写成 “出现即真” 的旗标）
_TRUE_FLAGS = {'invert', 'no_potrace', 'trim', 'no_exif', 'preview', 'quiet'}


# ============================= 纯函数（可单测） =============================

def _flat_spec():
    return [item for _, _, items in GROUPS for item in items]


def all_keys() -> set:
    """GUI 里声明的全部参数名"""
    return {item[0] for item in _flat_spec()}


def active_keys(mode: str) -> set:
    """某模式下真正生效的参数名"""
    return COMMON_KEYS | MODE_EXTRA.get(mode, set())


def default_values(parser=None) -> dict:
    """从 CLI 解析器取出 GUI 需要的全部默认值（也用于自检参数名是否拼错）"""
    a = (parser or core.build_parser()).parse_args([])
    return {item[0]: getattr(a, item[0]) for item in _flat_spec()}


def values_to_namespace(values: dict) -> argparse.Namespace:
    """界面参数字典 → 与 CLI 完全一致的 Namespace（GUI 与 CLI 参数永不漂移）"""
    a = core.build_parser().parse_args([])
    for k, v in values.items():
        if hasattr(a, k):
            if k == 'threshold' and isinstance(v, str) and v.strip() == '':
                v = 'auto'
            setattr(a, k, v)
    a.force = bool(values.get('force', a.force))       # 取消勾选 → 跳过已存在文件
    return a


def load_settings() -> dict:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:                                 # noqa: BLE001
        return {}


def save_settings(data: dict) -> None:
    try:
        SETTINGS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:                                 # noqa: BLE001
        pass


def env_summary(extra: str = '') -> str:
    """环境状态条文字：potrace / 细化后端（+ 各界面自己补充的信息）"""
    pot = core.find_potrace()
    contrib = hasattr(core.cv2, 'ximgproc')
    text = (f"potrace: {'可用' if pot else '未安装'} · "
            f"细化: {'opencv-contrib（快）' if contrib else '内置 Python（较慢）'}")
    return f"{text} · {extra}" if extra else text


def _fmt_num(v) -> str:
    if isinstance(v, float):
        return f'{v:g}'
    return str(v)


def _quote(tok: str) -> str:
    return f'"{tok}"' if (' ' in tok or not tok) else tok


def build_command(values: dict, inputs=None) -> str:
    """把当前界面参数导出为等效的 CLI 命令（只写非默认项，保持简短）"""
    inputs = list(inputs or ['input.png'])
    a = core.build_parser().parse_args([])
    parts = ['inklimner', *[_quote(str(i)) for i in inputs]]
    for key, _label, _kind, _extra, _hint, flag in _flat_spec():
        val = values.get(key)
        default = getattr(a, key, None)
        if key == 'force':                            # 默认覆盖，仅在关闭时写
            if not val:
                parts.append('--no-overwrite')
            continue
        if key in _TRUE_FLAGS:
            if val:
                parts.append(flag)
            continue
        if key == 'threshold':
            if val is not None and str(val) not in ('', 'auto'):
                parts += ['--threshold', str(val)]
            continue
        if val is None or val == '' or val == default:
            continue
        parts += [flag, _fmt_num(val) if not isinstance(val, str) else _quote(val)]
    return ' '.join(parts)


def parse_command(text: str) -> dict:
    """解析用户粘贴的 CLI 命令，返回可回填界面的参数字典"""
    toks = shlex.split(text.strip())
    while toks and Path(toks[0]).name.lower() in {
            'inklimner', 'inklimner.py', 'inklimner.exe', 'python', 'python3',
            'python.exe', 'py'}:
        toks.pop(0)
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            a = core.build_parser().parse_args(toks)
        except SystemExit:
            raise ValueError('命令无法解析：请检查参数拼写，或去掉图片路径以外'
                             '的未知内容') from None
    return {k: getattr(a, k) for k in all_keys()}


# ============================= 输出规划与批量执行 =============================

def safe_name(name: str, fallback: str = 'output') -> str:
    """把命名模板的产物名清洗成合法的文件名"""
    name = re.sub(r'[\\/:*?"<>|]+', '_', name).strip(' .')
    return name or fallback


def plan_pairs(files, out, mode: str = 'linedraw', use_template: bool = False,
               template: str = '{name}', dual: bool = False):
    """在 core.plan_jobs 之上叠加：命名模板 + 一次输出双版本（当前模式 + shape）

    files: 源图片路径列表；out: 输出文件或目录（None=原目录）
    返回 [(源路径, 目标路径, 模式), ...]
    """
    pairs = core.plan_jobs(list(files), Path(out) if out else None)
    single_svg = (out is not None and Path(out).suffix.lower() == '.svg'
                  and len(pairs) == 1)
    root_dir = Path(out) if (out and Path(out).suffix.lower() != '.svg') else None
    result = []
    for src, dst in pairs:
        base = dst
        if use_template and not single_svg:
            name = (template.replace('{name}', src.stem)
                            .replace('{mode}', str(mode)))
            base = Path(root_dir or dst.parent) / (safe_name(name, src.stem) + '.svg')
        result.append((src, base, mode))
        if dual and mode != 'shape':
            result.append((src, base.with_name(base.stem + '_shape.svg'), 'shape'))
    return result


def run_batch(pairs, args, on_log=None, on_progress=None, on_output=None,
              cancel: threading.Event | None = None):
    """串行执行一批转换任务，通过回调汇报进度（供 Tk / Qt 共用的工作线程体）

    返回 (成功数, 失败数, 跳过数, 是否被中断)
    """
    ok = fail = skip = 0
    total = len(pairs)
    for i, (src, dst, mode) in enumerate(pairs, 1):
        if cancel is not None and cancel.is_set():
            if on_log:
                on_log(f'■ 已停止，剩余 {total - i + 1} 个未处理')
            return ok, fail, skip, True
        a = args
        if mode != args.mode:                          # 双版本输出：另一份切到 shape
            a = copy.copy(args)
            a.mode = mode
            a.preview = False
        if on_log:
            on_log(f'── [{i}/{total}] {src.name} → {dst.name}')
        try:
            status = core.convert(src, dst, a)
        except Exception:                             # noqa: BLE001
            status = 'error'
            if on_log:
                on_log(traceback.format_exc().rstrip())
        if status == 'ok':
            ok += 1
            if on_output:
                on_output(dst, src, mode)
        elif status == 'skip':
            skip += 1
        else:
            fail += 1
        if on_progress:
            on_progress(i, total)
    return ok, fail, skip, False


class QueueLogHandler(logging.Handler):
    """把 inklimner 的 logging 记录转发到队列，界面据此刷新日志窗口"""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put(('LOG', self.format(record)))
        except Exception:                             # noqa: BLE001
            pass
