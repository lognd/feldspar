from __future__ import annotations

import logging

import pytest

_feldspar = pytest.importorskip(
    "feldspar._feldspar",
    reason="requires `maturin develop` to have built the native extension",
)


# frob:tests python/feldspar/logging_setup kind="integration"
def test_rust_span_reaches_python_logging(caplog: pytest.LogCaptureFixture) -> None:
    """A Rust `tracing::info_span!` emitted via `_feldspar.smoke_span()` must
    surface as a Python logging record through the pyo3-log bridge (AD-8)."""
    with caplog.at_level(logging.INFO):
        _feldspar.smoke_span()
    assert any("smoke span reached tracing" in r.message for r in caplog.records)
