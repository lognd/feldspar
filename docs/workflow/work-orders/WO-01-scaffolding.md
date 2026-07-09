# WO-01: Scaffolding

Status: todo
Depends: --
Language: mixed (repo infrastructure)
Spec: 00-architecture.md (layout, AD-6/8/11/12), 01 (personas)

## Goal

The empty-but-green repository: layout, build, lint, type, test, CI,
and logging exist so every later WO only adds content.

## Deliverables

- Layout per 00-architecture.md: cargo workspace (`feldspar-core`,
  `feldspar-library`, `feldspar-py`) + `python/feldspar/` package
  skeleton with `__about__.py` (the ONE version string), empty
  module stubs with docstrings, `tests/` with markers (`fea`,
  `regolith`, `slow`) registered in pytest config.
- `pyproject.toml`: maturin build backend, extras `mesh`/`regolith`
  (empty deps ok now), the `regolith.model_packs` entry point wired
  to `feldspar.pack:register` (a no-op stub), version sourced from
  `__about__`.
- Makefile: install, build (maturin develop), test, lint (ruff),
  format, typecheck (mypy), coverage, check, keys (generates dev
  keypair under `keys/`, private key gitignored).
- Logging: dictConfig setup per `~/.claude/refs/logging.md`; pyo3-log
  bridge in `feldspar-py`; `tracing` initialized in core; a smoke
  test proving a Rust-side span reaches Python logging.
- `.gitignore` per house baseline + `.feldspar/`, `keys/` private
  pattern; `deny.toml`; pinned Rust toolchain file.
- CI: the five AD-12 jobs (regolith/fea jobs may be `continue-on-
  error` until WO-08/09 land, but must exist and run).
- `TODO.md` ledger listing WO-01..10 with checkboxes.

## Acceptance

- Fresh clone: `make install && make check` green; `maturin develop`
  builds; `python -c "import feldspar"` works without gmsh, ccx, or
  regolith installed (AD-6/FINV-3 from day one).
- CI green on all jobs that can run; ledger committed.
