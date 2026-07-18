from __future__ import annotations

"""Generates a dev Ed25519 keypair under keys/ (`make keys`); private key gitignored."""

import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:
    print(
        "error: `cryptography` is required for `make keys` "
        "(uv add --dev cryptography)",
        file=sys.stderr,
    )
    sys.exit(1)

KEYS_DIR = Path(__file__).resolve().parent.parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "dev_ed25519.key"
PUBLIC_KEY_PATH = KEYS_DIR / "dev_ed25519.pub"


def main() -> None:
    """Writes a fresh dev keypair, refusing to overwrite an existing private key."""
    # frob:doc docs/workflow/dev-scripts.md
    # frob:ticket T-0007
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    if PRIVATE_KEY_PATH.exists():
        print(f"keys: {PRIVATE_KEY_PATH} already exists, not overwriting")
        return
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    PRIVATE_KEY_PATH.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    PRIVATE_KEY_PATH.chmod(0o600)
    PUBLIC_KEY_PATH.write_bytes(
        public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"keys: wrote {PRIVATE_KEY_PATH} and {PUBLIC_KEY_PATH}")


if __name__ == "__main__":
    main()
