from __future__ import annotations

"""CalculiX .frd/.dat result parsing into engine port values (WO-08).

CalculiX's `.dat` file is a best-effort human-readable text format with
no machine schema -- ccx emits `*NODE PRINT` and `*EL PRINT` blocks as
headers followed by whitespace-separated data rows, and the exact
header/column wording varies across ccx versions. Rather than parse the
headers, both parsers here scan every line and treat any line whose
first whitespace-separated token parses as an `int` as the START of a
data row; the remaining tokens must then parse as exactly the expected
number of `float`s (3 for displacements: ux, uy, uz; 6 for stresses: the
Sxx..Syz tensor components ccx prints for `*EL PRINT, S`, reduced to
principal stresses here, after dropping an optional integration-point
token). Any line that looks like a data row (leads with an int) but
fails to parse cleanly -- wrong column count or a non-numeric token --
is treated as a truncated/malformed table and fails the WHOLE parse
(fail closed, per WO-08 contract): never a partial/silent answer.
Non-data lines (headers, blank lines, footers) are skipped."""

import math
from typing import Mapping, Tuple

from typani import Err, Ok, Result

from feldspar import _feldspar
from feldspar.logging_setup import get_logger
from feldspar.solve.errors import SolveError

_log = get_logger(__name__)

__all__ = [
    "parse_dat_displacements",
    "parse_dat_principal_stresses",
    "parse_dat_frequencies",
    "max_displacement_magnitude",
    "max_von_mises",
    "first_mode_frequency",
]


def _parse_three_column_table(
    text: str, table_name: str
) -> Result[Mapping[int, Tuple[float, float, float]], SolveError]:
    """Shared row-scanning core for the two `<id> <a> <b> <c>` .dat
    tables (displacements: ux,uy,uz; principal stresses: s1,s2,s3) --
    same fail-closed row-parse rule for both, so it lives in one home
    (NO DUPLICATION) rather than being copy-pasted per table kind."""
    rows: dict[int, Tuple[float, float, float]] = {}
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        try:
            row_id = int(tokens[0])
        except ValueError:
            # Not a data row (header/label text) -- skip.
            continue
        # A row that starts with an integration-point-style token dropped
        # (e.g. "<elem> <ip> <s1> <s2> <s3>") reduces to 4 numeric tokens
        # for principal stresses; canonical shape here is exactly
        # `<id> <a> <b> <c>` (3 trailing numeric columns), so accept
        # either "id a b c" (4 tokens) directly.
        value_tokens = tokens[1:]
        if len(value_tokens) != 3:
            _log.warning(
                "%s: malformed row at line %d (expected 3 value columns, got %d): %r",
                table_name,
                line_no,
                len(value_tokens),
                raw_line,
            )
            return Err(SolveError.ParseFailed(context=f"line {line_no}: {raw_line!r}"))
        try:
            a, b, c = (float(tok) for tok in value_tokens)
        except ValueError:
            _log.warning(
                "%s: non-numeric value token at line %d: %r",
                table_name,
                line_no,
                raw_line,
            )
            return Err(SolveError.ParseFailed(context=f"line {line_no}: {raw_line!r}"))
        rows[row_id] = (a, b, c)
    _log.info("%s: parsed %d data rows", table_name, len(rows))
    return Ok(rows)


def parse_dat_displacements(
    text: str,
) -> Result[Mapping[int, Tuple[float, float, float]], SolveError]:
    """Parses a ccx `*NODE PRINT ... U` displacement table into
    `{node_id: (ux, uy, uz)}`; any malformed/truncated row fails the
    whole parse (SolveError.ParseFailed), never a partial map."""
    return _parse_three_column_table(text, "displacements")


def _principal_stresses(
    sxx: float, syy: float, szz: float, sxy: float, sxz: float, syz: float
) -> Tuple[float, float, float]:
    """Principal stresses (eigenvalues, descending) of the symmetric
    Cauchy stress tensor via the closed-form 3x3 symmetric-eigenvalue
    algorithm -- ccx has no principal-stress `*EL PRINT` label, so it
    prints the six tensor components (S) and the principals are reduced
    here (pure Python: numpy is not a feldspar runtime dependency)."""
    p1 = sxy * sxy + sxz * sxz + syz * syz
    if p1 == 0.0:
        # Already diagonal.
        ordered = sorted((sxx, syy, szz), reverse=True)
        return (ordered[0], ordered[1], ordered[2])
    q = (sxx + syy + szz) / 3.0
    p2 = (sxx - q) ** 2 + (syy - q) ** 2 + (szz - q) ** 2 + 2.0 * p1
    p = math.sqrt(p2 / 6.0)
    # B = (A - q*I) / p; r = det(B) / 2, clamped to [-1, 1] for acos.
    b11, b22, b33 = (sxx - q) / p, (syy - q) / p, (szz - q) / p
    b12, b13, b23 = sxy / p, sxz / p, syz / p
    det_b = (
        b11 * (b22 * b33 - b23 * b23)
        - b12 * (b12 * b33 - b23 * b13)
        + b13 * (b12 * b23 - b22 * b13)
    )
    r = max(-1.0, min(1.0, det_b / 2.0))
    phi = math.acos(r) / 3.0
    s1 = q + 2.0 * p * math.cos(phi)
    s3 = q + 2.0 * p * math.cos(phi + 2.0 * math.pi / 3.0)
    s2 = 3.0 * q - s1 - s3
    return (s1, s2, s3)


