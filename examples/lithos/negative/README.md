# examples/negative/

The rule-breaking corpus (design-log cycle 23 / D123). Each file breaks
EXACTLY ONE rule and declares it in a header
(`tests/golden/test_negative_corpus.py` parses and checks it):

```
# BREAKS: <one-line rule statement, citing the spec section>
# EXPECT: E0104            (code(s) the compiler MUST emit today)
# EXPECT-TODO: INV-4       (known-uncaught: driver xfails -- this IS
#                           the demand signal for a lint/check)
```

Files are named `<nn>_<rule_slug>.<ext>`, ordered obvious -> hidden.
This corpus is self-calibrating: every `EXPECT` below was verified
against real `regolith.compiler.check` output during authoring; where
the expected code did not actually fire, the header was flipped to
`EXPECT-TODO` with a "Self-calibration" note in the fixture explaining
what was actually observed. Nothing here was weakened to force a pass.

## Driver summary (last run)

`tests/golden/test_negative_corpus.py`: **40 passed (incl. the two
`.fluo` fluid-discipline fixtures E0201/E0202 from WO-31, fixture
43's E0203 from WO-32 deliverable 5, fixture 40's E0210 from WO-49,
the calcite fixtures 48-50 from WO-47, fixture 51's E0210 from
WO-52, fixtures 52-53 from WO-34 (E0307/E0308), the WO-28 rule
fixtures (35's E0601 flipped from EXPECT-TODO, 55/E0603, 56/E0604),
WO-51's three -- 57's E0442 (unbound walk-segment label, D150),
58's E0444 (cavity port unresolved), 59's E0445 (cavity chain
inexpressible, hematite/07 sec. 2a's named escalation; renumbered
from the branch's 51-53 at integration), and WO-48 slice A's three --
60's E0205 (circulation reference unreachable), 61's E0206 (egress
edge width undeclared), 62's E0207 (member cannot reach a support,
the load-leak check)), 23 xfailed (EXPECT-TODO,
incl. fixture 44 -- WO-32 deliverable 6, fixture 54's E0306, and
the three WO-36 elec-behavioral-body fixtures 45-47 below), 0
failed.** (Counts refreshed at cycle-28 integration; the driver run
is the arbiter.)

Fixtures 31 and 39 gained walk-step labels in the WO-51/D150 corpus
sweep (their `constraints:` reference segment names); their own
`EXPECT`/`EXPECT-TODO` contracts (E0702, E0441) are unchanged.

Incoming fixture waves (cycle 27 queue, updated at cycle-28
integration): WO-47's calcite negative block LANDED as fixtures
48-50 (calcite holds E0204-E0209 per the ratified spec; the WO-49
medium-mismatch check was renumbered to E0210 at integration, the
WO-36 lesson applied); WO-52 LANDED the mixer-laundering
sibling to fixture 40's medium-consistency case as fixture 51
(same E0210, a `Mixer` with no declared outlet does not exempt a
`from=`-bound mismatch); WO-34 LANDED the routed-runs block as
fixtures 52-54 (52 dangling endpoint E0307, 53 unknown bundle
E0308, both real; 54 cross-net E0306 EXPECT-TODO -- the cuprite
net-membership seam does not reach regolith-lower yet; renumbered
from the branch's 51-53 at integration); WO-50 adds drafting-rule
pass/fail fixtures (drawings quality audit, AD-27) -- see the format
note below, NOT filed under this directory; WO-54 adds the
expired-pricing-record fixture.

**WO-50 fixture-numbering note (60/61 reserved, not filed here):**
the drafting-rule pass/fail fixtures this reservation names are a
BACKEND-layer audit (`regolith.backends.drawings.audit` running over
a produced `DrawingModel`), not a `regolith.compiler.check` source
diagnostic -- the `# BREAKS`/`# EXPECT` header contract this driver
parses has no `.hema`/`.cupr`/`.fluo`/`.calx` analogue for a sheet
that does not exist until a backend runs. Fixtures 60 (deliberately
over-dimensioned: the same role dimensioned twice on one view) and 61
(deliberately under-dimensioned: a toleranced contract role drawn on
no sheet) are therefore fixture-shaped pytest cases at
`tests/backends/test_drawings.py::TestDraftingRules::
test_fixture_60_over_dimensioned_fails_dimension_completeness` and
`::test_fixture_61_under_dimensioned_fails_coverage_check`, proven
against the real `run_drafting_rules`/`contract_coverage_check`
functions the same way this corpus proves real diagnostic codes. 60/61
are reserved against a future compiler-level negative fixture only if
the WO-28 engine remainder later hosts drafting rules as first-class
`demand:`/`advise:` packs over a source-level sheet declaration; until
then this note IS the ledger entry.

## EXPECT-TODO inventory (the demand signal)

| file | rule | code/invariant | what was observed |
|---|---|---|---|
| `02_unknown_unit.hema` | unregistered unit suffix in arithmetic | E0101 | `5flerbs` combined with `5N` lowers clean; the incompatible-quantity check only fires on a KNOWN-dimension mismatch, not an unrecognized unit token |
| `06_duplicate_names.cupr` | duplicate port name in one scope | E0301 | two `out:` declarations in one `ports:` block lower clean; no duplicate-declaration check exists anywhere in the checked pipeline |
| `14_capability_vs_demand.cupr` | impl capability narrower than interface demand | E0410 | `regolith_ir::conformance::check_param_match`/capability-vs-demand logic is exercised only by `regolith-ir`'s own unit tests; `regolith-lower` never calls it |
| `18_single_driver.cupr` | two drivers, no `arbitrate` | E0301 | `regolith_sem::ownership::check_single_driver` is exported but never called from `regolith-lower`'s net-discipline checks |
| `19_supply_short.cupr` | two voltage imposers on one net | E0420 | documented in elec/03 sec. 2 but no diagnostic fires; no supply-short check found in the lowering crates |
| `20_unjoined_terminal.cupr` | declared port never joined, not `sealed` | E0301 | the net-discipline terminal ledger is not implemented |
| `21_conformance_narrower_than_promise.cupr` | impl narrower than spec promise | E0410 | same unwired-conformance finding as 14 |
| `23_asymmetric_givens_verify_one.hema` | INV-4 givens-invariance before orbit extension | INV-4 | the givens-invariance check is model/solver (feldspar) territory, not exercised by the static checked pipeline |
| `24_post_commit_mutation.hema` | INV-5 L4 post-realization verification | INV-5 | the mandatory L4 pass is realizer/pack territory (WO-22 lineage), not the static checked pipeline |
| `26_uncancelled_subtracted_dB.cupr` | uncancelled subtracted dB reference | E0104 | `10dBm - 3dB - 4dBm` lowers clean; `ILLEGAL_LOG_SUM` catches the multi-reference-sum shape but not this subtraction-cancellation shape |
| `27_overbroad_waiver.hema` | INV-12 match-set growth across builds | INV-12 | inherently a two-build diff property; a single `check` run has no prior snapshot to diff against |
| `29_uncontracted_sealed_import.hema` | INV-13 import with no equivalence contract | INV-13 | INV-13's obligation emission is driven by impl/extern bindings, not bare imports; no "sealed import" specific vocabulary found in the lowering crates |
| `33_structure_class_change.hema` | E0304 structure-class change | E0304 | code declared in the registry (`regolith-diag/src/code.rs`), zero emission sites found anywhere in `regolith-lower`/`regolith-ir`/`regolith-sem` |
| `34_index_vs_domain.hema` | E0501 positional index vs domain | E0501 | code declared in the registry, zero emission sites found |
| `36_rule_fact_unprovided.hema` | E0603 rule references unprovided fact | E0603 | the WO-28 engine's E0603 covers `forall`-scoped `<var>.<field>` references (see `55_...`); this fixture's rule has NO forall domain, and a bare unquantified identifier cannot be classified against a domain vocabulary -- still open |
| `37_rule_stale_resolver.hema` | E0604 stale `resolves:` field | E0604 | E0604 landed (WO-28 engine remainder; see `49_...`) but requires an ATTACHMENT to judge staleness against; this fixture's pack is attached by no design, so nothing can honestly fire |
| `38_singular_system.hema` | E0440 singular/rank-deficient numeric solve | E0440 | wired and unit-tested directly against `regolith_ir::solve`, but no minimal `.hema` source-level trigger reaching the solver was found within this authoring pass |
| `39_sketch_residual_inconsistent.hema` | E0441 inconsistent exactly-constrained sketch | E0441 | wired and unit-tested directly against `regolith_ir::solve::sketch`, but a profile with no owning stage never reaches the solver |
| `44_fluo_asymmetric_feed_verify_one.fluo` | INV-4 givens-invariance before flow-balance orbit extension | INV-4 | WO-32 deliverable 5/6 fluid analogue of `23_asymmetric_givens_verify_one.hema`: a symmetric four-leg manifold fed through an off-center supply run lowers `flow_imbalance([...])` clean; the givens-invariance check is model/solver (feldspar) territory, and `regolith-lower` has no orbit/symmetry machinery for flownet edges at all (fluorite has no `pattern`/`any` form), so there is no static hook to refuse extension on. |
| `45_bad_port_direction.cupr` | unrecognized port-direction word in a `digital(...)` port kind | E0301 | WO-36 types `ports:`/`spec:`/converter/`on`-event GRAMMAR only (its stated goal); no pass validates a converter/port call's argument values against a kind vocabulary -- `sideways` lowers clean |
| `46_unknown_event.cupr` | `on <clk>.<edge>:` names an undeclared clock port | E0301 | `OnBlock` is typed (WO-36) and feeds `ConverterGraph`, but nothing cross-references its clock identifier against declared `clock(...)` ports -- `nope` lowers clean |
| `47_claim_in_ports.cupr` | a claim line (`subject: predicate` / bare-comparator shorthand) inside `ports:` instead of `spec:`/`require`/`promises` | E0301 | `ports:` and `spec:` share one `field`/claim-line grammar (WO-05 residue, unchanged by WO-36); no pass rejects a claim shape by its enclosing block name |
| `55_rule_forall_field_unprovided.hema` | a rule's `forall`-scoped predicate dereferences a `Hole`/`Bend` field no layer provides | E0603 | WO-28 engine-remainder dispatch: `crates/regolith-lower/src/rules.rs::check_rule_fact_references` scans `demand:`/`advise:`/filter text for `<var>.<field>` references against `EntityKind::known_measure_keys`; narrower than `36_rule_fact_unprovided.hema`'s still-open no-`forall` shape |
| `56_rule_stale_resolver_attached.hema` | an attached `resolves:` rule whose target is never `free` at any use site | E0604 | WO-28 engine-remainder dispatch: `crates/regolith-lower/src/entities.rs` tracks per-resolver attachment + free-site accounting during the `resolves:` pass (the stale-waiver mirror); `37_...`'s unattached shape stays honestly silent |

Every `EXPECT-TODO` entry above is a candidate finding: a named
compiler gap mapped to its owning code/invariant, ready for a future
WO-40 lint or invariant-check work order. The coordinating design
cycle promotes any of these it wants tracked into
`docs/workflow/design-log/` -- this README does not edit the design log itself.

## Candidate findings (beyond the EXPECT-TODO table)

- The diagnostic-code registry (`regolith-diag/src/code.rs`) declares
  26 named codes across 6 families; this authoring pass found real,
  reproducible triggers for 17 of them through the full
  `regolith.compiler.check` facade (E0101-E0105, E0193/E0192,
  E0301-E0302, E0407, E0420, E0432-E0433, E0502-E0504, E0602, E0701-
  E0702) and confirmed the remaining 9 either unwired or requiring
  more machinery than a static-core fixture can reach (E0304, E0410,
  E0440-E0441, E0501, E0601, E0603-E0604). A full code-to-fixture
  matrix like this did not previously exist; it is now this
  directory's `EXPECT`/`EXPECT-TODO` split, discoverable by grepping
  `EXPECT:`/`EXPECT-TODO:` across the corpus.
- `E0194` (non-ASCII source byte) has no fixture here: this repo's own
  ASCII-only rule (`CLAUDE.md`) forbids authoring a file containing the
  non-ASCII byte the check exists to catch. Flagged rather than
  silently dropped; a fixture for it would need to be generated
  out-of-repo or written with an escaped/hex byte injection technique
  outside this corpus's plain-text convention.
- `regolith-lower/src/rules.rs`'s own test
  `same_rule_name_different_pack_is_not_a_collision` clarifies that
  rule-pack collision (E0602) keys on the QUALIFIED name (`pack.rule`);
  two different `process` names sharing a bare rule name is legal.
  `28_silent_shadowing.hema` was corrected during authoring after an
  initial draft (two differently-named processes) failed to reproduce
  E0602 -- left in the fixture's own header as a worked note so the
  same mistake is not repeated.

- **WO-49 escalation, cut scope: no "compatibility-record positive
  case" fixture.** The WO asks for a positive fixture exercising media
  "compatible per the media records' declared compatibility, not
  string equality (water/water_glycol is a RECORD question)". Checked
  fluorite/02 sec. 1 (the medium grammar), fluorite/04 (FOPEN-1), and
  D142 (cycle 27, the only design-log entry naming FOPEN-1): none
  define a compatibility-record FIELD or syntax -- a medium's `props:`
  binds a property registry object, nothing else. Implementing E0204
  against anything other than medium-NAME equality would mean
  inventing a record schema the spec does not specify, which the
  dispatch protocol forbids ("on spec ambiguity, STOP and escalate...
  never invent"). `E0204` ships as strict name equality (the one
  mechanism fluorite/02 sec. 1 actually states: "One medium per
  connected subnet in v1... a mismatch is a compile error"); the
  compatibility-record fixture is cut, escalated here for a future
  design-log entry to define the record shape before a WO implements
  it against real compatibility data.

## Conventions

- ASCII only, matching repo-wide policy.
- Header block is the first comment run in the file; the driver reads
  only `#`-prefixed lines up to the first non-comment, non-blank line.
- `.fluo` fixtures ride the same `EXPECT`/`EXPECT-TODO` contract as
  `.hema`/`.cupr` now that the extension is registered (WO-31,
  `crates/regolith-syntax/src/extension.rs`). Front-end-decidable
  fluid-discipline breaks carry `# EXPECT: E02xx` (the FluidNet family);
  breaks that need WO-32 lowering data (medium mixing, wall compliance)
  carry `# EXPECT-TODO: WO-32` with a self-calibration note. The driver
  never hardcodes a suffix list (the AD-14 tripwire).
