.PHONY: install build test lint format typecheck coverage check keys clean

install:
	uv sync --all-extras

build:
	uv run maturin develop

test:
	uv run pytest tests/ -n auto -m "not regolith and not fea"

lint:
	uv run ruff check python/ tests/

format:
	uv run ruff format python/ tests/

typecheck:
	uv run ty check python/

coverage:
	uv run pytest tests/ --cov=python --cov-report=term-missing --cov-report=html \
		-m "not regolith and not fea"

check: lint typecheck test
	cargo fmt --all -- --check
	cargo clippy --workspace --all-targets -- -D warnings
	cargo test --workspace

keys:
	mkdir -p keys
	uv run python scripts/gen_keys.py

clean:
	rm -rf dist/ build/ .venv/ target/ __pycache__ .pytest_cache .ruff_cache \
		.coverage htmlcov coverage.xml
