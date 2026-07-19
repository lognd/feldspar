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
<!-- frob:describes python/feldspar/heat/closed_form.py::dittus_boelter_nusselt_cooling -->
<!-- frob:describes python/feldspar/heat/closed_form.py::gnielinski_nusselt -->
<!-- frob:describes python/feldspar/heat/closed_form.py::laminar_fully_developed_nusselt_const_temp -->
<!-- frob:describes python/feldspar/heat/closed_form.py::laminar_fully_developed_nusselt_const_flux -->
<!-- frob:describes python/feldspar/heat/closed_form.py::churchill_chu_horizontal_cylinder_nusselt -->
<!-- frob:describes python/feldspar/heat/closed_form.py::churchill_chu_vertical_plate_nusselt -->
<!-- frob:describes python/feldspar/heat/closed_form.py::ntu_from_ua -->
<!-- frob:describes python/feldspar/heat/closed_form.py::effectiveness_parallel_flow -->
<!-- frob:describes python/feldspar/heat/closed_form.py::effectiveness_counterflow -->
<!-- frob:describes python/feldspar/heat/closed_form.py::effectiveness_shell_and_tube_one_pass -->
<!-- frob:describes python/feldspar/heat/closed_form.py::hx_rate_from_effectiveness -->
<!-- frob:describes python/feldspar/heat/closed_form.py::hx_outlet_temp_hot -->
<!-- frob:describes python/feldspar/heat/closed_form.py::hx_outlet_temp_cold -->
<!-- frob:describes python/feldspar/heat/closed_form.py::register -->

Heat-transfer closed-form solver directions (WO-20 Phase 2, widened by
WO-142): pure marshalling over `feldspar._feldspar.heat_*`,
`accuracy=EXACT` for every direction (each evaluates its own declared
model exactly). `plane_wall_resistance`/`cylindrical_wall_resistance`/
`convection_resistance` compute the three resistance-network element
types; `series_resistance` combines them; `rate_from_resistance`
derives heat rate from a total resistance and temperature difference;
`dittus_boelter_nusselt_heating`/`coefficient_from_nusselt` are the
forced-convection correlation and its coefficient conversion.

WO-142 growth: `dittus_boelter_nusselt_cooling` completes the
Dittus-Boelter branch (n=0.3, Dittus & Boelter 1930, reprinted 1985);
`gnielinski_nusselt` is the f-coupled Gnielinski (1976) correlation
(paywalled primary, restated Incropera & DeWitt ch. 8), consuming a
friction factor from `feldspar.fluids` the same way WO-139's friction
model feeds it; `laminar_fully_developed_nusselt_const_temp`/
`_const_flux` are the Incropera Table 8.1 laminar constants (3.66/
4.36); `churchill_chu_horizontal_cylinder_nusselt`/
`churchill_chu_vertical_plate_nusselt` are the Churchill & Chu (1975)
natural-convection correlations (both primaries paywalled, restated
Incropera & DeWitt eq. 9.34/9.26); `ntu_from_ua`/
`effectiveness_parallel_flow`/`effectiveness_counterflow`/
`effectiveness_shell_and_tube_one_pass`/`hx_rate_from_effectiveness`/
`hx_outlet_temp_hot`/`hx_outlet_temp_cold` compose the NTU-
effectiveness family (Kays & London, Compact Heat Exchangers, 3rd ed.,
1984; restated Incropera & DeWitt Table 11.4): UA -> NTU ->
effectiveness -> outlet temperatures.

Scope note (WO-20 close-out, amended WO-142): 1-D conduction/
convection resistance networks, Dittus-Boelter (both branches),
Gnielinski, laminar constants, Churchill-Chu natural convection, and
NTU-effectiveness are covered -- boiling/condensation and radiation
networks remain EXPLICITLY CUT (transient lumped is picked up by
`heat.thermal_transient`). Conjugate/coupled flow-and-wall problems
(the thermosiphon buoyancy-loop class) are a recorded wall, not
attempted here (`docs/spec/fluorite/03-lowering.md:114-124`).
`register(registry)` registers the family.

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
