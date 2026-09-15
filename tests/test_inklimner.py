# -*- coding: utf-8 -*-
"""InkLimner 的单元 / 集成测试。

运行：pytest -q
"""
import argparse
import re
import subprocess
import sys
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import inklimner as M  # noqa: E402


# --------------------------- 工具 ---------------------------

def make_args(**over):
    """构造一份与 argparse 默认值一致的参数空间"""
    d = dict(
        px_per_mm=0.0, dpi=0.0, max_size=2400, trim=False, margin=0, scale=1.0,
        blur=1, mode='linedraw', detail=0.7, quiet=True, preview=False,
        force=True, smooth=0.5, min_line_len=8, simplify=0.001, dilate=0,
        canny_low=30, canny_high=100, threshold='auto', invert=False,
        band_max=200, min_band=30, min_len=30, no_potrace=True, turdsize=2,
        alphamax=1.0, opticurve=1, opttolerance=0.2, stroke_width=0.1,
        stroke_color='#000000', no_exif=False,
    )
    d.update(over)
    return argparse.Namespace(**d)


def write_png(path, img):
    cv2.imencode('.png', img)[1].tofile(str(path))
    return path


def sample_image(w=600, h=400):
    img = np.full((h, w, 3), 255, np.uint8)
    cv2.circle(img, (150, 200), 90, (0, 0, 0), -1)
    cv2.rectangle(img, (320, 120), (520, 300), (0, 0, 0), -1)
    img[320:380, 300:520] = 225          # 浅灰块（测 band-max）
    img[60:100, 420:560] = 150           # 中灰块
    return img


def svg_attr(svg_text, name):
    m = re.search(rf'{name}="([^"]+)"', svg_text)
    return m.group(1) if m else None


# --------------------------- 基础算法 ---------------------------

def test_rectangle_thins_to_single_line():
    rect = np.zeros((60, 60), np.uint8)
    rect[20:40, 10:50] = 255
    sk = M._thin_zhang_suen(rect)
    assert 0 < int((sk > 0).sum()) < 60     # 远小于实心面积 800


def test_thinning_matches_reference_on_random():
    def ref(bw):
        I = np.pad((bw > 0).astype(np.uint8), 1)

        def sh(dy, dx):
            return np.roll(np.roll(I, -dy, 0), -dx, 1)

        steps = (((0, 2, 4), (2, 4, 6)), ((0, 2, 6), (0, 4, 6)))
        for _ in range(1000):
            ch = False
            for (i1, i2, i3), (j1, j2, j3) in steps:
                Ps = [sh(-1, 0), sh(-1, 1), sh(0, 1), sh(1, 1),
                      sh(1, 0), sh(1, -1), sh(0, -1), sh(-1, -1)]
                A = np.zeros(I.shape, np.uint8)
                for i in range(8):
                    A += ((Ps[i] == 0) & (Ps[(i + 1) % 8] == 1)).astype(np.uint8)
                B = sum(Ps)
                m = ((I == 1) & (B >= 2) & (B <= 6) & (A == 1) &
                     (Ps[i1] * Ps[i2] * Ps[i3] == 0) &
                     (Ps[j1] * Ps[j2] * Ps[j3] == 0))
                if m.any():
                    I[m] = 0
                    ch = True
            if not ch:
                break
        return (I[1:-1, 1:-1] * 255).astype(np.uint8)

    rng = np.random.default_rng(0)
    for _ in range(10):
        bw = (rng.random((50, 50)) < 0.35).astype(np.uint8) * 255
        assert np.array_equal(M._thin_zhang_suen(bw), ref(bw))


# --------------------------- 输出正确性 ---------------------------

def test_svg_structure(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image())
    dst = tmp_path / 'a.svg'
    assert M.convert(src, dst, make_args()) == 'ok'
    t = dst.read_text(encoding='utf-8')
    assert t.startswith('<?xml')
    assert '<svg' in t and 'fill="none"' in t
    assert svg_attr(t, 'viewBox') == '0 0 600 400'


def test_deterministic_output(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image())
    d1, d2 = tmp_path / 'a1.svg', tmp_path / 'a2.svg'
    M.convert(src, d1, make_args())
    M.convert(src, d2, make_args())
    assert d1.read_bytes() == d2.read_bytes()


def test_px_per_mm_compensates_downsampling(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image(600, 400))
    dst = tmp_path / 'a.svg'
    M.convert(src, dst, make_args(px_per_mm=11.81, max_size=200))
    width = float(svg_attr(dst.read_text(encoding='utf-8'), 'width')[:-2])
    assert abs(width - 600 / 11.81) < 0.05        # 降采样后毫米尺寸不变


