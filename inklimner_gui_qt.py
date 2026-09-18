#!/usr/bin/env python3
"""
inklimner_gui_qt.py —— InkLimner 图形界面（PySide6 / Qt 版 · 现代暗色）

这是推荐使用的界面：卡片式参数分组、深色主题、原生拖拽、实时预览、
原图/结果对比、一键导出/回填 CLI 命令、配置记忆。

共享逻辑（参数规格 / 预设 / 命令互转 / 批量执行）全在 inklimner_gui_core.py，
本文件只负责“长得好看、用着顺手”。

依赖：
    pip install "inklimner[gui]"          # 即 PySide6-Essentials
纯 Python 3.8 或不想装 Qt 的用户，可改用零依赖的 Tk 界面：
    python inklimner_gui_tk.py

启动：
    python inklimner_gui_qt.py
    python inklimner.py --gui             # 自动选择可用界面
    inklimner-gui                         # pip install . 之后

自检（无显示器也可跑，用于验证界面链路是否正常）：
    python inklimner_gui_qt.py --selftest
"""

from __future__ import annotations

import html
import os
import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    import inklimner as core
except ImportError:                                   # 直接运行本文件时
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import inklimner as core

try:
    import inklimner_gui_core as gc
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import inklimner_gui_core as gc

HERE = Path(__file__).resolve().parent
ACCENT = '#14B8A6'

THEME_LIGHT = """
QWidget { background: #F4F6F8; color: #1F2430; font-size: 13px; }
QMainWindow, QDialog { background: #F4F6F8; }
QToolTip { background: #FFFFFF; color: #1F2430; border: 1px solid #D8DDE5;
           padding: 4px 6px; }

#hero { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 14px; }
#heroTitle { font-size: 22px; font-weight: 700; color: #161A22; }
#heroVer { color: #6B7484; font-size: 12px; font-weight: 500; }
#heroSub { color: #6B7484; font-size: 12px; }
#pill { background: #E6F6F3; color: #0F766E; border: 1px solid #BFE7E1;
        border-radius: 10px; padding: 4px 12px; font-size: 12px; }
#pillWarn { background: #F2F4F7; color: #9A6B0E; border: 1px solid #E3E6EB;
            border-radius: 10px; padding: 4px 12px; font-size: 12px; }

#toolGroup { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 11px; }
#groupTag { color: #7A8494; font-size: 11px; font-weight: 600;
            padding-right: 2px; }

QGroupBox { background: #FFFFFF; border: 1px solid #E3E6EB; border-radius: 12px;
            margin-top: 18px; padding: 14px 12px 10px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                   left: 14px; top: 2px; padding: 0 6px; color: #0E8C82; }
#cardSub { color: #7A8494; font-size: 11px; font-weight: normal; }
#rowLabel { color: #3C4553; }

QPushButton { background: #FFFFFF; border: 1px solid #D8DDE5; border-radius: 9px;
              padding: 6px 14px; color: #1F2430; }
QPushButton:hover { background: #EFF7F6; border-color: #9BD8D1; }
QPushButton:pressed { background: #E4F1EF; }
QPushButton:disabled { color: #AAB2BE; background: #F2F4F6; border-color: #E7EAEF; }
QPushButton#primary { background: #0D9488; color: #FFFFFF; border: none;
                      font-weight: 700; padding: 8px 22px; }
QPushButton#primary:hover { background: #0FA99B; }
QPushButton#primary:disabled { background: #B7DED9; color: #F2FBFA; }
QPushButton#danger { background: #FFFFFF; border-color: #F0C9CF; color: #B4455A; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #FFFFFF;
    border: 1px solid #D8DDE5; border-radius: 8px; padding: 7px 10px;
    selection-background-color: #0D9488; selection-color: #FFFFFF; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #0D9488; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: #AAB2BE; background: #F2F4F6; border-color: #E7EAEF; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #FFFFFF; border: 1px solid #D8DDE5;
    selection-background-color: #0D9488; selection-color: #FFFFFF; outline: none; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid #C6CCD6; background: #FFFFFF; }
QCheckBox::indicator:checked { background: #0D9488; border-color: #0D9488; }
QCheckBox::indicator:disabled { border-color: #E7EAEF; background: #F2F4F6; }
QCheckBox::indicator:checked:disabled { background: #B7DED9; border-color: #B7DED9; }

QProgressBar { border: none; border-radius: 5px; background: #E4E8ED;
               height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { border-radius: 5px; background: #0D9488; }

QPlainTextEdit { background: #FFFFFF; border: 1px solid #E3E6EB;
                 border-radius: 10px; color: #3C4553;
                 font-family: Consolas, Menlo, monospace; font-size: 12px; }

QTabWidget::pane { border: 1px solid #E3E6EB; border-radius: 10px;
                   background: #FFFFFF; top: -1px; }
QTabBar::tab { background: #ECEFF3; color: #6B7484; padding: 7px 16px;
               border-top-left-radius: 9px; border-top-right-radius: 9px;
               margin-right: 3px; }
QTabBar::tab:selected { background: #FFFFFF; color: #0E8C82;
                        border-bottom: 2px solid #0D9488; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #D2D8E0; border-radius: 5px;
                              min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #BCC4CF; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #D2D8E0; border-radius: 5px; }

#statusText { color: #6B7484; }
"""

