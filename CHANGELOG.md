# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，
版本号遵循语义化版本。

## [3.4.1.1] - 2026-09-16

### Added
- **图形界面（两套外观，自动选择）**
  - `inklimner_gui_qt.py` —— **PySide6 / Qt 现代界面**（推荐）：**浅色 / 深色双主题**
    （默认浅色，界面右上角一键切换并记忆），卡片式参数分组、圆角控件、原生拖拽、
    原图/结果并排对照、日志语义化着色；可在无显示器环境用 `--selftest` 自检全链路
  - `inklimner_gui_tk.py` —— Tkinter 界面，作为**零第三方依赖**的回退方案
  - `inklimner_gui_core.py` —— 两套界面共享的参数规格 / 预设 / CLI 命令互转 / 批量执行，
    从架构上保证两边参数永不漂移
  - `inklimner_gui.py` —— 统一入口：有 PySide6 就用 Qt，否则自动回退 Tkinter
    （`--qt` / `--tk` 可强制指定）
  - 界面能力（两套一致）：多选 / 批量添加图片或整个文件夹、**参数随模式联动置灰**、
    6 套内置预设 + 自定义预设、**CLI 命令互转**、拖拽导入、实时预览（0.4s 防抖）、
    原图 / 结果对照、双版本输出、命名模板、环境状态条、高 DPI 适配、
    配置记忆（`~/.inklimner_gui.json`）、后台线程 + 进度条 + 可中断
- **`--gui`**：`inklimner --gui` 一条命令直接打开界面
- **`inklimner-gui`** 命令行入口（pip 安装后可用）
- 可选依赖组：`[gui]`（PySide6，Qt 界面）、`[tk]`（Pillow，Tk 界面清晰预览）、
  `[dnd]`（tkinterdnd2，Tk 界面拖拽）
- **云端打包（GitHub Actions）** —— 推 `v*` tag 即自动构建 **Windows / macOS / Linux**
  三平台的**免安装包**并发布到 Releases（`…-gui.zip` 图形界面版、`…-cli.zip` 命令行版）；
  也可在 Actions 页面手动触发、只取产物
  - **推送到 main 也会自动构建**，产物直接出现在该次运行的 **Artifacts** 区（保留 30 天），
    不用打 tag 就能随时拿最新构建
  - **Artifacts 按「平台 + 类型」分开**（`InkLimner-<版本>-<平台>-gui` / `-cli`），
    下载解压后**直接就是可执行文件 / 文件夹**，不用再扒一层 zip
  - 每个 job 结束时会在运行摘要里列出产物清单与体积，一眼看清打出了什么
  - 顺手排掉一个打包坑：`inklimner.py` 的 `--gui` 分支会让 PyInstaller 把整个 Qt 打进
    CLI 包（实测 160 MB），现在 CLI 版排除 PySide6，稳定在 ~105 MB；
    GUI 用**目录包**而非单文件，启动快得多（单文件每次启动都要解压几百 MB）
  - 新增 `tools/smoke_test.py`：跑一遍打包产物做冒烟测试（CLI `--version` +
    GUI 无显示器 `--selftest`），拦住「能打包、一运行就崩」
  - 新增 `tools/make_release.py`：跨平台把产物打成 zip（CI 与本地共用）
  - 新增 `tools/bump_version.py`：**一条命令同步全部版本号**（代码 / 打包配置 /
    README 标题与徽章 / 文档共 20+ 处），并列出还有哪些文件带着当前版本号；
    `CHANGELOG.md` 与 `docs/releases/` 作为历史记录不会被误改
  - 新增 `docs/BUILD.md`：云打包说明、各平台首次运行的签名提示、发版流程
  - README 顶部新增 **version 徽章**（图片上的版本号）与 **Releases 下载徽章**
  - GUI 的 `--selftest` 在没有 `examples/` 时会**自动生成合成测试图**，因此打包产物也能自检

### Changed
- 抽出 `build_parser()` 与 `plan_jobs()`，CLI 与 GUI **共用同一套参数与输出规划**，
  避免两边逻辑漂移
- 图形界面拆分为「共享核心层 + 两套界面层」，参数规格只有一份
- `inputs` 改为可选（`nargs='*'`），以便 `--gui` 无输入启动；无输入时给出明确提示

### Fixed
- **线条被切断（重点修复）**：输出 SVG 里「本应连贯的线条断开 / 碎成多段」的三个根因一并解决：
  - **8 连通骨架的「对角捷径」冗余边** —— 浅斜率处会凭空冒出度=3/4 的假交叉点，
    追踪时被迫频繁断线（1px 圆环 400 个骨架像素里有 232 个非 2 度点，被切成 35 段）。
    新增 `_build_nbrs()`：若对角邻点之外还存在正交公共邻点（可绕行），则剔除该对角边，
    骨架随即变回干净通路（圆环 400 像素全部恢复为度 2）。
  - **断口两端是自由端（度=1）**，而旧的 `_merge_fragments()` 只处理度=2 的断点，缺口永远补不上。
    新增 `_join_gaps()`：端点距离 ≤ 阈值**且方向连贯**时自动拼接（方向门控保证平行线不被误粘），
    另加 `_close_self()` 让首尾可平滑相接的链自动闭环。
  - **过滤顺序错误** —— `min_len` 原先在合并之前执行，被噪声切碎的长线每段都短于阈值 → 整条消失。
    流程调整为「补断口 → 拼断点 → 最后过滤」。
