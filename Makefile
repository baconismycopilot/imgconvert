.PHONY: help sync lock upgrade run test lint check build clean clean-pyc clean-test clean-dist
.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@uv run python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

sync: ## Create/update .venv from uv.lock
	uv sync

lock: ## Re-resolve dependencies and update uv.lock
	uv lock

upgrade: ## Upgrade all locked dependencies to their latest allowed versions
	uv lock --upgrade

run: ## Run the CLI, e.g. `make run ARGS="~/Pictures -f webp"`
	uv run imgconvert $(ARGS)

test: ## Run the test suite
	uv run pytest

lint: ## Validate code against PEP8
	uv run flake8 .

check: lint test ## Lint and test

build: ## Build sdist and wheel into dist/
	uv build

clean: clean-pyc clean-test clean-dist ## Remove all build, test and Python artifacts

clean-pyc: ## Remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -type d -exec rm -rf {} +

clean-test: ## Remove test and coverage artifacts
	rm -f .coverage
	rm -rf htmlcov/ .pytest_cache/

clean-dist: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
