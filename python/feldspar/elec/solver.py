from __future__ import annotations

"""ngspice (discretized-tier) solver directions (WO-17): registers
`elec.ngspice.divider` and `elec.ngspice.rc_step`, the ngspice-backed
twins of `library/elec.py`'s closed-form `divider_loaded` and
`rc_step` directions -- the SECOND discretized family (09 sec. 8 M7),
proving `feldspar.fea`'s deck -> run -> parse -> eps shape (05) was a
pattern, not an FEA one-off.

`divider` is a `.op` analysis: ngspice's DC operating-point solve has
no mesh/step parameter to refine, so its eps is a fixed DECLARED
ceiling (WO-17 deliverable: "eps via method-appropriate estimator ...
declared ceilings for op/ac"), not a measured quantity.

`rc_step` is a `.tran` analysis: its eps comes from STEP-HALVING (WO-17
deliverable) -- running the same deck at `dt` and `dt/2` and comparing,
reusing `feldspar.fea.richardson.richardson_extrapolate` (the same
generic two-point extrapolation `fea.solver` uses for mesh pairs; the
underlying math -- extrapolate a coarse/fine pair, inflate by a safety
factor, fall back to the raw delta on an implausible pair -- has
nothing FEA-specific about it, so this is reuse, not duplication, of
that one home).

Mirrors `python/feldspar/fea/solver.py`'s `register()` pattern exactly:
`SolverInfo`/`SolveFn` pairs are built at import time via `@solver`,
and `register(registry)` just calls `registry.register(*fn.
solver_direction)` for each, checks `.danger_ok`, and logs a count
(AD-4: no global registry access outside `register()`)."""

from pydantic import BaseModel, ConfigDict
from typani import Err, Ok

from feldspar.__about__ import __version__
from feldspar.core import Accuracy, Domain, Interval
from feldspar.elec import deck, ngspice, results
from feldspar.fea.richardson import richardson_extrapolate
from feldspar.logging_setup import get_logger
from feldspar.solve import Citation, SolveOutput, SolverRegistry, solver
from feldspar.solve.digest import canonical_digest

_log = get_logger(__name__)

__all__ = ["ToolVersion", "register"]


# frob:doc docs/modules/elec.md#elec_solver
class ToolVersion(BaseModel):
    """Best-effort ngspice version string folded into the
    settings_digest -- same fixed-at-registration-time limitation
    `fea.solver.ToolVersions` documents (no cheap version query that
    doesn't pay a real process spawn at registration time, before any
    solve has been requested)."""

    model_config = ConfigDict(frozen=True)

    ngspice_version: str
    feldspar_version: str


_NOMINAL_TOOL_VERSION = ToolVersion(
    ngspice_version="unknown", feldspar_version=__version__
)

_DEFAULT_TIMEOUT_S = 30.0

_NGSPICE_CITATION = Citation(
    kind="standard",
    ref="ngspice manual (BSD-3-Clause), batch mode / .op / .tran analyses, "
    "https://ngspice.sourceforge.io/docs.html",
)

# ---------------------------------------------------------------------------
# elec.ngspice.divider -- .op, declared ceiling eps.
# ---------------------------------------------------------------------------

# Declared ceiling: ngspice's DC operating-point solve is a direct
# linear solve for this resistive network (no discretization step to
# refine), so a fixed, loose relative ceiling stands in for a measured
# eps -- chosen loose enough not to overclaim precision beyond what a
# double-precision direct solve of a well-conditioned resistive network
# actually promises.
_DIVIDER_DECLARED_EPS = 1e-6

_DIVIDER_ANALYSIS = "op"


def _fold_divider_settings_digest(analysis: str, tool_version: ToolVersion) -> str:
    """The ONE settings_digest fold for `elec.ngspice.divider` (FINV-2):
    the analysis kind + nominal tool version. A private module function
    (mirroring `fea.solver._fold_settings_digest`) so the FINV-2 fold
    test can exercise it directly per field, without re-deriving the
    fold logic."""
    return canonical_digest({"analysis": analysis, "tool_version": tool_version})


