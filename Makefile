# inklimner —— 常用开发命令
# 用法： make <target>
.PHONY: help install dev test lint fmt run clean build docker

help:
	@echo "inklimner 可用命令："
	@echo "  make install   安装（pip install .）"
	@echo "  make dev       开发环境（pip install -e '.[dev]'）"
	@echo "  make test      运行测试（pytest）"
	@echo "  make lint      代码检查（ruff）"
	@echo "  make fmt       自动修复并格式化（ruff）"
	@echo "  make run IN=examples/sample.png [OUT=x.svg] [ARGS='--trim']"
	@echo "  make build     打包单文件可执行（PyInstaller）"
	@echo "  make docker    构建 Docker 镜像"
	@echo "  make clean     清理构建/缓存产物"

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest -q

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

docker:
	docker build -t inklimner .

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
