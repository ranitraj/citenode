.PHONY: setup init install precommit-install lint clean hooks-update

## First-time setup: run the interactive project initialiser
setup:
	python3 init.py

## Bootstrap: install root dev deps + all services + git hooks
init: install precommit-install

## Install root dev dependencies
install:
	uv sync --group dev
	@for dir in services/*/; do \
		echo "Installing $$dir..."; \
		(cd $$dir && uv sync --group dev); \
	done

## Install git hooks (pre-commit + commit-msg)
precommit-install:
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

## Update pre-commit hooks to latest versions
hooks-update:
	uv run pre-commit autoupdate

## Run all pre-commit hooks against every file
lint:
	uv run pre-commit run --all-files

## Remove caches and build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
