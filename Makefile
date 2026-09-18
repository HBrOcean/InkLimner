# inklimner —— 常用开发命令
# 用法： make <target>
.PHONY: help install dev test lint fmt run gui gui-qt gui-tk gui-check clean build build-gui docker

help:
	@echo "inklimner 可用命令："
	@echo "  make install   安装（pip install .）"
	@echo "  make dev       开发环境（pip install -e '.[dev]'）"
	@echo "  make test      运行测试（pytest）"
	@echo "  make lint      代码检查（ruff）"
	@echo "  make fmt       自动修复并格式化（ruff）"
	@echo "  make run IN=examples/sample.png [OUT=x.svg] [ARGS='--trim']"
	@echo "  make gui       打开图形界面（自动选 Qt / Tk）"
	@echo "  make gui-qt    强制用 Qt 界面"
	@echo "  make gui-tk    强制用 Tkinter 界面"
	@echo "  make gui-check 无显示器自检图形界面（CI / 服务器可用）"
	@echo "  make build     打包 CLI 单文件可执行（PyInstaller）"
	@echo "  make build-gui 打包 GUI 单文件可执行（体积较大）"
	@echo "  make docker    构建 Docker 镜像"
	@echo "  make clean     清理构建/缓存产物"

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest -q

gui:
	python inklimner_gui.py

gui-qt:
	python inklimner_gui_qt.py

gui-tk:
	python inklimner_gui_tk.py

# 无显示器环境（CI / Linux 服务器）下验证界面全链路
gui-check:
	QT_QPA_PLATFORM=offscreen python inklimner_gui_qt.py --selftest

lint:
	ruff check .

fmt:
	ruff check --fix .
	ruff format .

# 示例： make run IN=examples/sample.png OUT=/tmp/o.svg ARGS='--mode shape --trim'
IN ?= examples/sample.png
OUT ?=
ARGS ?=
run:
	python inklimner.py $(IN) $(if $(OUT),-o $(OUT),) $(ARGS)

build:
	pyinstaller --onefile --name inklimner inklimner.py

build-gui:
	pyinstaller --onefile --windowed --name inklimner-gui inklimner_gui.py

docker:
	docker build -t inklimner .

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