_DIVIDER_SETTINGS_DIGEST = _fold_divider_settings_digest(
    _DIVIDER_ANALYSIS, _NOMINAL_TOOL_VERSION
)

_DIVIDER_ACCURACY = {
    "elec.divider.vout": Accuracy(eps_abs=1e-6, eps_rel=1e-6),
}


def _probe_ngspice_tools():
    """Combined tool-presence probe attached to each registered
    `SolveFn` as `.probe_tools` (`cache.py`'s `_tools_still_consistent`
    convention, `getattr(fn, "probe_tools", None)`)."""
    return ngspice.probe_tools()


# frob:doc docs/modules/elec.md#elec_solver
@solver(
    namespace="elec.ngspice",
    inputs=(
        "elec.source.vin",
        "elec.divider.r1",
        "elec.divider.r2",
        "elec.divider.rl",
    ),
    outputs=("elec.divider.vout",),
    domain=Domain(
        box={
            "elec.source.vin": Interval(1e-3, 1e4),
            "elec.divider.r1": Interval(1.0, 1e9),
            "elec.divider.r2": Interval(1.0, 1e9),
            "elec.divider.rl": Interval(1.0, 1e12),
        },
        tags={"linear", "small_signal"},
    ),
    cost=5.0,
    accuracy=_DIVIDER_ACCURACY,
    citations=(_NGSPICE_CITATION,),
    version="1",
    tier="discretized",
    settings=_DIVIDER_SETTINGS_DIGEST,
    deterministic=True,
)
# frob:waive TEST005 reason="measured 55.0% branch cov on 2026-07-18; the ngspice-backed discretized twin of elec/closed_form.py::divider_loaded -- requires the ngspice binary (T-0014's documented external-tool floor, not installed in this sandbox). Backfill T-0014."
def divider(x):
    vin = x["elec.source.vin"]
    r1 = x["elec.divider.r1"]
    r2 = x["elec.divider.r2"]
    rl = x["elec.divider.rl"]

    cir = deck.build_divider_deck(vin, r1, r2, rl)
    run_result = ngspice.run_ngspice(cir, _DEFAULT_TIMEOUT_S)
    if run_result.is_err:
        _log.warning("elec.ngspice.divider: ngspice run failed: %r", run_result.err)
        return Err(run_result.danger_err)
    run = run_result.danger_ok
    _log.info("elec.ngspice.divider: ngspice run completed in %.3fs", run.elapsed_s)

    parsed = results.parse_print_value(run.log_text, "v(out)")
    if parsed.is_err:
        _log.warning("elec.ngspice.divider: result parse failed: %r", parsed.err)
        return Err(parsed.danger_err)
    vout = parsed.danger_ok
    _log.info("elec.ngspice.divider: v(out)=%s", vout)
    return Ok(
        SolveOutput(
            values={"elec.divider.vout": vout},
            measured_eps=_DIVIDER_DECLARED_EPS,
        )
    )


# ---------------------------------------------------------------------------
# elec.ngspice.rc_step -- .tran, step-halved measured eps.
# ---------------------------------------------------------------------------

# Coarse/fine timestep pair (step-halving, not mesh-halving -- the
# `.tran` twin of `fea.solver`'s (h, h/2) mesh pair): the coarse step is
# 1/200th of the requested time point (or a fixed floor for t=0), the
# fine step half that.
_RC_STEP_COARSE_DIVISOR = 200.0

_RC_STEP_ANALYSIS = "tran"


def _fold_rc_step_settings_digest(
    analysis: str, coarse_divisor: float, tool_version: ToolVersion
) -> str:
    """The ONE settings_digest fold for `elec.ngspice.rc_step` (FINV-2):
    the analysis kind + the step-halving policy (`coarse_divisor` --
    changing it changes which two timesteps get run) + nominal tool
    version. Mirrors `_fold_divider_settings_digest`'s shape, one fold
    per direction (no duplication of the fold CALL, only of its
    trivial `canonical_digest({...})` shell)."""
    return canonical_digest(
        {
            "analysis": analysis,
            "coarse_divisor": coarse_divisor,
            "tool_version": tool_version,
        }
    )


