#!/usr/bin/env python3
"""
InkLimner —— 位图转 SVG 线稿（inklimner.py v3.4.1.1，含图形界面）

模式：
  linedraw  XDoG 线稿 + 骨架中心线（默认，最像手绘线稿，激光只走单线）
  edge      Canny 边缘 + 骨架中心线（照片描线）
  multi     灰度波段等值线（层次分明，类似地形图）
  shape     色块轮廓（剪纸风，可借助 potrace 圆滑）

v3.1 已修复：
  1. 内置细化算法邻居索引越界崩溃
  2. 骨架走线在交叉点处丢边、闭环不闭合
  3. --dilate 1 无效
  4. potrace 未安装时启动崩溃 / transform 坐标错乱（完整保留）

v3.2 更新：
  1. 修复 --px-per-mm 与 --max-size 联用时的物理尺寸偏差
  2. multi 灰度带新增 --band-max
  3. --preview 扩展到全部模式
  4. 细化限定非零包围盒提速；批量多进程；失败返回非零退出码
  5. 新增 --version / -q/--quiet / --force / --no-overwrite
  6. potrace 改为惰性探测；调色板 PNG 自动按彩色解码

v3.3 更新：
  1. EXIF 方向自动校正（手机照片不再横竖颠倒），--no-exif 可关闭
  2. 新增 --dpi（比 --px-per-mm 更直观，自动按 dpi/25.4 换算）
  3. 新增 --trim（自动裁掉四周白边）与 --margin（成品留白）
  4. 输出确定性：轮廓/线段排序，同输入产出逐字节一致
  5. 细化算法向量化（A/B 计算）+ 大图非线性上限，纯 Python 回退更快
  6. 改用 logging；新增 -j/--jobs 控制并发与进度输出
  7. 支持 pip 安装与 `inklimner` 命令行入口（见 pyproject.toml）

v3.4.1.1 更新（新增图形界面）：
  1. 图形界面 inklimner_gui.py（Tkinter，零强制依赖）：参数随模式联动置灰、
     参数预设、CLI 命令互转、拖拽导入、实时预览、原图/结果对比、双版本输出、
     命名模板、环境状态条、配置记忆（~/.inklimner_gui.json）、高 DPI 适配
  2. 新增 --gui，一条命令直接打开界面；新增 inklimner-gui 命令行入口
  3. 抽出 build_parser() / plan_jobs()，CLI 与 GUI 共用同一套参数与输出规划

依赖：pip install opencv-python numpy
推荐（细化提速约百倍）：pip uninstall opencv-python && pip install opencv-contrib-python
可选（仅 shape/multi 模式受益，需 potrace 1.9+）：安装 potrace
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

__version__ = '3.4.1.1'
__all__ = ['convert', 'main', 'build_svg', 'gather_inputs', 'find_potrace']

log = logging.getLogger('inklimner')

SUPPORTED = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff')

# 复用的形态学核（避免每次调用重复分配）
K3 = np.ones((3, 3), np.uint8)
K2 = np.ones((2, 2), np.uint8)

# 8 邻域偏移（顺序 = P2..P9，顺时针）
_OFFS = ((-1, 0), (-1, 1), (0, 1), (1, 1),
         (1, 0), (1, -1), (0, -1), (-1, -1))


# ---------------- potrace 安全探测（惰性） ----------------

_POTRACE_CACHE: list = []


def find_potrace():
    """惰性探测 potrace：找到后缓存路径，找不到缓存 None（避免反复探测）"""
    if _POTRACE_CACHE:
        return _POTRACE_CACHE[0]
    exe = 'potrace.exe' if os.name == 'nt' else 'potrace'
    found = None
    for c in ('potrace', str(Path(__file__).resolve().parent / exe)):
        try:
            if subprocess.run([c, '--version'], capture_output=True).returncode == 0:
                found = c
                break
        except (OSError, PermissionError):
            continue
    _POTRACE_CACHE.append(found)
    return found


# ---------------- EXIF 方向 ----------------

def exif_orientation(data: bytes) -> int:
    """从图片字节流中解析 EXIF Orientation（1~8）；解析不到返回 1。

    支持 JPEG 的 APP1 Exif 段与 PNG 的 eXIf 块（同为 TIFF 结构）。
    """
    tiff = None
    i = data.find(b'Exif\x00\x00')
    if i != -1:
        tiff = i + 6
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        j = data.find(b'eXIf')
        if j != -1:
            tiff = j + 4
    if tiff is None or tiff + 8 > len(data):
        return 1
    b = data[tiff:tiff + 8]
    if b[:2] == b'II':
        end = 'little'
    elif b[:2] == b'MM':
        end = 'big'
    else:
        return 1
    if int.from_bytes(b[2:4], end) != 42:
        return 1
    off = int.from_bytes(b[4:8], end)
    base = tiff + off                                   # IFD0 起始
    if base + 2 > len(data):
        return 1
    n = int.from_bytes(data[base:base + 2], end)
    for k in range(n):
        e = base + 2 + k * 12
        if e + 12 > len(data):
            break
        tag = int.from_bytes(data[e:e + 2], end)
        if tag == 0x0112:                               # Orientation
            val = int.from_bytes(data[e + 8:e + 10], end)
            return val if 1 <= val <= 8 else 1
    return 1


def apply_exif(img, orientation: int):
    """按 EXIF Orientation 旋转/镜像图像"""
    if orientation == 2:
        return cv2.flip(img, 1)
    if orientation == 3:
        return cv2.rotate(img, cv2.ROTATE_180)
    if orientation == 4:
        return cv2.flip(img, 0)
    if orientation == 5:
        return cv2.transpose(img)
    if orientation == 6:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if orientation == 7:
        return cv2.flip(cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), 1)
    if orientation == 8:
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return img


# ---------------- 基础工具 ----------------

def imread_cn(path, apply_orientation: bool = True) -> np.ndarray:
    """读取图片（兼容中文路径；调色板 PNG 自动按彩色解码；可选自动应用 EXIF 方向）"""
    data = np.fromfile(path, dtype=np.uint8)
    # PNG 调色板图（IHDR color type == 3）用 IMREAD_UNCHANGED 可能拿到索引值，
    # 会把调色板索引误当灰度 → 改用彩色解码（PNG 头偏移 25 即 color type）。
    is_palette_png = (data[:8].tobytes() == b'\x89PNG\r\n\x1a\n'
                      and len(data) > 25 and int(data[25]) == 3)
    flag = cv2.IMREAD_COLOR if is_palette_png else cv2.IMREAD_UNCHANGED
    img = cv2.imdecode(data, flag)
    if img is None:
        raise OSError(f"无法读取图片: {path}")
    if apply_orientation:
        img = apply_exif(img, exif_orientation(data.tobytes()))
    return img


def to_gray(img: np.ndarray) -> np.ndarray:
    """转灰度；RGBA 透明区域按白底处理"""
    if img.ndim == 2:
        return img
    if img.shape[-1] == 4:
        bgr = img[:, :, :3].copy()
        bgr[img[:, :, 3] == 0] = 255
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def find_contours(binary):
    res = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    return res[0] if len(res) == 2 else res[1]


def _content_bbox(gray: np.ndarray, thresh: int = 250):
    """非白内容包围盒 (x, y, w, h)；全白时返回整幅"""
    ys, xs = np.nonzero(gray < thresh)
    if ys.size == 0:
        return 0, 0, gray.shape[1], gray.shape[0]
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return x0, y0, x1 - x0, y1 - y0


# ---------------- XDoG 线稿提取 ----------------

def xdog_line_art(gray: np.ndarray, detail: float = 0.7) -> np.ndarray:
    """返回二值图：线条=255(白)，背景=0(黑)。detail 0~1 越大细节越多"""
    g = gray.astype(np.float64) / 255.0
    sigma   = 0.5 + (1.0 - detail) * 1.5
    k       = 1.6
    p       = 20 + detail * 60
    epsilon = 0.005 + (1.0 - detail) * 0.04
    phi     = 0.5 + detail * 10

    g1 = cv2.GaussianBlur(g, (0, 0), sigma)
    g2 = cv2.GaussianBlur(g, (0, 0), sigma * k)
    dog = g1 - p * (g2 - g1) * 0.5

    u = np.where(dog >= epsilon, 1.0, 1.0 + np.tanh(phi * (dog - epsilon)))
    art = (u * 255).astype(np.uint8)                     # 白纸黑线
    _, bw = cv2.threshold(art, 128, 255, cv2.THRESH_BINARY_INV)  # → 白=线
    return bw


# ---------------- 细化（Zhang-Suen） ----------------

def thinning(bw: np.ndarray) -> np.ndarray:
    """优先用 opencv-contrib 的 C++ 实现；否则退回内置 numpy 版"""
    if hasattr(cv2, 'ximgproc') and hasattr(cv2.ximgproc, 'thinning'):
        return cv2.ximgproc.thinning(bw, cv2.ximgproc.THINNING_ZHANGSUEN)
    return _thin_zhang_suen(bw)


def _thin_zhang_suen(bw: np.ndarray) -> np.ndarray:
    src = (bw > 0).astype(np.uint8)
    ys, xs = np.nonzero(src)
    if ys.size == 0:
        return np.zeros_like(src) * 255

    # 只在非零包围盒内迭代（外圈恒为 0，结果与全图一致但快得多）
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    I = np.pad(src[y0:y1, x0:x1], 1)

    # 迭代上限随目标规模增长（避免大图白跑满 1000 轮）
    max_iter = max(20, min(1000, int(np.hypot(y1 - y0, x1 - x0))))

    steps = (((0, 2, 4), (2, 4, 6)),    # P2*P4*P6==0, P4*P6*P8==0
             ((0, 2, 6), (0, 4, 6)))    # P2*P4*P8==0, P2*P6*P8==0
    for _ in range(max_iter):
        changed = False
        for (i1, i2, i3), (j1, j2, j3) in steps:
            P = np.stack([np.roll(np.roll(I, -dy, 0), -dx, 1)
                          for dy, dx in _OFFS])               # (8, H, W) = P2..P9
            Pn = np.roll(P, -1, axis=0)                        # Pn[i] = P[i+1]
            A = np.count_nonzero((P == 0) & (Pn == 1), axis=0)  # 0→1 跳变数
            B = P.sum(axis=0)
            mask = ((I == 1) & (B >= 2) & (B <= 6) & (A == 1) &
                    (P[i1] * P[i2] * P[i3] == 0) &
                    (P[j1] * P[j2] * P[j3] == 0))
            if mask.any():
                I[mask] = 0
                changed = True
        if not changed:
            break

    out = np.zeros_like(src)
    out[y0:y1, x0:x1] = I[1:-1, 1:-1]
    return (out * 255).astype(np.uint8)


# ---------------- 骨架 → 中心线 ----------------

def _build_nbrs(pts):
    """构建 8 邻接表，并剔除「对角捷径」冗余边。

    浅斜率的 1px 骨架里，一个像素常会同时连到正前和斜前方的像素，
    从而凭空出现 "度=3/4" 的假交叉点 —— 追踪时会被迫在那里断线。
    规则：若对角邻点之外还存在正交公共邻点（可经由它绕过去），
    则该对角边冗余，去掉后骨架自然成为干净的通路。
    """
    nbrs = {}
    for (x, y) in pts:
        ns = []
        for dx, dy in _OFFS:
            q = (x + dx, y + dy)
            if q not in pts:
                continue
            if dx != 0 and dy != 0:
                if (x + dx, y) in pts or (x, y + dy) in pts:
                    continue
            ns.append(q)
        nbrs[(x, y)] = ns
    return nbrs


def trace_polylines(skel_bw: np.ndarray, min_len: int = 8,
                    simplify: float = 0.001, join_gap: float = 3.0):
    """1px 骨架 → [(折线坐标, 是否闭环), ...]（按位置排序，保证输出确定性）"""
    sk = skel_bw > 0
    ys, xs = np.nonzero(sk)
    pts = set(zip(xs.tolist(), ys.tolist()))
    if not pts:
        return []
    nbrs = _build_nbrs(pts)
    deg = {p: len(n) for p, n in nbrs.items()}
    visited, frags = set(), []

    def walk(p0, p1):
        path = [p0, p1]
        visited.update(((p0, p1), (p1, p0)))
        while deg[path[-1]] == 2:
            cur, prev = path[-1], path[-2]
            a, b = nbrs[cur]
            nxt = b if a == prev else a
            if (cur, nxt) in visited:
                break
            visited.update(((cur, nxt), (nxt, cur)))
            path.append(nxt)
        return path

    # 1) 自由端点优先走长链；2) 兜底扫全部剩余边（交叉点之间不再丢边）
    order = [p for p in pts if deg[p] == 1] + [p for p in pts if deg[p] >= 2]
    for p in order:
        for q in nbrs[p]:
            if (p, q) not in visited:
                frags.append(walk(p, q))

    # 顺序很关键：先补断口、再拼天然断点，最后才过滤毛刺。
    # 否则「被噪声切碎的长线」会因每段都短于 min_len 而整条消失。
    frags = [f for f in frags if len(f) >= 2]
    if join_gap > 0:
        frags = _join_gaps(frags, join_gap)              # ① 接上短断口
    frags = _merge_fragments(frags, deg)                 # ② 拼度数为 2 的断点
    if join_gap > 0:
        frags = _join_gaps(frags, join_gap)              # ③ 拼接后可能又现可接端点
    frags = [f for f in frags if len(f) >= min_len]      # ④ 最后才过滤毛刺/碎段

    out = []
    for pl in frags:
        closed = (len(pl) >= 4 and
                  abs(pl[0][0] - pl[-1][0]) <= 1 and
                  abs(pl[0][1] - pl[-1][1]) <= 1)        # 环形结构闭合
        arr = np.array(pl, np.float32).reshape(-1, 1, 2)
        ap = cv2.approxPolyDP(arr, max(simplify * len(pl), 0.3), closed)
        if len(ap) >= (3 if closed else 2):
            out.append((ap.reshape(-1, 2).astype(float), closed))
    out.sort(key=lambda pc: (float(pc[0][:, 0].min()),
                             float(pc[0][:, 1].min())))
    return out


def _out_dir(pts, which, k: int = 4):
    """端点处「向外」的单位方向（which：0=起点，1=终点）"""
    n = len(pts)
    if n < 2:
        return (0.0, 0.0)
    if which == 0:
        a, b = pts[0], pts[min(k, n - 1)]
    else:
        a, b = pts[max(0, n - 1 - k)], pts[-1]
    vx, vy = float(b[0] - a[0]), float(b[1] - a[1])
    m = (vx * vx + vy * vy) ** 0.5
    return (vx / m, vy / m) if m > 1e-9 else (0.0, 0.0)


def _join_gaps(frags, max_gap: float = 3.0, cos_thresh: float = 0.6):
    """把端点足够近、且方向连贯的折线接起来（修复「线条被切断」）。

    判定：从 a 的端点指向 b 的端点的方向，与**至少一侧**的前进方向夹角足够小
    （允许另一侧是拐角）。这样既能补上直线/曲线上的断口，又不会把两条平行线粘死。
    最后若某条链自身首尾可平滑相接，则补一个首点使其闭环。
    """
    chains = [list(f) for f in frags if len(f) >= 2]
    if max_gap <= 0 or len(chains) < 2:
        return _close_self(chains, max_gap, cos_thresh)
    g2, cell = max_gap * max_gap, max(max_gap, 0.5)
    while True:
        ends = []
        for i, c in enumerate(chains):
            if not c:
                continue
            d0, d1 = _out_dir(c, 0), _out_dir(c, 1)
            if d0 != (0.0, 0.0):
                ends.append((i, 0, c[0], d0))
            if d1 != (0.0, 0.0):
                ends.append((i, 1, c[-1], d1))
        buckets = {}
        for idx, (_i, _w, pt, _d) in enumerate(ends):
            buckets.setdefault((int(pt[0] // cell), int(pt[1] // cell)),
                               []).append(idx)
        best = None
        for ai, (i, wi, pi, di) in enumerate(ends):
            cx, cy = int(pi[0] // cell), int(pi[1] // cell)
            for gx in (cx - 1, cx, cx + 1):
                for gy in (cy - 1, cy, cy + 1):
                    for bj in buckets.get((gx, gy), ()):
                        if bj <= ai:
                            continue
                        j, wj, pj, dj = ends[bj]
                        if i == j:
                            continue
                        vx, vy = pj[0] - pi[0], pj[1] - pi[1]
                        d2 = vx * vx + vy * vy
                        if d2 > g2 or d2 < 1e-12:
                            continue
                        ux, uy = vx / (d2 ** 0.5), vy / (d2 ** 0.5)
                        # 端点朝向感知：接在「终点」后面取正号，接在「起点」前面取负号
                        ta = ux * di[0] + uy * di[1]
                        if wi == 0:
                            ta = -ta
                        tb = ux * dj[0] + uy * dj[1]
                        if wj == 1:
                            tb = -tb
                        if max(ta, tb) < cos_thresh:
                            continue
                        if best is None or d2 < best[0]:
                            best = (d2, i, wi, j, wj)
        if best is None:
            break
        _, i, wi, j, wj = best
        a = chains[i] if wi == 1 else chains[i][::-1]      # 让 a 以断口结尾
        b = chains[j][::-1] if wj == 1 else chains[j]      # 让 b 以断口开头
        chains[i] = a + b
        chains[j] = []
    return _close_self([c for c in chains if c], max_gap, cos_thresh)


def _close_self(chains, max_gap: float, cos_thresh: float):
    """首尾可平滑相接的链 → 补一个首点使其闭环"""
    out = []
    for c in chains:
        if len(c) >= 4 and c[0] != c[-1]:
            p0, p1 = c[0], c[-1]
            vx, vy = p0[0] - p1[0], p0[1] - p1[1]
            d2 = vx * vx + vy * vy
            if 1e-12 < d2 <= max_gap * max_gap:
                ux, uy = vx / (d2 ** 0.5), vy / (d2 ** 0.5)
                d1, d0 = _out_dir(c, 1), _out_dir(c, 0)
                if (ux * d1[0] + uy * d1[1] >= cos_thresh and
                        ux * d0[0] + uy * d0[1] >= cos_thresh):
                    c = c + [c[0]]
        out.append(c)
    return out


def _merge_fragments(frags, deg):
    """在度数为 2 的断点处把碎片重新拼成长链"""
    end_map = defaultdict(list)
    for i, f in enumerate(frags):
        end_map[f[0]].append(i)
        end_map[f[-1]].append(i)
    alive = [True] * len(frags)
    out = []
    for i in range(len(frags)):
        if not alive[i]:
            continue
        chain = frags[i][:]
        alive[i] = False
        for tail in (True, False):
            while True:
                e = chain[-1] if tail else chain[0]
                js = [j for j in end_map[e] if alive[j]]
                if deg[e] != 2 or len(js) != 1:
                    break
                j = js[0]
                g = frags[j]
                alive[j] = False
                seg = g if ((g[0] == e) if tail else (g[-1] == e)) else g[::-1]
                chain = chain + seg if tail else seg + chain
        out.append(chain)
    return out


# ---------------- 路径字符串 ----------------

def poly_d(pts) -> str:
    """闭合折线"""
    d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    for x, y in pts[1:]:
        d += f"L{x:.2f},{y:.2f}"
    return d + "Z"


def smooth_d(pts, t: float) -> str:
    """闭合点列 → Catmull-Rom 平滑三次贝塞尔（自带 Z 结尾）"""
    n = len(pts)
    d = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    for i in range(n):
        p0, p1, p2, p3 = (pts[(i - 1) % n], pts[i],
                          pts[(i + 1) % n], pts[(i + 2) % n])
        c1 = p1 + (p2 - p0) * (t / 6.0)
        c2 = p2 - (p3 - p1) * (t / 6.0)
        d += (f"C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} "
              f"{p2[0]:.2f},{p2[1]:.2f}")
    return d + "Z"


def open_d(pts, t: float) -> str:
    """开放点列 → 平滑/折线路径（不闭合）"""
    pts = np.asarray(pts, float)
    if len(pts) == 2 or t <= 0:
        return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    n = len(pts)
    P = np.vstack([pts[:1], pts, pts[-1:]])
    d = [f"M{P[1][0]:.2f},{P[1][1]:.2f}"]
    for j in range(n - 1):
        p0, p1, p2, p3 = P[j], P[j + 1], P[j + 2], P[j + 3]
        c1 = p1 + (p2 - p0) * (t / 6.0)
        c2 = p2 - (p3 - p1) * (t / 6.0)
        d.append(f"C{c1[0]:.2f},{c1[1]:.2f} {c2[0]:.2f},{c2[1]:.2f} "
                 f"{p2[0]:.2f},{p2[1]:.2f}")
    return " ".join(d)


def contour_polys(mask: np.ndarray, a) -> list:
    """区域 mask → 简化后的闭合点列列表（供轮廓路径与预览共用；按位置排序）"""
    out = []
    for cnt in find_contours(mask):
        per = cv2.arcLength(cnt, True)
        if per < a.min_len:
            continue
        pts = cv2.approxPolyDP(cnt, max(a.simplify * per, 0.3),
                               True).reshape(-1, 2).astype(float)
        if len(pts) >= 3:
            out.append(pts)
    out.sort(key=lambda p: (float(p[:, 0].min()), float(p[:, 1].min())))
    return out


def closed_paths_from_mask(mask: np.ndarray, a) -> list:
    """区域 mask → 闭合轮廓路径（OpenCV 备选方案，无 potrace 时用）"""
    return [smooth_d(p, a.smooth) if a.smooth > 0 else poly_d(p)
            for p in contour_polys(mask, a)]


# ---------------- potrace 矢量化 ----------------

def potrace_paths(bw_white: np.ndarray, a):
    """白=前景 的二值图 → (路径 d 列表, transform 字符串)"""
    exe = find_potrace()
    if not exe:
        raise RuntimeError('potrace 不可用')
    with tempfile.TemporaryDirectory() as td:
        pgm, svg = Path(td) / 'in.pgm', Path(td) / 'out.svg'
        cv2.imencode('.pgm', 255 - bw_white)[1].tofile(str(pgm))  # potrace 要黑=前景
        cmd = [exe, '-s', '-t', str(a.turdsize),
               '-a', str(a.alphamax), '-O', str(a.opttolerance)]
        if not a.opticurve:
            cmd.append('-n')
        cmd += ['-o', str(svg), str(pgm)]
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError('potrace: ' + r.stderr.decode(errors='ignore'))
        text = svg.read_text(errors='ignore')
    m = re.search(r'transform="([^"]+)"', text)          # 必须保留 transform
    tf = m.group(1) if m else ''
    ds = [' '.join(d.split()) for d in
          re.findall(r'<path[^>]*?\bd="([^"]+)"', text)]
    return ds, tf


# ---------------- 各模式 ----------------
# 每个模式返回 (groups, preview)：groups 供 SVG 组装；preview 为
# [(折线点列, 是否闭环), ...]，位于“加工分辨率”坐标系。

def shape_body(gray: np.ndarray, a):
    """色块轮廓模式"""
    th = None
    if str(a.threshold).lower() not in ('auto', ''):
        try:
            th = int(a.threshold)
        except ValueError:
            raise ValueError('--threshold 只能是 0~255 整数或 auto') from None
    if th is None:
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    else:
        _, bw = cv2.threshold(gray, th, 255, cv2.THRESH_BINARY_INV)
    if a.invert:
        bw = 255 - bw
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, K3)
    preview = [(p, True) for p in contour_polys(bw, a)]
    if find_potrace() and not a.no_potrace:
        ds, tf = potrace_paths(bw, a)
        return [(' '.join(ds), tf)], preview
    return [(' '.join(closed_paths_from_mask(bw, a)), '')], preview


def multi_body(gray: np.ndarray, a):
    """灰度波段等值线模式（逐带提取，不坍缩）"""
    vmax = max(1, min(255, int(a.band_max)))              # 带覆盖上限（≥vmax 视为背景）
    n = int(2 + a.detail * 5)
    cuts = [round(vmax * i / n) for i in range(1, n)]     # 内部切分点
    bands = ([(0, cuts[0])] if cuts else [])
    bands += [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]
    bands.append((cuts[-1] if cuts else 0, vmax))
    merged, preview = {}, []
    for lo, hi in bands:
        if hi <= lo:
            continue
        mask = ((gray >= lo) & (gray < hi)).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, K2)
        nlab, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for i in range(1, nlab):
            if stats[i, cv2.CC_STAT_AREA] < a.min_band:
                mask[lab == i] = 0
        if cv2.countNonZero(mask) == 0:
            continue
        preview.extend((p, True) for p in contour_polys(mask, a))
        if find_potrace() and not a.no_potrace:
            ds, tf = potrace_paths(mask, a)
        else:
            ds, tf = closed_paths_from_mask(mask, a), ''
        if ds:
            merged.setdefault(tf, []).extend(ds)
    return [(' '.join(ds), tf) for tf, ds in merged.items()], preview


def line_body(gray: np.ndarray, a, mode: str) -> list:
    """linedraw / edge：二值线稿 → 细化 → 中心线（坐标=输入分辨率）"""
    if mode == 'linedraw':
        bw = xdog_line_art(gray, a.detail)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, K3)
    else:
        bw = cv2.Canny(gray, a.canny_low, a.canny_high)
    if a.dilate > 0:
        k = 2 * a.dilate + 1                             # 已修复：1 不再无效
        bw = cv2.dilate(bw, np.ones((k, k), np.uint8))
    skel = thinning(bw)
    return trace_polylines(skel, a.min_line_len, a.simplify,
                           getattr(a, 'join_gap', 0.0))


# ---------------- SVG 组装 ----------------

def build_svg(w: float, h: float, groups, a,
              outer_scale: float = 1.0, px_per_mm: float | None = None) -> str:
    """
    w/h 为处理分辨率；outer_scale>1 时（--scale 放大处理）自动套一层
    scale(1/outer) 并把 viewBox 换算回原始尺寸；potrace 的 transform
    坐标系会按比例补偿描边宽度。px_per_mm 可显式覆盖（用于降采样补偿）。
    """
    ppm = a.px_per_mm if px_per_mm is None else px_per_mm
    w0, h0 = w / outer_scale, h / outer_scale
    if ppm > 0:
        size = f'width="{w0 / ppm:.3f}mm" height="{h0 / ppm:.3f}mm"'
    else:
        size = f'width="{w0:g}" height="{h0:g}"'
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" {size} '
           f'viewBox="0 0 {w0:g} {h0:g}">']
    if outer_scale != 1.0:
        out.append(f'<g transform="scale({1.0 / outer_scale:.6g})">')
    for body, tf in groups:
        if not body.strip():
            continue
        s_p = 1.0
        if tf:
            m = re.search(r'scale\(\s*([-\d.eE+]+)', tf)
            s_p = abs(float(m.group(1))) if m else 1.0
        eff = (s_p / outer_scale) if outer_scale > 0 else s_p
        sw = a.stroke_width / eff if eff > 0 else a.stroke_width
        head = (f'<g fill="none" stroke="{a.stroke_color}" '
                f'stroke-width="{sw:.3f}" stroke-linecap="round" '
                f'stroke-linejoin="round"')
        out.append(head + (f' transform="{tf}">' if tf else '>'))
        out.append(f'<path d="{body}"/>')
        out.append('</g>')
    if outer_scale != 1.0:
        out.append('</g>')
    out += ['</svg>', '']
    return '\n'.join(out)


# ---------------- 主流程 ----------------

def convert(src: Path, dst: Path, a) -> str:
    """返回状态：'ok'（已生成）/ 'empty'（无线条）/ 'skip'（已存在且不允许覆盖）"""
    img = imread_cn(str(src), apply_orientation=not getattr(a, 'no_exif', False))
    gray = to_gray(img)

    # 像素/毫米换算（--dpi 优先换算为 px/mm）
    ppm = float(a.px_per_mm) if a.px_per_mm > 0 else (
        float(a.dpi) / 25.4 if getattr(a, 'dpi', 0) > 0 else 0.0)

    # 大图降采样（防卡死）
    if a.max_size > 0 and max(gray.shape) > a.max_size:
        s0 = a.max_size / max(gray.shape)
        gray = cv2.resize(gray, None, fx=s0, fy=s0, interpolation=cv2.INTER_AREA)
        ppm *= s0                                        # 保持物理尺寸不变
        log.info("  [缩放] 原图过大，降采样至 %dx%d", gray.shape[1], gray.shape[0])

    # 裁白边 / 留白
    if a.trim or a.margin > 0:
        if a.trim:
            x, y, cw, ch = _content_bbox(gray)
            before = gray.shape
            gray = gray[y:y + ch, x:x + cw]
            log.info("  [裁边] %dx%d -> %dx%d", before[1], before[0],
                     gray.shape[1], gray.shape[0])
        if a.margin > 0:
            m = int(a.margin)
            gray = cv2.copyMakeBorder(gray, m, m, m, m,
                                      cv2.BORDER_CONSTANT, value=255)

    h0, w0 = gray.shape                                  # 输出尺寸（画布基准）

    # 小图放大处理（保细节）
    scale = float(a.scale or 1.0)
    if scale > 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale,
                          interpolation=cv2.INTER_CUBIC)
        log.info("  [放大] --scale %g → 处理分辨率 %dx%d",
                 scale, gray.shape[1], gray.shape[0])

    if a.blur > 1:
        gray = cv2.GaussianBlur(gray, (a.blur | 1,) * 2, 0)
    h, w = gray.shape

    if a.mode in ('linedraw', 'edge'):
        pls = line_body(gray, a, a.mode)
        if scale > 1.0:                                  # 坐标缩回原始尺寸
            pls = [(pl / scale, closed) for pl, closed in pls]
        body = ' '.join(smooth_d(pl, a.smooth) if closed else open_d(pl, a.smooth)
                        for pl, closed in pls)
        groups = [(body, '')]
        preview = pls
        info = f"{len(pls)} 条中心线"
    else:
        groups, preview = (multi_body(gray, a) if a.mode == 'multi'
                           else shape_body(gray, a))
        if scale > 1.0:
            preview = [(p / scale, c) for p, c in preview]
        info = f"{sum(g[0].count('M') for g in groups)} 条闭合路径"

    if not any(g[0].strip() for g in groups):
        log.info("[跳过] %s：未提取到线条，试试 --detail 0.9 / --scale 2 / --invert",
                 src.name)
        return 'empty'

    if dst.exists() and not a.force:
        log.info("[跳过] %s：已存在（加 --force 覆盖）", dst)
        return 'skip'
    if dst.exists():
        log.info("  [覆盖] %s", dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(build_svg(w, h, groups, a, outer_scale=scale, px_per_mm=ppm),
                   encoding='utf-8')

    if a.preview:
        canvas = np.full((h0, w0), 255, np.uint8)
        for pl, closed in preview:
            pp = np.round(np.asarray(pl)).astype(np.int32).reshape(-1, 1, 2)
            cv2.polylines(canvas, [pp], bool(closed), 0, 1, cv2.LINE_AA)
        pv = dst.with_name(dst.stem + '.preview.png')
        cv2.imencode('.png', canvas)[1].tofile(str(pv))
        log.info("  [预览] %s", pv)

    log.info("[完成] %s -> %s（%s）", src.name, dst, info)
    return 'ok'


def gather_inputs(items) -> list:
    files = []
    for s in items:
        p = Path(s)
        if p.is_dir():
            files += [f for f in sorted(p.iterdir())
                      if f.suffix.lower() in SUPPORTED]
        elif any(c in s for c in '*?['):
            files += [Path(f) for f in sorted(glob.glob(s))]
        else:
            files.append(p)
    return [f for f in files if f.is_file() and f.suffix.lower() in SUPPORTED]


def _process_one(job):
    """供多进程调用；返回 (src, status, err)"""
    src, dst, a = job
    try:
        return src, convert(src, dst, a), None
    except Exception as e:                                # noqa: BLE001
        return src, 'error', str(e)


def _init_worker(quiet: bool) -> None:
    logging.basicConfig(level=logging.WARNING if quiet else logging.INFO,
                        format='%(message)s', stream=sys.stdout)


def plan_jobs(files, out):
    """(图片列表, 输出路径或 None) → [(src, dst), ...]（CLI / GUI 共用）

    - out 以 .svg 结尾且只有一个输入 → 直接写入该文件
    - 其余情况 → 写入 out 目录（或原目录），文件名为 原文件名.svg
    - out 是 .svg 但有多个输入 → 抛 ValueError
    """
    out = Path(out) if out else None
    if out is not None and out.suffix.lower() == '.svg' and len(files) > 1:
        raise ValueError(f'检测到 {len(files)} 个输入文件，'
                         '请给出输出目录而非 .svg 文件')
    jobs = []
    for src in files:
        if out is not None and len(files) == 1 and out.suffix.lower() == '.svg':
            dst = out
        else:
            d = out if (out and out.suffix.lower() != '.svg') else src.parent
            dst = d / (src.stem + '.svg')
        jobs.append((src, Path(dst)))
    return jobs


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description='InkLimner：位图转 SVG 线稿（v3.4.1.1，中心线输出，激光切割推荐）',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('inputs', nargs='*',
                    help='图片/目录/通配符，可多个（--gui 时可留空）')
    ap.add_argument('-o', '--output', default=None,
                    help='输出 SVG 文件（单张）或输出目录')
    ap.add_argument('--mode', choices=['linedraw', 'multi', 'shape', 'edge'],
                    default='linedraw',
                    help='linedraw=XDoG线稿+中心线(推荐); multi=灰度等值线; '
                         'shape=色块轮廓; edge=Canny+中心线')
    ap.add_argument('--detail', type=float, default=0.7,
                    help='细节丰富度 0~1（linedraw/multi 有效）')
    ap.add_argument('--scale', type=float, default=1.0,
                    help='处理前放大倍数，小图保细节建议 2（输出坐标自动换算）')
    ap.add_argument('--preview', action='store_true',
                    help='同步输出 PNG 预览图（全部模式）')
    ap.add_argument('--trim', action='store_true',
                    help='自动裁掉四周白边（切割省料）')
    ap.add_argument('--margin', type=int, default=0,
                    help='在成品四周补白边距（像素）')
    ap.add_argument('--max-size', type=int, default=2400,
                    help='处理分辨率最长边上限，0=不限制')
    ap.add_argument('--dilate', type=int, default=0,
                    help='线条加粗半径 0~2（0=不加粗）')
    ap.add_argument('--min-line-len', type=int, default=8,
                    help='中心线最短长度 px（过滤毛刺）')
    ap.add_argument('--join-gap', type=float, default=3.0,
                    help='断线修复：端点相距 <= 该值(px) 且方向连贯时自动接上；0=关闭')
    ap.add_argument('--min-len', type=int, default=30,
                    help='闭合轮廓最小周长（shape/multi 无 potrace 时）')
    ap.add_argument('--min-band', type=int, default=30,
                    help='灰度带最小面积（multi）')
    ap.add_argument('--band-max', type=int, default=200,
                    help='multi 灰度带覆盖上限 1~255（越大保留越多浅灰细节）')
    ap.add_argument('--simplify', type=float, default=0.001,
                    help='简化强度，越小越精细')
    ap.add_argument('--smooth', type=float, default=0.5,
                    help='平滑强度 0~1，0=折线')
    ap.add_argument('--no-potrace', action='store_true',
                    help='强制不用 potrace')
    ap.add_argument('--turdsize', type=int, default=2,
                    help='potrace 噪点面积阈值，0=保留一切')
    ap.add_argument('--alphamax', type=float, default=1.0,
                    help='potrace 曲线圆滑度')
    ap.add_argument('--opticurve', type=int, default=1,
                    help='potrace 曲线优化 1=开')
    ap.add_argument('--opttolerance', type=float, default=0.2,
                    help='potrace 曲线优化容差')
    ap.add_argument('--threshold', default='auto',
                    help='shape 模式二值化阈值 0~255 或 auto')
    ap.add_argument('--invert', action='store_true',
                    help='黑白反转（黑底浅色图用）')
    ap.add_argument('--no-exif', action='store_true',
                    help='不按 EXIF 方向校正（默认会校正手机照片方向）')
    ap.add_argument('--canny-low', type=int, default=30)
    ap.add_argument('--canny-high', type=int, default=100)
    ap.add_argument('--blur', type=int, default=1,
                    help='预模糊核，1=关闭（linedraw 建议关闭）')
    ap.add_argument('--stroke-width', type=float, default=0.1,
                    help='SVG 描边宽度（仅显示用）')
    ap.add_argument('--stroke-color', default='#000000')
    ap.add_argument('--px-per-mm', type=float, default=0,
                    help='像素/毫米换算，如 11.81=300DPI；0=像素单位')
    ap.add_argument('--dpi', type=float, default=0,
                    help='按 DPI 换算毫米（= --px-per-mm dpi/25.4）；0=不启用')
    ap.add_argument('-j', '--jobs', type=int, default=0,
                    help='批量并发进程数，0=自动')
    ap.add_argument('-f', '--force', dest='force', action='store_true',
                    help='覆盖已存在的输出（默认行为）')
    ap.add_argument('--no-overwrite', dest='force', action='store_false',
                    help='目标已存在时跳过（不覆盖）')
    ap.add_argument('-q', '--quiet', action='store_true',
                    help='安静模式，只输出错误')
    ap.add_argument('--version', action='version',
                    version=f'InkLimner {__version__}')
    ap.add_argument('--gui', action='store_true',
                    help='打开图形界面（忽略其余命令行参数）')
    ap.set_defaults(force=True)
    return ap


def _force_utf8_output() -> None:
    """把输出流切成 UTF-8。

    Windows 终端默认是 cp1252 / charmap，直接 print 中文会抛
    UnicodeEncodeError 把进程带崩（CI / 重定向输出时最常见）。
    backslashreplace 兜底：极端环境下也只是显示成转义形式，不会崩。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
        except Exception:                                     # noqa: BLE001
            pass


