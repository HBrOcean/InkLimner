# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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

[3.3.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.3.0
[3.2.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.2.0
[3.1.0]: https://github.com/HBrOcean/inklimner/releases/tag/v3.1.0
