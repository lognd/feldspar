from __future__ import annotations

"""WO-03 tests: SolverInfo/Citation/@solver/SolverRegistry/sugar layer.

Covers the WO-03 rows of docs/spec/toolchain/02-edge-cases.md, the
acceptance criterion (a toy thermo.ideal_gas solver registers, freezes,
iterates sorted), and the AD-4/FINV-5/FINV-6/FINV-7 guarantees."""

import pytest
from typani import Err, Ok

from feldspar.core import Accuracy, Domain, Interval, PortDecl
from feldspar.solve import (
    EXACT,
    Citation,
    ClaimSenses,
    Correlation,
    CoupledGroup,
    RegistryError,
    Relation,
    SolveError,
    SolverRegistry,
    make_direction,
    solver,
    table_solver_1d,
    table_solver_2d,
)

R = 287.05  # J/(kg K)


def _ideal_gas_relation() -> Relation:
    return Relation(
        namespace="thermo",
        ports=("thermo.pressure", "thermo.specific_volume", "thermo.temperature"),
        domain={
            "thermo.pressure": (1e3, 1e7),
            "thermo.specific_volume": (1e-3, 1e2),
            "thermo.temperature": (200.0, 2000.0),
        },
        tags=("ideal_gas",),
        cost=1e-6,
        accuracy=EXACT,
        citations=("handbook: Moran, Fund. of Eng. Thermo. 9e, sec. 3.5",),
        version="1",
    )


def _declare_ideal_gas_ports(registry: SolverRegistry) -> None:
    registry.declare_ports(
        PortDecl("thermo.pressure", "Pa"),
        PortDecl("thermo.specific_volume", "m^3/kg"),
        PortDecl("thermo.temperature", "K"),
    )


def test_toy_ideal_gas_registers_freezes_iterates_sorted() -> None:
    """Acceptance: 'a toy thermo.ideal_gas solver registers, freezes,
    iterates sorted'."""
    ideal_gas = _ideal_gas_relation()

    @ideal_gas.direction(solves_for="thermo.temperature")
    def t_from_pv(x):
        return x["thermo.pressure"] * x["thermo.specific_volume"] / R

    @ideal_gas.direction(solves_for="thermo.pressure")
    def p_from_tv(x):
        return R * x["thermo.temperature"] / x["thermo.specific_volume"]

    registry = SolverRegistry()
    _declare_ideal_gas_ports(registry)
    assert ideal_gas.register(registry).is_ok

    registry.freeze()
    assert registry.is_frozen()

    ids = [info.solver_id for info, _fn in registry]
    assert ids == sorted(ids)
    assert ids == ["thermo.p_from_tv", "thermo.t_from_pv"]


def test_registry_digest_stable_and_folds_every_solver() -> None:
    ideal_gas = _ideal_gas_relation()

    @ideal_gas.direction(solves_for="thermo.temperature")
    def t_from_pv(x):
        return x["thermo.pressure"] * x["thermo.specific_volume"] / R

    registry_a = SolverRegistry()
    _declare_ideal_gas_ports(registry_a)
    ideal_gas.register(registry_a)

    registry_b = SolverRegistry()
    _declare_ideal_gas_ports(registry_b)
    ideal_gas.register(registry_b)

    assert registry_a.digest() == registry_b.digest()


# -- RegistryError: every variant reachable ------------------------------


def test_duplicate_solver_id_is_err() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.section.second_moment",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def rect_second_moment(x):
        return 1.0

    info, fn = rect_second_moment.solver_direction
    assert registry.register(info, fn).is_ok
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.DuplicateSolverId(solver_id=info.solver_id)


def test_port_unit_conflict() -> None:
    registry = SolverRegistry()
    registry.declare_ports(PortDecl("mech.p", "Pa"))
    result = registry.declare_ports(PortDecl("mech.p", "m"))
    assert result.is_err
    assert result.err == RegistryError.PortUnitConflict(port="mech.p")


