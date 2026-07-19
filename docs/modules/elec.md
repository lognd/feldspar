# feldspar.elec

Circuits/electronics solver directions (WO-17, WO-25, 07 "elec"): a
closed-form family (exact, oracle-grade), an ngspice-backed discretized
twin family (deck -> run -> parse -> eps), and the signal-integrity
family (PCB trace impedance and termination sizing).

## elec_closed_form

<!-- frob:describes python/feldspar/elec/closed_form.py::divider_loaded -->
<!-- frob:describes python/feldspar/elec/closed_form.py::rc_step -->
<!-- frob:describes python/feldspar/elec/closed_form.py::rlc_resonance -->
<!-- frob:describes python/feldspar/elec/closed_form.py::bjt_bias -->
<!-- frob:describes python/feldspar/elec/closed_form.py::nmos_bias -->
<!-- frob:describes python/feldspar/elec/closed_form.py::register -->

Pure marshalling over `feldspar._feldspar.elec_*` (the single Rust home
of each formula, `crates/feldspar-library/src/elec.rs`) -- no math is
reimplemented here (NO DUPLICATION, AD-3). `divider_loaded`, `rc_step`,
`rlc_resonance`, `bjt_bias`, `nmos_bias` are exactly the closed-form
twin of the five ngspice calibration cases (loaded divider, RC step,
RLC resonance, BJT bias, NMOS bias); each declares `accuracy=EXACT`
(A-7) since these are the oracles the ngspice tier calibrates against,
not the other way around. `register(registry)` registers all five
against `registry`.

## elec_deck

<!-- frob:describes python/feldspar/elec/deck.py::build_divider_deck -->
<!-- frob:describes python/feldspar/elec/deck.py::build_rc_step_deck -->

SPICE deck (`.cir`) generation for the ngspice discretized tier: pure
text generation, no IO/subprocess, every float routed through
`feldspar.core.format_f64` so identical inputs produce byte-identical
deck text (FINV-2). `build_divider_deck` and `build_rc_step_deck` each
build a `.control ... print ... quit .endc` deck whose stdout is plain
text (no rawfile parsing needed).

## elec_ngspice

<!-- frob:describes python/feldspar/elec/ngspice.py::NgspiceRun -->
<!-- frob:describes python/feldspar/elec/ngspice.py::find_ngspice -->
<!-- frob:describes python/feldspar/elec/ngspice.py::run_ngspice -->
<!-- frob:describes python/feldspar/elec/ngspice.py::probe_tools -->

The external ngspice binary boundary, mirroring `feldspar.fea.ccx`'s
shape exactly. `find_ngspice` locates the binary; `run_ngspice` writes
a deck to a throwaway `tempfile.TemporaryDirectory`, runs ngspice in
batch mode (`-b`), and captures stdout into memory (`NgspiceRun`)
before the tempdir is torn down ("contents, not paths"). `probe_tools`
is a best-effort `ngspice --version` scrape, advisory only, never used
for behavior decisions.

## elec_results

<!-- frob:describes python/feldspar/elec/results.py::parse_print_value -->

`parse_print_value` parses ngspice batch-mode `print` output
(`<expr> = <value>` lines, e.g. `v(out) = 4.761905e+00`) into engine
port values: the first line matching `<name> = <float>` is taken as
the result; anything else is `SolveError.ParseFailed` -- fail closed,
never a partial/silent answer (same contract as `feldspar.fea.results`).

## elec_signal_integrity

<!-- frob:describes python/feldspar/elec/signal_integrity.py::microstrip_z0 -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::stripline_z0 -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::series_termination -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::thevenin_termination_r1 -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::thevenin_termination_r2 -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::ac_shunt_sizing_r -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::ac_shunt_sizing_c -->
<!-- frob:describes python/feldspar/elec/signal_integrity.py::register -->

Signal-integrity closed-form models (WO-25: PCB trace controlled
impedance + termination sizing). `microstrip_z0`/`stripline_z0` compute
characteristic impedance (Hammerstad-Jensen / Wadell closed forms,
calibrated against published field-solver tables); `series_termination`,
`thevenin_termination_r1`/`_r2`, and `ac_shunt_sizing_r`/`_c` size
termination components from geometry/material numbers already resolved
by the caller (same "caller-resolved numbers" posture as
`mech.member_capacity`) -- no registry-resolution of a stackup/net
record. Each direction is CUT WHOLE (never approximated) if it has no
citable published numeric agreement, per the WO-24/WO-25 standing law.
`register(registry)` registers the family.

## elec_solver

<!-- frob:describes python/feldspar/elec/solver.py::ToolVersion -->
<!-- frob:describes python/feldspar/elec/solver.py::divider -->
<!-- frob:describes python/feldspar/elec/solver.py::rc_step -->
<!-- frob:describes python/feldspar/elec/solver.py::register -->

ngspice (discretized-tier) solver directions: registers
`elec.ngspice.divider` and `elec.ngspice.rc_step`, the ngspice-backed
twins of `elec.closed_form`'s `divider_loaded`/`rc_step`, proving
`feldspar.fea`'s deck -> run -> parse -> eps shape is a pattern, not an
FEA one-off. `divider` is a `.op` analysis with a fixed declared eps
ceiling (no mesh/step to refine); `rc_step` is a `.tran` analysis whose
eps comes from step-halving via `feldspar.fea.richardson.
richardson_extrapolate` (reused, not duplicated). `ToolVersion` records
the probed ngspice version; `register(registry)` registers both
directions.
