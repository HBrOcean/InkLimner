# Contributing

感谢你有兴趣改进 inklimner！这份指南帮你快速上手。

## 开发环境

```bash
git clone https://github.com/HBrOcean/inklimner.git
cd inklimner
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"                             # 含 pytest / ruff
# 想要更快的细化： pip install opencv-contrib-python
```

## 运行与自测

```bash
python inklimner.py --help
python inklimner.py examples/sample.png -o /tmp/out.svg --preview
pytest -q
ruff check .
```

也可以直接用 `Makefile`（`make help` 查看全部）：

```bash
make dev     # pip install -e ".[dev]"
make test    # pytest -q
make lint    # ruff check .
make run IN=examples/sample.png ARGS='--mode shape --trim'
```

## 提交规范

- 分支：`feat/xxx`、`fix/xxx`、`docs/xxx`
- 提交信息：建议 [Conventional Commits](https://www.conventionalcommits.org/)
  （`feat: ...` / `fix: ...` / `docs: ...`）
- 一个 PR 只做一件事，并在 `CHANGELOG.md` 的 `Unreleased` 段落记一笔

## 代码约定

- 保持**单文件** `inklimner.py`（便于分发/打包成可执行），函数职责清晰、带 docstring
- 新增 CLI 参数：默认值要安全，并同步更新 **README.md + README.en.md + `--help`**
- **输出必须确定性**：涉及遍历时请排序（见 `trace_polylines` / `contour_polys`）
- 改动算法后，请运行 `pytest`，并尽量附一张前后对比图

## 报告问题

请附上：系统 / Python / OpenCV 版本、完整命令行、原图（或类似的复现图）、
期望结果与实际结果。
