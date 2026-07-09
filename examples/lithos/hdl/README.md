# examples/hdl -- the D120 HDL coverage fixtures

One fixture pair per (planned) row of the cuprite/09 HDL coverage
matrix: the FOREIGN HDL source (legal in its own language; regolith
never parses it) plus the native cuprite equivalent, with the
original embedded via `by extern(ref, format)` and an equivalence
obligation binding the pair. Until these existed, the rows marked
(planned) made the superset claim a stated intent -- these files are
what make it an asserted (and falsifiable) fact.

Every `.cupr` file is parse-clean under `regolith check`
(0 diagnostics); harness deferrals are expected and captured in
`tests/golden/data/deferral_hdl.json`. The `.v`/`.sv`/`.vhd` files
are invisible to `check` (the extension registry owns what counts as
source) -- they are hash-pinned artifacts of the extern route.

## Fixture -> matrix row -> mechanism -> mapping quality

| fixture pair | matrix rows proved (09 sec.) | cuprite mechanism | embedding route | mapping quality |
|---|---|---|---|---|
| `counter.v` + `counter.cupr` | 1: module/ports; hierarchy; always_ff; always_comb; typed signals | typed-port block; `by composing` construction scope; `on clk.rise:`; derived `=` signal; width+domain typing | Verilog-2005, TRANSPARENT (`verilog2005`) | FULL -- native side strictly stronger (domains, ownership, checked widths) |
| `alu_generic.sv` + `alu_generic.cupr` | 1: parameters/generics; generate loops | generics + monomorphization (INV-11); `PatternOf` orbit + pairwise/flatten | SystemVerilog-2017, OPAQUE-with-contracts (`sv2017`) | FULL for parameters; PARTIAL in practice for generate -- see finding M3 |
| `fsm_traffic.vhd` + `fsm_traffic.cupr` | 1: FSMs (enum/case) | mode config variable (`exposing phase:`) + on-event transition claims; per-mode claims | VHDL-2008, OPAQUE-with-contracts (`vhdl2008`) | FULL for states/outputs; exhaustiveness claim overstated -- see finding M2 |
| `fifo_cdc.sv` + `fifo_cdc.cupr` | 1: SV interfaces/modports; clock/reset abstraction; CDC handling | interfaces with contract roles + promises; clock domains + membership typing; `cdc_sync` crossing ledger rows | SystemVerilog-2017, OPAQUE-with-contracts (`sv2017`) | FULL at the boundary; opaque interior rides evidence -- see finding M4 |
| `assertions_map.sv` + `assertions_map.cupr` | 2: SVA immediate; SVA concurrent (bounded vs deep); covergroups | `require:` comparison; `within d after e` claim; extern-bound `by test(...)` evidence + coverage statement | verification content: NOT an impl extern -- evidence-bound only | FULL / PARTIAL-as-designed / DIFFERENT-BY-DESIGN, exactly as the matrix states |

Notes on the two embedding verdicts: Verilog elaborates (full static
tier + LEC-dischargeable equivalence); SV/VHDL link opaque in v1 with
retro-declared contracts and simulation-comparison equivalence --
`alu_generic.cupr` and `fsm_traffic.cupr` each say so at their
`impl ... by extern` site. Veryl needs no fixture of its own: its
emitted SystemVerilog takes the `sv2017` route (09 sec. 3), and its
language-level features (clock/reset types, explicit ff/comb) are the
rows `counter`/`fifo_cdc` prove natively.

## Candidate findings (D119 ledger -- promotion is the coordinator's)

Findings about the MATRIX itself are flagged **[MATRIX]**.

1. **[MATRIX] M1: the tristate/inout row's fixture pointer is
   dangling.** 09 sec. 1 points the tristate/open-drain row at
   "(covered by net-discipline fixtures)" -- no such fixture exists
   under `examples/hdl/`, and nothing elsewhere embeds a foreign
   inout/tristate design against a native `arbitrate`. By D120 rule 4
   (a row with neither mechanism-in-evidence nor extern fixture is a
   finding by definition), this row is currently asserted on prose.
   The sdr project's T/R `arbitrate` exercises the native half only.
2. **[MATRIX] M2: the FSM row's "exhaustiveness is checkable" has no
   owning check.** No section of cuprite 03/05 defines a
   mode-exhaustiveness or transition-coverage check; fsm_traffic.cupr
   had to state exit-per-mode as ordinary within-after claims, which
   is designer vigilance -- exactly what the row claims to replace.
   Either a checker owns it (a mode-machinery ledger: every mode
   reachable, every mode exits, event set covers the transition
   relation) or the row's "stronger because" column overstates.
3. **[MATRIX] M3: orbits + patterns cannot express ripple topologies.**
   The generate row maps instance ARRAYS well, but the most common
   generate idiom is a CHAIN (ripple carry, shift stages): a
   sequential dependency between orbit instances. The settled orbit
   connection forms are exactly broadcast / pairwise / flatten (03
   sec. 4) -- none expresses instance[i].cout -> instance[i+1].cin.
   alu_generic.cupr writes an invented `chain(...)` connector to keep
   the fixture honest about what it NEEDS; until a chain/reduce form
   is settled (or the row documents the escape: write the chain as an
   explicit composing body), the generate row is PARTIAL, not FULL.
4. **[MATRIX] M4: the CDC row is proven only at the boundary for
   opaque embeds.** Natively the crossing ledger is compile-checked
   (the row's claim, true). But the fixture's foreign half is opaque
   SV: its interior gray-code synchronizers are invisible, so the
   pairing discharges on simulation evidence, and an interior CDC bug
   in embedded SV is NOT caught by the ledger. The row (or sec. 3's
   opaque-route paragraph) should say the guarantee's scope shrinks
   to the contract boundary under the opaque route.
5. **Stream-handshake promises have no vocabulary.** Mapping SV
   modports to contract roles begged one promise: "producer holds
   valid/data until ready" (fifo_cdc.cupr `no_overrun`). It parses as
   prose (opaque island); no promise-slot vocabulary row covers
   handshake disciplines, though every bus mating needs exactly this.
6. **The extern-verification evidence shape is unspecified.**
   assertions_map.cupr records the non-mapping SVA as
   `by test(sva_sim(...), coverage=swept(...))` per the matrix's
   sec. 2 prescription -- but no grammar row in regolith 07 or
   cuprite 07 defines `coverage=` inside an evidence clause, nor how
   a `by test` ref names a property WITHIN a foreign file. The
   honesty route the matrix mandates needs a settled spelling.
7. **Realization extern vs verification extern is a real distinction
   the docs never draw.** A checker module must NOT be `impl ... by
   extern` (it would claim the checker realizes the block);
   assertions_map.cupr keeps it evidence-bound instead. regolith 08
   sec. 4 taxonomizes extern by LEVEL (L3/L4/L5) but "extern at L5"
   is one line -- the matrix's own sec. 2 route deserves a named
   citizen there.
