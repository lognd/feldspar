from __future__ import annotations

"""Vibration-tier closed-form + payload-consuming solver directions
(WO-16, 07 vibration Phase 3; M6, 09 secs. 4/8): the closed-form
fundamental-frequency competitors ccx's modal direction
(`feldspar.fea.modal`) escalates from, Miles' equation over a spectrum
payload (random-vibe GRMS), and a mask-containment check over a
profile payload (the `stays_within` claim form's edge, 02
"Claim-form reductions").

Payload content schemas (own home here, JSON, no external dependency):

- `spectrum` (kind "spectrum"): `{"freq_hz": [...], "asd_g2_per_hz":
  [...]}`, both lists the same length, `freq_hz` strictly ascending.
- `profile`/`mask` (kind "profile"/"mask"): `{"t": [...], "y": [...]}`
  -- a mask's `y` is read as an upper-bound envelope. Containment
  requires the two payloads' `t` grids to match EXACTLY (same length,
  same values); a mismatch is a domain-misalignment error, never an
  implicit resample (02 "honest errors, never clipping").

Miles' GRMS and the closed-form frequency directions call through
`feldspar._feldspar.mech_*` (NO DUPLICATION, mirrors `library/mech.py`);
the mask-containment comparison and payload JSON parsing are ordinary
Python since they are not physics formulas."""

import json
from typing import Sequence

from typani import Err, Ok

from feldspar import _feldspar
from feldspar.core import Accuracy, Domain, Interval, PortDecl, Rank
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    EXACT,
    Citation,
    SolveOutput,
    SolverRegistry,
    make_direction,
    solver,
)
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadResolver

_log = get_logger(__name__)

__all__ = [
    "FIRST_MODE_PORT",
    "GRMS_PORT",
    "SPECTRUM_PORT",
    "PROFILE_PORT",
    "MASK_PORT",
    "MASK_CONTAINMENT_PORT",
    "register",
]

#: The vibration tier's fundamental-frequency port (Hz): both this
#: module's closed-form beam direction and `feldspar.fea.modal`'s ccx
#: direction target it (04 planner tier-blind selection).
FIRST_MODE_PORT = "mech.vibe.first_mode_freq"

GRMS_PORT = "mech.vibe.grms"
SPECTRUM_PORT = "mech.vibe.spectrum"
PROFILE_PORT = "mech.vibe.profile"
MASK_PORT = "mech.vibe.mask"
MASK_CONTAINMENT_PORT = "mech.vibe.mask_containment"

_BEAM_CITATION = Citation(
    kind="handbook",
    ref="Blevins, Formulas for Natural Frequency and Mode Shape, "
    "Table 8-1 (cantilever beam, case 1)",
)
_SDOF_CITATION = Citation(
    kind="handbook",
    ref="Rao, Mechanical Vibrations, latest ed., ch. 2 (SDOF free "
    "vibration, undamped natural frequency)",
)
_MILES_CITATION = Citation(
    kind="handbook",
    ref="Steinberg, Vibration Analysis for Electronic Equipment, 3rd "
    "ed., ch. 2 (Miles' equation, random vibration)",
)
_MASK_CITATION = Citation(
    kind="handbook",
    ref="Steinberg, Vibration Analysis for Electronic Equipment, 3rd "
    "ed., ch. 10 (specification envelope / mask containment)",
)


# ---------------------------------------------------------------------------
# mech.vibe.first_mode_freq -- closed-form beam-table direction (07
# vibration Phase 3's "cheap competitor"): the ccx modal tier
# (feldspar.fea.modal) escalates to when this direction's domain does
# not admit the caller's box, or when the caller demands finer margin.
# ---------------------------------------------------------------------------


