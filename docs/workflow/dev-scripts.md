# Dev scripts

Utility scripts under `scripts/`, run via `make` targets, not imported
by the package. Documented here for frob's doc graph (COV001); each
`frob:doc` edge below binds a function to its paragraph.

<a id="gen-keys"></a>

## gen_keys.py

`make keys` invokes `scripts/gen_keys.py::main`. Generates a dev
Ed25519 keypair under `keys/` for local signing; refuses to overwrite
an existing private key at `keys/dev_ed25519.key`. Requires the
`cryptography` package (`uv add --dev cryptography`); exits 1 with an
error message on stderr if it is missing.

<a id="sync-lithos-examples"></a>

## sync_lithos_examples.py

`make sync-examples` invokes `scripts/sync_lithos_examples.py::main`,
which parses `--lithos PATH` (default `../lithos`) and calls
`sync_lithos_examples.py::sync`. `sync` deletes the current
`examples/lithos/` mirror and recursively copies
`<lithos>/examples/` in its place verbatim, writing a `.mirror`
marker file, then returns the count of files copied. Never edit
`examples/lithos/` by hand; see `../../examples/README.md`.