def test_dpi_equals_px_per_mm(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image(600, 400))
    dst = tmp_path / 'a.svg'
    M.convert(src, dst, make_args(dpi=300))
    width = float(svg_attr(dst.read_text(encoding='utf-8'), 'width')[:-2])
    assert abs(width - 600 / (300 / 25.4)) < 0.05


def test_band_max_recovers_light_gray(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image())
    d200, d255 = tmp_path / 'a200.svg', tmp_path / 'a255.svg'
    M.convert(src, d200, make_args(mode='multi', band_max=200))
    M.convert(src, d255, make_args(mode='multi', band_max=255))
    n200 = d200.read_text(encoding='utf-8').count('M')
    n255 = d255.read_text(encoding='utf-8').count('M')
    assert n255 > n200                            # 255 保留浅灰 → 路径更多


def test_trim_and_margin(tmp_path):
    img = np.full((300, 300, 3), 255, np.uint8)
    cv2.circle(img, (150, 150), 40, (0, 0, 0), -1)
    src = write_png(tmp_path / 'a.png', img)
    d_plain, d_trim, d_margin = tmp_path / 'p.svg', tmp_path / 't.svg', tmp_path / 'm.svg'
    M.convert(src, d_plain, make_args())
    M.convert(src, d_trim, make_args(trim=True))
    M.convert(src, d_margin, make_args(trim=True, margin=20))
    vb_plain = svg_attr(d_plain.read_text(encoding='utf-8'), 'viewBox')
    vb_trim = svg_attr(d_trim.read_text(encoding='utf-8'), 'viewBox')
    vb_margin = svg_attr(d_margin.read_text(encoding='utf-8'), 'viewBox')
    assert vb_plain == '0 0 300 300'
    w_trim, h_trim = (int(v) for v in vb_trim.split()[2:])
    assert w_trim < 300 and h_trim < 300
    w_m, h_m = (int(v) for v in vb_margin.split()[2:])
    assert (w_m, h_m) == (w_trim + 40, h_trim + 40)


def test_no_overwrite_skips(tmp_path):
    src = write_png(tmp_path / 'a.png', sample_image())
    dst = tmp_path / 'a.svg'
    assert M.convert(src, dst, make_args()) == 'ok'
    assert M.convert(src, dst, make_args(force=False)) == 'skip'


# --------------------------- EXIF ---------------------------

def test_exif_orientation_rotates(tmp_path):
    pytest.importorskip('PIL')
    from PIL import Image

    small = np.full((100, 200, 3), 255, np.uint8)
    small[20:80, 20:180] = 0
    im = Image.fromarray(small)
    ex = im.getexif()
    ex[274] = 6                                    # Orientation = 6
    jpg = tmp_path / 'r.jpg'
    im.save(str(jpg), format='JPEG', exif=ex)

    assert M.exif_orientation(jpg.read_bytes()) == 6

    dst = tmp_path / 'r.svg'
    M.convert(jpg, dst, make_args(mode='shape'))
    assert svg_attr(dst.read_text(encoding='utf-8'), 'viewBox') == '0 0 100 200'

    dst2 = tmp_path / 'r2.svg'
    M.convert(jpg, dst2, make_args(mode='shape', no_exif=True))
    assert svg_attr(dst2.read_text(encoding='utf-8'), 'viewBox') == '0 0 200 100'


# --------------------------- 调色板 PNG ---------------------------

def test_palette_png(tmp_path):
    pytest.importorskip('PIL')
    from PIL import Image

    idx = np.ones((200, 200), np.uint8)
    cv2.circle(idx, (100, 100), 60, 0, -1)
    im = Image.fromarray(idx, mode='P')
    im.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
    png = tmp_path / 'p.png'
    im.save(str(png))

    dst = tmp_path / 'p.svg'
    assert M.convert(png, dst, make_args(mode='shape')) == 'ok'
    assert dst.read_text(encoding='utf-8').count('M') >= 1


# --------------------------- CLI ---------------------------

def test_cli_version():
    r = subprocess.run([sys.executable, str(ROOT / 'inklimner.py'), '--version'],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert M.__version__ in r.stdout


def test_cli_multi_file_rejects_svg_output(tmp_path):
    a = write_png(tmp_path / 'a.png', sample_image())
    b = write_png(tmp_path / 'b.png', sample_image())
    r = subprocess.run([sys.executable, str(ROOT / 'inklimner.py'),
                        str(a), str(b), '-o', str(tmp_path / 'x.svg')],
                       capture_output=True, text=True)
    assert r.returncode == 2


def test_gather_inputs(tmp_path):
    p1 = write_png(tmp_path / 'a.png', sample_image())
    (tmp_path / 'note.txt').write_text('x')
    files = M.gather_inputs([str(tmp_path)])
    assert files == [p1]
