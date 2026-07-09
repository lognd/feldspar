# Peregrine -- UHF software-defined radio transceiver

Cycle-23 stress project (D119): cuprite's computer track pushed to
the limit -- FPGA + MCU partition, multi-clock CDC, DDR-class timing
budgets, dB-native link budgets both directions, an extern Verilog
DSP core, a mode statechart, and a small mech enclosure closing the
xdomain thermal loop. Every `.cupr`/`.hema` file below is
parse-clean under `regolith check` (0 diagnostics); harness deferrals
are expected and captured by the deferral golden
(`tests/golden/data/deferral_sdr_transceiver.json`).

The deliberate NEGATIVE fixture lives in `negative/` and is EXCLUDED
from the golden corpus paths (the corpus registers this project's
clean files explicitly).

## File map

| file | content | pressure applied |
|---|---|---|
| `magnetite.toml` | project manifest | evidence hash pins for masks/derating docs |
| `contracts.cupr` | shared interface pack (RfDeck, DeckBay, DeckMate, AntennaFeed) | mixed-domain roles; dissipation promise the mech side consumes; dependency-cycle breaking |
| `sdr.cupr` | top-level system | rx/tx/cal statechart (`exposing op:` + on-event transition claims); dB link budgets BOTH directions; emissions mask; mode-qualified power budget; T/R sequencing claims |
| `clock_tree.cupr` | ClockTree + LoSynth blocks | four declared clock domains; jitter as event interval; phase-noise promises in dBc; a cdc_sync on the synth's tuning path |
| `dds_core.cupr` | DdsCore contract + `by extern` | the extern Verilog seam: native `spec:`, transparent verilog2005 embed, T3 equivalence, dBc spur promise |
| `rtl/dds_core.v` | FOREIGN artifact (Verilog-2005) | real synthesizable quadrature DDS: 32-bit accumulator, folded quarter-wave LUT; regolith never parses it |
| `dsp_core.cupr` | Ddc + Duc blocks | two-domain RTL specs; FOUR crossings per block across two mating kinds (async_fifo + cdc_sync) -- the crossing ledger under real load; `use HandRtl` pins at two sites |
| `adc_chain.cupr` | IfDigitizer + IfReconstructor | converter ports as the only continuous/discrete contact; RMS noise-floor claims per band; SNR/ENOB dB views; `by circuit` with the analog net discipline |
| `rf_frontend.cupr` | RxFrontend, TxLineup, front-end board | NF cascade as a noise budget (Friis pressure, see findings); dBc/dBm harmonic claims; the ONE deliberate `arbitrate` (T/R switch, granted_by=op) |
| `sdr_ctl.cupr` | computer + architecture + bind | `realizes` ledger over six workloads; FPGA/MCU split; hosted_on with IO-banking pressure; pin-mux contention by construction (documented assignment) |
| `firmware.cupr` | ctl_fw image + sdr_bits image | fit/stack/WCET claims; A/B partitions + remainder; boot claim spanning hw+fw; fmax margin forced thin on purpose |
| `board.cupr` | PeregrinePcb | DDR3 matched bus: `arbitrate ddr.dq bidir`; `budget ddr_timing kind=timing` allocating slack silicon-vs-routes with a locked route share; bus length-match DRC-rule pressure; two PDN noise budgets over decap orbits; sequencing mask; USB2 eye-mask claim |
| `enclosure.hema` | CaseBody + SdrUnit assembly | the xdomain chain: promised dissipation -> DeckMate effects -> enclosure rise -> local ambient -> derating -> PA junction; shield-wall isolation claim; zones |
| `negative/db_illegal.cupr` | DELIBERATE NEGATIVE | `30dBm + 27dBm` AND `30dBm + -110dBm` both die at L1 with E0104 (regolith 02 sec. 5a); excluded from corpus |

## Candidate findings (D119 ledger -- promotion is the coordinator's)

1. ~~**Negative-literal log sums escape E0104.**~~ FIXED: `log_terms`
   (`crates/regolith-syntax/src/checks.rs`) now folds a unary minus on
   a log-unit literal into the signed term list instead of bailing out
   the flatten, so `30dBm + -110dBm >= 12dBm` is E0104 same as
   `30dBm + 27dBm >= 12dBm`. Both spellings are asserted-rejected in
   `negative/db_illegal.cupr` (locked in by
   `tests/golden/test_golden_corpus.py::test_sdr_transceiver_db_illegal_fixture_is_rejected`
   and a `regolith-syntax` unit test).
2. **`budget kind=noise` closure math vs the Friis cascade.** An RF
   noise-figure budget (rf_frontend.cupr `rx_nf`) is not an interval
   SUM: F = F1 + (F2-1)/G1 + ... , evaluated linear at the worst gain
   corner. The budget grammar carries members and an allocate policy
   but no way to name a NONLINEAR closure model; if `kind=` packs
   assume additive closure (as `kind=timing`/`kind=tolerance` do),
   an NF budget silently means the wrong math. Wanted: pack-provided
   budget kinds declare their closure operator (D49 extension), so
   `kind=noise_figure` can bind Friis.
3. **No first-class `10*log10(x)` view constructor.** The RX
   sensitivity chain (-174dBm/Hz + 10*log10(B/Hz) + NF + SNR) needs
   the log view OF a dimensioned ratio (bandwidth over 1Hz) as a
   TERM. Sec. 5a legislates sums of log literals/views but gives no
   spelling for constructing a dB term from a linear quantity inside
   an expression, so `capture.sensitivity` had to stay an opaque
   handle instead of a derived quantity. The kTB derivation is the
   most standard calculation in radio -- it should be writable.
4. **`arbitrate` discipline vocabulary has no RF/analog member.** The
   listed disciplines are `bidir(granted_by=)`, `open_drain`,
   `parallel(share)` (03 sec. 2 / 07 sec. C). A T/R switch is a
   mode-granted SPDT over a shared analog path; `spdt(granted_by=op)`
   parses but is invented vocabulary, and `granted_by=` referencing a
   CONFIG DOMAIN (not a protocol direction rule) is nowhere blessed.
5. **Statechart exhaustiveness is not a check.** Mode transitions are
   written as within-after claims (sdr.cupr `require Modes`); nothing
   verifies every mode has an exit or that transition claims cover
   the event set. Contrast cuprite/09 sec. 1's FSM row, which
   advertises "exhaustiveness is checkable" -- see the hdl project's
   matrix finding; the two projects hit the same gap from both sides.
6. **Eye-mask claim subject is unspecified.** 04 sec. 6 promises
   "eye-mask claims on links"; the natural spelling
   `stays_within(eye(host), mask=usb2_hs_template1)` (board.cupr)
   invents an `eye(...)` derived entity that no vocabulary row
   defines.
7. **Jitter promises want an rms qualifier.** `timing.jitter(x): <=
   300fs rms` (clock_tree.cupr) attaches `rms` to a VALUE; regolith
   02 defines `rms()` only as a claim form over bands. Promise-slot
   statistics (rms vs pk-pk jitter) have no settled spelling.