THEME_DARK = """
QWidget { background: #14161B; color: #E7EAF0; font-size: 13px; }
QMainWindow, QDialog { background: #14161B; }
QToolTip { background: #222834; color: #DCE3EC; border: 1px solid #333B49;
           padding: 4px 6px; }

#hero { background: #1A1D24; border: 1px solid #242A35; border-radius: 14px; }
#heroTitle { font-size: 22px; font-weight: 700; color: #F2F5F9; }
#heroVer { color: #8B95A6; font-size: 12px; }
#heroSub { color: #8B95A6; font-size: 12px; }
#pill { background: #1F2A2C; color: #7FE3D4; border: 1px solid #2C4144;
        border-radius: 10px; padding: 4px 12px; font-size: 12px; }
#pillWarn { background: #2C2A20; color: #E4C878; border: 1px solid #46402A;
            border-radius: 10px; padding: 4px 12px; font-size: 12px; }

#toolGroup { background: #191C22; border: 1px solid #232935; border-radius: 11px; }
#groupTag { color: #9BA9C0; font-size: 11px; font-weight: 600;
            padding-right: 2px; }

QGroupBox { background: #1A1D24; border: 1px solid #242A35; border-radius: 12px;
            margin-top: 18px; padding: 14px 12px 10px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left;
                   left: 14px; top: 2px; padding: 0 6px; color: #7FE3D4; }
#cardSub { color: #7C8698; font-size: 11px; font-weight: normal; }
#rowLabel { color: #C3CBDA; }

QPushButton { background: #232833; border: 1px solid #313847; border-radius: 9px;
              padding: 6px 14px; color: #E7EAF0; }
QPushButton:hover { background: #2B3140; border-color: #3C4557; }
QPushButton:pressed { background: #1E232C; }
QPushButton:disabled { color: #5A6274; background: #1B1F27; border-color: #262B35; }
QPushButton#primary { background: #14B8A6; color: #04211D; border: none;
                      font-weight: 700; padding: 8px 22px; }
QPushButton#primary:hover { background: #22C7B4; }
QPushButton#primary:disabled { background: #23403C; color: #6C7B79; }
QPushButton#danger { background: #2A2028; border-color: #4A2E38; color: #F0A9B4; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #10131A;
    border: 1px solid #2A303C; border-radius: 8px; padding: 7px 10px;
    selection-background-color: #14B8A6; selection-color: #04211D; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #14B8A6; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
    color: #5A6274; background: #16191F; border-color: #222831; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #1A1D24; border: 1px solid #2A303C;
    selection-background-color: #14B8A6; selection-color: #04211D; outline: none; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid #39404E; background: #10131A; }
QCheckBox::indicator:checked { background: #14B8A6; border-color: #14B8A6; }
QCheckBox::indicator:disabled { border-color: #262B35; background: #16191F; }
QCheckBox::indicator:checked:disabled { background: #23403C; border-color: #23403C; }

QProgressBar { border: none; border-radius: 5px; background: #1E232C;
               height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { border-radius: 5px; background: #14B8A6; }

QPlainTextEdit { background: #0F1219; border: 1px solid #242A35;
                 border-radius: 10px; color: #B9C2D0;
                 font-family: Consolas, Menlo, monospace; font-size: 12px; }

QTabWidget::pane { border: 1px solid #242A35; border-radius: 10px;
                   background: #14171D; top: -1px; }
QTabBar::tab { background: #1A1D24; color: #8B95A6; padding: 7px 16px;
               border-top-left-radius: 9px; border-top-right-radius: 9px;
               margin-right: 3px; }
QTabBar::tab:selected { background: #242A35; color: #7FE3D4;
                        border-bottom: 2px solid #14B8A6; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2E3542; border-radius: 5px;
                              min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3B4453; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #2E3542; border-radius: 5px; }

#statusText { color: #8B95A6; }
"""

THEMES = {'light': THEME_LIGHT, 'dark': THEME_DARK}
THEME_NAMES = ['light', 'dark']
THEME_LABELS = ['☀ 浅色', '🌙 深色']
DEFAULT_THEME = 'light'
# 参数置灰时用的“不可用”文字色
DIM_COLOR = {'light': '#98A3B2', 'dark': '#5A6274'}
# 图片预览区的底色与描边
VIEW_STYLE = {
    'light': 'color: #98A0AE; background: #FFFFFF;'
             'border: 1px solid #E3E6EB; border-radius: 10px;',
    'dark': 'color: #5C667A; background: #171A21;'
            'border: 1px solid #242A35; border-radius: 10px;',
}
# 日志的语义化配色：成功 / 失败 / 提示 / 次要
LOG_COLORS = {
    'light': {'ok': '#0F8A7E', 'err': '#C0392B', 'info': '#B8801E', 'dim': '#8A93A3'},
    'dark': {'ok': '#5FD3C4', 'err': '#F08A98', 'info': '#E4C878', 'dim': '#8B95A6'},
}

HELP_TEXT = f"""InkLimner v{core.__version__} — 使用说明

1) 添加图片：点「＋ 图片」/「📁 文件夹」，或把文件/文件夹直接拖进窗口
2) 选模式：linedraw（手绘线稿，默认）/ edge（照片描线）/ multi（灰度层次）/ shape（剪纸轮廓）
3) 调参数：灰色（变暗）的参数表示当前模式用不到，切模式会自动亮起
4) 开始转换：点右下角「▶ 开始转换」；改参数会自动刷新左侧预览
5) 线条莫名断开？把「② 线稿参数 → 断线修复 join-gap」调大（如 8）
"""


# ============================= 小工具 =============================

