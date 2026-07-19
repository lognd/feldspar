# feldspar.thermo

Thermo property-table solver directions (WO-20 residual): a thin wrapper
over CoolProp's `PropsSI` (`props` extra) giving `thermo.*`
density/specific-heat/viscosity lookups the property tables the 07
`thermo` catalog scopes.

Scope note (this WO's honest coverage declaration, per the pack contract
03): ONLY single-phase density/cp/viscosity lookups for the three fluids
the calibration anchors cover -- water (liquid, including the
saturated-liquid boiling-point row), dry air, and nitrogen -- over the
temperature/pressure box the anchors bracket. The rest of the 07
`thermo` catalog (ideal/real-gas directions as separate closed-form
laws, device models, cycles, combustion, psychrometrics, exergy,
two-phase/saturation-region property lookups, arbitrary CoolProp fluid
strings) is EXPLICITLY CUT and recorded in the WO-20 file, not silently
dropped.

## thermo_properties

<!-- frob:describes python/feldspar/thermo/properties.py::register -->

`register(registry)` registers every `thermo.<fluid>.<property>`
direction (density, specific heat, viscosity) for every calibrated
fluid against `registry`, declaring the generated per-fluid port table
first (WO111b: one source for the port names, ports generated per fluid
here rather than hand-enumerated). Returns the count of directions
registered.
