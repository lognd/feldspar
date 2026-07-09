# WO-17: ngspice electrical tier (M7)

Status: todo
Depends: WO-12/13 (payload + budget machinery the pipeline pattern
assumes), WO-14 (kind/coverage/regime reporting)
Language: Python (`feldspar/elec/` numeric tier), library entries in
Rust formula homes where closed-form
Spec: 09 sec. 8 (M7: the proof the pipeline pattern generalizes),
07 elec (closed forms + the (d) ngspice row; OPEN-7: INSIDE `elec`,
never a sibling pack), 05 (the pipeline stage pattern to
instantiate), 03 (external tool interfacing: find/run/parse as
values)

## Goal

The second discretized family: ngspice op/dc/ac/tran behind the
same stage pattern (deck -> run -> parse -> eps), registered under
`elec.*` claim kinds beside the closed-form entries -- proving the
05 pattern was a pattern, not an FEA one-off.

## Deliverables

- `elec` closed-form wave sufficient to compete/calibrate: DC/AC
  steady state, first/second-order transients, op-amp
  non-idealities, IPC-2221/2141 interconnect entries (07 list;
  citations + calibration per 03; coordinate claim kinds with
  regolith built-ins -- share, never duplicate).
- ngspice stages mirroring WO-08's shape: `deck.py` (pure text,
  deterministic), `ngspice.py` (find_ngspice: FELDSPAR_NGSPICE then
  PATH; batch run; ToolMissing/ToolFailed values), `results.py`
  (raw-file parser -> Result), eps via method-appropriate estimator
  (step-halving for tran; declared ceilings for op/ac) -- all
  settings digest-folded, FINV-2 fold test enumerates fields.
- Registration under the same `elec.*` kinds as closed forms
  (tier=discretized, dispatch-blind by test); regime tags
  (`linear`, `small_signal`) via WO-14's channel.
- `spice`-marked integration tests (the `fea`-mark precedent:
  written per spec, skipped valueless where the binary is absent,
  first-green in a tooled environment).

## Acceptance

- A divider/RC-step known-answer set: |ngspice - closed form| <=
  reported eps; twice-run digest equality; without ngspice
  installed everything imports and returns ToolMissing values;
  planner tier-blindness test extended to the elec namespace.