def value_of(widget):
    """从任意参数控件取出 Python 值"""
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QSpinBox):
        return int(widget.value())
    if isinstance(widget, QDoubleSpinBox):
        return float(widget.value())
    if isinstance(widget, QComboBox):
        return widget.currentText()
    return widget.text()


def set_value(widget, value):
    """把 Python 值写回参数控件（用于回填预设 / 命令 / 记忆配置）"""
    if value is None:
        return
    if isinstance(widget, QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, QSpinBox):
        widget.setValue(int(float(value)))
    elif isinstance(widget, QDoubleSpinBox):
        widget.setValue(float(value))
    elif isinstance(widget, QComboBox):
        idx = widget.findText(str(value))
        if idx >= 0:
            widget.setCurrentIndex(idx)
    else:
        widget.setText(str(value))


def _decimals_for(step) -> int:
    """按步长决定小数位数（0.05 → 2 位，0.0005 → 4 位），避免满屏 0.7000 这种尴尬"""
    text = f'{float(step):f}'.rstrip('0')
    return len(text.split('.')[1]) if '.' in text else 0


def pill(text: str, warn: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName('pillWarn' if warn else 'pill')
    lab.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return lab


class ImageView(QLabel):
    """等比自适应缩放的图片显示区"""

    EMPTY = '（暂无预览）'

    def __init__(self):
        super().__init__(self.EMPTY)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(260, 200)
        self._src: QPixmap | None = None
        self.set_theme(DEFAULT_THEME)

    def set_theme(self, theme: str) -> None:
        """预览区底色跟随界面主题（浅色 / 深色）"""
        self.setStyleSheet(VIEW_STYLE.get(theme, VIEW_STYLE[DEFAULT_THEME]))

    def set_image(self, path) -> None:
        pm = QPixmap(str(path))
        self._src = None if pm.isNull() else pm
        if self._src is None:
            self.setText(self.EMPTY)
        else:
            self.setText('')
            self._rescale()

    def clear_image(self) -> None:
        self._src = None
        super().setPixmap(QPixmap())
        self.setText(self.EMPTY)

    def set_hint(self, text: str) -> None:
        """显示一段提示文字（例如「已生成 SVG，但未生成 PNG 预览」）"""
        self._src = None
        super().setPixmap(QPixmap())
        self.setText(text)

    def _rescale(self) -> None:
        if self._src is None:
            return
        # 四周留 14px 呼吸位，白底线稿不会顶到卡片边缘
        box = self.size() - QSize(28, 28)
        if box.width() < 40 or box.height() < 40:
            box = self.size()
        self.setPixmap(self._src.scaled(
            box, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):                      # noqa: N802
        super().resizeEvent(event)
        self._rescale()


# ============================= 后台线程 =============================

class BatchWorker(QThread):
    """批量转换工作线程（把 core 层的回调转成 Qt 信号）"""

    log = Signal(str)
    prog = Signal(int, int)
    out = Signal(str, str, str)
    done = Signal(int, int, int, bool)

    def __init__(self, pairs, args, cancel, parent=None):
        super().__init__(parent)
        self.pairs, self.args, self.cancel = pairs, args, cancel

    def run(self) -> None:
        ok, fail, skip, cancelled = gc.run_batch(
            self.pairs, self.args,
            on_log=self.log.emit,
            on_progress=self.prog.emit,
            on_output=lambda dst, src, mode: self.out.emit(
                str(dst), str(src), str(mode)),        # 信号只吃 str
            cancel=self.cancel)
        self.done.emit(ok, fail, skip, cancelled)


class LiveWorker(QThread):
    """实时预览：单张小图 + 临时目录，跑完把 PNG 路径回传"""

    ready = Signal(str, str)

    def __init__(self, src, args, parent=None):
        super().__init__(parent)
        self.src, self.args = src, args

    def run(self) -> None:
        try:
            outdir = Path(tempfile.mkdtemp(prefix='inklimner_live_'))
            dst = outdir / (self.src.stem + '.svg')
            core.convert(self.src, dst, self.args)
            pv = dst.with_name(dst.stem + '.preview.png')
            if pv.exists():
                self.ready.emit(str(pv), str(self.src))
        except Exception:                              # noqa: BLE001
            pass


# ============================= 主窗口 =============================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = gc.load_settings()
        self.theme = self._pick_theme()
        self.inputs: list[Path] = []
        self.widgets: dict[str, QWidget] = {}
        self.row_labels: dict[str, QLabel] = {}
        self.custom_presets: dict = dict(self.settings.get('presets') or {})
        self.last_out: Path | None = None
        self.worker: BatchWorker | None = None
        self.live_worker: LiveWorker | None = None
        self._live_busy = False

        self.setWindowTitle(gc.APP_TITLE)
        self.setAcceptDrops(True)
        self.resize(1180, 760)
        self._build_ui()
        self._restore_settings()

        self.live_timer = QTimer(self)
        self.live_timer.setSingleShot(True)
        self.live_timer.setInterval(400)
        self.live_timer.timeout.connect(self._run_live)

    # ---------------- 界面搭建 ----------------

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 10)
        outer.setSpacing(10)

        outer.addWidget(self._build_hero())
        outer.addWidget(self._build_toolrow())

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(self._build_params())
        split.addWidget(self._build_right())
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 7)
        split.setSizes([500, 660])
        outer.addWidget(split, 1)

        outer.addWidget(self._build_status())
        self._apply_theme(self.theme, save=False)      # 应用记住的配色

    def _build_hero(self) -> QWidget:
        box = QFrame()
        box.setObjectName('hero')
        lay = QHBoxLayout(box)
        lay.setContentsMargins(18, 12, 18, 12)

        left = QVBoxLayout()
        left.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel('InkLimner')
        title.setObjectName('heroTitle')
        ver = QLabel(f'v{core.__version__}')
        ver.setObjectName('heroVer')
        title_row.addWidget(title)
        title_row.addWidget(ver)
        title_row.addStretch(1)
        sub = QLabel(gc.APP_TAGLINE + '　·　线稿 / 剪纸，一次成型')
        sub.setObjectName('heroSub')
        left.addLayout(title_row)
        left.addWidget(sub)
        lay.addLayout(left)
        lay.addStretch(1)

        # 配色切换：浅色（默认）/ 深色，选择会被记住
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_LABELS)
        self.theme_combo.setToolTip('界面配色（浅色 / 深色，自动记忆）')
        self.theme_combo.setCurrentIndex(max(0, THEME_NAMES.index(self.theme)))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        lay.addWidget(self.theme_combo)

        env = gc.env_summary('拖拽 ✓')
        pot_ok = '未安装' not in env.split('·')[0]
        self.env_pill = pill(env, warn=not pot_ok)
        lay.addWidget(self.env_pill)
        return box

    # ---------------- 主题 ----------------

    def _pick_theme(self) -> str:
        """主题优先级：环境变量 INKLIMNER_THEME > 上次记忆 > 默认浅色"""
        forced = os.environ.get('INKLIMNER_THEME', '').strip().lower()
        if forced in THEMES:
            return forced
        saved = str(self.settings.get('theme') or '')
        return saved if saved in THEMES else DEFAULT_THEME

    def _on_theme_changed(self, index: int) -> None:
        name = THEME_NAMES[index] if 0 <= index < len(THEME_NAMES) else DEFAULT_THEME
        self._apply_theme(name)

    def _apply_theme(self, name: str, save: bool = True) -> None:
        """切换整套配色：全局样式表 + 预览区 + 置灰文字色"""
        self.theme = name if name in THEMES else DEFAULT_THEME
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(THEMES[self.theme])
        for view in (getattr(self, 'result_view', None),
                     getattr(self, 'source_view', None),
                     getattr(self, 'cmp_result', None)):
            if view is not None:
                view.set_theme(self.theme)
        if 'mode' in self.widgets:                     # 重新计算置灰颜色
            self._apply_mode(self.widgets['mode'].currentText())
        combo = getattr(self, 'theme_combo', None)
        if combo is not None:
            idx = THEME_NAMES.index(self.theme)
            if combo.currentIndex() != idx:
                combo.blockSignals(True)
                combo.setCurrentIndex(idx)
                combo.blockSignals(False)
        if save:
            self._persist()

    def _build_toolrow(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        def group(tag, buttons):
            """把相关按钮收进一个小容器，视觉上分组、降低认知负担"""
            frame = QFrame()
            frame.setObjectName('toolGroup')
            gl = QHBoxLayout(frame)
            gl.setContentsMargins(10, 5, 10, 5)
            gl.setSpacing(6)
            lab = QLabel(tag)
            lab.setObjectName('groupTag')
            gl.addWidget(lab)
            for text, tip, slot in buttons:
                b = QPushButton(text)
                b.setToolTip(tip)
                # clicked 会附带一个 checked 参数；用 lambda 吃掉它，
                # 保证槽函数按自己的签名被调用（避免 add_files 收到 bool）
                b.clicked.connect(lambda _checked=False, fn=slot: fn())
                gl.addWidget(b)
            return frame

        lay.addWidget(group('文件', (
            ('＋ 图片', '添加一张或多张图片', self.add_files),
            ('📁 文件夹', '把整个文件夹里的图片都加进来', self.add_folder),
            ('🗑 清空', '清空待转换列表', self.clear_files))))

        preset_frame = QFrame()
        preset_frame.setObjectName('toolGroup')
        pl = QHBoxLayout(preset_frame)
        pl.setContentsMargins(10, 5, 10, 5)
        pl.setSpacing(6)
        ptag = QLabel('预设')
        ptag.setObjectName('groupTag')
        pl.addWidget(ptag)
        self.preset_combo = QComboBox()
        self.preset_combo.setToolTip('套用一套调好的参数')
        self._refresh_presets()
        self.preset_combo.setMinimumWidth(150)
        pl.addWidget(self.preset_combo)
        for text, tip, slot in (('套用', '套用所选预设', self.apply_preset),
                                ('另存', '把当前参数存成自己的预设', self.save_preset)):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda _checked=False, fn=slot: fn())
            pl.addWidget(b)
        lay.addWidget(preset_frame)

        lay.addWidget(group('命令', (
            ('⌨ 导出', '把当前设置导出成等效 CLI 命令', self.export_command),
            ('📥 回填', '粘贴一条 CLI 命令，自动填回界面', self.import_command),
            ('↺ 重置', '恢复全部默认参数', self.reset_defaults))))

        lay.addStretch(1)
        self.file_label = QLabel('未添加图片')
        self.file_label.setObjectName('heroSub')
        lay.addWidget(self.file_label)
        return row

    def _build_params(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        box = QVBoxLayout(inner)
        box.setContentsMargins(0, 0, 6, 0)
        box.setSpacing(10)

        defaults = gc.default_values()
        self.mode_tip_label = QLabel('')
        self.mode_tip_label.setObjectName('cardSub')
        self.mode_tip_label.setWordWrap(True)
        self.mode_tip_label.setContentsMargins(4, 0, 4, 2)
        box.addWidget(self.mode_tip_label)
        for title, subtitle, items in gc.GROUPS:
            grp = QGroupBox(title)
            gv = QVBoxLayout(grp)
            gv.setContentsMargins(10, 6, 10, 6)
            gv.setSpacing(6)
            sub = QLabel(subtitle)
            sub.setObjectName('cardSub')
            gv.addWidget(sub)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(11)
            grid.setColumnStretch(1, 1)
            for r, (key, label, kind, extra, hint, _flag) in enumerate(items):
                lab = QLabel(label)
                lab.setObjectName('rowLabel')
                lab.setToolTip(hint)
                widget = self._make_widget(key, kind, extra, defaults.get(key), hint)
                grid.addWidget(lab, r, 0)
                grid.addWidget(widget, r, 1)
                self.row_labels[key] = lab
            gv.addLayout(grid)
            box.addWidget(grp)

        box.addWidget(self._build_run_card())
        box.addStretch(1)
        scroll.setWidget(inner)
        self._apply_mode(defaults.get('mode', 'linedraw'))
        return scroll

    def _make_widget(self, key, kind, extra, default, hint):
        if kind == 'combo':
            w = QComboBox()
            w.addItems(list(extra))
            w.setCurrentText(str(default))
            w.currentTextChanged.connect(lambda *_: self._on_change())
        elif kind == 'spin_i':
            lo, hi, step = extra
            w = QSpinBox()
            w.setRange(int(lo), int(hi))
            w.setSingleStep(int(step))
            w.setValue(int(default))
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda *_: self._on_change())
        elif kind == 'spin_f':
            lo, hi, step = extra
            w = QDoubleSpinBox()
            w.setRange(float(lo), float(hi))
            w.setSingleStep(float(step))
            w.setDecimals(_decimals_for(step))
            w.setValue(float(default))
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda *_: self._on_change())
        elif kind == 'check':
            w = QCheckBox()
            w.setChecked(bool(default))
            w.toggled.connect(lambda *_: self._on_change())
        else:
            w = QLineEdit('' if default is None else str(default))
            w.editingFinished.connect(self._on_change)
        w.setToolTip(hint)
        w.setMinimumWidth(150)
        self.widgets[key] = w
        if key == 'mode':
            w.currentTextChanged.connect(self._apply_mode)
        return w

    def _build_run_card(self) -> QWidget:
        grp = QGroupBox('⑦ 运行')
        v = QVBoxLayout(grp)
        v.setContentsMargins(10, 6, 10, 8)
        v.setSpacing(8)

        outrow = QHBoxLayout()
        outrow.addWidget(QLabel('输出位置'))
        self.out_edit = QLineEdit(str(self.settings.get('out_dir') or ''))
        self.out_edit.setPlaceholderText('留空 = 与图片同目录；填 .svg 路径 = 指定单文件')
        outrow.addWidget(self.out_edit, 1)
        pick = QPushButton('浏览…')
        pick.clicked.connect(self.pick_out)
        outrow.addWidget(pick)
        v.addLayout(outrow)

        tplrow = QHBoxLayout()
        self.tpl_enable = QCheckBox('命名模板')
        self.tpl_enable.toggled.connect(lambda *_: self._on_change())
        tplrow.addWidget(self.tpl_enable)
        self.tpl_edit = QLineEdit(str(self.settings.get('template') or '{name}_cut'))
        self.tpl_edit.setToolTip('可用占位符：{name}=原文件名，{mode}=模式名')
        self.tpl_edit.textChanged.connect(lambda *_: self._on_change())
        tplrow.addWidget(self.tpl_edit, 1)
        v.addLayout(tplrow)

        opts = QHBoxLayout()
        self.dual_check = QCheckBox('同时输出 shape 轮廓版')
        self.dual_check.setToolTip('一次产出「当前模式 + 剪纸轮廓」，方便分图层')
        self.dual_check.toggled.connect(lambda *_: self._on_change())
        opts.addWidget(self.dual_check)
        self.live_check = QCheckBox('实时预览')
        self.live_check.setChecked(bool(self.settings.get('live', True)))
        self.live_check.setToolTip('改参数自动重跑单张小图并刷新预览')
        self.live_check.toggled.connect(self._on_live_toggle)
        opts.addWidget(self.live_check)
        opts.addStretch(1)
        v.addLayout(opts)
        return grp

    def _build_right(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.tabs = QTabWidget()
        self.result_view = ImageView()
        self.tabs.addTab(self.result_view, '转换结果')
        self.tabs.addTab(self._build_compare_page(), '原图对照')
        lay.addWidget(self.tabs, 3)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('日志会显示在这里…')
        self.log.setMaximumBlockCount(4000)
        lay.addWidget(self.log, 2)
        return panel

    def _build_compare_page(self) -> QWidget:
        """左右并排的「原图 ↔ 结果」对比页"""
        page = QWidget()
        lay = QHBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)
        for caption, attr in (('原图', 'source_view'), ('转换结果', 'cmp_result')):
            col = QVBoxLayout()
            col.setSpacing(4)
            cap = QLabel(caption)
            cap.setObjectName('cardSub')
            view = ImageView()
            setattr(self, attr, view)
            col.addWidget(cap)
            col.addWidget(view, 1)
            lay.addLayout(col, 1)
        return page

    def _build_status(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(10)

        self.status = QLabel('就绪')
        self.status.setObjectName('statusText')
        lay.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Fixed)
        lay.addWidget(self.progress, 1)

        self.open_btn = QPushButton('📂 输出目录')
        self.open_btn.setToolTip('在文件管理器里打开最近一次的输出目录')
        self.open_btn.clicked.connect(self.open_output)
        lay.addWidget(self.open_btn)

        self.help_btn = QPushButton('? 帮助')
        self.help_btn.clicked.connect(lambda: QMessageBox.information(
            self, '使用说明', HELP_TEXT))
        lay.addWidget(self.help_btn)

        self.stop_btn = QPushButton('■ 停止')
        self.stop_btn.setObjectName('danger')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        lay.addWidget(self.stop_btn)

        self.run_btn = QPushButton('▶ 开始转换')
        self.run_btn.setObjectName('primary')
        self.run_btn.clicked.connect(self.start)
        lay.addWidget(self.run_btn)
        return bar

    # ---------------- 参数联动 / 预设 / 命令 ----------------

    def _apply_mode(self, mode: str) -> None:
        """按当前模式把无关参数置灰（只亮出真正生效的旋钮）"""
        active = gc.active_keys(mode)
        for key, widget in self.widgets.items():
            on = key in active
            widget.setEnabled(on)
            lab = self.row_labels.get(key)
            if lab is not None:
                lab.setStyleSheet('' if on else f'color: {DIM_COLOR[self.theme]};')
        tip = gc.MODE_TIPS.get(mode, '')
        if getattr(self, 'status', None) is not None:   # 状态栏可能还没建好
            self.status.setToolTip(tip)
        if hasattr(self, 'mode_tip_label'):
            self.mode_tip_label.setText(tip)

    def _refresh_presets(self) -> None:
        current = self.preset_combo.currentText() if hasattr(self, 'preset_combo') else ''
        self.preset_combo.clear()
        self.preset_combo.addItems(list(gc.PRESETS) + list(self.custom_presets))
        if current:
            idx = self.preset_combo.findText(current)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)

    def current_values(self) -> dict:
        return {k: value_of(w) for k, w in self.widgets.items()}

    def apply_values(self, values: dict) -> None:
        for key, val in values.items():
            w = self.widgets.get(key)
            if w is not None:
                w.blockSignals(True)
                set_value(w, val)
                w.blockSignals(False)
        if 'mode' in values:
            self._apply_mode(str(values['mode']))

    def apply_preset(self) -> None:
        name = self.preset_combo.currentText()
        data = self.custom_presets.get(name) or gc.PRESETS.get(name)
        if not data:
            QMessageBox.warning(self, '预设', f'找不到预设「{name}」')
            return
        self.apply_values(dict(data))
        self._append_log(f'◆ 已套用预设：{name}')
        self._on_change()

    def save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, '另存预设', '预设名称：')
        if not ok or not name.strip():
            return
        self.custom_presets[name.strip()] = self.current_values()
        self._refresh_presets()
        self._persist()
        self._append_log(f'◆ 已保存预设：{name.strip()}')

    def export_command(self) -> None:
        cmd = gc.build_command(self.current_values(),
                               [str(p) for p in self.inputs] or None)
        dlg = QDialog(self)
        dlg.setWindowTitle('等效 CLI 命令')
        dlg.resize(720, 260)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel('把它复制走，就能在终端里复现当前设置：'))
        edit = QTextEdit(cmd)
        edit.setReadOnly(True)
        lay.addWidget(edit, 1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        copy_btn = btns.addButton('复制', QDialogButtonBox.ButtonRole.ActionRole)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(cmd))
        btns.rejected.connect(dlg.reject)
        btns.clicked.connect(dlg.accept)
        lay.addWidget(btns)
        dlg.exec()

    def import_command(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self, '回填 CLI 命令', '粘贴一条 inklimner 命令（或别人给你的调参）：')
        if not ok or not text.strip():
            return
        try:
            values = gc.parse_command(text)
        except ValueError as e:
            QMessageBox.warning(self, '解析失败', str(e))
            return
        self.apply_values(values)
        toks = text.split()
        files = [t for t in toks[1:] if not t.startswith('-')
                 and Path(t).suffix.lower() in core.SUPPORTED]
        if files:
            self.add_files(files)
        self._append_log('◆ 已从命令回填参数')
        self._on_change()

    def reset_defaults(self) -> None:
        self.apply_values(gc.default_values())
        self._append_log('◆ 已恢复默认参数')
        self._on_change()

    # ---------------- 文件列表 ----------------

    def add_files(self, paths=None) -> None:
        """添加图片。

        paths 可以是 None（弹出选择框）、单个路径，或路径列表。
        注意：QPushButton.clicked 会附带一个 bool 参数，所以这里必须把
        bool 当成「没给参数」处理，否则会变成 `for p in False`。
        """
        if paths is None or isinstance(paths, bool):
            exts = ' '.join('*' + e for e in core.SUPPORTED)
            paths, _ = QFileDialog.getOpenFileNames(
                self, '选择图片', self.settings.get('last_dir') or '', f'图片 ({exts})')
        elif isinstance(paths, (str, Path)):
            paths = [paths]
        paths = [p for p in (paths or []) if p]
        added = 0
        for p in paths:
            path = Path(p)
            if path.is_dir():
                added += self._add_dir(path)
            elif path.is_file():
                if path not in self.inputs:
                    self.inputs.append(path)
                    added += 1
        if added:
            last = self.inputs[-1]
            self.settings['last_dir'] = str(last.parent)
            self.source_view.set_image(self.inputs[0])
            self.tabs.setCurrentIndex(1)
            self._append_log(f'◆ 已添加 {added} 个图片/文件夹')
            self._on_change()
        self._sync_file_label()

    def _add_dir(self, path: Path) -> int:
        n = 0
        for p in sorted(path.iterdir()):
            if p.is_file() and p.suffix.lower() in core.SUPPORTED and p not in self.inputs:
                self.inputs.append(p)
                n += 1
        return n

    def add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, '选择文件夹', self.settings.get('last_dir') or '')
        if folder:
            self.add_files([folder])

    def clear_files(self) -> None:
        self.inputs.clear()
        self.source_view.clear_image()
        self._sync_file_label()
        self._append_log('◆ 已清空图片列表')

    def _sync_file_label(self) -> None:
        n = len(self.inputs)
        self.file_label.setText(f'待转换 {n} 张' if n else '未添加图片')

    def pick_out(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, '选择输出目录',
                                                  self.out_edit.text() or '')
        if folder:
            self.out_edit.setText(folder)

    def open_output(self) -> None:
        target = self.last_out
        if target is None and self.out_edit.text().strip():
            target = Path(self.out_edit.text().strip())
        if target is None:
            target = Path(self.settings.get('last_dir') or Path.home())
        if target.is_file():
            target = target.parent
        if target.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        else:
            QMessageBox.information(self, '输出目录', '还没有输出目录可打开')

    # ---------------- 拖拽 ----------------

    def dragEnterEvent(self, event):                   # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):                        # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls()]
        self.add_files([p for p in paths if p])
        event.acceptProposedAction()

    # ---------------- 事件 ----------------

    def _on_change(self, *_args) -> None:
        if self.live_check.isChecked():
            self.live_timer.start()

    def _on_live_toggle(self, on: bool) -> None:
        if on:
            self._on_change()
        else:
            self.live_timer.stop()

    def _append_log(self, text: str) -> None:
        """日志按语义着色，便于一眼扫到成功 / 失败 / 提示"""
        c = LOG_COLORS[self.theme]
        color = ''
        if text.startswith('■ 完成'):
            color = c['ok']
        elif text.startswith(('▶', '── [', '◆')):
            color = c['info']
        elif 'Traceback' in text or text.startswith(('[失败]', '[跳过]')):
            color = c['err']
        if color:
            self.log.appendHtml(
                f'<span style="color:{color}">{html.escape(text)}</span>')
        else:
            self.log.appendPlainText(text)

    # ---------------- 转换 ----------------

    def collect_pairs(self, args):
        out = self.out_edit.text().strip() or None
        files = [p for f in self.inputs
                 for p in (sorted(f.iterdir()) if f.is_dir() else [f])
                 if p.is_file() and p.suffix.lower() in core.SUPPORTED]
        if not files:
            raise ValueError('请先添加至少一张图片（点「＋ 图片」或直接把文件拖进窗口）')
        return gc.plan_pairs(files, out, mode=args.mode,
                             use_template=self.tpl_enable.isChecked(),
                             template=self.tpl_edit.text() or '{name}',
                             dual=self.dual_check.isChecked())

    def start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            args = gc.values_to_namespace(self.current_values())
            pairs = self.collect_pairs(args)
        except ValueError as e:
            QMessageBox.warning(self, '还不能开始', str(e))
            return

        self.log.clear()
        self.progress.setValue(0)
        self.status.setText(f'处理中… 0/{len(pairs)}')
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._append_log(f'▶ 共 {len(pairs)} 个任务，模式 {args.mode}')

        from threading import Event
        self.cancel = Event()
        self._run_mode = args.mode
        self.worker = BatchWorker(pairs, args, self.cancel, self)
        self.worker.log.connect(self._append_log)
        self.worker.prog.connect(self._on_prog)
        self.worker.out.connect(self._on_out)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def stop(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.cancel.set()
            self.status.setText('正在停止…（当前文件处理完后中断）')

    def _on_prog(self, i: int, total: int) -> None:
        self.progress.setValue(int(i / max(total, 1) * 100))
        self.status.setText(f'处理中… {i}/{total}')

    def _on_out(self, dst: str, src: str, mode: str) -> None:
        self.last_out = Path(dst).parent
        # 双版本输出里的 shape 副本不抢占预览；当前模式的产物才展示
        if mode == getattr(self, '_run_mode', mode) or self.dual_check.isChecked():
            self._show_images(dst, src)
            self.tabs.setCurrentIndex(0)

    def _show_images(self, dst: str, src: str) -> None:
        """结果区显示：SVG 不能直接进位图控件，优先显示同名 PNG 预览图"""
        png = Path(dst).with_name(Path(dst).stem + '.preview.png')
        if png.exists():
            self.result_view.set_image(png)
            self.cmp_result.set_image(png)
        else:
            self.result_view.set_hint('已生成 SVG ✓\n'
                                      '勾选「生成 PNG 预览」即可在窗口内直接查看')
            self.cmp_result.set_hint('已生成 SVG ✓')
        self.source_view.set_image(src)

    def _on_done(self, ok: int, fail: int, skip: int, cancelled: bool) -> None:
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        tail = '（已中断）' if cancelled else ''
        self.status.setText(f'完成{tail}：成功 {ok} / 失败 {fail} / 跳过 {skip}')
        self._append_log(f'■ 完成{tail}：成功 {ok}，失败 {fail}，跳过 {skip}')
        self.progress.setValue(100 if not cancelled else self.progress.value())
        self._persist()

    # ---------------- 实时预览 ----------------

    def _run_live(self) -> None:
        if self._live_busy or (self.worker is not None and self.worker.isRunning()):
            return
        if not self.inputs:
            return
        src = self.inputs[0]
        if src.is_dir():
            return
        try:
            args = gc.values_to_namespace(self.current_values())
        except Exception:                              # noqa: BLE001
            return
        args.preview = True
        args.quiet = True
        self._live_busy = True
        self.status.setText('正在刷新实时预览…')
        self.live_worker = LiveWorker(src, args, self)
        self.live_worker.ready.connect(self._on_live_ready)
        self.live_worker.finished.connect(self._on_live_finished)
        self.live_worker.start()

    def _on_live_ready(self, png: str, src: str) -> None:
        self.result_view.set_image(png)
        self.cmp_result.set_image(png)
        self.source_view.set_image(src)
        self.status.setText('实时预览已更新')

    def _on_live_finished(self) -> None:
        self._live_busy = False

    # ---------------- 配置记忆 ----------------

    def _persist(self) -> None:
        if getattr(self, '_no_persist', False):        # 自检模式不写用户配置
            return
        data = {
            'params': self.current_values(),
            'presets': self.custom_presets,
            'out_dir': self.out_edit.text().strip(),
            'template': self.tpl_edit.text(),
            'live': self.live_check.isChecked(),
            'theme': self.theme,
            'size': [self.width(), self.height()],
            'last_dir': self.settings.get('last_dir', ''),
        }
        gc.save_settings(data)

    def _restore_settings(self) -> None:
        params = self.settings.get('params')
        if isinstance(params, dict) and params:
            self.apply_values(params)
        size = self.settings.get('size')
        if isinstance(size, list) and len(size) == 2:
            self.resize(int(size[0]), int(size[1]))
        if self.settings.get('dual'):
            self.dual_check.setChecked(True)

    def closeEvent(self, event):                       # noqa: N802
        self.live_timer.stop()
        self._persist()
        super().closeEvent(event)

    # ---------------- 自检 ----------------

    def _selftest(self, app: QApplication) -> int:
        """无显示器（QT_QPA_PLATFORM=offscreen）下验证界面全链路"""
        self._no_persist = True                        # 不污染用户配置
        self.apply_values({'mode': 'linedraw'})        # 固定参数，保证自检可复现
        print('[selftest] 主题：', self.theme,
              '| 全局样式表长度：', len(QApplication.instance().styleSheet()))
        print('[selftest] 窗口构建成功：', self.windowTitle())
        print('[selftest] 参数控件数量：', len(self.widgets),
              '| 分组：', len(gc.GROUPS))
        sample = HERE / 'examples' / 'sample.png'
        if not sample.exists():                        # 打包成 exe 后没有 examples 目录
            sample = Path(tempfile.mkdtemp(prefix='inklimner_selftest_')) / 'sample.png'
            canvas = core.np.full((240, 320, 3), 255, core.np.uint8)
            core.cv2.circle(canvas, (110, 120), 60, (0, 0, 0), 3)
            core.cv2.rectangle(canvas, (190, 70), (290, 180), (0, 0, 0), 3)
            core.cv2.imwrite(str(sample), canvas)
            print('[selftest] 未找到示例图片，已生成合成测试图：', sample)
        self.live_check.setChecked(False)               # 自检时不与实时预览抢线程
        self.add_files([str(sample)])
        self.widgets['preview'].setChecked(True)
        with tempfile.TemporaryDirectory() as td:
            self.out_edit.setText(td)
            self.start()
            deadline = time.time() + 180
            while self.worker is not None and self.worker.isRunning() \
                    and time.time() < deadline:
                app.processEvents()
                time.sleep(0.05)
            app.processEvents()
            out = sorted(Path(td).glob('*.svg'))
            print('[selftest] 产出 SVG：', [p.name for p in out])
            print('[selftest] 目录内容：', sorted(p.name for p in Path(td).iterdir()))
            print('[selftest] tab索引：', self.tabs.currentIndex(),
                  '| 结果有图：', self.result_view._src is not None,
                  '| 对比有图：', self.cmp_result._src is not None,
                  '| 原图有图：', self.source_view._src is not None)
            print('[selftest] 日志末尾：', self.log.toPlainText().strip().splitlines()[-1:])
            if not out:
                print('[selftest] 失败：没有产出 SVG')
                return 1
            shot = os.environ.get('INKLIMNER_SHOT')
            if shot:
                try:
                    self.grab().save(shot)
                    print('[selftest] 界面截图已保存：', shot)
                except Exception as e:                 # noqa: BLE001
                    print('[selftest] 截图失败：', e)
        print('[selftest] 通过 ✓')
        return 0


# ============================= 入口 =============================

def run(argv=None, selftest: bool = False) -> int:
    app = QApplication.instance() or QApplication(list(argv or sys.argv[:1]))
    app.setApplicationName('InkLimner')
    # 先铺一层默认（浅色）底，避免窗口构建瞬间闪一下；真实主题由 MainWindow 应用
    if not app.styleSheet():
        app.setStyleSheet(THEMES[DEFAULT_THEME])
    win = MainWindow()
    win.show()
    if selftest:
        return win._selftest(app)
    return app.exec()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run(args, selftest='--selftest' in args)


if __name__ == '__main__':
    sys.exit(main())
