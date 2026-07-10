# WO-23: tributary load paths + resolved-frame consumption (WO-21 completion half)

Status: todo
Depends: WO-21 (the direct-stiffness `mech.struct.frame2d` tier,
landed PARTIAL -- read its Close-out first: this WO is its two named
residuals made dispatchable), WO-12 (payload ports). LITHOS side:
the `frame` payload (calcite/03) is unchanged this WO -- consume it
as-is by digest; the lithos section-search engine (its cycle-30
WO-55/56) resolves `section: free` and is NOT this repo's concern
beyond producing resolvable member sections.
Language: Rust formula/matrix homes + Python registration (the
WO-21 split).
Spec: docs/spec (07 mech.struct Phase 6; 09 sec. 4 `frame` kind);
lithos:docs/spec/calcite/03-lowering.md secs. 4-5 (Bearing/
tributary vocabulary + the utilization/deflection obligation
shapes); lithos:docs/workflow/work-orders/WO-48-calcite-lowering.md
close-out (the `frame_load_untargeted` gap this closes, recorded
from the consumer side); lithos design-log 2026-07-09-cycle-31 D173.

## Goal

Member demands become derivable when loads arrive through
`Bearing(tributary=...)` transfer records rather than direct
`on [...]` targets: the load-path analysis walks tributary
transfers to member line/point loads, feeds the landed frame2d
tier, and `civil.utilization`/`mech.deflection` claims over
RESOLVED members (fixed or search-pinned sections) discharge to
real verdicts instead of `frame_load_untargeted` deferrals.

## Deliverables

1. **Tributary resolution**: `Bearing(tributary=<width|area>)`
   transfers resolve to member-distributed loads (deterministic:
   declared tributary geometry x the source load intensity; no
   inferred tributary widths -- a member whose tributary is not
   declared stays honestly deferred with the existing reason).
   Load-path walk is cited evidence content (which transfers, which
   sources, per member).
2. **Demand extraction**: resolved member demands (moment/shear/
   axial envelopes from the frame2d solve under the resolved load
   set) exposed to the utilization check surface WO-21 landed.
3. **Design-check completion (scoped)**: the `civil.utilization`
   numeric half for the benchmark-covered member classes (flexure +
   combined axial-flexure per the memo's cited code equations;
   buckling stays a recorded residual if the calibration tier for
   it is not achievable this dispatch -- name it, never guess it).
4. **Calibration**: the remaining benchmarks-memo closed-form cases
   relevant to distributed/tributary loading; every solver result
   within the memo's stated tolerance or the case is a recorded
   failure, never absorbed.
5. **Conformance run readiness**: a fixture `frame` payload with
   tributary transfers + resolved sections discharging end-to-end
   through the pack protocol (the lithos-side five-design corpus
   run itself is lithos WO-65, not this WO -- but the fixture must
   mirror a real corpus member's shape, cite which).
6. **Docs**: spec 07 Phase 6 updates, WO-21 close-out cross-note,
   this WO's ledger.

## Acceptance criteria

- The fixture payload's utilization/deflection claims produce
  Valid/Violated (not indeterminate) with the load-path walk in
  evidence; removing the tributary declaration reverts to the
  honest deferral.
- Calibration cases green within memo tolerances; failures (if
  any) recorded with numbers.
- No invented physics, no invented tributary geometry, no code
  equations without the memo/citation trail (this repo's standing
  law).
- Repo checks green (its own make/test gates); Status flipped with
  a full close-out ledger.
