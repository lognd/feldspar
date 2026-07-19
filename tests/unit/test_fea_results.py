from __future__ import annotations

"""WO-08 tests: parsing of ccx .dat displacement/principal-stress tables
and the scalar reductions built on top of them
(`python/feldspar/fea/results.py`). Pure Python -- no gmsh/ccx needed,
so these carry no `fea` pytest marker (unlike the solver.py integration
tests, which do)."""

import math

import pytest

from feldspar.fea.results import (
    first_mode_frequency,
    max_displacement_magnitude,
    max_von_mises,
    parse_dat_displacements,
    parse_dat_frequencies,
    parse_dat_principal_stresses,
)
from feldspar.solve.errors import SolveError


def test_parse_dat_displacements_valid_table():
    """A small, well-formed *NODE PRINT block parses to {node_id:
    (ux, uy, uz)}, skipping the header/blank lines."""
    text = """
    DISPLACEMENTS FOR NODE SET SNALL

     NODE           U1              U2              U3
        1  0.0000000E+00   0.0000000E+00   0.0000000E+00
        2  1.2500000E-03  -3.4000000E-04   0.0000000E+00
        3  2.5000000E-03  -6.8000000E-04   1.0000000E-05
    """
    result = parse_dat_displacements(text)
    assert result.is_ok
    displacements = result.danger_ok
    assert displacements == {
        1: (0.0, 0.0, 0.0),
        2: (1.25e-3, -3.4e-4, 0.0),
        3: (2.5e-3, -6.8e-4, 1.0e-5),
    }


# frob:tests crates/feldspar-py/src/library/mech.rs::mech_von_mises_principal_py
def test_parse_dat_principal_stresses_valid_table_and_max_von_mises():
    """A small *EL PRINT S block (the six tensor components ccx actually
    prints, `<elem> <ip> Sxx Syy Szz Sxy Sxz Syz`) parses and reduces to
    principals; max_von_mises matches the hand-computed uniaxial identity
    (s1=100, s2=0, s3=0 -> von Mises = 100), same case as WO-07's
    test_library_mech.py uniaxial check."""
    text = """
    STRESSES (ELEMENT INTEGRATION POINTS) FOR ELEMENT SET ESET

     ELEMENT   PT   SXX      SYY      SZZ      SXY      SXZ      SYZ
           1    1  1.0000000E+02  0.0  0.0  0.0  0.0  0.0
           2    1  5.0000000E+01  5.0000000E+01  0.0  0.0  0.0  0.0
    """
    result = parse_dat_principal_stresses(text)
    assert result.is_ok
    stresses = result.danger_ok
    # Keyed by running row index; uniaxial -> (100,0,0), equibiaxial -> (50,50,0).
    values = sorted(stresses.values(), reverse=True)
    assert values[0] == pytest.approx((100.0, 0.0, 0.0))
    assert values[1] == pytest.approx((50.0, 50.0, 0.0))
    assert max_von_mises(stresses) == pytest.approx(100.0, rel=1e-9)


def test_parse_dat_displacements_truncated_row_fails_closed():
    """A row that starts like a data row (leads with an int node id)
    but is missing a column must produce Err(SolveError.ParseFailed)
    with line context -- never a partial/silent map."""
    text = """
     NODE           U1              U2              U3
        1  0.0000000E+00   0.0000000E+00   0.0000000E+00
        2  1.2500000E-03  -3.4000000E-04
    """
    result = parse_dat_displacements(text)
    assert result.is_err
    error = result.danger_err
    assert isinstance(error, SolveError)
    assert error.kind == "ParseFailed"
    assert "line 4" in error.context


def test_parse_dat_principal_stresses_non_numeric_token_fails_closed():
    """A would-be data row with a non-numeric token mid-row must fail
    the whole parse, not just skip that row."""
    text = """
     ELEMENT   PT   SXX      SYY      SZZ      SXY      SXZ      SYZ
           1    1  1.0000000E+02   NaNgarbage   0.0   0.0   0.0   0.0
    """
    result = parse_dat_principal_stresses(text)
    assert result.is_err
    error = result.danger_err
    assert isinstance(error, SolveError)
    assert error.kind == "ParseFailed"
    assert "line 3" in error.context


# frob:tests python/feldspar/fea/results.py::first_mode_frequency kind="unit"
def test_parse_dat_frequencies_reads_only_the_eigenvalue_table():
    """A real ccx *FREQUENCY .dat holds several int-leading tables; only
    the EIGENVALUE OUTPUT rows (mode, eigenvalue, rad/time, cycles/time,
    imaginary) are the frequencies, and first_mode_frequency returns the
    fundamental mode's cycles/time (Hz)."""
    text = """
     E I G E N V A L U E   O U T P U T

 MODE NO    EIGENVALUE                       FREQUENCY
                                     REAL PART            IMAGINARY PART
                           (RAD/TIME)      (CYCLES/TIME     (RAD/TIME)

      1   0.1382130E+08   0.3717700E+04   0.5916904E+03   0.0000000E+00
      2   0.1382130E+08   0.3717700E+04   0.5916904E+03   0.0000000E+00
      3   0.2422965E+08   0.4922362E+04   0.7834182E+03   0.0000000E+00

     P A R T I C I P A T I O N   F A C T O R S

MODE NO.   X-COMPONENT     Y-COMPONENT     Z-COMPONENT
      1   0.9183150E-11   0.4170385E+02   0.1014089E+02
    """
    result = parse_dat_frequencies(text)
    assert result.is_ok
    freqs = result.danger_ok
    # Only the three eigenvalue rows -- the participation-factor row is not
    # mistaken for a fourth mode.
    assert set(freqs) == {1, 2, 3}
    assert first_mode_frequency(freqs) == pytest.approx(591.6904)


def test_parse_dat_frequencies_missing_table_fails_closed():
    """A .dat with no EIGENVALUE OUTPUT section is an error, not an empty
    (silently wrong) frequency map."""
    result = parse_dat_frequencies(
        "     P A R T I C I P A T I O N\n  1  2.0  3.0  4.0\n"
    )
    assert result.is_err
    assert result.danger_err.kind == "ParseFailed"


def test_max_displacement_magnitude_known_map():
    """max_displacement_magnitude picks the row with the largest
    Euclidean displacement magnitude sqrt(ux^2+uy^2+uz^2)."""
    displacements = {
        1: (0.0, 0.0, 0.0),
        2: (3.0e-3, 4.0e-3, 0.0),  # magnitude 5e-3
        3: (1.0e-3, 1.0e-3, 1.0e-3),  # magnitude ~1.732e-3
    }
    expected = math.sqrt(3.0e-3**2 + 4.0e-3**2)
    assert max_displacement_magnitude(displacements) == pytest.approx(
        expected, rel=1e-9
    )