- 新增 **`--join-gap`**（默认 `3.0`，`0`=关闭）：断线修复阈值，线条莫名断开时调大即可，
  不必再手动进 Inkscape 补线。GUI「② 线稿参数」组同步提供该项。
- **修复「＋ 图片」等按钮点了直接报错** —— Qt 的 `clicked` 信号会附带一个 `checked`(bool) 参数，
  而 `add_files(paths=None)` 误把它当成了文件路径列表，于是执行 `for p in False`，
  抛出 `TypeError: 'bool' object is not iterable`，按钮完全点不动。
  现在按钮统一用 lambda 吃掉该参数，`add_files` 也会把 bool 视作「未提供路径」；
  并补了**回归测试**（真实 click 按钮 + 直接传 bool 两种路径）。
- **修复 CI 在 Windows 上失败**（GUI 冒烟测试步骤）—— 真因是 **Windows 终端默认用
  cp1252 / charmap 编码**：自检脚本 `print` 中文时抛 `UnicodeEncodeError`，直接把进程带崩。
  Linux / macOS 终端默认 UTF-8 所以没事；日志用 `logging` 没崩，是因为它内部会吞掉编码
  异常，而 `print` 不会 —— 这也是这个坑难查的原因。修复（多层防护）：
  - 新增统一的 `force_utf8_output()`：程序启动时把 stdout / stderr 切成 UTF-8，
    并用 `backslashreplace` 兜底，极端环境下最多显示成 `\uXXXX` 转义，**绝不会崩**
  - CLI、两套 GUI、三个 tools 脚本、CI 与打包工作流全部接入；打包冒烟测试还会把
    `PYTHONIOENCODING=utf-8` 传给子进程
  - `--selftest` 的输出改为 **ASCII 安全**（动态中文自动转义），任何编码的控制台下都不会崩
  - 顺带修正 `--selftest` 的平台插件探测：改用 Qt 官方 `QLibraryInfo` 取插件目录
    （原先写死的路径在部分平台不存在），插件缺失时优雅回退而非让 Qt 静默终止
- README（中/英）参数表、调参速查表与 FAQ 补充断线排查指引。

### Tests
- 新增 `plan_jobs` 输出规划、GUI 参数一致性、预设合法性、模式覆盖完整性、
  CLI 命令往返一致与配置读写等测试，测试总数 **14 → 38**
- 新增断线修复专项测试：对角捷径剔除、闭环图形单一折线、小断口自动拼接、
  「先拼接后过滤」顺序、平行线不被误粘、`join_gap=0` 向后兼容，以及端到端连贯性回归护栏
- 新增界面层测试：两套界面共用同一份规格、后端自动选择（Qt 优先 / Tk 回退）、
  配色**默认浅色**与深浅切换 / 记忆、**按钮点击不会把 checked 参数当路径**（真实 click 回归）、
  以及 **Qt 界面在 offscreen 无显示器环境下完整构建**（CI 可跑）

## [3.3.0] - 2026-09-14

### Added
- **EXIF 方向自动校正**：手机照片不再横竖颠倒；新增 `--no-exif` 可关闭
- **`--dpi`**：按 DPI 换算毫米（等价 `--px-per-mm dpi/25.4`），比手填 11.81 直观
- **`--trim`**：自动裁掉四周白边，切割省料
- **`--margin N`**：产出成品四周留白
- **`-j/--jobs`**：控制批量并发进程数，并输出 `[i/n]` 进度
- **`pyproject.toml`**：支持 `pip install .` 与 `inklimner` 命令行入口

### Changed
- 日志改用 `logging`（`-q/--quiet` 更干净，便于库调用）
- 输出**确定性**：轮廓/线段按位置排序，同输入产出逐字节一致
- 细化算法**向量化**（A/B 计算），并加迭代上限，纯 Python 回退路径更快

### Added (repo)
- `LICENSE` / `.gitignore` / `requirements.txt` / `CONTRIBUTING.md`
- `tests/`（pytest）、`.github/workflows/`（CI + 跨平台构建）、`Dockerfile`、`examples/`

## [3.2.0] - 2026-09-13

### Fixed
- 修复 `--px-per-mm` 与 `--max-size` 联用时的**物理尺寸偏差**（降采样自动补偿）
- 修复调色板 PNG 被误当灰度的问题（自动按彩色解码）

### Added
- `--band-max`：multi 灰度带覆盖上限，浅灰细节可控
- `--preview` 扩展到**全部模式**
- `--version` / `-q,--quiet` / `--force` / `--no-overwrite`
- 批量多进程；失败返回非零退出码

### Changed
- 细化算法限定**非零包围盒**，明显提速
- potrace 改为**惰性探测**（不再在启动时跑子进程）

## [3.1.0] - 2026-09-12

### Added
- 核心算法升级为 **XDoG 线稿 + 骨架中心线**（单线输出）
- 四种模式：`linedraw`（默认）/ `edge` / `multi` / `shape`

### Fixed
- 内置细化算法邻居索引越界崩溃
- 骨架走线在交叉点处丢边、闭环不闭合
- `--dilate 1` 无效
- potrace 未安装时启动崩溃 / `transform` 坐标错乱

[3.4.1.1]: https://github.com/HBrOcean/inklimner/releases/tag/v3.4.1.1
[3.3.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.3.0
[3.2.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.2.0
[3.1.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.1.0
