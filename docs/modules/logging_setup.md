# feldspar.logging_setup

Stdlib-`logging` wiring for feldspar: one dictConfig-driven setup
(`logger.py`), a plain formatter, and a level-ceiling filter used to keep
stdout limited to below-WARNING records (the "stdout is data, logs go to
stderr" split, config in `config.toml`).

## logging_setup_logger

<!-- frob:describes python/feldspar/logging_setup/logger.py::get_logger -->

`get_logger(name)` returns a module logger, applying the package's
`config.toml` via `logging.config.dictConfig` exactly once per process
(guarded by the module-level `_initialized` flag) before the first call
returns.

## logging_setup_formatter

<!-- frob:describes python/feldspar/logging_setup/formatter.py::MalmbergFormatter -->
<!-- frob:describes python/feldspar/logging_setup/formatter.py::MalmbergFormatter.format -->

`MalmbergFormatter` is a plain `logging.Formatter`: WARNING-and-above
records are prefixed with the level name (`"WARNING: ..."`), DEBUG/INFO
records emit the bare message only (or always prefixed, if constructed
with `show_level=True`). `format()` implements that rule.

## logging_setup_filter

<!-- frob:describes python/feldspar/logging_setup/filter.py::BelowLevelFilter -->
<!-- frob:describes python/feldspar/logging_setup/filter.py::BelowLevelFilter.filter -->

`BelowLevelFilter` is a `logging.Filter` that passes only records
strictly below a configured `below` level; it is how a stdout handler is
kept clean of WARNING+ noise while a stderr handler carries everything.
`filter()` implements the strict less-than check against `record.levelno`.