def test_port_rank_conflict() -> None:
    from feldspar.core import Rank

    registry = SolverRegistry()
    registry.declare_ports(PortDecl("mech.p", "Pa", Rank.scalar()))
    result = registry.declare_ports(PortDecl("mech.p", "Pa", Rank.vector(3)))
    assert result.is_err
    assert result.err == RegistryError.PortRankConflict(port="mech.p")


def test_duplicate_port_decl_is_err() -> None:
    registry = SolverRegistry()
    registry.declare_ports(PortDecl("mech.p", "Pa"))
    result = registry.declare_ports(PortDecl("mech.p", "Pa"))
    assert result.is_err
    assert result.err == RegistryError.DuplicatePortDecl(port="mech.p")


def test_unknown_port_once_registry_has_a_declared_table() -> None:
    """F12 is opt-in: it activates once ANY module has declared ports
    (see registry.py comment) -- the WO-03 required-behavior row."""
    registry = SolverRegistry()
    registry.declare_ports(PortDecl("mech.known", "Pa"))

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.typo_port",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def bad(x):
        return 1.0

    info, fn = bad.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.UnknownPort(port="mech.typo_port")


def test_empty_citations_is_err() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=(),
        version="1",
    )
    def f(x):
        return 1.0

    info, fn = f.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.EmptyCitations(solver_id=info.solver_id)


def test_calibration_only_citations_is_err() -> None:
    """'citations empty or calibration-only' both map to EmptyCitations."""
    registry = SolverRegistry()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("calibration: run blake3:abc",),
        version="1",
    )
    def f(x):
        return 1.0

    info, fn = f.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.EmptyCitations(solver_id=info.solver_id)


def test_non_positive_cost_is_err() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=0.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def f(x):
        return 1.0

    info, fn = f.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.NonPositiveCost(solver_id=info.solver_id)


def test_accuracy_output_mismatch_is_err() -> None:
    registry = SolverRegistry()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x", "mech.y"),
        domain={},
        cost=1.0,
        accuracy={"mech.x": EXACT},
        citations=("handbook: ref",),
        version="1",
    )
    def f(x):
        return {"mech.x": 1.0, "mech.y": 2.0}

    info, fn = f.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.AccuracyOutputMismatch(solver_id=info.solver_id)


def test_register_after_freeze_is_err() -> None:
    registry = SolverRegistry()
    registry.freeze()

    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def f(x):
        return 1.0

    info, fn = f.solver_direction
    result = registry.register(info, fn)
    assert result.is_err
    assert result.err == RegistryError.Frozen()

    assert (
        registry.declare_ports(PortDecl("mech.x", "Pa")).err == RegistryError.Frozen()
    )


def test_bad_table_reachable_and_table_ascending_check() -> None:
    with pytest.raises(ValueError):
        table_solver_1d(
            namespace="thermo",
            x_port="thermo.pressure",
            y_port="thermo.saturation_temperature",
            x=(1.0, 0.5, 2.0),
            y=(1.0, 2.0, 3.0),
            method="linear",
            eps_abs=0.1,
            citations=("handbook: ref",),
            version="1",
        )
    # BadTable itself is directly constructible/reachable (01-interfaces
    # RegistryError variant list) even though table_solver_1d raises a
    # plain ValueError rather than routing a Result -- see sugar.py's
    # _check_strictly_ascending docstring for why.
    err = RegistryError.BadTable(reason="x not strictly ascending")
    assert err.reason == "x not strictly ascending"


# -- AD-4: import order never changes behavior ---------------------------


def test_import_order_permutation_invariant() -> None:
    def build_a():
        @solver(
            namespace="mech",
            inputs=(),
            outputs=("mech.a",),
            domain={},
            cost=1.0,
            accuracy=EXACT,
            citations=("handbook: ref A",),
            version="1",
        )
        def a(x):
            return 1.0

        return a.solver_direction

    def build_b():
        @solver(
            namespace="mech",
            inputs=(),
            outputs=("mech.b",),
            domain={},
            cost=1.0,
            accuracy=EXACT,
            citations=("handbook: ref B",),
            version="1",
        )
        def b(x):
            return 2.0

        return b.solver_direction

    order1 = SolverRegistry()
    order1.register(*build_a())
    order1.register(*build_b())

    order2 = SolverRegistry()
    order2.register(*build_b())
    order2.register(*build_a())

    assert order1.digest() == order2.digest()
    assert [i.solver_id for i, _ in order1] == [i.solver_id for i, _ in order2]