def main(argv=None) -> int:
    _force_utf8_output()
    a = build_parser().parse_args(argv)

    logging.basicConfig(level=logging.WARNING if a.quiet else logging.INFO,
                        format='%(message)s', stream=sys.stdout)

    if a.gui:
        from inklimner_gui import main as gui_main
        return gui_main()

    if not hasattr(cv2, 'ximgproc'):
        log.info("[提示] 未安装 opencv-contrib-python，将使用内置纯 Python 细化"
                 "（大图较慢）。建议：\n"
                 "       pip uninstall opencv-python\n"
                 "       pip install opencv-contrib-python")
    pot = find_potrace()
    log.info("[环境] potrace: %s%s", '可用' if pot else '未安装',
             '（linedraw/edge 模式不受影响）' if not pot else '')

    if not a.inputs:
        log.error('请提供至少一个输入（图片 / 目录 / 通配符），或用 --gui 打开界面')
        return 2

    files = gather_inputs(a.inputs)
    if not files:
        log.error('未找到可处理的图片（支持 %s）', ' '.join(SUPPORTED))
        return 2

    try:
        pairs = plan_jobs(files, Path(a.output) if a.output else None)
    except ValueError as e:
        log.error('%s', e)
        return 2
    jobs = [(src, dst, a) for src, dst in pairs]

    total = len(jobs)
    if total > 1:
        log.info("[批量] 共 %d 个文件", total)

    results = []
    if total > 1 and (a.jobs == 0 or a.jobs > 1):
        workers = a.jobs if a.jobs > 0 else min(os.cpu_count() or 1, total)
        workers = max(1, min(workers, total))
        try:
            with ProcessPoolExecutor(max_workers=workers,
                                     initializer=_init_worker,
                                     initargs=(a.quiet,)) as ex:
                results = list(ex.map(_process_one, jobs))
        except Exception:                                # noqa: BLE001
            results = [_process_one(j) for j in jobs]     # 多进程不可用 → 串行兜底
    else:
        results = [_process_one(j) for j in jobs]

    failed = 0
    for i, (src, status, err) in enumerate(results, 1):
        if status == 'error':
            failed += 1
            log.error("[失败] %s: %s", src.name, err)
        elif status == 'empty':
            failed += 1
        if total > 1 and not a.quiet:
            log.info("  [%d/%d] %s", i, total, src.name)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
