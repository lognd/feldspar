from __future__ import annotations

"""Thermo property-table solver directions (WO-20 residual): a thin
wrapper over CoolProp's `PropsSI` (`props` extra), giving `thermo.*`
density/specific-heat/viscosity lookups the property tables the 07
`thermo` catalog scopes and the `heat`/`fluids` directions consume as
givens (`fluids.fluid.density`, etc. are supplied by an obligation's
resolved givens today; these directions let a discharge derive them
from state instead of asserting them by hand).

Scope note (this WO's honest coverage declaration, per the pack
contract 03): ONLY single-phase density/cp/viscosity lookups for the
three fluids the calibration anchors cover -- water (liquid, including
the saturated-liquid boiling-point row), dry air, and nitrogen -- over
the temperature/pressure box the anchors bracket. The rest of the 07
`thermo` catalog (ideal/real-gas directions as separate closed-form
laws, device models, cycles, combustion, psychrometrics, exergy,
two-phase/saturation-region property lookups, arbitrary CoolProp fluid
strings) is EXPLICITLY CUT and recorded in the WO-20 file, not silently
dropped. Interpolation eps is set from the benchmarks memo sec. 3.4
tolerances (+/-0.5% density/cp, +/-2% viscosity -- the correlation-band
figure CoolProp itself carries against IAPWS-95/Lemmon reference
equations of state, not a table-interpolation error of feldspar's own
making)."""

import math
from dataclasses import dataclass

from typani import Ok

from feldspar.core import Accuracy, Domain, Interval, PortDecl
from feldspar.logging_setup import get_logger
from feldspar.solve import Citation, Err, SolveError, SolverRegistry, solver

_log = get_logger(__name__)

__all__ = ["register"]

_COOLPROP_CITATION = Citation(
    kind="paper",
    ref="Bell, I. H., Wronski, J., Quoilin, S., and Lemmon, E. W., "
    "Pure and Pseudo-pure Fluid Thermophysical Property Evaluation "
    "and the Open-Source Thermophysical Property Library CoolProp, "
    "Ind. Eng. Chem. Res., 53(6), 2014.",
)
_IAPWS_CITATION = Citation(
    kind="standard",
    ref="IAPWS-95: Release on the IAPWS Formulation 1995 for the "
    "Thermodynamic Properties of Ordinary Water Substance",
)
_LEMMON_CITATION = Citation(
    kind="paper",
    ref="Lemmon, E. W., Jacobsen, R. T, Penoncello, S. G., and "
    "Friend, D. G., Thermodynamic Properties of Air and Mixtures of "
    "Nitrogen, Argon, and Oxygen, J. Phys. Chem. Ref. Data, 29(3), 2000 "
    "(air); Span, R. et al., A Reference Equation of State for the "
    "Thermodynamic Properties of Nitrogen, J. Phys. Chem. Ref. Data, "
    "29(6), 2000 (nitrogen).",
)

#: The correlation-band tolerance the benchmarks memo sec. 3.4 pins
#: (CoolProp vs. IAPWS-95/Lemmon reference EOS at the calibrated state
#: points): tighter for density/cp, looser for viscosity.
_DENSITY_ACCURACY = Accuracy(eps_abs=0.0, eps_rel=5e-3)
_CP_ACCURACY = Accuracy(eps_abs=0.0, eps_rel=5e-3)
_VISCOSITY_ACCURACY = Accuracy(eps_abs=0.0, eps_rel=2e-2)


@dataclass(frozen=True)
class _FluidSpec:
    """One registered fluid's CoolProp name, validity box, and extra
    citations (beyond the CoolProp library paper itself) backing its
    reference EOS."""

    coolprop_name: str
    t_box: Interval
    p_box: Interval
    citations: tuple[Citation, ...]


#: Registered fluid table (single home, NO DUPLICATION): the WO's
#: calibration anchors bracket each fluid's (T, P) validity box.
_FLUIDS: dict[str, _FluidSpec] = {
    "water": _FluidSpec(
        coolprop_name="Water",
        t_box=Interval(273.16, 373.124),
        p_box=Interval(6.11e2, 2e7),
        citations=(_COOLPROP_CITATION, _IAPWS_CITATION),
    ),
    "air": _FluidSpec(
        coolprop_name="Air",
        t_box=Interval(200.0, 400.0),
        p_box=Interval(1e4, 2e7),
        citations=(_COOLPROP_CITATION, _LEMMON_CITATION),
    ),
    "nitrogen": _FluidSpec(
        coolprop_name="Nitrogen",
        t_box=Interval(200.0, 400.0),
        p_box=Interval(1e4, 2e7),
        citations=(_COOLPROP_CITATION, _LEMMON_CITATION),
    ),
}


def _lazy_propsi():
    """Presence probe + import indirection: CoolProp is an optional
    (`props`) extra (WO-20 close-out note: unused pinned dependency is
    its own smell, so this stays import-on-first-use, never a
    module-level `import CoolProp`)."""
    try:
        from CoolProp.CoolProp import PropsSI
    except ImportError as exc:  # pragma: no cover - exercised via probe_tools
        _log.warning("thermo: CoolProp not importable (%s)", exc)
        raise
    return PropsSI


