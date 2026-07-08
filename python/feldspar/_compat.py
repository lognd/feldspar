from __future__ import annotations

"""Single home for stdlib-version shims (house rule); import from here only."""

# tomllib is stdlib on 3.11+; fall back to tomli, then toml, on older Python.
# Unconditional try/except so type checkers only evaluate the first branch.
try:
    import tomllib as toml  # type: ignore[no-redef]  # ty: ignore[unresolved-import]
except ImportError:
    try:
        import tomli as toml  # type: ignore[import-not-found,no-redef]
    except ImportError:
        import toml  # type: ignore[no-redef]  # ty: ignore[unresolved-import]

__all__ = ["toml"]