@solver(
    namespace="mech",
    inputs=(
        "mech.geom.cantilever.length",
        "mech.section.second_moment",
        "mech.material.youngs_modulus",
        "mech.material.density",
        "mech.section.area",
    ),
    outputs=(FIRST_MODE_PORT,),
    domain=Domain(
        box={
            "mech.geom.cantilever.length": Interval(1e-3, 10.0),
            "mech.section.second_moment": Interval(1e-12, 1.0),
            "mech.material.youngs_modulus": Interval(1e6, 1e13),
            "mech.material.density": Interval(1.0, 3e4),
            "mech.section.area": Interval(1e-8, 10.0),
        },
        tags={"linear_elastic"},
    ),
    cost=1e-7,
    accuracy={FIRST_MODE_PORT: Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(_BEAM_CITATION,),
    version="1",
)
def beam_cantilever_first_mode(x):
    length = x["mech.geom.cantilever.length"]
    second_moment = x["mech.section.second_moment"]
    youngs_modulus = x["mech.material.youngs_modulus"]
    density = x["mech.material.density"]
    area = x["mech.section.area"]
    freq = _feldspar.mech_beam_cantilever_first_mode(
        youngs_modulus, second_moment, density, area, length
    )
    return Ok({FIRST_MODE_PORT: freq})


# ---------------------------------------------------------------------------
# mech.vibe.first_mode_freq -- SDOF closed-form competitor (a lumped-
# mass/spring idealization, distinct domain from the beam direction:
# no beam geometry, just k/m -- both directions targeting the same
# port is the ordinary multi-direction planner shape, 04).
# ---------------------------------------------------------------------------


@solver(
    namespace="mech",
    inputs=("mech.vibe.stiffness", "mech.vibe.mass"),
    outputs=(FIRST_MODE_PORT,),
    domain=Domain(
        box={
            "mech.vibe.stiffness": Interval(1e-3, 1e12),
            "mech.vibe.mass": Interval(1e-6, 1e6),
        },
        tags=set(),
    ),
    cost=1e-7,
    accuracy={FIRST_MODE_PORT: Accuracy(eps_abs=0.0, eps_rel=0.0)},
    citations=(_SDOF_CITATION,),
    version="1",
)
def sdof_first_mode(x):
    stiffness = x["mech.vibe.stiffness"]
    mass = x["mech.vibe.mass"]
    freq = _feldspar.mech_sdof_first_mode(stiffness, mass)
    return Ok({FIRST_MODE_PORT: freq})


# ---------------------------------------------------------------------------
# Payload schema helpers (own home: no external schema library, just
# JSON in/out through the resolver, per 09 sec. 4's "feldspar never
# does store IO itself" -- parsing content it already resolved is not
# store IO).
# ---------------------------------------------------------------------------


def _lookup_asd(freq_hz: Sequence[float], asd: Sequence[float], fn_hz: float):
    """Linear interpolation of `asd` at `fn_hz` over the ascending
    `freq_hz` grid; `Err(SolveError.OutOfDomain(...))` if `fn_hz` falls
    outside `[freq_hz[0], freq_hz[-1]]` (02-edge-cases: "band outside
    spectrum domain" -- honest error, never extrapolated/clipped)."""
    if not freq_hz or fn_hz < freq_hz[0] or fn_hz > freq_hz[-1]:
        _log.info(
            "miles_grms: fn_hz=%s outside spectrum domain [%s, %s]",
            fn_hz,
            freq_hz[0] if freq_hz else None,
            freq_hz[-1] if freq_hz else None,
        )
        return Err(
            SolveError.OutOfDomain(
                violation=(
                    f"first_mode_freq {fn_hz} Hz is outside the supplied "
                    f"spectrum's domain [{freq_hz[0] if freq_hz else 'nan'}, "
                    f"{freq_hz[-1] if freq_hz else 'nan'}] Hz"
                )
            )
        )
    for i in range(len(freq_hz) - 1):
        lo_f, hi_f = freq_hz[i], freq_hz[i + 1]
        if lo_f <= fn_hz <= hi_f:
            if hi_f == lo_f:
                return Ok(asd[i])
            t = (fn_hz - lo_f) / (hi_f - lo_f)
            return Ok(asd[i] + t * (asd[i + 1] - asd[i]))
    return Ok(asd[-1])  # fn_hz == freq_hz[-1] exactly


def _make_miles_grms_direction(resolver: PayloadResolver):
    """`mech.vibe.grms` via Miles' equation (WO-16, 09 sec. 4): resolves
    the spectrum payload, looks up the ASD at the caller's
    `first_mode_freq`, and evaluates Miles' closed form. Corner-swept
    like any scalar direction -- the payload is exact-by-reference and
    merges into every corner unchanged; only `first_mode_freq`/`q` vary
    across the sweep."""

    def grms_fn(x):
        spectrum_result = resolver.resolve(x[SPECTRUM_PORT])
        if spectrum_result.is_err:
            _log.warning(
                "miles_grms: spectrum payload unresolvable: %r", spectrum_result.err
            )
            return spectrum_result
        spectrum = json.loads(spectrum_result.danger_ok)
        freq_hz = spectrum["freq_hz"]
        asd = spectrum["asd_g2_per_hz"]
        looked_up = _lookup_asd(freq_hz, asd, x[FIRST_MODE_PORT])
        if looked_up.is_err:
            return looked_up
        grms = _feldspar.mech_miles_grms(
            x[FIRST_MODE_PORT], x["mech.vibe.q"], looked_up.danger_ok
        )
        return Ok(SolveOutput(values={GRMS_PORT: grms}))

    info, fn = make_direction(
        solver_id="mech.vibe.miles_grms",
        namespace="mech.vibe",
        inputs=(FIRST_MODE_PORT, "mech.vibe.q", SPECTRUM_PORT),
        outputs=(GRMS_PORT,),
        domain=Domain(
            box={
                FIRST_MODE_PORT: Interval(1e-3, 1e5),
                "mech.vibe.q": Interval(1.0, 200.0),
            },
            tags=set(),
        ),
        cost=1e-6,
        accuracy=EXACT,
        citations=(_MILES_CITATION,),
        version="1",
        tier="closed_form",
        fn=grms_fn,
    )
    return info, fn


def _grids_match(a: Sequence[float], b: Sequence[float]) -> bool:
    return len(a) == len(b) and all(x == y for x, y in zip(a, b, strict=True))


def _make_mask_containment_direction(resolver: PayloadResolver):
    """`mech.vibe.mask_containment` (the `stays_within` claim form's
    edge, 02): resolves both payloads, requires their `t` grids to
    match EXACTLY (a mismatch is `SolveError.OutOfDomain`, never an
    implicit resample), and reports 1.0 iff `profile.y[i] <=
    mask.y[i]` for every sample, else 0.0."""

    def containment_fn(x):
        profile_result = resolver.resolve(x[PROFILE_PORT])
        if profile_result.is_err:
            return profile_result
        mask_result = resolver.resolve(x[MASK_PORT])
        if mask_result.is_err:
            return mask_result
        profile = json.loads(profile_result.danger_ok)
        mask = json.loads(mask_result.danger_ok)
        if not _grids_match(profile["t"], mask["t"]):
            _log.info(
                "mask_containment: domain misalignment, profile has %d samples, "
                "mask has %d",
                len(profile["t"]),
                len(mask["t"]),
            )
            return Err(
                SolveError.OutOfDomain(
                    violation=(
                        "profile/mask domain misalignment: sample grids differ "
                        f"({len(profile['t'])} vs {len(mask['t'])} points or "
                        "differing t values)"
                    )
                )
            )
        contained = all(p <= m for p, m in zip(profile["y"], mask["y"], strict=True))
        return Ok(
            SolveOutput(values={MASK_CONTAINMENT_PORT: 1.0 if contained else 0.0})
        )

    info, fn = make_direction(
        solver_id="mech.vibe.mask_containment",
        namespace="mech.vibe",
        inputs=(PROFILE_PORT, MASK_PORT),
        outputs=(MASK_CONTAINMENT_PORT,),
        domain=Domain({}, set()),
        cost=1e-5,
        accuracy=EXACT,
        citations=(_MASK_CITATION,),
        version="1",
        tier="closed_form",
        fn=containment_fn,
    )
    return info, fn


def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Declares this module's port table (payload ports need declared
    kinds, F12) and registers every vibration-tier direction. Any
    catalog also using `feldspar.fea.modal` must register THIS module
    first (its ccx direction shares `FIRST_MODE_PORT`/
    `mech.material.density`, declared here)."""
    # F12 (registry.py "accumulated-table rule", also noted in
    # `fea/payload_steps.py`'s docstring): declaring ANY port here means
    # every subsequent registration in the SAME registry is checked
    # against the table, INCLUDING the beam direction's non-vibe-owned
    # inputs (`mech.geom.cantilever.length`, `mech.section.
    # second_moment`, `mech.material.youngs_modulus` -- shared with
    # `library/mech.py`, which never declares its own table). This
    # module deliberately does NOT declare those three here: a real
    # catalog combining this module with `fea/payload_steps.py` (which
    # DOES declare `mech.material.youngs_modulus`) would hit
    # `RegistryError.DuplicatePortDecl` on an identical re-declaration
    # (registry.py's declare_ports treats an exact repeat as an error,
    # not a no-op) -- the same unresolved cross-module port-table
    # composition tension `payload_steps.py` already documents. Callers
    # combining this module with another that owns those three ports
    # must declare them exactly once, in whichever module runs first
    # (this module's own unit tests do so locally).
    ports_result = registry.declare_ports(
        PortDecl(FIRST_MODE_PORT, "Hz"),
        PortDecl("mech.vibe.stiffness", "N/m"),
        PortDecl("mech.vibe.mass", "kg"),
        PortDecl("mech.material.density", "kg/m^3"),
        PortDecl("mech.section.area", "m^2"),
        PortDecl(GRMS_PORT, "1"),
        PortDecl("mech.vibe.q", "1"),
        PortDecl(SPECTRUM_PORT, "", Rank.payload("spectrum")),
        PortDecl(PROFILE_PORT, "", Rank.payload("profile")),
        PortDecl(MASK_PORT, "", Rank.payload("mask")),
        PortDecl(MASK_CONTAINMENT_PORT, "1"),
    )
    _ = ports_result.danger_ok
    result_a = registry.register(*beam_cantilever_first_mode.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_a.danger_ok
    result_b = registry.register(*sdof_first_mode.solver_direction)  # ty: ignore[unresolved-attribute]
    _ = result_b.danger_ok
    for info, fn in (
        _make_miles_grms_direction(resolver),
        _make_mask_containment_direction(resolver),
    ):
        result = registry.register(info, fn)
        _ = result.danger_ok
    _log.info("library.vibe: registered 4 solver directions")
