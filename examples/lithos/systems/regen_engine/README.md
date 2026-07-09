# Regen engine -- the cross-domain torture test

A 2kN regeneratively-cooled kerolox thruster: five files chosen to
attack both toolchains at their weakest joints -- strong two-way
coupling, distributed fields, fluid circuits, empirical stability,
2-D operating domains. Findings G22-G33 continue the log
(../README.md has G1-G12; ../reaction_wheel/ has G13-G21).

## Where FELDSPAR fell flat (and the fixes)

- **G22 (FIXED, 09 sec. 4b + examples/solvers/06): strong coupling
  breaks the DAG.** The regen wall loop is two-way and distributed;
  G20's hot-corner envelope is uselessly conservative here. Fix:
  **CoupledGroup** -- members + a deterministic fixed-point closure
  registered as ONE composite solver (tier="coupled" now has
  semantics). Composite accuracy is calibrated as a unit (member eps
  do not compose linearly through a fixed point; EXACT forbidden);
  closure residual charges into measured_eps; non-convergence is
  `SolveError.NoConvergence`, reroutable. The graph stays a DAG by
  construction; uncoupled cyclic registrations remain an error.
  Scheduled M8.
- **G24 (DECIDED interim, chamber.hema): station marching is internal.**
  1-D distributed solvers (regen marching) expose EXTREMAL boundary
  ports (`thermo.wall_temp.hot_side_max`, flux at throat) with the
  reduction inside, `conservative_for`-declared. Routable
  per-station quantities need zone/station ports -- OPEN-14.
- **G26 (FIXED, 07 catalog): no `acoustics` namespace existed.**
  Added: cavity mode frequencies, Helmholtz/quarter-wave damper
  sizing, mode-separation screening. Also added the `prop` area:
  CEA-wrapper equilibrium tier, c*/Cf ideal relations, Bartz,
  regen-channel hydraulics, film cooling.
- **G28 (fixture): extreme-range properties.** CuCrZr and RP-1
  records must span 100K..800K and near-critical states; the record
  edge's domain box IS the published range, so out-of-range is
  honest indeterminate -- the design holds, the DATA obligation is
  now explicit (registry records need range citations).
- **G30 (confirms design): the performance chain is pure routing.**
  CEA (external tool tier) -> c* -> Cf -> thrust -> Isp crosses four
  namespaces with zero new mechanism.
- **G31 (FIXED, 02-edge-cases row): referenced units.** Isp seconds
  is g0-referenced (ve/g0) -- an ingest/print VIEW like regolith's
  dB rule; stored value stays m/s.

## Where LITHOS fell flat (recorded as asks, sec. 7 items 6-7)

- **G23: computed zone-valued fields.** The igniter ASSERTED wall
  temps as boundary givens; a regen engine COMPUTES them, zone-
  indexed, and sibling claims consume them (`sigma_y(T_local)` with
  T_local from the thermal solve, and the FEA needs the temperature
  FIELD payload as a load). There is no language form for
  claim-computed zone fields feeding other claims' givens -- today it
  degenerates to N worst-zone scalar claims and a hand-carried
  conservatism argument. Ask: sec. 7 item 7.
- **G25: no fluid-circuit home.** hematite describes solids; cuprite
  nets are electrical. Flow topology (manifold -> 18 elements;
  tank -> valve -> jacket -> injector) is not expressible, so
  hydraulic obligations cannot be LOWERED -- givens are hand-asserted
  and feldspar's entire fluids catalog has no source of truth to
  consume. `feed_lines.hema` is the reproduction case + strawman
  (`FluidPort` through/across pairs, `flownet` as the KCL-like
  fluids analog of `nets:`). Ask: sec. 7 item 6. THE biggest lithos
  gap this project found. UPDATE 2026-07-07: draft spec written --
  the fluorite track (`lithos:docs/spec/fluorite/`); awaiting design-cycle
  ratification (fluorite COPEN-1). RESOLVED: ratified cycle 20
  (D93) and IMPLEMENTED (lithos WO-31 front end + WO-32 lowering;
  `flownet` payloads on the D96 channel); the fluids catalog's
  source of truth exists -- feldspar's consumer side is WO-20.
- **G27 (accepted): empirical stability stays on the honesty
  ladder.** Combustion-instability rating is hot-fire-empirical
  (SP-194); the right form is `assume!`/`waive ... by test(...)`,
  not a fake solver. No change; the fixture pins the pattern.
- **G29: 2-D sweep coverage.** `forall mr x throttle` is one swept
  obligation over a 2-D domain; coverage needs grid(k x m) or
  per-axis monotonicity -- OPEN-8's gap, squared. Folded into the
  sec. 7 item 2 ask.
- **G32 (candidate lithos sugar, no feldspar impact): proof-test
  claims are operating claims under scaled givens** -- longhand
  duplication today; a claim-transform form would remove it. The
  solver graph serves both from the same registrations either way.
- **G33 (confirms design): shared event vocabulary across .hema/.cupr
  files (startup vs valve commands) already has regolith machinery
  (events are datums); the fixture pins cross-file identity.

## Net assessment

feldspar's protocol survived everything this project threw except
strong coupling (fixed by CoupledGroup) and distributed fields
(interim reductions now, OPEN-14 for the real thing). The deepest
UNSOLVED gaps are lithos-side: fluid circuits (G25) and computed
zone fields (G23) -- both are language/lowering questions feldspar
can only wait on, and both are now recorded asks with reproduction
cases.