# -- sugar vs hand-built: digest equivalence ------------------------------


def test_sugar_direction_digest_equals_hand_built_twin() -> None:
    hand_domain = Domain(
        {
            "mech.section.width": Interval(1e-4, 1.0),
            "mech.section.height": Interval(1e-4, 1.0),
        },
        frozenset(),
    )

    @solver(
        namespace="mech",
        inputs=("mech.section.width", "mech.section.height"),
        outputs=("mech.section.second_moment",),
        domain=hand_domain,
        cost=1e-7,
        accuracy={"mech.section.second_moment": Accuracy(0.0, 0.0)},
        citations=(Citation(kind="handbook", ref="Gere 9e, App. E"),),
        version="1",
    )
    def rect_second_moment_raw(x):
        b, h = x["mech.section.width"], x["mech.section.height"]
        return Ok({"mech.section.second_moment": b * h**3 / 12.0})

    @solver(
        namespace="mech",
        inputs=("mech.section.width", "mech.section.height"),
        outputs=("mech.section.second_moment",),
        domain={
            "mech.section.width": (1e-4, 1.0),
            "mech.section.height": (1e-4, 1.0),
        },
        cost=1e-7,
        accuracy=EXACT,
        citations=("handbook: Gere 9e, App. E",),
        version="1",
    )
    def rect_second_moment_sugar(x):
        return x["mech.section.width"] * x["mech.section.height"] ** 3 / 12.0

    from feldspar.core import canonical_digest

    info_raw, _ = rect_second_moment_raw.solver_direction
    info_sugar, _ = rect_second_moment_sugar.solver_direction
    # Different fn.__name__ (deliberately, since solver_id embeds it) is
    # excluded from the comparison; every other field must match exactly.
    dump_raw = info_raw.model_dump(exclude={"solver_id"})
    dump_sugar = info_sugar.model_dump(exclude={"solver_id"})
    assert canonical_digest(dump_raw) == canonical_digest(dump_sugar)


# -- make_direction / Correlation / table_solver_1d / CoupledGroup -------


