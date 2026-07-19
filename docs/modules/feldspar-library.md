# feldspar-library (rust crate)

Formula homes per engineering namespace (mech, thermo/fluids/heat,
elec, ...), each also exposed `extern "C"` (AD-3). Depends on
`feldspar-core` only; no Python. Populated across WO-07/17/20/21. Every
closed-form formula is defined once as `#[no_mangle] pub extern "C" fn`
-- this makes it BOTH the plain Rust `pub fn` other Rust code calls
(PyO3 bindings, other formulas, tests) AND the symbol visible to
`dlopen`/`nm` from outside the crate: a single definition per formula,
no separate wrapper (NO DUPLICATION, AD-3).

## library_lib

<!-- frob:describes crates/feldspar-library/src/lib.rs -->

Crate root: wires up the per-namespace formula modules (`mech`,
`fluids`, `heat`, `elec`) and re-exports their `extern "C"` symbols.
Depends on `feldspar-core` only.

## library_mech_mod

<!-- frob:describes crates/feldspar-library/src/mech/mod.rs -->

Mechanical-engineering closed-form formula home (WO-07), split by
subdomain: `sections` (cross-section properties), `statics` (beam
deflection, thick-cylinder Lame/von Mises stress), and `vibration`
(SDOF/beam natural frequency, Miles' equation). All math here uses
only `+ - * / powi sqrt`, which are IEEE-754 exempt (AD-13); no
transcendentals appear, so `libm` is not needed in this module. `pub
use` re-exports keep every `feldspar_library::mech::X` path stable
across the subdomain split.

## library_mech_sections

<!-- frob:describes crates/feldspar-library/src/mech/sections.rs -->

Cross-section geometric property formulas (area moment of inertia,
etc.), e.g. rectangular second moment of area `I = width * height^3 /
12` (Gere, *Mechanics of Materials*, 9th ed., App. E). The workspace
denies `unsafe_code`, but `#[no_mangle]` on an `extern "C" fn` requires
an explicit, function-scoped `#[allow(unsafe_code)]` (AD-3's whole
point is these symbols being link-visible via a C ABI); the allow is
scoped to each function, never the module, so it cannot silently mask
an unrelated unsafe block elsewhere in the file.

## library_mech_statics

<!-- frob:describes crates/feldspar-library/src/mech/statics.rs -->

Static structural formulas: Euler-Bernoulli cantilever beam tip
deflection `delta = F * L^3 / (3 * E * I)` (Gere; Young & Budynas,
*Roark's Formulas for Stress and Strain*, 8th ed., Table 8.1) and
thick-walled-cylinder Lame/von Mises stress. Same AD-3 `#[no_mangle]
pub extern "C" fn` discipline as the rest of `mech`.

## library_mech_vibration

<!-- frob:describes crates/feldspar-library/src/mech/vibration.rs -->

Vibration formulas: SDOF/cantilever-beam natural frequency `f = (1 /
2*pi) * sqrt(k / m)` (Rao, *Mechanical Vibrations*, ch. 2) and Miles'
equation random-vibration response. Same AD-3 `extern "C"` discipline
as the rest of `mech`.

## library_mech_frame

<!-- frob:describes crates/feldspar-library/src/mech/frame.rs -->

2D direct-stiffness frame solver (WO-21 `mech.struct`, Phase 6). Unlike
the rest of `mech` this is a variable-size matrix assemble/solve, not a
single closed-form scalar law, so it does not fit the one-formula
`extern "C"` shape (AD-3) the sibling modules use -- it is exposed as
an ordinary `pub fn` plus a PyO3 wrapper only (cut recorded in the
WO-21 close-out). Scope: a 2D planar frame element with axial +
Euler-Bernoulli bending stiffness, an optional moment release (hinge)
at either end handled by static condensation of that end's rotational
DOF, assembled into a global stiffness system and solved for
displacements/reactions/member-end forces; distributed-load member
loads are supplied by the CALLER as local fixed-end forces (standard
FEA convention).

## library_fluids_mod

<!-- frob:describes crates/feldspar-library/src/fluids/mod.rs -->

Fluid-mechanics closed-form formula home (WO-20 Phase 2), split by
regime: `incompressible` (internal flow, pipe networks, turbomachinery,
water hammer) and `compressible` (D141 isentropic relations, normal
shocks, the Fanno function). Both regimes register under the SAME
`fluids` namespace via `pub use` re-exports; Python side distinguishes
the regime via `Domain.tags` ("compressible"/"incompressible") since
the low-Mach/choked screening lives there (09 sec. 4 / lithos WO-14
regime channel).

## library_fluids_incompressible

<!-- frob:describes crates/feldspar-library/src/fluids/incompressible.rs -->

Incompressible internal-flow formulas: pipe friction factors,
Darcy-Weisbach/minor losses, pipe-network combination, pump/system
operating point, NPSH, and water hammer. Every function evaluates its
DECLARED closed-form model exactly (A-7) -- Haaland and Dittus-Boelter
are themselves approximations of reality, but this module computes
their formulas to floating-point precision, which is what
`accuracy=EXACT` certifies (same convention `mech`'s Lame equations
use: the model is textbook-approximate, the evaluation is exact).
Colebrook is the one implicit root in this file, solved by Newton
iteration to a tight, fixed tolerance (`_COLEBROOK_TOL`) -- evaluating
the SAME defining equation to floating-point precision, not a separate
approximate model.

## library_fluids_compressible

<!-- frob:describes crates/feldspar-library/src/fluids/compressible.rs -->

Compressible-flow formulas (D141): isentropic relations (e.g.
stagnation-to-static temperature ratio `T0/T = 1 + (k-1)/2 * M^2`,
Anderson *Modern Compressible Flow*, 3rd ed., ch. 3), normal shocks,
and the Fanno function. Registered under the SAME `fluids` namespace as
the incompressible regime; regime distinguished via `Domain.tags`.

## library_heat

<!-- frob:describes crates/feldspar-library/src/heat.rs -->

Heat-transfer closed-form formula home (WO-20 Phase 2, widened by
WO-142): 1-D conduction resistance networks (plane-wall conduction
`R = L / (k * A)`, cylindrical wall, convection) and Dittus-Boelter
forced convection (both heating n=0.4 and cooling n=0.3 branches).
Same `#[no_mangle] pub extern "C" fn` discipline as `mech`/`fluids`.

WO-142 growth adds: `heat_gnielinski_nusselt` (f-coupled correlation,
Gnielinski 1976, paywalled primary restated Incropera & DeWitt ch. 8);
`heat_laminar_nusselt` (Table 8.1 constants, 3.66/4.36);
`heat_churchill_chu_horizontal_cylinder_nusselt`/
`heat_churchill_chu_vertical_plate_nusselt` (Churchill & Chu 1975,
both primaries paywalled, restated Incropera & DeWitt eq. 9.34/9.26);
and the NTU-effectiveness family `heat_ntu_from_ua`/
`heat_effectiveness_parallel_flow`/`heat_effectiveness_counterflow`/
`heat_effectiveness_shell_and_tube_one_pass`/
`heat_hx_rate_from_effectiveness`/`heat_hx_outlet_temp` (Kays &
London, *Compact Heat Exchangers*, 3rd ed., 1984; restated Incropera &
DeWitt Table 11.4).

Scope note (WO-20 close-out, amended WO-142): boiling/condensation and
radiation networks remain EXPLICITLY CUT; conjugate/coupled solves
(flow-and-wall mutually dependent) are a recorded wall, not attempted
(`docs/spec/fluorite/03-lowering.md:114-124`) -- not silently dropped.

## library_elec

<!-- frob:describes crates/feldspar-library/src/elec.rs -->

Circuits/electronics closed-form formula home (WO-17, 07 "elec"). Same
AD-3 contract as `mech.rs`: every formula is a single `#[no_mangle] pub
extern "C" fn`. `rc_step_response` is the one formula in this module
with a transcendental term (`exp`), so it goes through `libm` (AD-13)
rather than `std`'s platform-dependent `f64::exp`; every other formula
here uses only `+ - * / powi sqrt`, which are IEEE-754 exempt.
`divider_loaded_vout` computes loaded resistive-divider output voltage
`Vout = Vin * Rp / (R1 + Rp)` where `Rp` is `R2` in parallel with the
load `RL` (degenerates to the unloaded divider as `RL` grows large).

## library_extern_c_smoke

<!-- frob:describes crates/feldspar-library/tests/extern_c_smoke.rs -->

Integration test binding (frob:tests, TEST003) exercising the crate's
`extern "C"` link-visible symbols end to end -- verifies the AD-3
"single definition, dlopen/nm-visible" contract actually holds for the
compiled artifact, not just at the Rust type level.
