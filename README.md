<p align="center">
  <img src="assets/cover.png" alt="InkLimner — raster to single-line SVG art for laser cutting" width="780">
</p>

# InkLimner —— 位图转 SVG 线稿工具（v3.4.1.1 · 激光切割用）

![Version](https://img.shields.io/badge/version-3.4.1.1-0d9488)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
[![CI](https://github.com/HBrOcean/inklimner/actions/workflows/ci.yml/badge.svg)](https://github.com/HBrOcean/inklimner/actions/workflows/ci.yml)
[![Downloads](https://img.shields.io/badge/download-Releases-0d9488)](https://github.com/HBrOcean/inklimner/releases)

将 PNG / JPG / JPEG / BMP / WEBP / TIF / TIFF 等常见位图转换为**纯描边、无填充**的
SVG 矢量线稿，输出为**单线中心线**（激光只走一遍），可直接导入 LightBurn、LaserGRBL、
RDWorks、LaserMaker 等激光切割 / 雕刻软件使用。

> 设计目标：用最简单的命令行流程，把「一张图」变成「一圈能切出来的线」。

> 版本说明：本版为 **v3.4.1.1**，核心算法为 **XDoG 线稿 + 骨架中心线**，
> 输出是细化后的**单线走线**，天生适合输出黑白线稿。
> v3.4.1.1 起附带**图形界面**，命令行依旧完整可用。

---

## ✨ 特性

- 🎯 **四种提取模式**
  - `linedraw` —— XDoG 线稿 + 骨架中心线（**默认**，最像手绘线稿，激光只走单线）
  - `edge` —— Canny 边缘 + 骨架中心线（照片描线）
  - `multi` —— 灰度波段等值线（层次分明，类似地形图）
  - `shape` —— 色块轮廓（剪纸风，可借助 potrace 圆滑）
- 📱 **EXIF 方向校正**：手机照片不再横竖颠倒（`--no-exif` 可关闭）
- 🪄 **自动阈值**：`shape` 模式默认使用 Otsu 算法自动二值化
- 🧹 **智能清理 + 断线修复**：形态学闭运算补缝、碎段过滤；**断口按「端点距离 + 方向连贯」自动拼接**，
  线条不再莫名断开、碎成多段（`--join-gap`，默认 `3.0`，`0`=关闭）
- 📐 **平滑可调**：Catmull-Rom 三次贝塞尔平滑，0（硬朗折线）～ 1（圆滑曲线）
- 📏 **真实尺寸**：`--px-per-mm` 或更直观的 `--dpi` 换算毫米，导入即得实际尺寸
- ✂️ **裁白边 / 留白**：`--trim` 自动去掉四周空白，`--margin` 留边距（切割省料）
- 📦 **批量处理**：目录、通配符、多文件混合输入，自动**多进程**并行
- 🖼️ **全模式预览**：`--preview` 同步输出 PNG 预览图（无需打开浏览器）
- 🇨🇳 **中文路径**：兼容包含中文 / 空格的文件路径
- 🖥️ **大图防卡死**：`--max-size` 自动降采样；`--scale` 小图放大保细节
- 🧮 **物理尺寸稳定**：`--max-size` 降采样会自动补偿，毫米尺寸不受影响
- 🔒 **输出确定性**：同输入产出逐字节一致，方便 diff 与版本管理
- ⚡ **potrace 可选加速**：安装后 `shape` / `multi` 模式轮廓更圆滑
- 🖥️ **图形界面（Qt / Tkinter 双外观）**：参数可视化 + 模式联动 + 实时预览 + 拖拽导入，
  `inklimner_gui.py` 自动挑选可用界面（详见下文）
- 🚀 **失败返回非零退出码**：便于脚本化 / CI 集成

---

## ⬇️ 直接下载（免安装 Python）

不想装 Python、也不熟命令行？直接下打包好的程序：

👉 **到 [Releases 页面](https://github.com/HBrOcean/inklimner/releases) 下载**

| 下载 | 适合谁 |
|:--|:--|
| `InkLimner-*-gui.zip` | **图形界面版**：解压后双击 `InkLimner(.exe)` 就能用 |
| `InkLimner-*-cli.zip` | **命令行版**：单个可执行文件，适合脚本、批处理 |

Windows / macOS / Linux 三个平台都有，由 GitHub Actions 自动构建。
程序没有代码签名证书，首次运行会被 SmartScreen（Windows）或 Gatekeeper（macOS）
拦一下，按提示允许即可 —— 详见 [docs/BUILD.md](docs/BUILD.md)。

---

## 📦 安装

需要 **Python 3.8+**。

### 方式一：直接使用单文件（最简单）

只需要装依赖，然后下载 `inklimner.py` 即可运行：

```bash
pip install opencv-python numpy
```

### 方式二：pip 安装（获得 `inklimner` 命令）

```bash
pip install .
# 之后可直接：
inklimner --help
```

### 可选依赖

**推荐（细化提速约百倍）**——把 OpenCV 换成 contrib 版（含 `ximgproc.thinning`）：

```bash
pip uninstall opencv-python
pip install opencv-contrib-python
# 或： pip install ".[fast]"
```

**可选（仅 `shape` / `multi` 模式受益）**——安装
[potrace](http://potrace.sourceforge.net/)，需 **1.9+**（用到 `-O` 曲线优化选项）。
未安装时自动退回 OpenCV 轮廓，不影响运行。

**可选（图形界面）**——想要现代暗色界面：

```bash
pip install ".[gui]"          # PySide6，Qt 界面（推荐）
```
不装也行：`inklimner_gui.py` 会自动回退到零依赖的 Tkinter 界面。
Tk 界面想让预览更清晰可再装 Pillow（`pip install ".[tk]"`），
想支持拖拽可装 tkinterdnd2（`pip install ".[dnd]"`）。

### 方式三：Docker

```bash
docker build -t inklimner .
docker run --rm -v "$PWD:/work" inklimner /work/input.png -o /work/output.svg --trim
```

---

## 🚀 快速开始

```bash
# 最简单的用法：默认 linedraw 模式，输出到原图同目录
python inklimner.py 图案.png
# → 在同目录生成 图案.svg

# 指定输出文件名
python inklimner.py 图案.png -o 线稿.svg

# 批量转换整个文件夹（自动多进程）
python inklimner.py 图片文件夹/ -o 输出目录/

# 使用通配符
python inklimner.py "*.jpg" -o svg_out/

# 手机照片：自动校正方向 + 描线 + 预览
python inklimner.py 照片.jpg --mode edge --preview

# 小图保细节：处理前放大 2 倍
python inklimner.py 小图.png --scale 2 --detail 0.9

# 剪纸风色块轮廓（闭合路径，适合切穿）+ 裁白边
python inklimner.py logo.png --mode shape --trim --margin 10

# 300 DPI 原图 → 毫米尺寸（两种写法等价）
python inklimner.py 图案.png --dpi 300
python inklimner.py 图案.png --px-per-mm 11.81
```

---

## 🖥️ 图形界面

不想敲命令？直接用界面 —— 提供两种外观，启动时**自动挑一个能用的**：

```bash
python inklimner_gui.py       # 直接运行（优先 Qt，装不了再回退 Tkinter）
python inklimner.py --gui     # 或从 CLI 启动
inklimner-gui                 # pip 安装后
python inklimner_gui.py --qt  # 强制用 Qt 版
python inklimner_gui.py --tk  # 强制用 Tkinter 版
```

| 界面 | 外观 | 依赖 | 适用 |
|:--|:--|:--|:--|
| **Qt 版**（推荐）<br>`inklimner_gui_qt.py` | 现代暗色卡片式、原生拖拽、圆角控件 | `pip install "inklimner[gui]"`（PySide6） | Python 3.9+ |
| **Tk 版**<br>`inklimner_gui_tk.py` | 简洁原生界面 | **零第三方依赖**（标准库 tkinter） | Python 3.8+ |

两个界面**功能完全一致**，共用同一份参数规格、预设与执行逻辑（`inklimner_gui_core.py`），
所以参数永远不会两边不一致。

界面能力：

- **浅色 / 深色双主题**：默认**浅色**，界面右上角一键切换深浅，选择会被记住（预览区、日志配色同步跟随）
- **参数随模式联动**：选 `shape` 时自动灰掉 Canny / 灰带等无关项，只亮出真正生效的参数
- **参数预设**：内置「剪纸轮廓 / 照片描线 / 手绘线稿 / 印章 / 小图补细节 / 灰度层次」，也可把自己的调参存成预设
- **CLI 命令互转**：一键把当前设置导出成 `inklimner ...` 命令；也能粘贴别人的命令自动回填参数
- **拖拽导入**：图片 / 文件夹直接拖进窗口（Qt 版原生支持；Tk 版需 `pip install "inklimner[dnd]"`）
- **实时预览**：改参数自动重跑（单张小图、0.4s 防抖），所见即所得
- **原图 / 结果对照**：左右并排，一眼看出调参效果
- **双版本输出**：一次同时产出 `shape` 轮廓版和当前模式版
- **命名模板**：如 `{name}_cut` → `图案_cut.svg`，避免覆盖源目录产物
- **环境状态条**：顶部实时显示 potrace 与细化后端
- **记忆配置**：窗口尺寸、上次目录、参数自动保存到 `~/.inklimner_gui.json`

> Tk 版个别 Linux 发行版需补系统包：`sudo apt install python3-tk`
> Qt 版想要更清晰的预览可再装 Pillow：`pip install "inklimner[tk]"`

---

## 📖 详细用法

### 命令格式

```
inklimner <输入...> [选项]        # pip 安装后
python inklimner.py <输入...> [选项]   # 直接运行单文件
```

`<输入...>` 可同时传入多个：图片路径、目录、通配符（`*` `?` `[`）均可混用。

### 全部参数

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `inputs` | （必填） | 图片路径 / 目录 / 通配符，可多个 |
| `-o`, `--output` | 自动 | 输出 SVG 文件（单张）或输出目录 |
| `--mode` | `linedraw` | `linedraw`=XDoG 线稿+中心线（推荐）；`multi`=灰度等值线；`shape`=色块轮廓；`edge`=Canny+中心线 |
| `--detail` | `0.7` | 细节丰富度 0~1（linedraw / multi 有效） |
| `--scale` | `1.0` | 处理前放大倍数，小图保细节建议 2（输出坐标自动换算） |
| `--preview` | 关 | 同步输出 PNG 预览图（全部模式） |
| `--trim` | 关 | 自动裁掉四周白边（切割省料） |
| `--margin` | `0` | 在成品四周补白边距（像素） |
| `--max-size` | `2400` | 处理分辨率最长边上限，`0`=不限制 |
| `--dilate` | `0` | 线条加粗半径 0~2（`0`=不加粗） |
| `--min-line-len` | `8` | 中心线最短长度 px（过滤毛刺） |
| `--join-gap` | `3.0` | **断线修复**：端点相距 ≤ 该值(px) 且方向连贯时自动接上；`0`=关闭（linedraw / edge） |
| `--min-len` | `30` | 闭合轮廓最小周长（shape / multi 无 potrace 时） |
| `--min-band` | `30` | 灰度带最小面积（multi） |
| `--band-max` | `200` | multi 灰度带覆盖上限 1~255（越大保留越多浅灰细节） |
| `--simplify` | `0.001` | 简化强度，越小越精细 |
| `--smooth` | `0.5` | 平滑强度 0~1，`0`=折线（最忠实原轮廓） |
| `--no-potrace` | 关 | 强制不用 potrace |
| `--turdsize` | `2` | potrace 噪点面积阈值，`0`=保留一切 |
| `--alphamax` | `1.0` | potrace 曲线圆滑度 |
| `--opticurve` | `1` | potrace 曲线优化，`1`=开 |
| `--opttolerance` | `0.2` | potrace 曲线优化容差 |
| `--threshold` | `auto` | shape 模式二值化阈值 0~255，或 `auto` 自动（Otsu） |
| `--invert` | 关 | 黑白反转（黑底浅色图用） |
| `--no-exif` | 关 | 不按 EXIF 方向校正（默认会校正手机照片方向） |
| `--canny-low` | `30` | edge 模式低阈值 |
| `--canny-high` | `100` | edge 模式高阈值 |
| `--blur` | `1` | 预模糊核大小，`1`=关闭（linedraw 建议关闭） |
| `--stroke-width` | `0.1` | SVG 描边宽度（仅显示用，不影响切割） |
| `--stroke-color` | `#000000` | SVG 描边颜色 |
| `--px-per-mm` | `0` | 像素/毫米换算，如 `11.81`=300DPI；`0`=保持像素单位 |
| `--dpi` | `0` | 按 DPI 换算毫米（等价 `--px-per-mm dpi/25.4`） |
| `-j`, `--jobs` | `0` | 批量并发进程数，`0`=自动 |
| `-f`, `--force` | 开 | 覆盖已存在的输出（默认行为） |
| `--no-overwrite` | 关 | 目标已存在时跳过（不覆盖） |
| `-q`, `--quiet` | 关 | 安静模式，只输出错误 |
| `--version` | — | 打印版本号并退出 |

### 输出规则

- **单张 + `-o` 以 `.svg` 结尾** → 直接写入该文件；
- 其余情况 → 输出到 `-o` 指定的**目录**（未指定则为原图所在目录），文件名为 `原文件名.svg`；
- `--scale` 放大处理时，输出的 `viewBox` 与坐标会**自动缩回原始尺寸**；
- `--trim` / `--margin` 会改变输出画布尺寸，毫米尺寸按最终画布计算。

---

## 🎨 四种模式怎么选

### `linedraw` 模式（默认，最像手绘线稿）

用 **XDoG（扩展高斯差分）** 提取线稿，闭运算补缝后细化为 1px 骨架并追踪**中心线**，
输出一条条单线，激光只走一遍。

适合：照片转手绘线稿、插画描线、需要单线切割 / 描线的场景。

```bash
python inklimner.py 图案.png
python inklimner.py 照片.jpg --mode linedraw --detail 0.9 --scale 2
```

### `edge` 模式（照片 / 物理边缘）

用 **Canny** 提取边缘，同样经细化输出中心线。

适合：边缘清晰的照片描线、硬边物体轮廓。

```bash
python inklimner.py 照片.jpg --mode edge --canny-low 30 --canny-high 100
```

### `multi` 模式（灰度等值线，层次分明）

把灰度按阈值切成多个**波段**，逐带提取区域轮廓，效果类似地形图等高线。
`--band-max` 控制覆盖上限（默认 `200`，≥ 该值的区域视为背景）；想保留浅灰细节设为 `255`。

适合：需要分层表现明暗、渐变、雕刻深度的图。

```bash
python inklimner.py 照片.jpg --mode multi --detail 0.8
python inklimner.py 照片.jpg --mode multi --band-max 255   # 保留浅灰细节
```

### `shape` 模式（色块轮廓，剪纸风）

二值化后提取**闭合轮廓**，装有 potrace 时轮廓更圆滑。

适合：剪纸、logo、印章、实心图案、皮影、剪影——**需要闭合路径切穿的场景首选**。

```bash
python inklimner.py logo.png --mode shape --trim
python inklimner.py logo.png --mode shape --threshold 160 --no-potrace
```

---

## 🔧 调参速查表

| 现象 | 解决方法 |
|:---|:---|
| 边缘有毛刺、锯齿 | `--blur 3`，或 `--simplify 0.003` |
| 有很多细小碎线 | `--min-line-len 20`（linedraw / edge）；`--min-len 60`（shape / multi） |
| 图案细节丢失、变圆 | `--detail 0.9` `--simplify 0.0005` `--smooth 0` |
| 背景不纯、噪点多 | `--threshold 160`（shape，手动反复试），或调 `--canny-low/-high` |
| 想要硬朗折线感 | `--smooth 0` |
| 黑底白图提取不到 | 加 `--invert` |
| 线条太细、易断 | `--dilate 1`（或 2） |
| 线条莫名断开、碎成好几段 | 先调 `--join-gap 8`（默认 3，最大可到 20）；仍断则配合 `--dilate 1` |
| 小图细节糊成一团 | `--scale 2`（低分辨率小图必备） |
| 大图处理卡死 | `--max-size 1600`（降低最长边上限） |
| 输出四周留白太多 | `--trim`（可选再 `--margin 5`） |
| 输出尺寸不对 | `--dpi 300`（或 `--px-per-mm 11.81`） |
| 照片方向倒了 | 默认已校正；若图本身方向就该如此，加 `--no-exif` |

---

## ⚡ 激光切割实用建议

1. **尺寸换算**：用 `--dpi 300`（或 `--px-per-mm 11.81`）最省心；也可导入软件后手动改尺寸。
2. **stroke-width 只影响显示**：实际切缝由激光功率 / 速度 / 焦距决定，与 SVG 描边宽度无关。
3. **中心线 vs 闭合轮廓**：`linedraw` / `edge` 输出**单线走线**（适合描线、单线切割）；`shape` 输出**闭合轮廓**（适合沿边切穿）。按用途选模式。
4. **先裁白边再切割**：`--trim` 能去掉无效空白，省材料、方便对位；需要操作边距就加 `--margin`。
5. **悬空细结构会掉**：飘带、天线、细枝、镂空字母等会和主体断开，建议在 Inkscape 里手动加「连接桥」或删掉这些细节。
6. **内部小孔要谨慎**：大量小闭合路径会全部切穿、很碎。建议把内部细节设为「描线 / 低功率雕刻」层，只切外形。
7. **分图层工作流（推荐）**：同一张图用不同模式/参数跑两次，导入 LightBurn 后分到不同 layer，分别设切割 / 描线参数。
8. **大图案先降采样**：超大图先用 `--max-size` 控制处理分辨率避免卡死，再按需 `--scale` 补细节。

---

## ❓ 常见问题

**Q：转换后 SVG 打开是空白？**
A：多半是黑底浅色图被当成背景了，加 `--invert` 试试；或降低 `--threshold`。也可先用 `--preview` 看看提取结果。

**Q：为什么轮廓有断开的小缺口？**
A：优先调大 `--join-gap`（默认 `3.0`，可试 `8`）：端点相距在阈值内且方向连贯的线段会被自动接上，
无需手动去 Inkscape 补线。若仍断，再排查 `--min-line-len`（中心线）或 `--min-len`（闭合轮廓）
是否设太大把真轮廓过滤了，或关闭 `--blur`。

**Q：手机拍的照片方向倒了？**
A：v3.3 起默认按 EXIF 自动校正。若你要保留原始方向，加 `--no-exif`。

**Q：能保留色彩吗？**
A：不能。本工具输出的是纯描边线稿，专为切割设计。要彩色矢量请用 Adobe Illustrator / Inkscape 的图像描摹功能。

**Q：支持的输入格式有哪些？**
A：`.png` `.jpg` `.jpeg` `.bmp` `.webp` `.tif` `.tiff`。

**Q：为什么大图处理很慢 / 卡住？**
A：默认 `--max-size 2400` 已自动降采样防卡死；若仍慢可降到 `1600`。安装 `opencv-contrib-python` 后细化可提速约百倍。

**Q：必须装 potrace 吗？**
A：不必。potrace 仅让 `shape` / `multi` 模式轮廓更圆滑；未安装时自动改用 OpenCV 轮廓。

**Q：`--px-per-mm` 和 `--max-size` 一起用时，尺寸还准吗？**
A：准。降采样会自动补偿，输出毫米尺寸始终按原图 DPI 计算。

**Q：输出会覆盖同名文件吗？**
A：默认覆盖并打印 `[覆盖]` 提示；加 `--no-overwrite` 则跳过已存在文件。

**Q：索引色 / 调色板 PNG 会出错吗？**
A：不会，会自动按彩色解码，避免调色板索引被误当成灰度值。

**Q：和 potrace / Inkscape 描摹比有什么区别？**
A：potrace 曲线更圆滑、保真度更高，适合精细图案；本工具更轻量、参数更贴近激光切割场景（中心线单线输出、碎线过滤、物理尺寸、大图防护），开箱即用，并可选择性调用 potrace 取长补短。

---

## 🖼️ 示例

`examples/` 里有可直接试跑的样例：

```bash
python inklimner.py examples/sample.png -o examples/sample_linedraw.svg --trim --preview
python inklimner.py examples/sample.png -o examples/sample_shape.svg --mode shape --trim
```

| 文件 | 说明 |
|:---|:---|
| `examples/sample.png` | 示例输入（黑底图案） |
| `examples/sample_linedraw.svg` | linedraw 模式产出（中心线线稿） |
| `examples/sample_shape.svg` | shape 模式产出（闭合轮廓） |
| `examples/sample_linedraw.preview.png` | 预览图 |

---

## 📁 项目结构

```
inklimner/
├── inklimner.py                  # 主程序（单文件，便于分发/打包）
├── inklimner_gui.py              # 图形界面统一入口（自动选 Qt / Tk）
├── inklimner_gui_qt.py           # Qt 界面（PySide6，现代暗色）
├── inklimner_gui_tk.py           # Tkinter 界面（零第三方依赖）
├── inklimner_gui_core.py         # 两个界面共享的参数规格与执行逻辑
├── pyproject.toml              # 打包与 inklimner 命令入口
├── requirements.txt            # 运行依赖
├── Makefile                    # 常用开发命令（make test / make build ...）
├── README.md                   # 中文说明（本文件）
├── README.en.md                # English README
├── CHANGELOG.md                # 更新日志
├── CONTRIBUTING.md             # 贡献指南
├── LICENSE                     # MIT
├── Dockerfile                  # 含 potrace 的容器镜像
├── assets/                     # 项目封面 / logo
├── docs/BUILD.md               # 云打包说明（各平台安装包怎么来）
├── docs/releases/              # 各版本 Release 说明
├── tools/                      # 打包 / 冒烟测试 / 版本号同步脚本（CI 用）
├── .github/                    # CI / 打包工作流 + issue / PR 模板
├── examples/                   # 示例输入与产出
└── tests/                      # pytest 测试
```

---

## 🧪 开发与测试

```bash
pip install -e ".[dev]"      # pytest / ruff / Pillow / PySide6
pytest -q                    # 运行测试（含 Qt 界面的 offscreen 构建测试）
ruff check .                 # 代码检查

# 无显示器环境也可自检图形界面（Linux 服务器 / CI 同样适用）
QT_QPA_PLATFORM=offscreen python inklimner_gui_qt.py --selftest

# 发版辅助（版本号散落在多处，用它一次改完，不会漏）
python tools/bump_version.py            # 检查：版本号出现在哪些文件
python tools/bump_version.py 3.4.2      # 同步：一条命令改完 20+ 处
python tools/smoke_test.py              # 冒烟测试打出来的可执行文件
```

---

## 📝 许可证

[MIT License](LICENSE) —— 可自由使用、修改、分发。