def _probe_coolprop():
    try:
        _lazy_propsi()
    except ImportError:
        return Err(
            SolveError.ToolMissing(
                tool="CoolProp",
                guidance="install the 'props' extra: pip install feldspar[props]",
            )
        )
    return Ok(None)


def _make_property_direction(fluid_key: str, prop_code: str, prop_name: str, accuracy):
    """Builds one `thermo.<fluid>.<prop_name>(T, P) -> value` direction,
    closed over `fluid_key`/`prop_code` (CoolProp's `PropsSI` letter:
    `'D'` density, `'C'` specific heat at constant pressure, `'V'`
    dynamic viscosity) so the three properties x three fluids stay one
    factory, not nine hand-written bodies (NO DUPLICATION)."""
    spec = _FLUIDS[fluid_key]
    coolprop_name = spec.coolprop_name
    t_port = f"thermo.{fluid_key}.temperature"
    p_port = f"thermo.{fluid_key}.pressure"
    out_port = f"thermo.{fluid_key}.{prop_name}"

    def fn(x):
        propsi = _lazy_propsi()
        t = x[t_port]
        p = x[p_port]
        # M5 (cycle-28 audit): the rectangular T-P `Domain` box does not
        # guarantee CoolProp accepts every interior point (saturation
        # line, sub-triple-point, rejected T,P pairs) -- `PropsSI` raises
        # `ValueError` for those states and this must be an honest
        # `OutOfDomain`, never an unhandled crash (mirrors struct.py's
        # direct-stiffness `ValueError -> OutOfDomain` mapping).
        try:
            value = propsi(prop_code, "T", t, "P", p, coolprop_name)
        except ValueError as exc:
            _log.warning(
                "thermo.%s.%s: PropsSI rejected T=%s P=%s (%s)",
                fluid_key,
                prop_name,
                t,
                p,
                exc,
            )
            return Err(SolveError.OutOfDomain(violation=str(exc)))
        if not math.isfinite(value):
            _log.warning(
                "thermo.%s.%s: PropsSI returned non-finite value %s for T=%s P=%s",
                fluid_key,
                prop_name,
                value,
                t,
                p,
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        f"{coolprop_name} {prop_name} at T={t}, P={p}: "
                        f"PropsSI returned non-finite value {value!r}"
                    )
                )
            )
        _log.debug("thermo.%s.%s: T=%s P=%s -> %s", fluid_key, prop_name, t, p, value)
        return Ok({out_port: value})

    fn.__name__ = f"{fluid_key}_{prop_name}"
    decorated = solver(
        namespace="thermo",
        inputs=(t_port, p_port),
        outputs=(out_port,),
        domain=Domain(
            box={t_port: spec.t_box, p_port: spec.p_box},
            tags={"thermo", fluid_key, "single_phase"},
        ),
        cost=1e-4,
        accuracy=accuracy,
        citations=spec.citations,
        version="1",
    )(fn)
    info, wrapped_fn = decorated.solver_direction  # ty: ignore[unresolved-attribute]
    wrapped_fn.probe_tools = _probe_coolprop
    return info, wrapped_fn


#: Per-property (unit) table for this family's generated ports
#: (WO111b composition fix; the ports themselves are generated per
#: fluid in `register`, so the declarations are generated in the same
#: loop rather than hand-enumerated -- one source for the port names).
_PROPERTY_UNITS = {
    "temperature": "K",
    "pressure": "Pa",
    "density": "kg/m^3",
    "specific_heat_cp": "J/(kg*K)",
    "viscosity": "Pa*s",
}


# frob:doc docs/modules/thermo.md#thermo_properties
def register(registry: SolverRegistry) -> int:
    """Registers every `thermo.<fluid>.<property>` direction (density,
    specific heat, viscosity) for every calibrated fluid. Declares the
    generated per-fluid port table first (WO111b). Returns the count
    of directions registered."""
    decls = [
        PortDecl(f"thermo.{fluid_key}.{prop}", unit)
        for fluid_key in _FLUIDS
        for prop, unit in _PROPERTY_UNITS.items()
    ]
    _ = registry.declare_ports(*decls).danger_ok
    directions = []
    for fluid_key in _FLUIDS:
        directions.append(
            _make_property_direction(fluid_key, "D", "density", _DENSITY_ACCURACY)
        )
        directions.append(
            _make_property_direction(fluid_key, "C", "specific_heat_cp", _CP_ACCURACY)
        )
        directions.append(
            _make_property_direction(fluid_key, "V", "viscosity", _VISCOSITY_ACCURACY)
        )
    count = 0
    for info, fn in directions:
        result = registry.register(info, fn)
        _ = result.danger_ok
        count += 1
    _log.info("thermo: registered %d solver directions", count)
    return count
