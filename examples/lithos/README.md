# examples/ -- the spec pressure corpus

Every file here is a pressure test of the language specs and (where
the toolchain can compile it) a golden-corpus input. Conventions:
comments cite the spec section a construct exercises; engineering
numbers are realistic; `.hema`/`.cupr` files are parse-clean
(INV-20: a poisoned subject is corpus rot unless deliberately
negative); claim forms the harness cannot yet lower are EXPECTED and
captured by the deferral golden (`tests/golden/`). Never hand-edit a
golden -- regenerate per the driver docstrings and diff-review.

```
examples/
  tracks/       single-file (or paired) per-track pressure tests
    hematite/   mech: pillow_block, sheet_bracket, weldment_frame,
                molded_clip, torch_igniter (flagship), gear_reducer,
                regen_chamber, suspension_link; + manifold and
                sensor_boom (feldspar fixtures, D148); +
                coolant_gallery (the D152 cavity->flow_paths
                exemplar, WO-51)
    cuprite/    elec + computer: thermostat, mux6to64,
                buck_converter, motor_drive, fpga_mcu_board,
                sampled_buck, flight_controller; + psu_enclosure
                (feldspar fixture, D148)
    xdomain/    cross-track pairs: sensor_pod, imu_board,
                servo_drive + servo_module
    fluorite/   (cycle 23 / D122, grown by WO-31 D5) seven fluid
                circuits -- check-clean since WO-31, lowered since
                WO-32
    calcite/    (cycle 27 / D139) four civil designs -- spec
                pressure tests until WO-47, then its golden corpus
  systems/      multi-file, multi-track projects (the stress corpus,
                design-log cycle 23 / D119)
    cubesat/    Kestrel: the ten-file flagship + magnetite.toml
    cnc_router/ espresso_machine/ sdr_transceiver/ -- the cycle-23
                stress trio
    small_office/ (cycle 27 / D139) the cross-track building
                flagship: .calx + .fluo + .cupr + cost profiles
    reaction_wheel/ regen_engine/ dune_buggy/ -- the feldspar
                pressure fixtures, migrated cycle 27 (D148; the
                G-nn friction logs; see ../feldspar-fixtures.md)
  hdl/          (D120) foreign-HDL fixture pairs proving
                the cuprite/09 coverage matrix: legal .v/.sv/.vhd
                sources + native cuprite equivalents + equivalence
                obligations
  registry/     component-record fixtures (stm32g0, atsamd21,
                rp2040, i2c_protocol) -- the datasheet-transcription
                format, EOPEN-12/D58
  negative/     (cycle 23 / D123) the rule-breaking corpus: each
                file breaks EXACTLY ONE rule, graded obvious ->
                hidden; `# BREAKS:`/`# EXPECT:` headers drive
                tests/golden/test_negative_corpus.py; known-uncaught
                breaks are `# EXPECT-TODO:` xfails = demand signal
```

`.fluo` files have been checked sources since WO-31/32 (registered
extension, net discipline, lowering). `.calx` files are the current
spec-pressure generation: invisible to `regolith check` until WO-47
registers the extension, exactly the arc `.fluo` followed.

Every `std.*` reference in this corpus (`import std.mech.X (...)`,
bare `material: <Name>`, `process=pcb_fab(jlc_2l)`, ...) resolves
against the real starter packages in `stdlib/` at the repo root
(D135, WO-45) -- no phantom references; `tests/magnetite/
test_stdlib.py` enumerates and checks every one. `std.civil`
references (calcite fixtures) and the `std.compute`/`std.fluorite`
language-builtin namespaces are the named exceptions (see that test
module's docstring).

THIS DIRECTORY IS THE ONE CORPUS (D148, cycle 27): the feldspar
repo's `examples/lithos/` is a verbatim MIRROR of it, refreshed by
feldspar's `make sync-examples` from a sibling checkout -- never
edited there. Fixture changes land HERE first.
Per-project READMEs carry a file map
(file | subsystem | pressure applied) and a "Candidate findings"
ledger that the coordinating design cycle promotes into
`docs/workflow/design-log/` (project authors never edit the design log).
