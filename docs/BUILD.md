# 打包成各系统的应用程序（云打包）

不用在自己电脑上装编译环境 —— **交给 GitHub 免费构建**：
推代码会自动出构建产物（Artifacts），打 tag 会自动发布 Windows / macOS / Linux
三个平台的安装包到 Releases。

---

## 方式一：推代码到 main（最省事，自动出 artifacts）

直接：

```bash
git push origin main
```

推上去就会自动构建三个平台，产物在该次运行的 **Artifacts** 区（保留 **30 天**）。
适合"随时想拿一个最新版试试"。

## 方式二：手动触发（想指定时机时用）

仓库页 → **Actions** → 左侧选 **Build release packages** → 右侧 **Run workflow** →
选分支 → **Run workflow**。同样在 **Artifacts** 区下载。

## 方式三：打 tag（发正式版，自动发布到 Releases）

```bash
git tag v3.4.1.1
git push origin v3.4.1.1
```

这是**唯一**会把产物发布到 Releases 页面的方式，适合对外发版。

---

## 产物在哪、长什么样

**① Artifacts 区**（推 main / 手动触发时）—— 每个平台两个包：

| Artifact 名 | 下载解压后 |
|:--|:--|
| `InkLimner-<版本>-<平台>-gui` | 直接就是 `InkLimner.exe` + `_internal/`，**双击 exe 即用** |
| `InkLimner-<版本>-<平台>-cli` | 单个可执行文件（`inklimner` / `inklimner.exe`） |

（macOS 的 gui 包里是 `InkLimner.app`）

**② Releases 页面**（打 tag 时）—— 规范命名的 zip：

| 文件 | 内容 | 大小（参考） |
|:--|:--|:--|
| `InkLimner-<版本>-<平台>-gui.zip` | 图形界面版：解压后双击 `InkLimner(.exe)` 即用 | 约 210 MB（解压约 380 MB） |
| `InkLimner-<版本>-<平台>-cli.zip` | 命令行版：单个可执行文件 | 约 105 MB |

`<平台>` 为 `windows` / `macos` / `linux`。

> **体积为什么这么大？** 包里塞进了 Qt、OpenCV、NumPy 三套运行时 —— 换来的是
> **目标电脑不需要装 Python、不需要装任何依赖**。

## 首次运行的提示（未签名程序的正常现象）

- **Windows**：可能弹 SmartScreen「Windows 已保护你的电脑」→ 点**更多信息** → **仍要运行**。
- **macOS**：`.app` 首次打开可能提示「无法验证开发者」→ **右键点 App → 打开**，
  或到「系统设置 → 隐私与安全性」里点「仍要打开」。
- **Linux**：GUI 版依赖系统的图形库（libGL、libxcb 等）。若双击没反应，
  先在终端运行看缺什么，或改用 `cli` 版。

---

## 本地自己打包（可选）

想在自己电脑上构建，或调试打包问题：

```bash
pip install opencv-python-headless numpy pyinstaller PySide6-Essentials

# CLI：单文件（输出到 dist/cli）
python -m PyInstaller --noconfirm --onefile --name inklimner \
    --distpath dist/cli --workpath build/cli \
    --exclude-module PySide6 --exclude-module shiboken6 inklimner.py

# GUI：目录包（输出到 dist/gui；用目录而非单文件，启动快很多）
python -m PyInstaller --noconfirm --name InkLimner --windowed \
    --distpath dist/gui --workpath build/gui \
    --exclude-module tkinter --exclude-module PIL inklimner_gui.py

# 冒烟测试：确认打出来的东西真能跑（含 GUI 无显示器自检）
python tools/smoke_test.py

# 打成便于分发的 zip
python tools/make_release.py --slug windows --version v3.4.1.1
```

产物在 `dist/cli`（命令行版）与 `dist/gui`（界面版），zip 在 `release/`。

> **为什么分成两个目录？** macOS 的文件系统**不区分大小写** —— `inklimner`（命令行版）
> 和 `InkLimner`（界面版）会被当成同一个名字，放同一个目录里会互相顶掉，
> 表现为构建"成功"了但产物不见了、冒烟测试报 `PermissionError`。
> 冒烟测试与打包脚本会在 `dist/`、`dist/cli`、`dist/gui` 三处自动探测，两种布局都能用。

> **PyInstaller 不能交叉编译**：Windows 的 exe 必须在 Windows 上构建，
> macOS 的包必须在 macOS 上构建 —— 这正是要交给 GitHub Actions 的原因。

## 实用备注

- `--exclude-module PySide6` 让 **CLI 版保持在 ~105 MB**：否则 `inklimner.py` 里
  `--gui` 分支的 import 会把整个 Qt 一起打进去（实测膨胀到 160 MB）。
- GUI 用 **目录包（onedir）** 而不是单文件：单文件每次启动都要把几百 MB 解压到临时目录，
  双击后要等好几秒；目录包几乎秒开。
- 打包后 `examples/` 不在产物里，所以界面的 `--selftest` 会**自动生成一张合成测试图**
  来完成自检 —— CI 也正是靠它验证打包产物。

---

## 发版流程（推荐顺序）

```bash
# 1. 同步版本号（代码 / 打包配置 / README 标题与徽章 / 打包文档，一次改完 20+ 处）
python tools/bump_version.py 3.4.2

# 2. 在 CHANGELOG.md 顶部新增一节，并新建 docs/releases/v3.4.2.md

# 3. 跑测试与代码检查
pytest -q && ruff check .

# 4. 提交并推送
git add . && git commit -m "release: v3.4.2" && git push

# 5. 打 tag → 自动构建三平台安装包并发布 Release
git tag v3.4.2
git push origin v3.4.2

# 6. 到 Releases 页面确认三个平台的 zip 都已上传
```

> 版本号同时出现在 `inklimner.py`、`pyproject.toml`、README 标题与徽章、
> 本文档、打包工作流注释等 20 多处 —— 用 `tools/bump_version.py`
> 一条命令改完，避免漏改。
> `CHANGELOG.md` 与 `docs/releases/` 是历史记录，脚本**故意不动**它们
> （否则会把旧版本的链接一起改坏）。
>
> README 顶部的 `version` 徽章是**静态**的（由脚本同步），
> 另外还挂了一个指向 Releases 的下载徽章，点进去就是最新的安装包。
