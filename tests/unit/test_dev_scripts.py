from __future__ import annotations

"""Unit tests for scripts/gen_keys.py and scripts/sync_lithos_examples.py
(frob compliance T-0007): binds TEST001 for their public entry points."""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load(name: str, path: Path):
    """Import a scripts/*.py module by path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# frob:tests scripts/gen_keys.py::main kind="unit"
def test_gen_keys_main_writes_and_refuses_overwrite(tmp_path, monkeypatch):
    """main() writes a fresh keypair once, then refuses to clobber it."""
    pytest.importorskip("cryptography")
    module = _load("gen_keys_under_test", SCRIPTS_DIR / "gen_keys.py")
    keys_dir = tmp_path / "keys"
    monkeypatch.setattr(module, "KEYS_DIR", keys_dir)
    monkeypatch.setattr(module, "PRIVATE_KEY_PATH", keys_dir / "dev_ed25519.key")
    monkeypatch.setattr(module, "PUBLIC_KEY_PATH", keys_dir / "dev_ed25519.pub")

    module.main()
    assert module.PRIVATE_KEY_PATH.exists()
    assert module.PUBLIC_KEY_PATH.exists()
    first_contents = module.PRIVATE_KEY_PATH.read_bytes()

    module.main()  # second call must not overwrite the existing private key
    assert module.PRIVATE_KEY_PATH.read_bytes() == first_contents


# frob:tests scripts/sync_lithos_examples.py::sync kind="unit"
def test_sync_copies_examples_tree_and_returns_count(tmp_path, monkeypatch):
    """sync() mirrors <lithos>/examples into examples/lithos and returns the file count."""
    module = _load("sync_lithos_under_test", SCRIPTS_DIR / "sync_lithos_examples.py")
    lithos_root = tmp_path / "lithos"
    (lithos_root / "examples" / "sub").mkdir(parents=True)
    (lithos_root / "examples" / "a.py").write_text("# a\n", encoding="ascii")
    (lithos_root / "examples" / "sub" / "b.py").write_text("# b\n", encoding="ascii")

    mirror = tmp_path / "mirror"
    monkeypatch.setattr(module, "MIRROR", mirror)

    count = module.sync(lithos_root)

    assert count == 3  # a.py, sub/b.py, and the .mirror marker written into the copy
    assert (mirror / "a.py").read_text(encoding="ascii") == "# a\n"
    assert (mirror / "sub" / "b.py").read_text(encoding="ascii") == "# b\n"
    assert (mirror / ".mirror").exists()


def test_sync_raises_when_lithos_examples_missing(tmp_path, monkeypatch):
    """sync() raises SystemExit(2) when <lithos>/examples does not exist."""
    module = _load("sync_lithos_under_test2", SCRIPTS_DIR / "sync_lithos_examples.py")
    monkeypatch.setattr(module, "MIRROR", tmp_path / "mirror")
    with pytest.raises(SystemExit):
        module.sync(tmp_path / "no-such-lithos")


# frob:tests scripts/sync_lithos_examples.py::main kind="unit"
# frob:tests scripts kind="integration"
def test_main_parses_lithos_arg_and_invokes_sync(tmp_path, monkeypatch, capsys):
    """main() parses --lithos and delegates to sync(), printing the file count."""
    module = _load("sync_lithos_under_test3", SCRIPTS_DIR / "sync_lithos_examples.py")
    monkeypatch.setattr(module, "MIRROR", tmp_path / "mirror")
    lithos_root = tmp_path / "lithos"
    (lithos_root / "examples").mkdir(parents=True)
    (lithos_root / "examples" / "a.py").write_text("# a\n", encoding="ascii")

    monkeypatch.setattr(sys, "argv", ["sync_lithos_examples.py", "--lithos", str(lithos_root)])
    exit_code = module.main()

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "2 files mirrored" in out  # a.py plus the .mirror marker
