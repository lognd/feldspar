from __future__ import annotations

"""ngspice batch-mode `print` output parsing into engine port values
(WO-17).

ngspice's interactive `print <expr>` command (run inside a `.control
... .endc` block in batch mode) writes a single line of the form
`<expr-as-written> = <value>` to stdout, e.g. `v(out) = 4.761905e+00`.
This is a best-effort text scrape (ngspice has no machine-schema
output for a bare `print`, only the heavier `.raw` file format this
module deliberately avoids, see `deck.py`): the FIRST line matching
`<name> = <float>` (case-insensitive on `<name>`) is taken as the
result; a deck that emits no such line, or whose value token fails to
parse as a float, is `SolveError.ParseFailed` -- fail closed, never a
partial/silent answer (same contract as `feldspar.fea.results`)."""

import re

from typani import Err, Ok
from typani.result import Result

from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = ["parse_print_value"]

_PRINT_LINE_RE = re.compile(r"^\s*(\S+)\s*=\s*([+-]?[0-9.eE+-]+)\s*$")


def parse_print_value(log_text: str, expr_name: str) -> Result[float, SolveError]:
    """Scans `log_text` for a `print`-emitted `<expr_name> = <value>`
    line (case-insensitive match on the name) and parses `<value>` as
    a float. Returns the FIRST match (a `.tran` print emits one line
    per requested variable per timepoint printed; batch `.control`
    decks here request exactly one timepoint's worth via a single
    `print`, so first-match is also only-match in practice)."""
    target = expr_name.strip().lower()
    for line_no, raw_line in enumerate(log_text.splitlines(), start=1):
        match = _PRINT_LINE_RE.match(raw_line)
        if match is None:
            continue
        name, value_token = match.group(1), match.group(2)
        if name.strip().lower() != target:
            continue
        try:
            value = float(value_token)
        except ValueError:
            _log.warning(
                "parse_print_value: line %d matched name=%s but value "
                "token %r did not parse as a float",
                line_no,
                expr_name,
                value_token,
            )
            return Err(
                SolveError.ParseFailed(
                    context=f"ngspice print line {line_no!r}: {raw_line!r}"
                )
            )
        _log.info(
            "parse_print_value: parsed %s=%s from line %d", expr_name, value, line_no
        )
        return Ok(value)

    _log.warning(
        "parse_print_value: no line matching %r = <value> found in ngspice "
        "output; raw output follows (truncated to 2000 chars):\n%s",
        expr_name,
        log_text[:2000],
    )
    return Err(
        SolveError.ParseFailed(
            context=f"no ngspice print line found for expression {expr_name!r}"
        )
    )
