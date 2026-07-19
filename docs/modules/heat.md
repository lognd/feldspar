# feldspar.heat

Heat-transfer solver directions: a steady-state closed-form tier
(resistance networks, forced convection) and a lumped-capacitance
transient tier built on top of it.

## heat_closed_form

<!-- frob:describes python/feldspar/heat/closed_form.py::plane_wall_resistance -->
<!-- frob:describes python/feldspar/heat/closed_form.py::cylindrical_wall_resistance -->
<!-- frob:describes python/feldspar/heat/closed_form.py::convection_resistance -->
<!-- frob:describes python/feldspar/heat/closed_form.py::series_resistance -->
<!-- frob:describes python/feldspar/heat/closed_form.py::rate_from_resistance -->
<!-- frob:describes python/feldspar/heat/closed_form.py::dittus_boelter_nusselt_heating -->
<!-- frob:describes python/feldspar/heat/closed_form.py::coefficient_from_nusselt -->
<!-- frob:describes python/feldspar/heat/closed_form.py::register -->

Heat-transfer closed-form solver directions (WO-20 Phase 2): pure
marshalling over `feldspar._feldspar.heat_*`, `accuracy=EXACT` for
every direction (each evaluates its own declared model exactly).
`plane_wall_resistance`/`cylindrical_wall_resistance`/
`convection_resistance` compute the three resistance-network element
types; `series_resistance` combines them; `rate_from_resistance`
derives heat rate from a total resistance and temperature difference;
`dittus_boelter_nusselt_heating`/`coefficient_from_nusselt` are the
forced-convection correlation and its coefficient conversion. Scope
note (WO-20 close-out): 1-D conduction/convection resistance networks
and Dittus-Boelter only -- transient lumped/Heisler, natural
convection, boiling/condensation, radiation networks, and LMTD/
effectiveness-NTU heat exchangers are EXPLICITLY CUT (transient lumped
is picked up by `heat.thermal_transient`). `register(registry)`
registers the family.

## heat_thermal_transient

<!-- frob:describes python/feldspar/heat/thermal_transient.py::biot_number_from_convection -->
<!-- frob:describes python/feldspar/heat/thermal_transient.py::step_temperature -->
<!-- frob:describes python/feldspar/heat/thermal_transient.py::time_to_threshold -->
<!-- frob:describes python/feldspar/heat/thermal_transient.py::duty_cycle_peak_temperature -->
<!-- frob:describes python/feldspar/heat/thermal_transient.py::register -->

Lumped-capacitance thermal TRANSIENT tier (WO-24 deliverable 6):
extends the steady resistance-network tier with the single-node
governing ODE (`C_th * dT/dt = P - (T - T_amb)/R_th`, Incropera & DeWitt
ch. 5) those steady directions never solve in time.
`biot_number_from_convection` checks the lumped-capacitance validity
assumption; `step_temperature` evaluates the exponential step response
for constant `P`; `time_to_threshold` inverts it to solve for time at a
given temperature; `duty_cycle_peak_temperature` composes the step
response over a periodic duty cycle to find the steady-periodic peak.
`register(registry)` registers the family.
