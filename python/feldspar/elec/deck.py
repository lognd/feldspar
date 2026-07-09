from __future__ import annotations

"""SPICE deck (.cir) generation for the ngspice discretized tier (WO-17).

PURE text generation: no IO, no ngspice import, no subprocess. Every
float written into the deck goes through `feldspar.core.format_f64` so
two calls with identical inputs produce byte-identical deck text (the
digest-fold contract, FINV-2) -- no float-repr nondeterminism.

Both decks use a `.control ... print ... quit .endc` block (rather than
`-r out.raw`) so the result value comes back as plain text on stdout,
matching the ngspice invocation shape documented in
`lithos:docs/workflow/research/2026-07-08-benchmarks-and-datasets.md`
sec. 4 ("`.control ... write out.raw ... .endc` inside the deck is the
alternative" to `-r`); `print` is the simplest of the two to parse
reliably across ngspice versions (no rawfile binary/ASCII format
variance to handle)."""

from feldspar.core import format_f64

__all__ = ["build_divider_deck", "build_rc_step_deck"]


def build_divider_deck(vin: float, r1: float, r2: float, rl: float) -> str:
    """Loaded resistive divider deck (benchmark memo sec. 4.3): a DC
    source `vin` through `r1` into node `out`, `r2` from `out` to
    ground, load `rl` from `out` to ground in parallel with `r2`. A
    single `.op` analysis, `print v(out)` reports the operating-point
    voltage."""
    return (
        "loaded resistive divider (feldspar WO-17)\n"
        f"vin in 0 DC {format_f64(vin)}\n"
        f"r1 in out {format_f64(r1)}\n"
        f"r2 out 0 {format_f64(r2)}\n"
        f"rl out 0 {format_f64(rl)}\n"
        ".control\n"
        "op\n"
        "print v(out)\n"
        "quit\n"
        ".endc\n"
        ".end\n"
    )


def build_rc_step_deck(vf: float, r: float, c: float, t: float, timestep: float) -> str:
    """Series RC step-response deck (benchmark memo sec. 4.1): a
    piecewise-linear step source `vf` at t=0 through `r` into node
    `out`, `c` from `out` to ground. A `.tran` analysis at the given
    `timestep` out to `t`, `print v(out)` at the final timepoint
    reports `v_C(t)`.

    `timestep` is a caller-supplied parameter (not fixed) so
    `solver.py` can run the same deck shape at two step sizes for the
    step-halving eps estimate the WO-17 deliverable calls for."""
    stop_time = t
    # PWL step: 0V until a tiny rise-time epsilon, then vf held --
    # ngspice needs a nonzero rise time for a clean transient step.
    rise_time = min(timestep / 10.0, t / 10.0) if t > 0.0 else timestep / 10.0
    return (
        "series RC step response (feldspar WO-17)\n"
        f"vin in 0 PWL(0 0 {format_f64(rise_time)} {format_f64(vf)} "
        f"{format_f64(stop_time)} {format_f64(vf)})\n"
        f"r1 in out {format_f64(r)}\n"
        f"c1 out 0 {format_f64(c)}\n"
        ".control\n"
        f"tran {format_f64(timestep)} {format_f64(stop_time)}\n"
        f"print v(out)\n"
        "quit\n"
        ".endc\n"
        ".end\n"
    )
