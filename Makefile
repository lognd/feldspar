.PHONY: install install-regolith build test regolith-test lint import-lint fmt-check format typecheck coverage check check-consistency keys clean sync-examples

# Default install works WITHOUT a sibling lithos checkout: the
# `regolith` extra is an editable path dependency on ../lithos and only
# `install-regolith` (and the conformance tests) needs it.
install:
	uv sync --all-extras --no-extra regolith
	uv run maturin develop

install-regolith:
	uv sync --all-extras
	uv run maturin develop

build:
	uv run maturin develop

test:
	uv run pytest tests/ -n auto -m "not regolith and not fea and not spice"

regolith-test:
	uv run pytest tests/regolith/ -m regolith

lint:
	uv run ruff check python/ tests/

import-lint:
	uv run lint-imports

fmt-check:
	uv run ruff format --check python/ tests/
	cargo fmt --all -- --check

format:
	uv run ruff format python/ tests/
	cargo fmt --all

typecheck:
	uv run ty check python/

coverage:
	uv run pytest tests/ --cov=python --cov-report=term-missing --cov-report=html \
		-m "not regolith and not fea and not spice"

check: fmt-check lint import-lint typecheck test
	cargo clippy --workspace --all-targets -- -D warnings
	cargo test --workspace

check-consistency: ## Report stray git worktrees whose branch is already merged into main (separate leg, not part of `check`)
	bash scripts/consistency_sweep.sh

keys:
	mkdir -p keys
	uv run python scripts/gen_keys.py

clean:
	rm -rf dist/ build/ .venv/ target/ __pycache__ .pytest_cache .ruff_cache \
		.coverage htmlcov coverage.xml

# Refresh examples/lithos as a verbatim mirror of ../lithos/examples
# (lithos D148: one corpus, single-sourced in lithos). Review the
# diff like any generated artifact.
sync-examples:
	python3 scripts/sync_lithos_examples.py