def test_make_direction_registers() -> None:
    info, fn = make_direction(
        solver_id="mech.section_properties.rect",
        fn=lambda x: x["mech.b"] * x["mech.h"] ** 3 / 12.0,
        namespace="mech",
        inputs=("mech.b", "mech.h"),
        outputs=("mech.section.rect.second_moment",),
        domain={"mech.b": (1e-4, 1.0), "mech.h": (1e-4, 1.0)},
        cost=1e-7,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    registry = SolverRegistry()
    assert registry.register(info, fn).is_ok


def test_correlation_registers_and_rejects_non_positive_accuracy_rel() -> None:
    with pytest.raises(ValueError):
        Correlation(
            namespace="heat",
            inputs=("fluids.reynolds",),
            output="heat.nusselt",
            domain={"fluids.reynolds": (1e3, 1e6)},
            accuracy_rel=0.0,
            citations=("paper: ref",),
            version="1",
        )

    gnielinski = Correlation(
        namespace="heat",
        inputs=("fluids.reynolds",),
        output="heat.nusselt",
        domain={"fluids.reynolds": (1e3, 1e6)},
        accuracy_rel=0.1,
        citations=("paper: Gnielinski 1976 -- +-10% band",),
        version="1",
    )

    @gnielinski.formula
    def _nu(x):
        return x["fluids.reynolds"] * 0.01

    registry = SolverRegistry()
    assert gnielinski.register(registry).is_ok


def test_table_solver_1d_registers_and_interpolates() -> None:
    info, fn = table_solver_1d(
        namespace="thermo",
        x_port="thermo.pressure",
        y_port="thermo.saturation_temperature",
        x=(1e3, 1e4, 1e5),
        y=(280.0, 320.0, 373.0),
        method="pchip",
        eps_abs=0.4,
        citations=("handbook: NIST Webbook",),
        version="1",
    )
    registry = SolverRegistry()
    assert registry.register(info, fn).is_ok
    result = fn({"thermo.pressure": 1e4})
    assert result.is_ok
    assert result.danger_ok.values["thermo.saturation_temperature"] == pytest.approx(
        320.0
    )


def test_table_solver_2d_registers_and_interpolates() -> None:
    info, fn = table_solver_2d(
        namespace="thermo",
        x_port="thermo.pressure",
        y_port="thermo.quality",
        z_port="thermo.enthalpy",
        x=(1e3, 1e5),
        y=(0.0, 1.0),
        z=[[100.0, 200.0], [150.0, 250.0]],
        method="linear",
        eps_abs=1.0,
        citations=("handbook: ref",),
        version="1",
    )
    registry = SolverRegistry()
    assert registry.register(info, fn).is_ok
    result = fn({"thermo.pressure": 1e3, "thermo.quality": 0.5})
    assert result.danger_ok.values["thermo.enthalpy"] == pytest.approx(150.0)


def test_coupled_group_registers_and_closure_not_implemented() -> None:
    group = CoupledGroup(
        group_id="heat.regen_wall_loop",
        namespace="heat",
        members=("heat.bartz_hot_side",),
        boundary_inputs=("prop.chamber_pressure",),
        boundary_outputs=("thermo.wall_temp.hot_side_max",),
        closure="damped_fixed_point",
        settings=dict(damping=0.5, tol=1e-4, max_iter=200),
        accuracy=Accuracy(0.0, 0.12),
        citations=("paper: Bartz 1957 -- +-25% band",),
        conservative_for="upper",
        cost=0.3,
        version="1",
    )
    registry = SolverRegistry()
    result = group.register(registry)
    assert result.is_ok

    _info, fn = next(iter(registry))
    with pytest.raises(NotImplementedError):
        fn({"prop.chamber_pressure": 1e6})


def test_coupled_group_forbids_exact_accuracy() -> None:
    with pytest.raises(ValueError):
        CoupledGroup(
            group_id="heat.x",
            namespace="heat",
            members=("heat.a",),
            boundary_inputs=("heat.in",),
            boundary_outputs=("heat.out",),
            closure="damped_fixed_point",
            settings={},
            accuracy=EXACT,
            citations=("paper: ref",),
            cost=0.1,
            version="1",
        )


# -- @solver coercions (F10/F11/F13/F14/F15) ------------------------------


def test_bare_float_return_with_single_output() -> None:
    @solver(
        namespace="mech",
        inputs=("mech.b", "mech.h"),
        outputs=("mech.section.second_moment",),
        domain={"mech.b": (1e-4, 1.0), "mech.h": (1e-4, 1.0)},
        cost=1e-7,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def rect(x):
        return x["mech.b"] * x["mech.h"] ** 3 / 12.0

    _info, fn = rect.solver_direction
    result = fn({"mech.b": 0.1, "mech.h": 0.2})
    assert result.is_ok
    assert result.danger_ok.values["mech.section.second_moment"] == pytest.approx(
        0.1 * 0.2**3 / 12.0
    )


def test_bare_float_return_with_two_outputs_errors() -> None:
    @solver(
        namespace="mech",
        inputs=("mech.b",),
        outputs=("mech.x", "mech.y"),
        domain={"mech.b": (1e-4, 1.0)},
        cost=1e-7,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def bad(x):
        return 1.0

    _info, fn = bad.solver_direction
    with pytest.raises(TypeError):
        fn({"mech.b": 0.5})


def test_ok_wrapped_mapping_return() -> None:
    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def f(x):
        return Ok({"mech.x": 42.0})

    _info, fn = f.solver_direction
    result = fn({})
    assert result.danger_ok.values == {"mech.x": 42.0}


def test_err_result_passes_through() -> None:
    @solver(
        namespace="mech",
        inputs=(),
        outputs=("mech.x",),
        domain={},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: ref",),
        version="1",
    )
    def f(x):
        return Err(SolveError.ToolMissing(tool="ccx", guidance="install calculix-ccx"))

    _info, fn = f.solver_direction
    result = fn({})
    assert result.is_err
    assert result.err == SolveError.ToolMissing(
        tool="ccx", guidance="install calculix-ccx"
    )


def test_solve_error_variants_are_total() -> None:
    """FINV-5 exhaustiveness: every named SolveError variant is
    constructible (executor enforcement lands in WO-04/WO-06)."""
    variants = [
        SolveError.ToolMissing(tool="ccx", guidance="install"),
        SolveError.ToolFailed(tool="ccx", log_tail="crash"),
        SolveError.Timeout(tool="ccx", seconds=30.0),
        SolveError.ParseFailed(context="frd"),
        SolveError.OutOfDomain(violation=None),
        SolveError.NonFinite(port="mech.x"),
        SolveError.MissingOutput(port="mech.y"),
        SolveError.InvalidMeasurement(reason="negative"),
        SolveError.BudgetExceeded(realized=0.2, budget=0.1),
        SolveError.NoRouteRemaining(attempts=()),
    ]
    kinds = {v.kind for v in variants}
    assert len(kinds) == len(variants)


def test_claim_senses_coercion() -> None:
    assert ClaimSenses.coerce("upper") is ClaimSenses.UPPER
    assert ClaimSenses.coerce(ClaimSenses.LOWER) is ClaimSenses.LOWER


# ---------------------------------------------------------------------------
# WO-13 (09 sec. 3): `@solver(eps_seeking=..., cost_curve=...)` wiring --
# generic, solver-family-agnostic (the FEA-specific ladder itself is
# covered by tests/unit/test_fea_ladder.py and
# tests/unit/test_fea_solver_seeking.py).
# ---------------------------------------------------------------------------


def test_eps_seeking_defaults_false_and_cost_curve_none() -> None:
    @solver(
        namespace="wo13",
        inputs=("wo13.x",),
        outputs=("wo13.y",),
        domain={"wo13.x": (0.0, 1.0)},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: fixture",),
        version="1",
    )
    def plain(x):
        return Ok({"wo13.y": x["wo13.x"]})

    info, _fn = plain.solver_direction
    assert info.eps_seeking is False
    assert info.cost_curve is None


def test_eps_seeking_solver_body_receives_eps_budget() -> None:
    from feldspar.solve._build import invoke_solve_fn
    from feldspar.solve.seeking import CostCurve

    seen_budgets = []

    @solver(
        namespace="wo13",
        inputs=("wo13.x",),
        outputs=("wo13.y",),
        domain={"wo13.x": (0.0, 1.0)},
        cost=1.0,
        accuracy=EXACT,
        citations=("handbook: fixture",),
        version="1",
        eps_seeking=True,
        cost_curve=CostCurve.scalar(1.0),
    )
    def seeking(x, eps_budget=None):
        seen_budgets.append(eps_budget)
        return Ok({"wo13.y": x["wo13.x"]})

    info, fn = seeking.solver_direction
    assert info.eps_seeking is True
    assert info.cost_curve is not None
    assert info.cost_curve.cost_for_budget(1e30) == 1.0

    result = invoke_solve_fn(fn, {"wo13.x": 0.5}, 0.01)
    assert result.is_ok
    assert seen_budgets == [0.01]

    # A raw single-argument (non-eps-seeking) SolveFn is untouched --
    # `invoke_solve_fn` never passes the extra argument to it.
    plain_calls = []

    def raw_fn(x):
        plain_calls.append(x)
        return Ok({"wo13.y": x["wo13.x"]})

    raw_result = invoke_solve_fn(raw_fn, {"wo13.x": 0.5}, 0.01)
    assert raw_result.is_ok
    assert plain_calls == [{"wo13.x": 0.5}]
