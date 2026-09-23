#!/usr/bin/env python3
"""
inklimner_gui_tk.py —— InkLimner 图形界面（Tkinter 版 · **零第三方依赖**）

本文件只包含**界面层**：参数规格、预设、CLI 命令互转、输出规划、批量执行等
共享逻辑全部在 inklimner_gui_core.py 里，两个界面（Tk / Qt）共用同一份。

更现代的外观请用 PySide6 版（inklimner_gui_qt.py），或直接运行 inklimner_gui.py
—— 它会自动挑选当前环境可用的界面。

可选增强：
  · tkinterdnd2 —— 把图片/文件夹拖进窗口     pip install "inklimner[dnd]"
  · Pillow      —— 预览与原图对比更清晰       pip install "inklimner[gui]"

启动：python inklimner_gui_tk.py
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

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

from inklimner_gui_core import (  # noqa: F401  (re-export)
    APP_TAGLINE,
    APP_TITLE,
    GROUPS,
    MODE_EXTRA,
    MODE_TIPS,
    PRESETS,
    SETTINGS_PATH,
    active_keys,
    all_keys,
    build_command,
    default_values,
    env_summary,
    force_utf8_output,
    load_settings,
    parse_command,
    save_settings,
)

QueueLogHandler = gc.QueueLogHandler
HERE = Path(__file__).resolve().parent

# 可选：拖拽支持（未安装则自动退化，不影响其它功能）
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except Exception:                                     # noqa: BLE001
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False


def enable_hidpi(root: tk.Tk) -> None:
    """高分屏适配：Windows 声明 DPI 感知 + 按实际 DPI 调整 Tk 缩放"""
    if sys.platform.startswith('win'):
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:                         # noqa: BLE001
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:                             # noqa: BLE001
            pass
    try:
        dpi = root.winfo_fpixels('1i')
        if dpi > 110:                                 # 仅在明显高 DPI 时放大
            root.tk.call('tk', 'scaling', dpi / 72.0)
    except Exception:                                 # noqa: BLE001
        pass



# ============================= 主界面 =============================

class InkLimnerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.inputs: list[Path] = []
        self.vars: dict[str, tk.Variable] = {}
        self.wrefs: dict[str, dict] = {}
        self.custom_presets: dict = {}
        self.last_out: Path | None = None
        self.busy = False
        self._live_job = None
        self._photos: dict = {}

        self.settings = load_settings()
        self.custom_presets = dict(self.settings.get('presets') or {})
        self.last_in_dir = self.settings.get('last_in_dir', '')
        self.last_out_dir = self.settings.get('last_out_dir', '')

        root.title(APP_TITLE)
        root.minsize(1120, 720)
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        try:
            style = ttk.Style()
            if 'clam' in style.theme_names():
                style.theme_use('clam')
        except tk.TclError:
            pass

        self._build()
        self._attach_logger()
        self._set_icon()
        self._restore_settings()
        self._refresh_active()

    # ---------------- 搭建 ----------------

    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill='both', expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=3)
        outer.rowconfigure(1, weight=2)

        bar = ttk.Frame(outer)
        bar.grid(row=0, column=0, sticky='ew')
        ttk.Label(bar, text=env_summary('拖拽✓' if HAS_DND else '拖拽需装 tkinterdnd2'),
                  foreground='#555').pack(side='left')

        body = ttk.Frame(outer)
        body.grid(row=1, column=0, sticky='nsew', pady=(6, 0))
        body.columnconfigure(0, weight=0, minsize=340)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_left(body)
        self._build_params(body)

        bottom = ttk.Frame(outer)
        bottom.grid(row=2, column=0, sticky='nsew', pady=(8, 0))
        outer.rowconfigure(2, weight=2)
        bottom.columnconfigure(0, weight=2)
        bottom.columnconfigure(1, weight=3)
        bottom.rowconfigure(0, weight=1)
        self._build_log(bottom)
        self._build_preview(bottom)

    def _build_left(self, parent):
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

        box = ttk.LabelFrame(left, text='输入图片', padding=8)
        box.pack(fill='both', expand=True)
        self.listbox = tk.Listbox(box, selectmode='extended', activestyle='none',
                                  height=10)
        sb = ttk.Scrollbar(box, orient='vertical', command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        ttk.Label(box, text='可拖拽图片 / 文件夹到此处' if HAS_DND
                  else '（装 tkinterdnd2 后可直接拖拽）',
                  foreground='#888').pack(anchor='w', pady=(4, 0))

        btns = ttk.Frame(left)
        btns.pack(fill='x', pady=(6, 8))
        ttk.Button(btns, text='添加图片…', command=self.add_files).pack(side='left')
        ttk.Button(btns, text='添加文件夹…', command=self.add_folder).pack(
            side='left', padx=6)
        ttk.Button(btns, text='移除选中', command=self.remove_selected).pack(side='left')
        ttk.Button(btns, text='清空', command=lambda: self._set_inputs([])).pack(
            side='left', padx=6)

        outbox = ttk.LabelFrame(left, text='输出', padding=8)
        outbox.pack(fill='x')
        self.out_var = tk.StringVar()
        row = ttk.Frame(outbox)
        row.pack(fill='x')
        ttk.Entry(row, textvariable=self.out_var).pack(
            side='left', fill='x', expand=True)
        ttk.Button(row, text='目录…', width=6,
                   command=self.pick_out_dir).pack(side='left', padx=(4, 0))
        ttk.Button(row, text='.svg', width=5,
                   command=self.pick_out_file).pack(side='left', padx=2)

        trow = ttk.Frame(outbox)
        trow.pack(fill='x', pady=(6, 0))
        self.tpl_enable = tk.BooleanVar(value=False)
        ttk.Checkbutton(trow, text='命名模板', variable=self.tpl_enable).pack(side='left')
        self.tpl_var = tk.StringVar(value='{name}')
        ttk.Entry(trow, textvariable=self.tpl_var, width=22).pack(
            side='left', padx=4, fill='x', expand=True)
        ttk.Label(outbox, foreground='#888', text='可用占位符：{name} 原文件名、'
                  '{mode} 模式名（如 {name}_cut → 图案_cut.svg）',
                  justify='left').pack(anchor='w', pady=(2, 0))
        self.dual_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(outbox, text='同时再输出一份 shape 轮廓版（_shape.svg）',
                        variable=self.dual_var).pack(anchor='w', pady=(6, 0))

        act = ttk.Frame(left)
        act.pack(fill='x', pady=(10, 0))
        self.run_btn = ttk.Button(act, text='▶  开始转换', command=self.start)
        self.run_btn.pack(side='left')
        self.stop_btn = ttk.Button(act, text='■ 停止', command=self.stop,
                                   state='disabled')
        self.stop_btn.pack(side='left', padx=6)
        ttk.Button(act, text='打开输出目录', command=self.open_output).pack(side='left')

        act2 = ttk.Frame(left)
        act2.pack(fill='x', pady=(6, 0))
        ttk.Button(act2, text='复制 CLI 命令', command=self.show_command).pack(side='left')
        ttk.Button(act2, text='粘贴 CLI 命令', command=self.paste_command).pack(
            side='left', padx=6)
        ttk.Button(act2, text='重置默认', command=self.reset_defaults).pack(side='left')

        self.progress = ttk.Progressbar(left, mode='determinate', maximum=100)
        self.progress.pack(fill='x', pady=(8, 0))
        self.status = ttk.Label(left, foreground='#444', text='就绪')
        self.status.pack(anchor='w', pady=(4, 0))

        if HAS_DND:
            try:
                self.listbox.drop_target_register(DND_FILES)
                self.listbox.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:                         # noqa: BLE001
                pass

    def _build_params(self, parent):
        wrap = ttk.LabelFrame(parent, text='参数', padding=6)
        wrap.grid(row=0, column=1, sticky='nsew')
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        canvas = tk.Canvas(wrap, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind('<Configure>',
                   lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        self.param_canvas = canvas
        canvas.bind_all('<MouseWheel>', self._on_wheel)
        canvas.bind_all('<Button-4>', lambda e: self._on_wheel(e, -1))
        canvas.bind_all('<Button-5>', lambda e: self._on_wheel(e, 1))

        # —— 预设 ——
        pbox = ttk.LabelFrame(inner, text='预设', padding=8)
        pbox.pack(fill='x', padx=4, pady=(2, 6))
        self.preset_var = tk.StringVar()
        self.preset_combo = ttk.Combobox(pbox, textvariable=self.preset_var,
                                         state='readonly', width=20)
        self.preset_combo.pack(side='left')
        ttk.Button(pbox, text='应用', width=6,
                   command=self.apply_preset).pack(side='left', padx=(6, 2))
        ttk.Button(pbox, text='另存为…', command=self.save_preset).pack(side='left', padx=2)
        ttk.Button(pbox, text='删除', width=6,
                   command=self.delete_preset).pack(side='left', padx=2)
        self._refresh_preset_list()

        defaults = default_values()
        self.mode_tip = ttk.Label(inner, foreground='#0057b8', wraplength=640,
                                  justify='left', text='')
        self.mode_tip.pack(anchor='w', padx=6, pady=(0, 6))

        for title, _subtitle, items in GROUPS:
            box = ttk.LabelFrame(inner, text=title, padding=8)
            box.pack(fill='x', padx=4, pady=4)
            box.columnconfigure(1, weight=1)
            for r, (key, label, kind, extra, hint, _flag) in enumerate(items):
                lab = ttk.Label(box, text=label)
                lab.grid(row=r, column=0, sticky='w', pady=3)
                w = self._make_widget(box, r, key, kind, extra, defaults.get(key))
                hl = ttk.Label(box, text=hint, foreground='#777')
                hl.grid(row=r, column=2, sticky='w', padx=(12, 0), pady=3)
                self.wrefs[key] = {'label': lab, 'input': w, 'hint': hl, 'kind': kind}

        lbox = ttk.LabelFrame(inner, text='实时预览', padding=8)
        lbox.pack(fill='x', padx=4, pady=(6, 4))
        self.live_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lbox, text='修改参数后自动重跑（单张小图，约 0.4s 防抖）',
                        variable=self.live_var,
                        command=lambda: None).pack(anchor='w')
        ttk.Label(lbox, foreground='#888',
                  text='仅当只选了 1 张图片、且最长边 ≤ 2000px 时触发；'
                       '大图请手动点「开始转换」').pack(anchor='w')

    def _make_widget(self, box, row, key, kind, extra, default):
        if kind == 'check':
            var = tk.BooleanVar(value=bool(default))
            w = ttk.Checkbutton(box, variable=var, command=self._on_change)
            w.grid(row=row, column=1, sticky='w')
        elif kind == 'combo':
            var = tk.StringVar(value=str(default))
            w = ttk.Combobox(box, textvariable=var, values=extra,
                             state='readonly', width=14)
            w.grid(row=row, column=1, sticky='w')
            w.bind('<<ComboboxSelected>>', lambda e: self._on_change())
        elif kind in ('spin_i', 'spin_f'):
            lo, hi, step = extra
            var = tk.IntVar(value=int(default)) if kind == 'spin_i' \
                else tk.DoubleVar(value=float(default))
            w = ttk.Spinbox(box, from_=lo, to=hi, increment=step,
                            textvariable=var, width=14,
                            command=self._on_change)
            w.bind('<FocusOut>', lambda e: self._on_change())
            w.bind('<Return>', lambda e: self._on_change())
        else:
            var = tk.StringVar(value='' if default is None else str(default))
            w = ttk.Entry(box, textvariable=var, width=16)
            w.grid(row=row, column=1, sticky='w')
            w.bind('<FocusOut>', lambda e: self._on_change())
            w.bind('<Return>', lambda e: self._on_change())
        self.vars[key] = var
        return w

    def _build_log(self, parent):
        box = ttk.LabelFrame(parent, text='日志', padding=6)
        box.grid(row=0, column=0, sticky='nsew')
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.log_text = tk.Text(box, height=10, wrap='word', state='disabled',
                                background='#1e1e1e', foreground='#d4d4d4',
                                insertbackground='#d4d4d4', font=('Consolas', 9))
        sb = ttk.Scrollbar(box, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.grid(row=0, column=0, sticky='nsew')
        sb.grid(row=0, column=1, sticky='ns')
        row = ttk.Frame(box)
        row.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        ttk.Button(row, text='清空日志', command=self.clear_log).pack(side='left')
        ttk.Button(row, text='复制日志', command=self.copy_log).pack(side='left', padx=6)

    def _build_preview(self, parent):
        box = ttk.LabelFrame(parent, text='预览', padding=6)
        box.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
        head = ttk.Frame(box)
        head.pack(fill='x')
        self.cmp_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(head, text='对比原图', variable=self.cmp_var,
                        command=self._layout_preview).pack(side='left')
        self.preview_name = ttk.Label(head, foreground='#666', text='')
        self.preview_name.pack(side='left', padx=8)

        self.pv_body = ttk.Frame(box)
        self.pv_body.pack(fill='both', expand=True, pady=(6, 0))
        self.pv_orig = ttk.Label(self.pv_body, anchor='center',
                                 background='#fafafa', text='原图')
        self.pv_res = ttk.Label(self.pv_body, anchor='center',
                                background='#fafafa',
                                text='（转换后在此显示线稿预览）')

    # ---------------- 通用 ----------------

    def _set_icon(self):
        p = HERE / 'assets' / 'logo.png'
        if not p.exists():
            return
        try:
            self._icon = tk.PhotoImage(file=str(p))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass

    def _attach_logger(self):
        lg = logging.getLogger('inklimner')
        lg.setLevel(logging.INFO)
        lg.addHandler(QueueLogHandler(self.q))
        lg.propagate = False

    def _append_log(self, text: str):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        self.log_text.configure(state='disabled')

    def copy_log(self):
        text = self.log_text.get('1.0', 'end').strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._append_log('[界面] 日志已复制到剪贴板')

    def _on_wheel(self, event, direction=None):
        try:
            w = self.root.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return
        while w is not None:
            if w is self.log_text or w is self.listbox:
                return
            w = getattr(w, 'master', None)
        if direction is None:
            direction = -1 if getattr(event, 'delta', 0) > 0 else 1
        self.param_canvas.yview_scroll(direction, 'units')

    def _on_change(self):
        """任一参数变化：刷新联动状态 + 排程实时预览"""
        self._refresh_active()
        self._schedule_live()

    def _refresh_active(self):
        mode = self.vars['mode'].get()
        self.mode_tip.configure(text=MODE_TIPS.get(mode, ''))
        act = active_keys(mode)
        for key, ref in self.wrefs.items():
            on = key in act
            kind = ref['kind']
            if kind == 'combo':
                ref['input'].configure(state='readonly' if on else 'disabled')
            else:
                ref['input'].configure(state='normal' if on else 'disabled')
            col = '#000000' if on else '#b4b4b4'
            ref['label'].configure(foreground=col)
            ref['hint'].configure(foreground='#777777' if on else '#c8c8c8')

    # ---------------- 输入 ----------------

    def _set_inputs(self, paths):
        self.inputs = []
        for p in paths:
            p = Path(p)
            if p not in self.inputs:
                self.inputs.append(p)
        self.listbox.delete(0, 'end')
        for p in self.inputs:
            self.listbox.insert('end', str(p))
        self.status.configure(text=f'已选 {len(self.inputs)} 项')
        self._schedule_live()

    def _on_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:                             # noqa: BLE001
            paths = [event.data]
        cur = [str(p) for p in self.inputs]
        for p in paths:
            if p not in cur:
                cur.append(p)
        self._set_inputs(cur)
        self._append_log(f'[拖拽] 已添加 {len(paths)} 项')

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title='选择图片（可多选）', initialdir=self.last_in_dir or None,
            filetypes=[('图片', ' '.join('*' + e for e in core.SUPPORTED)),
                       ('所有文件', '*.*')])
        if paths:
            self.last_in_dir = str(Path(paths[0]).parent)
            self._set_inputs(list(self.inputs) + [Path(p) for p in paths])

    def add_folder(self):
        d = filedialog.askdirectory(title='选择图片文件夹',
                                    initialdir=self.last_in_dir or None)
        if d:
            self.last_in_dir = d
            self._set_inputs(list(self.inputs) + [Path(d)])

    def remove_selected(self):
        for i in sorted(self.listbox.curselection(), reverse=True):
            del self.inputs[i]
        self._set_inputs(list(self.inputs))

    def pick_out_dir(self):
        d = filedialog.askdirectory(title='选择输出目录',
                                    initialdir=self.last_out_dir or None)
        if d:
            self.last_out_dir = d
            self.out_var.set(d)

    def pick_out_file(self):
        f = filedialog.asksaveasfilename(
            title='指定输出 SVG 文件（仅单张）', defaultextension='.svg',
            initialdir=self.last_out_dir or None, filetypes=[('SVG', '*.svg')])
        if f:
            self.last_out_dir = str(Path(f).parent)
            self.out_var.set(f)

    # ---------------- 预设 ----------------

    def _refresh_preset_list(self):
        names = list(PRESETS) + list(self.custom_presets)
        self.preset_combo.configure(values=names)
        if names and not self.preset_var.get():
            self.preset_var.set(names[0])

    def apply_preset(self):
        name = self.preset_var.get()
        data = self.custom_presets.get(name) or PRESETS.get(name)
        if not data:
            return
        for k, v in data.items():
            if k in self.vars:
                self.vars[k].set(v)
        self._on_change()
        self._append_log(f'[预设] 已应用「{name}」（仅覆盖该预设涉及的参数）')

    def save_preset(self):
        name = simpledialog.askstring('另存为预设', '预设名称：', parent=self.root)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in PRESETS:
            messagebox.showwarning('名称冲突', '该名称与内置预设相同，请换一个')
            return
        self.custom_presets[name] = {
            k: v.get() for k, v in self.vars.items()}
        self._refresh_preset_list()
        self.preset_var.set(name)
        self._persist()
        self._append_log(f'[预设] 已保存「{name}」（含全部参数当前值）')

    def delete_preset(self):
        name = self.preset_var.get()
        if name not in self.custom_presets:
            messagebox.showinfo('提示', '只能删除自己保存的预设（内置预设不可删）')
            return
        if not messagebox.askyesno('确认', f'删除预设「{name}」？'):
            return
        self.custom_presets.pop(name, None)
        self._refresh_preset_list()
        self.preset_var.set('')
        self._persist()
        self._append_log(f'[预设] 已删除「{name}」')

    # ---------------- 参数 ↔ 命令 ----------------

    def collect_args(self) -> argparse.Namespace:
        """界面取值 → 与 CLI 完全一致的参数空间（经 core 层统一，避免两边漂移）"""
        return gc.values_to_namespace(self.current_values())

    def current_values(self) -> dict:
        out = {}
        for k, v in self.vars.items():
            try:
                out[k] = v.get()
            except tk.TclError:
                out[k] = None
        return out

    def show_command(self):
        cmd = build_command(self.current_values(),
                            [str(p) for p in self.inputs] or None)
        win = tk.Toplevel(self.root)
        win.title('等效 CLI 命令')
        win.transient(self.root)
        ttk.Label(win, text='把下面这行贴到终端即可复现当前设置（也可用来求助）：',
                  foreground='#555').pack(anchor='w', padx=10, pady=(10, 4))
        txt = tk.Text(win, width=96, height=6, wrap='word')
        txt.insert('1.0', cmd)
        txt.configure(state='disabled')
        txt.pack(padx=10, fill='both', expand=True)

        def _copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(cmd)
            self._append_log('[界面] CLI 命令已复制')

        row = ttk.Frame(win)
        row.pack(pady=8, padx=10, anchor='e')
        ttk.Button(row, text='复制', command=_copy).pack(side='left')
        ttk.Button(row, text='关闭', command=win.destroy).pack(side='left', padx=6)

    def paste_command(self):
        text = simpledialog.askstring(
            '粘贴 CLI 命令', '粘贴一条 inklimner 命令（会自动回填各项参数）：',
            parent=self.root)
        if not text or not text.strip():
            return
        try:
            vals = parse_command(text)
        except ValueError as e:
            messagebox.showerror('解析失败', str(e))
            return
        for k, v in vals.items():
            if k in self.vars:
                self.vars[k].set(v)
        self._on_change()
        self._append_log('[界面] 已从命令回填参数')

    def reset_defaults(self):
        for k, v in default_values().items():
            self.vars[k].set(v)
        self._on_change()
        self._append_log('[界面] 参数已重置为默认值')

    # ---------------- 配置持久化 ----------------

    def _restore_settings(self):
        for k, v in (self.settings.get('params') or {}).items():
            if k in self.vars:
                try:
                    self.vars[k].set(v)
                except tk.TclError:
                    pass
        geo = self.settings.get('geometry')
        if geo:
            try:
                self.root.geometry(geo)
            except tk.TclError:
                pass
        self.out_var.set(self.settings.get('output', ''))
        self.tpl_var.set(self.settings.get('template', '{name}'))
        self.tpl_enable.set(bool(self.settings.get('template_on', False)))
        self.dual_var.set(bool(self.settings.get('dual', False)))
        self.live_var.set(bool(self.settings.get('live', True)))
        paths = self.settings.get('inputs') or []
        if paths:
            self._set_inputs([Path(p) for p in paths if Path(p).exists()])

    def _persist(self):
        data = {
            'geometry': self.root.winfo_geometry(),
            'params': self.current_values(),
            'inputs': [str(p) for p in self.inputs],
            'output': self.out_var.get(),
            'template': self.tpl_var.get(),
            'template_on': self.tpl_enable.get(),
            'dual': self.dual_var.get(),
            'live': self.live_var.get(),
            'last_in_dir': self.last_in_dir,
            'last_out_dir': self.last_out_dir,
            'presets': self.custom_presets,
        }
        save_settings(data)

    def on_close(self):
        try:
            self._persist()
        finally:
            self.root.destroy()

    # ---------------- 实时预览 ----------------

    def _schedule_live(self):
        if not self.live_var.get() or self.busy:
            return
        if len(self.inputs) != 1 or self.inputs[0].is_dir():
            return
        if self._live_job:
            self.root.after_cancel(self._live_job)
        self._live_job = self.root.after(400, self._run_live)

    def _run_live(self):
        self._live_job = None
        if self.busy or len(self.inputs) != 1:
            return
        src = self.inputs[0]
        try:
            img = core.imread_cn(str(src), apply_orientation=False)
            if max(img.shape[:2]) > 2000:
                return
            args = self.collect_args()
        except Exception:                             # noqa: BLE001
            return
        args.preview = True
        args.quiet = True
        args.force = True
        self.busy = True
        self.status.configure(text='实时预览中…')
        threading.Thread(target=self._live_worker, args=(src, args),
                         daemon=True).start()
        self.root.after(60, self._drain)

    def _live_worker(self, src, args):
        try:
            outdir = Path(tempfile.mkdtemp(prefix='inklimner_live_'))
            dst = outdir / (src.stem + '.svg')
            core.convert(src, dst, args)
            pv = dst.with_name(dst.stem + '.preview.png')
            if pv.exists():
                self.q.put(('LIVE', str(pv), src))
        except Exception:                             # noqa: BLE001
            pass
        finally:
            self.q.put(('LIVE_DONE',))

    # ---------------- 正式转换 ----------------

    def start(self):
        if self.busy:
            return
        files = [p for f in self.inputs
                 for p in (sorted(f.iterdir()) if f.is_dir() else [f])
                 if p.is_file() and p.suffix.lower() in core.SUPPORTED]
        if not files:
            messagebox.showwarning('没有输入',
                                   '请先添加至少一张图片（或包含图片的文件夹）')
            return
        try:
            args = self.collect_args()
        except ValueError as e:
            messagebox.showerror('参数错误', str(e))
            return
        out = Path(self.out_var.get().strip()) if self.out_var.get().strip() else None
        try:
            pairs = self._plan(files, out, args)
        except ValueError as e:
            messagebox.showerror('输出设置有问题', str(e))
            return

        self.clear_log()
        self.cancel.clear()
        self.run_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.progress.configure(value=0)
        self.status.configure(text=f'开始处理 {len(pairs)} 个文件…')
        self._append_log(f'▶ 共 {len(pairs)} 个文件，模式 {args.mode}')
        self._run_mode = args.mode
        self.busy = True
        threading.Thread(target=self._worker, args=(pairs, args),
                         daemon=True).start()
        self.root.after(80, self._drain)

    def _plan(self, files, out, args):
        """在 core.plan_jobs 之上叠加：命名模板 + 双模式输出"""
        return gc.plan_pairs(
            files, out, mode=args.mode,
            use_template=bool(self.tpl_enable.get()),
            template=self.tpl_var.get() or '{name}',
            dual=bool(self.dual_var.get()))

    def stop(self):
        self.cancel.set()
        self.status.configure(text='正在停止…（当前文件处理完后中断）')

    def _worker(self, pairs, args):
        """后台工作线程：实际执行交给 gc.run_batch，本方法只负责转发事件"""
        ok, fail, skip, _ = gc.run_batch(
            pairs, args,
            on_log=lambda msg: self.q.put(('LOG', msg)),
            on_progress=lambda i, total: self.q.put(('PROG', i, total)),
            on_output=lambda dst, s, mode: self.q.put(('OUT', str(dst), str(s), mode)),
            cancel=self.cancel)
        self.q.put(('DONE', ok, fail, skip))

    def _drain(self):
        done = False
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == 'LOG':
                    self._append_log(item[1])
                elif kind == 'PROG':
                    i, total = item[1], item[2]
                    self.progress.configure(value=i / max(total, 1) * 100)
                    self.status.configure(text=f'进度 {i}/{total}')
                elif kind == 'OUT':
                    self.last_out = Path(item[1]).parent
                    if item[3] == getattr(self, '_run_mode', item[3]) \
                            or self.cmp_var.get():
                        self._show_result(Path(item[1]), Path(item[2]))
                elif kind == 'LIVE':
                    self._show_result(Path(item[1]), Path(item[2]))
                    self.status.configure(text='实时预览已更新')
                elif kind == 'LIVE_DONE':
                    self.busy = False
                elif kind == 'DONE':
                    done = True
                    ok, fail, skip = item[1], item[2], item[3]
                    self.busy = False
                    self._append_log(f'■ 完成：成功 {ok}，失败 {fail}，跳过 {skip}')
                    self.status.configure(
                        text=f'完成（成功 {ok} / 失败 {fail} / 跳过 {skip}）')
                    self.run_btn.configure(state='normal')
                    self.stop_btn.configure(state='disabled')
                    self._persist()
        except queue.Empty:
            pass
        if not done and self.busy:
            self.root.after(80, self._drain)

    # ---------------- 预览显示 ----------------

    def _fit_photo(self, path, box):
        try:
            from PIL import Image, ImageTk
            im = Image.open(path)
            im.thumbnail(box)
            return ImageTk.PhotoImage(im)
        except ImportError:
            pass
        except Exception:                             # noqa: BLE001
            return None
        try:
            img = tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None
        k = max(1, int(max(img.width() / box[0], img.height() / box[1])))
        return img.subsample(k, k) if k > 1 else img

    def _show_result(self, dst, src):
        pv = dst.with_name(dst.stem + '.preview.png')
        if not pv.exists():
            return
        self._photos['res'] = self._fit_photo(pv, (300, 320) if self.cmp_var.get()
                                              else (620, 360))
        if src and Path(src).exists():
            self._photos['orig'] = self._fit_photo(
                src, (300, 320) if self.cmp_var.get() else (620, 360)) \
                if self.cmp_var.get() else None
        self.preview_name.configure(text=f'{dst.name}   ←   {Path(src).name}')
        self._layout_preview()

    def _layout_preview(self):
        self.pv_orig.pack_forget()
        self.pv_res.pack_forget()
        res = self._photos.get('res')
        orig = self._photos.get('orig')
        if self.cmp_var.get():
            self.pv_orig.pack(side='left', fill='both', expand=True, padx=(0, 4))
            self.pv_res.pack(side='left', fill='both', expand=True)
            if orig is None:
                self.pv_orig.configure(image='', text='原图预览需安装 Pillow\n'
                                                      'pip install "inklimner[gui]"')
            else:
                self.pv_orig.configure(image=orig, text='')
        else:
            self.pv_res.pack(fill='both', expand=True)
        if res is None:
            self.pv_res.configure(image='',
                                  text='（勾选"生成 PNG 预览"并转换后显示）')
        else:
            self.pv_res.configure(image=res, text='')

    # ---------------- 其它 ----------------

    def open_output(self):
        d = self.last_out
        if d is None:
            out = self.out_var.get().strip()
            d = Path(out) if out else (self.inputs[0].parent if self.inputs else None)
            if d is not None and d.suffix.lower() == '.svg':
                d = d.parent
        if d is None or not Path(d).exists():
            messagebox.showinfo('提示', '还没有可打开的输出目录')
            return
        d = str(d)
        try:
            if sys.platform.startswith('win'):
                os.startfile(d)                       # noqa: S606
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', d])
            else:
                subprocess.Popen(['xdg-open', d])
        except Exception as e:                        # noqa: BLE001
            messagebox.showwarning('打不开目录', f'{e}\n目录：{d}')


def make_root():
    """优先用支持拖拽的 TkinterDnD.Tk()，否则退回标准 tk.Tk()"""
    if HAS_DND:
        try:
            return TkinterDnD.Tk()
        except Exception:                             # noqa: BLE001
            pass
    return tk.Tk()


def main(argv=None) -> int:
    """启动图形界面"""
    force_utf8_output()          # 控制台编码兜底（非 UTF-8 环境打印中文会崩）
    try:
        root = make_root()
    except tk.TclError as e:
        print('无法启动图形界面（缺少显示环境？）：', e, file=sys.stderr)
        print('若在 Linux 服务器上，请安装 python3-tk 并使用图形桌面；'
              '也可直接用命令行： inklimner --help', file=sys.stderr)
        return 3
    enable_hidpi(root)
    InkLimnerGUI(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
