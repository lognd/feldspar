from __future__ import annotations

"""Integration regression closing the coverage hole that let the
plan-time output-port-domain bug (`feldspar_core::search`) survive:
NOTHING plans over the REAL `feldspar.library` registry. Registers
real `mech` + `elec` directions, freezes, and exercises the
`Relation`-built multi-direction promise end to end -- both
`cantilever` directions solve, a two-step chain routes through it, and
a plain `elec` direction solves too. Also proves execution-time
output-domain checking (`execute.py`'s `_check_step_output_domain`,
added alongside the planner fix) fires as a named `SolveError`."""

import pytest

from feldspar.core import Accuracy, Domain, Interval
from feldspar.library.elec import register as register_elec
from feldspar.library.mech import register as register_mech
from feldspar.plan import execute, plan, solve
from feldspar.solve import Citation, SolverRegistry, solver

_MECH_TAGS = frozenset({"linear_elastic", "small_deflection"})
_GENEROUS_EPS = 1.0  # generous eps budget; every direction here is EXACT


def _library_registry() -> SolverRegistry:
    registry = SolverRegistry()
    register_mech(registry)
    register_elec(registry)
    registry.freeze()
    return registry


def test_cantilever_tip_deflection_solves():
    """(a) known E, I, L, F -> closed-form deflection F*L^3/(3EI)."""
    registry = _library_registry()
    force = 100.0
    length = 0.5
    youngs_modulus = 69e9
    second_moment = 8.3e-9
    known = {
        "mech.load.tip_force": Interval(force, force),
        "mech.geom.cantilever.length": Interval(length, length),
        "mech.material.youngs_modulus": Interval(youngs_modulus, youngs_modulus),
        "mech.section.second_moment": Interval(second_moment, second_moment),
    }
    result = solve(
        registry, known, _MECH_TAGS, "mech.deflection.tip", _GENEROUS_EPS
    )
    assert result.is_ok, result.err
    expected = force * length**3 / (3.0 * youngs_modulus * second_moment)
    solution = result.danger_ok
    assert solution.value.lo == pytest.approx(expected, rel=1e-9)
    assert solution.value.hi == pytest.approx(expected, rel=1e-9)


def test_cantilever_reverse_direction_solves():
    """(b) the REVERSE `Relation` direction: known F, L, I, deflection
    -> required youngs modulus. This is the multi-direction promise the
    bug broke -- BOTH directions share the same box, spanning inputs
    AND outputs for each direction, which pre-fix made every direction
    permanently unroutable."""
    registry = _library_registry()
    force = 100.0
    length = 0.5
    second_moment = 8.3e-9
    deflection = force * length**3 / (3.0 * 69e9 * second_moment)
    known = {
        "mech.load.tip_force": Interval(force, force),
        "mech.geom.cantilever.length": Interval(length, length),
        "mech.section.second_moment": Interval(second_moment, second_moment),
        "mech.deflection.tip": Interval(deflection, deflection),
    }
    result = solve(
        registry, known, _MECH_TAGS, "mech.material.youngs_modulus", _GENEROUS_EPS
    )
    assert result.is_ok, result.err
    assert result.danger_ok.value.lo == pytest.approx(69e9, rel=1e-6)


def test_chained_route_through_rect_second_moment_and_cantilever():
    """(c) a two-step chain: known width/height/L/F -> rect_second_moment
    -> cantilever -> mech.deflection.tip."""
    registry = _library_registry()
    width = 0.04
    height = 0.06
    force = 100.0
    length = 0.5
    youngs_modulus = 69e9
    known = {
        "mech.section.width": Interval(width, width),
        "mech.section.height": Interval(height, height),
        "mech.load.tip_force": Interval(force, force),
        "mech.geom.cantilever.length": Interval(length, length),
        "mech.material.youngs_modulus": Interval(youngs_modulus, youngs_modulus),
    }
    result = solve(
        registry, known, _MECH_TAGS, "mech.deflection.tip", _GENEROUS_EPS
    )
    assert result.is_ok, result.err
    solution = result.danger_ok
    assert len(solution.route.steps) == 2
    second_moment = width * height**3 / 12.0
    expected = force * length**3 / (3.0 * youngs_modulus * second_moment)
    assert solution.value.lo == pytest.approx(expected, rel=1e-9)


def test_elec_divider_vout_solves():
    """(d) a plain (non-`Relation`) `elec` direction still solves."""
    registry = _library_registry()
    vin = 5.0
    r1 = 1000.0
    r2 = 2000.0
    rl = 1e6
    known = {
        "elec.source.vin": Interval(vin, vin),
        "elec.divider.r1": Interval(r1, r1),
        "elec.divider.r2": Interval(r2, r2),
        "elec.divider.rl": Interval(rl, rl),
    }
    result = solve(
        registry,
        known,
        frozenset({"linear", "small_signal"}),
        "elec.divider.vout",
        _GENEROUS_EPS,
    )
    assert result.is_ok, result.err


# ---------------------------------------------------------------------------
# Execution-time output-domain checking (added alongside the planner fix,
# `execute.py`'s `_check_step_output_domain`): an output that lands
# outside the solver's own declared `Domain.box` entry for that port is a
# named `SolveError.OutputOutOfDomain`, not a silent pass.
# ---------------------------------------------------------------------------


def _registry_with_narrow_output_box() -> SolverRegistry:
    """A synthetic `Relation`-shaped solver (own box entry on its own
    output port, same pattern as `mech.cantilever`) whose output box is
    narrower than the value the known input actually produces -- the
    step must plan (the fix) but fail execution against its own
    declared output validity range."""
    registry = SolverRegistry()

    @solver(
        namespace="narrow",
        inputs=("narrow.a",),
        outputs=("narrow.b",),
        domain=Domain(
            box={
                "narrow.a": Interval(0.0, 100.0),
                "narrow.b": Interval(0.0, 1.0),  # too narrow for a=5..6
            },
            tags=frozenset(),
        ),
        cost=1.0,
        accuracy={"narrow.b": Accuracy(eps_abs=0.0, eps_rel=0.0)},
        citations=(Citation(kind="handbook", ref="test fixture"),),
        version="1",
    )
    def narrow_step(x):
        from typani import Ok

        return Ok({"narrow.b": x["narrow.a"]})

    assert registry.register(*narrow_step.solver_direction).is_ok
    registry.freeze()
    return registry


def test_output_out_of_declared_box_is_named_execution_failure():
    registry = _registry_with_narrow_output_box()
    known = {"narrow.a": Interval(5.0, 6.0)}

    # Plan-time: succeeds now (the fix) -- the output box entry does not
    # block admission.
    route = plan(registry, known, frozenset(), "narrow.b", _GENEROUS_EPS).danger_ok
    assert route.steps[0].solver_id == "narrow.narrow_step"

    # Execution-time: the realized output (5..6) is not a subset of the
    # declared box (0..1) -- a named SolveError, not a silent pass.
    result = execute(route, registry, known)
    assert result.is_err
    err = result.danger_err
    assert err.kind == "OutputOutOfDomain"
    assert err.port == "narrow.b"


def test_output_in_declared_box_still_succeeds():
    """Control: same registry, input in range that keeps the output
    inside its declared box -- must still succeed."""
    registry = _registry_with_narrow_output_box()
    known = {"narrow.a": Interval(0.2, 0.3)}
    route = plan(registry, known, frozenset(), "narrow.b", _GENEROUS_EPS).danger_ok
    result = execute(route, registry, known)
    assert result.is_ok, result.err
