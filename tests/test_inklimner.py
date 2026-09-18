"""InkLimner 的单元 / 集成测试。

运行：pytest -q
"""
import argparse
import re
import subprocess
import sys
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
        force=True, smooth=0.5, min_line_len=8, join_gap=3.0, simplify=0.001, dilate=0,
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
    # 说明：完全对称的「实心正方块」在 Zhang-Suen 下会退化成一两个像素
    # （skimage.skeletonize 行为一致），这是算法特性而非 bug；
    # 这里用的是扁长实心条，更贴近真实线稿里的粗笔画。
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


# --------------------------- 线条连贯性（断线修复） ---------------------------

def ring_mask(n=120, r=40):
    """画一个 1px 细圆环"""
    img = np.zeros((n, n), np.uint8)
    cv2.circle(img, (n // 2, n // 2), r, 255, 1)
    return img


def frame_mask():
    """空心矩形（真实线稿常见形状）"""
    img = np.zeros((120, 120), np.uint8)
    img[20:100, 20:100] = 255
    img[24:96, 24:96] = 0
    return img


def test_build_nbrs_kills_diagonal_shortcut():
    """8 连通骨架的「对角捷径」必须被剔除，否则度=3/4 假交叉点会反复截断线条"""
    sk = M.thinning(ring_mask())
    ys, xs = np.nonzero(sk > 0)
    pts = set(zip(xs.tolist(), ys.tolist()))
    deg = [len(v) for v in M._build_nbrs(pts).values()]
    assert len(deg) > 100
    assert max(deg) <= 2, f'仍存在 {max(deg)} 度交叉点'


def test_trace_closed_frame_is_single_polyline():
    """闭合图形必须输出「1 条闭环」，而不是碎成多段"""
    pls = M.trace_polylines(M.thinning(frame_mask()), 8, 0.001, 3.0)
    assert len(pls) == 1
    assert pls[0][1] is True


def test_trace_closed_ring_is_single_polyline():
    pls = M.trace_polylines(M.thinning(ring_mask()), 8, 0.001, 3.0)
    assert len(pls) == 1 and pls[0][1] is True


def test_trace_joins_small_gap():
    """小断口（≤ join_gap）应被自动接上"""
    img = np.zeros((40, 120), np.uint8)
    img[20, 10:50] = 255
    img[20, 52:100] = 255                    # 2px 断口
    sk = img
    assert len(M.trace_polylines(sk, 8, 0.001, 0.0)) == 2     # 关闭修复 → 两段
    assert len(M.trace_polylines(sk, 8, 0.001, 3.0)) == 1     # 开启修复 → 一条


def test_min_len_filtered_after_joining():
    """过滤必须发生在「补断口」之后，否则被切碎的长线会整条消失"""
    img = np.zeros((40, 140), np.uint8)
    img[20, 10:70] = 255
    img[20, 71:130] = 255                    # 1px 断口，两段各 ~60px
    ok = M.trace_polylines(img, 100, 0.001, 3.0)             # min_len=100 > 单段
    assert len(ok) == 1, '长线被断口切碎后整条丢失了'
    assert len(M.trace_polylines(img, 100, 0.001, 0.0)) == 0  # 不做修复则两段都被滤掉


def test_trace_does_not_merge_parallel_lines():
    """平行线不能被误粘成一条（方向门控）"""
    img = np.zeros((80, 140), np.uint8)
    for sp in (3, 5, 8):
        img[:] = 0
        img[20, 10:110] = 255
        img[20 + sp, 10:110] = 255
        for jg in (3.0, 10.0):
            assert len(M.trace_polylines(img, 8, 0.001, jg)) == 2, f'间距{sp} 误粘'


def test_trace_closes_near_loop():
    """首尾仅差 1px 的开口应被闭合成环"""
    img = np.zeros((14, 14), np.uint8)
    img[2:12, 2:12] = 255
    img[3:11, 3:11] = 0
    img[2, 2] = 0                             # 抽掉一个角 → 开口 1px
    pls = M.trace_polylines(img, 4, 0.001, 3.0)
    assert len(pls) == 1 and pls[0][1] is True


def test_join_gap_zero_is_backward_compatible():
    """join_gap=0 时不改变原有行为（不合并任何断口）"""
    img = np.zeros((40, 120), np.uint8)
    img[20, 10:50] = 255
    img[20, 52:100] = 255
    assert len(M.trace_polylines(img, 8, 0.001, 0.0)) == 2


def test_end_to_end_join_gap_strengthens_continuity(tmp_path):
    """端到端：整条管线（XDoG → 细化 → 追踪 → SVG）开启断口修复后，碎片数应下降。

    这是对「输出 SVG 线条断开」故障的回归护栏 —— 子路径（d 里的 M 段）越少，
    线条越连贯。
    """
    src = write_png(tmp_path / 'a.png', sample_image())

    def subpaths(join_gap):
        dst = tmp_path / f'a{join_gap}.svg'
        assert M.convert(src, dst, make_args(join_gap=join_gap)) == 'ok'
        text = dst.read_text(encoding='utf-8')
        return sum(d.count('M') for d in re.findall(r'd="([^"]+)"', text))

    off, on = subpaths(0.0), subpaths(3.0)
    assert on <= off, f'开启断口修复后子路径反而变多：{off} → {on}'


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


# --------------------------- 输出规划 / GUI ---------------------------

def test_plan_jobs_single_svg(tmp_path):
    a = Path('/x/a.png')
    assert M.plan_jobs([a], tmp_path / 'o.svg') == [(a, tmp_path / 'o.svg')]


def test_plan_jobs_directory(tmp_path):
    jobs = M.plan_jobs([Path('/x/a.png'), Path('/x/b.png')], tmp_path)
    assert [j[1].name for j in jobs] == ['a.svg', 'b.svg']
    assert all(j[1].parent == tmp_path for j in jobs)


def test_plan_jobs_rejects_svg_for_many(tmp_path):
    with pytest.raises(ValueError):
        M.plan_jobs([Path('a.png'), Path('b.png')], tmp_path / 'o.svg')


def test_build_parser_defaults():
    a = M.build_parser().parse_args([])          # inputs 为 nargs='*'，可为空
    assert a.mode == 'linedraw'
    assert a.force is True
    assert a.max_size == 2400
    assert a.gui is False


def test_gui_param_keys_match_cli():
    gui = pytest.importorskip('inklimner_gui')
    vals = gui.default_values()
    assert vals, 'GUI 应声明参数'
    a = M.build_parser().parse_args([])
    missing = [k for k in vals if not hasattr(a, k)]
    assert not missing, f'GUI 参数在 CLI 中不存在: {missing}'


def test_gui_presets_and_mode_coverage():
    gui = pytest.importorskip('inklimner_gui')
    keys = gui.all_keys()
    # 预设里出现的键必须都是真实参数
    for name, data in gui.PRESETS.items():
        bad = [k for k in data if k not in keys]
        assert not bad, f'预设 {name} 含未知参数: {bad}'
    # 每个参数至少在一个模式下生效，否则界面里永远点不了
    covered = set(gui.COMMON_KEYS)
    for mode in ('linedraw', 'edge', 'multi', 'shape'):
        covered |= gui.MODE_EXTRA[mode]
    assert keys <= covered, f'这些参数没有任何模式可启用: {keys - covered}'


def test_gui_command_roundtrip():
    gui = pytest.importorskip('inklimner_gui')
    vals = gui.default_values()
    vals.update(mode='shape', trim=True, dpi=300, min_len=60,
                threshold='160', preview=True, force=False)
    cmd = gui.build_command(vals, ['a.png', 'b c.png'])
    assert 'inklimner' in cmd and '"b c.png"' in cmd and '--no-overwrite' in cmd
    back = gui.parse_command(cmd)
    for k, v in vals.items():
        assert back[k] == v, f'{k}: {back[k]!r} != {v!r}'


def test_gui_parse_command_with_prefix_and_unknown_flag():
    gui = pytest.importorskip('inklimner_gui')
    parsed = gui.parse_command('python inklimner.py in.png --mode edge --blur 3')
    assert parsed['mode'] == 'edge' and parsed['blur'] == 3
    with pytest.raises(ValueError):
        gui.parse_command('inklimner in.png --not-a-real-flag')


def test_gui_settings_roundtrip(tmp_path, monkeypatch):
    gui = pytest.importorskip('inklimner_gui')
    core_gui = pytest.importorskip('inklimner_gui_core')
    # 配置读写定义在共享 core 层（两个界面共用），要 patch 到真实定义处
    monkeypatch.setattr(core_gui, 'SETTINGS_PATH', tmp_path / 'settings.json')
    gui.save_settings({'params': {'mode': 'shape'}, 'presets': {'我的': {'trim': True}}})
    data = gui.load_settings()
    assert data['params']['mode'] == 'shape'
    assert data['presets']['我的']['trim'] is True
    monkeypatch.setattr(core_gui, 'SETTINGS_PATH', tmp_path / 'nope' / 'x.json')
    assert gui.load_settings() == {}


def test_gui_env_summary():
    gui = pytest.importorskip('inklimner_gui')
    s = gui.env_summary()
    assert 'potrace' in s and '细化' in s
    assert gui.env_summary('拖拽✓').endswith('拖拽✓')


def test_both_backends_share_one_spec():
    """Qt 与 Tk 两个界面必须共用同一份参数规格（否则两边会漂移）"""
    core_gui = pytest.importorskip('inklimner_gui_core')
    tk_gui = pytest.importorskip('inklimner_gui_tk')
    assert tk_gui.GROUPS is core_gui.GROUPS
    assert tk_gui.PRESETS is core_gui.PRESETS
    entry = pytest.importorskip('inklimner_gui')
    assert entry.GROUPS is core_gui.GROUPS


def test_backend_pick_prefers_qt(monkeypatch):
    """自动选择后端：有 PySide6 就用 Qt，否则回退 Tk"""
    gui = pytest.importorskip('inklimner_gui')
    monkeypatch.setattr(gui, 'has_pyside6', lambda: True)
    monkeypatch.setattr(gui, 'has_tkinter', lambda: True)
    assert gui.pick_backend() == 'qt'
    monkeypatch.setattr(gui, 'has_pyside6', lambda: False)
    assert gui.pick_backend() == 'tk'
    monkeypatch.setattr(gui, 'has_tkinter', lambda: False)
    assert gui.pick_backend() == ''
    assert gui.pick_backend('tk') == 'tk'          # 显式指定优先


def test_qt_gui_builds_offscreen(monkeypatch, tmp_path):
    """Qt 界面能在无显示器环境构建出全部控件（CI 也能跑）"""
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    qt = pytest.importorskip('inklimner_gui_qt')
    core_gui = pytest.importorskip('inklimner_gui_core')
    monkeypatch.setattr(core_gui, 'SETTINGS_PATH', tmp_path / 'settings.json')
    try:
        app = qt.QApplication.instance() or qt.QApplication([])
    except Exception as e:                             # noqa: BLE001
        pytest.skip(f'当前环境无法创建 QApplication: {e}')
    assert app is not None
    win = qt.MainWindow()
    try:
        assert set(win.widgets) == qt.gc.all_keys()
        assert win.run_btn.text() and win.stop_btn.isEnabled() is False
        # 模式联动：切到 shape 后 Canny 应被置灰、threshold 应可用
        win.widgets['mode'].setCurrentText('shape')
        assert not win.widgets['canny_low'].isEnabled()
        assert win.widgets['threshold'].isEnabled()
        win.widgets['mode'].setCurrentText('edge')
        assert win.widgets['canny_low'].isEnabled()
        assert not win.widgets['threshold'].isEnabled()
        # 参数取值 / 回填往返
        vals = win.current_values()
        assert vals['mode'] == 'edge' and 'join_gap' in vals
        win.apply_values({'mode': 'linedraw', 'join_gap': 7.5})
        assert win.current_values()['join_gap'] == 7.5
    finally:
        win.close()


def test_qt_theme_light_by_default_and_switchable(monkeypatch, tmp_path):
    """配色默认浅色，可在界面里切深浅，并且选择会被记住"""
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    monkeypatch.delenv('INKLIMNER_THEME', raising=False)
    qt = pytest.importorskip('inklimner_gui_qt')
    core_gui = pytest.importorskip('inklimner_gui_core')
    monkeypatch.setattr(core_gui, 'SETTINGS_PATH', tmp_path / 'settings.json')
    assert set(qt.THEMES) == {'light', 'dark'}
    assert qt.DEFAULT_THEME == 'light'
    assert len(qt.THEME_NAMES) == len(qt.THEME_LABELS) == 2
    try:
        app = qt.QApplication.instance() or qt.QApplication([])
    except Exception as e:                             # noqa: BLE001
        pytest.skip(f'当前环境无法创建 QApplication: {e}')

    win = qt.MainWindow()
    try:
        assert win.theme == 'light'                    # 默认浅色
        assert app.styleSheet() == qt.THEMES['light']
        win.theme_combo.setCurrentIndex(1)             # 切到深色
        assert win.theme == 'dark'
        assert app.styleSheet() == qt.THEMES['dark']
        assert win.result_view.styleSheet() == qt.VIEW_STYLE['dark']
        win.theme_combo.setCurrentIndex(0)
        assert win.theme == 'light'
        assert app.styleSheet() == qt.THEMES['light']
    finally:
        win.close()

    core_gui.save_settings({'theme': 'dark'})          # 记忆：下次启动应是深色
    win2 = qt.MainWindow()
    try:
        assert win2.theme == 'dark'
        assert app.styleSheet() == qt.THEMES['dark']
        win2.theme_combo.setCurrentIndex(0)
        assert win2.theme == 'light'
    finally:
        win2.close()


def test_qt_gui_buttons_survive_checked_argument(monkeypatch, tmp_path):
    """回归：QPushButton.clicked 会附带一个 bool（checked），
    槽函数不能把它当成文件列表 —— 旧代码会 `for p in False` 直接报 TypeError。
    """
    pytest.importorskip('PySide6')
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    qt = pytest.importorskip('inklimner_gui_qt')
    core_gui = pytest.importorskip('inklimner_gui_core')
    monkeypatch.setattr(core_gui, 'SETTINGS_PATH', tmp_path / 'settings.json')
    try:
        qt.QApplication.instance() or qt.QApplication([])
    except Exception as e:                             # noqa: BLE001
        pytest.skip(f'当前环境无法创建 QApplication: {e}')

    opened = []

    class FakeDialog:
        @staticmethod
        def getOpenFileNames(*_a, **_k):
            opened.append(1)
            return [], ''

    monkeypatch.setattr(qt, 'QFileDialog', FakeDialog)

    win = qt.MainWindow()
    try:
        win.add_files(False)                           # 旧代码在这里 TypeError
        win.add_files(True)
        assert win.inputs == []

        btn = next(b for b in win.findChildren(qt.QPushButton)
                   if b.text() == '＋ 图片')
        btn.click()                                    # 走真实信号：clicked(False)
        assert opened, '按钮点击应当打开文件选择框'

        src = write_png(tmp_path / 'x.png', sample_image(60, 40))
        win.add_files([str(src)])                      # 正常路径依旧可用
        assert [p.name for p in win.inputs] == ['x.png']
        win.add_files(str(src))                        # 单个字符串也应被接受
        assert [p.name for p in win.inputs] == ['x.png']    # 且不重复添加
    finally:
        win.close()