def parse_dat_principal_stresses(
    text: str,
) -> Result[Mapping[int, Tuple[float, float, float]], SolveError]:
    """Parses a ccx `*EL PRINT ... S` stress table into
    `{row_index: (s1, s2, s3)}` principal stresses. ccx prints one row
    per element integration point as `<elem> <ip> Sxx Syy Szz Sxy Sxz
    Syz` (an optional leading integration-point column is tolerated);
    each row's six components are reduced to principals here. Rows are
    keyed by a running index so every integration point is preserved for
    the downstream max reduction. Any malformed/truncated row fails the
    whole parse (SolveError.ParseFailed), never a partial map."""
    rows: dict[int, Tuple[float, float, float]] = {}
    row_index = 0
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        try:
            int(tokens[0])
        except ValueError:
            # Not a data row (header/label text) -- skip.
            continue
        value_tokens = tokens[1:]
        # Tolerate an optional leading integration-point column: a stress
        # row is `<elem> <ip> S11..S23` (7 trailing tokens) or `<elem>
        # S11..S23` (6). Anything else is malformed.
        if len(value_tokens) == 7:
            value_tokens = value_tokens[1:]
        if len(value_tokens) != 6:
            _log.warning(
                "principal stresses: malformed row at line %d (expected 6 "
                "stress components, got %d): %r",
                line_no,
                len(value_tokens),
                raw_line,
            )
            return Err(SolveError.ParseFailed(context=f"line {line_no}: {raw_line!r}"))
        try:
            sxx, syy, szz, sxy, sxz, syz = (float(tok) for tok in value_tokens)
        except ValueError:
            _log.warning(
                "principal stresses: non-numeric value token at line %d: %r",
                line_no,
                raw_line,
            )
            return Err(SolveError.ParseFailed(context=f"line {line_no}: {raw_line!r}"))
        rows[row_index] = _principal_stresses(sxx, syy, szz, sxy, sxz, syz)
        row_index += 1
    _log.info("principal stresses: parsed %d data rows", len(rows))
    return Ok(rows)


def parse_dat_frequencies(
    text: str,
) -> Result[Mapping[int, Tuple[float, float, float]], SolveError]:
    """Parses a ccx `*FREQUENCY` step's mode table (WO-16, 07 vibration
    Phase 3): ccx prints one row per requested mode,
    `<mode_no> <eigenvalue> <freq_rad_per_time> <freq_cycles_per_time>`,
    the same shape as the displacement/stress tables (an id column plus
    3 numeric columns), so this reuses `_parse_three_column_table`
    (NO DUPLICATION) rather than a bespoke scanner. Returns
    `{mode_no: (eigenvalue, freq_rad_per_time, freq_cycles_per_time)}`;
    any malformed/truncated row fails the whole parse, same fail-closed
    rule as the other two tables."""
    return _parse_three_column_table(text, "frequencies")


def first_mode_frequency(
    frequencies: Mapping[int, Tuple[float, float, float]],
) -> float:
    """The lowest-mode-number row's cycles/time (Hz) column -- ccx lists
    modes in ascending eigenvalue order starting at mode 1, so `min` over
    the row keys picks the first (fundamental) mode."""
    first_mode = min(frequencies)
    return frequencies[first_mode][2]


def max_displacement_magnitude(
    displacements: Mapping[int, Tuple[float, float, float]],
) -> float:
    """Max Euclidean displacement magnitude sqrt(ux^2+uy^2+uz^2) over
    every parsed node row -- the scalar reduction WO-08's solver.py
    feeds into Richardson extrapolation for the cantilever family."""
    return max(
        (ux * ux + uy * uy + uz * uz) ** 0.5 for ux, uy, uz in displacements.values()
    )


def max_von_mises(
    principal_stresses: Mapping[int, Tuple[float, float, float]],
) -> float:
    """Max von Mises equivalent stress over every parsed
    element/integration-point row, via
    `feldspar._feldspar.mech_von_mises_principal` (the single Rust home
    of the von Mises reduction -- never reimplemented here)."""
    return max(
        _feldspar.mech_von_mises_principal(s1, s2, s3)
        for s1, s2, s3 in principal_stresses.values()
    )