_RC_STEP_SETTINGS_DIGEST = _fold_rc_step_settings_digest(
    _RC_STEP_ANALYSIS, _RC_STEP_COARSE_DIVISOR, _NOMINAL_TOOL_VERSION
)

_RC_STEP_ACCURACY = {
    "elec.rc.vc": Accuracy(eps_abs=1e-4, eps_rel=1e-2),
}


# frob:doc docs/modules/elec.md#elec_solver
@solver(
    namespace="elec.ngspice",
    inputs=(
        "elec.rc.vf",
        "elec.rc.resistance",
        "elec.rc.capacitance",
        "elec.rc.time",
    ),
    outputs=("elec.rc.vc",),
    domain=Domain(
        box={
            "elec.rc.vf": Interval(1e-3, 1e4),
            "elec.rc.resistance": Interval(1e-3, 1e12),
            "elec.rc.capacitance": Interval(1e-15, 1.0),
            "elec.rc.time": Interval(1e-9, 1e6),
        },
        tags={"linear", "small_signal"},
    ),
    cost=5.0,
    accuracy=_RC_STEP_ACCURACY,
    citations=(_NGSPICE_CITATION,),
    version="1",
    tier="discretized",
    settings=_RC_STEP_SETTINGS_DIGEST,
    deterministic=True,
)
# frob:waive TEST005 reason="measured 6.7% branch cov on 2026-07-18; the ngspice-backed discretized twin of elec/closed_form.py::rc_step -- requires the ngspice binary (T-0014's documented external-tool floor, not installed in this sandbox). Backfill T-0014."
def rc_step(x):
    vf = x["elec.rc.vf"]
    r = x["elec.rc.resistance"]
    c = x["elec.rc.capacitance"]
    t = x["elec.rc.time"]

    coarse_dt = t / _RC_STEP_COARSE_DIVISOR
    fine_dt = coarse_dt / 2.0

    def _run_at(timestep: float):
        cir = deck.build_rc_step_deck(vf, r, c, t, timestep)
        run_result = ngspice.run_ngspice(cir, _DEFAULT_TIMEOUT_S)
        if run_result.is_err:
            _log.warning(
                "elec.ngspice.rc_step: ngspice run failed at dt=%s: %r",
                timestep,
                run_result.err,
            )
            return Err(run_result.danger_err)
        run = run_result.danger_ok
        _log.info(
            "elec.ngspice.rc_step: ngspice run completed at dt=%s in %.3fs",
            timestep,
            run.elapsed_s,
        )
        parsed = results.parse_print_value(run.log_text, "vc")
        if parsed.is_err:
            _log.warning(
                "elec.ngspice.rc_step: result parse failed at dt=%s: %r",
                timestep,
                parsed.err,
            )
            return Err(parsed.danger_err)
        return Ok(parsed.danger_ok)

    coarse_result = _run_at(coarse_dt)
    if coarse_result.is_err:
        return Err(coarse_result.danger_err)
    fine_result = _run_at(fine_dt)
    if fine_result.is_err:
        return Err(fine_result.danger_err)

    richardson = richardson_extrapolate(coarse_result.danger_ok, fine_result.danger_ok)
    _log.info(
        "elec.ngspice.rc_step: step-halved extrapolated=%s eps=%s fallback_used=%s",
        richardson.extrapolated,
        richardson.eps,
        richardson.fallback_used,
    )
    return Ok(
        SolveOutput(
            values={"elec.rc.vc": richardson.extrapolated},
            measured_eps=richardson.eps,
        )
    )


divider.solver_direction[1].probe_tools = _probe_ngspice_tools  # ty: ignore[unresolved-attribute]
rc_step.solver_direction[1].probe_tools = _probe_ngspice_tools  # ty: ignore[unresolved-attribute]


# frob:doc docs/modules/elec.md#elec_solver
def register(registry: SolverRegistry) -> None:
    """Registers both ngspice (discretized-tier) directions (WO-17)."""
    result_a = registry.register(*divider.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*rc_step.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    _log.info("elec.ngspice: registered %d solver directions", 2)
