# feldspar.pack

`FeaStaticStressModel`/`FeaStaticDeflectionModel` and every other
regolith `Model` wrapper around the engine's solve directions (06
"Models", WO-27): ALL regolith imports live under this package
(FINV-3/10). `feldspar.pack` is the ONE place `regolith` is imported
from anywhere in this codebase.

## pack_init

<!-- frob:describes python/feldspar/pack/__init__.py::register -->

ALL regolith imports live here (FINV-3/10); the `regolith.plugins`
entry point target (06 "Boundary rules", `[project.entry-points]` in
`pyproject.toml`). `register` is the entry-point-facing function
regolith's plugin loader calls to obtain this pack's registered models.

## pack_errors

<!-- frob:describes python/feldspar/pack/errors.py::map_engine_error -->
<!-- frob:describes python/feldspar/pack/errors.py::margin_exhausted_error -->

The ONE feldspar-error -> regolith-error mapping (06 "Failures"): every
`feldspar.solve.errors.SolveError`/`feldspar.plan.errors.PlanError`
variant maps to a regolith `DomainError` carrying the original message
embedded -- honest indeterminate, never a silent wrong answer, never an
exception. `map_engine_error` is that one mapping function;
`margin_exhausted_error` builds the specific `DomainError` for a
margin-exhausted claim outcome.

## pack_converters

<!-- frob:describes python/feldspar/pack/converters.py::to_feldspar_interval -->
<!-- frob:describes python/feldspar/pack/converters.py::to_regolith_interval -->
<!-- frob:describes python/feldspar/pack/converters.py::to_feldspar_payload_ref -->
<!-- frob:describes python/feldspar/pack/converters.py::to_regolith_payload_ref -->

The ONE regolith<->feldspar `Interval` (and `PayloadRef`) converter pair
(06, FINV-3/10): both sides use the same closed `[lo, hi]` semantics so
conversion is a straight field copy, done in exactly one place so no
other module needs to know both types exist. `to_feldspar_interval`/
`to_regolith_interval` convert `Interval` values; `to_feldspar_
payload_ref`/`to_regolith_payload_ref` convert `PayloadRef` values.
Round-trip tested both directions.

## pack_payload_bridge

<!-- frob:describes python/feldspar/pack/payload_bridge.py::NoStoreResolver -->
<!-- frob:describes python/feldspar/pack/payload_bridge.py::NoStoreResolver.resolve -->
<!-- frob:describes python/feldspar/pack/payload_bridge.py::NoStoreResolver.store -->
<!-- frob:describes python/feldspar/pack/payload_bridge.py::RegolithResolverAdapter -->
<!-- frob:describes python/feldspar/pack/payload_bridge.py::RegolithResolverAdapter.resolve -->
<!-- frob:describes python/feldspar/pack/payload_bridge.py::RegolithResolverAdapter.store -->

`NoStoreResolver` is the honest stand-in `PayloadResolver` a pack model
closes the engine's payload-step catalog over when no lithos resolver
reaches `Model.estimate` (WO-14 boundary v2): its `resolve`/`store`
methods refuse rather than fabricate a value.
`RegolithResolverAdapter` is the pack-side seam that wraps a lithos-
provided `PayloadStore`-backed callable (`digest -> Result[bytes,
<lithos error>]`, structural-typed per FINV-3) into feldspar's own
`PayloadResolver` protocol, enforcing D154's wire-format contract (a
payload ref's bytes ARE the schema-versioned JSON `regolith._schema`
publishes) -- any schema-version mismatch is
`SolveError.ParseFailed`, naming both versions, never a silent parse of
an unrecognized shape. Its own `resolve`/`store` implement that
adapter contract.

## pack_models

<!-- frob:describes python/feldspar/pack/models.py::_FeaModel -->
<!-- frob:describes python/feldspar/pack/models.py::_ClosedFormEngineModel -->
<!-- frob:describes python/feldspar/pack/models.py::FeaStaticStressModel -->
<!-- frob:describes python/feldspar/pack/models.py::FeaStaticDeflectionModel -->
<!-- frob:describes python/feldspar/pack/models.py::FeaStaticDeflectionFromGeometryModel -->
<!-- frob:describes python/feldspar/pack/models.py::MechStiffnessModel -->
<!-- frob:describes python/feldspar/pack/models.py::ElecRailModel -->
<!-- frob:describes python/feldspar/pack/models.py::MemberFlexuralCapacityModel -->
<!-- frob:describes python/feldspar/pack/models.py::MemberAxialCapacityModel -->
<!-- frob:describes python/feldspar/pack/models.py::EulerBucklingLoadModel -->
<!-- frob:describes python/feldspar/pack/models.py::BoltLoadFactorModel -->
<!-- frob:describes python/feldspar/pack/models.py::WeldUtilizationModel -->
<!-- frob:describes python/feldspar/pack/models.py::BearingRatingLifeModel -->
<!-- frob:describes python/feldspar/pack/models.py::FatigueGoodmanFactorOfSafetyModel -->
<!-- frob:describes python/feldspar/pack/models.py::FatigueGerberFactorOfSafetyModel -->
<!-- frob:describes python/feldspar/pack/models.py::FatigueSnCyclesToFailureModel -->
<!-- frob:describes python/feldspar/pack/models.py::FatigueMinerDamageModel -->
<!-- frob:describes python/feldspar/pack/models.py::LeadscrewTorqueRaiseModel -->
<!-- frob:describes python/feldspar/pack/models.py::ThermalTransientStepTemperatureModel -->
<!-- frob:describes python/feldspar/pack/models.py::ThermalTransientDutyCyclePeakTemperatureModel -->
<!-- frob:describes python/feldspar/pack/models.py::ShaftCriticalSpeedModel -->
<!-- frob:describes python/feldspar/pack/models.py::DriveAccelTorqueModel -->
<!-- frob:describes python/feldspar/pack/models.py::PlateMaxStressModel -->
<!-- frob:describes python/feldspar/pack/models.py::PlateMaxDeflectionModel -->
<!-- frob:describes python/feldspar/pack/models.py::MicrostripImpedanceModel -->
<!-- frob:describes python/feldspar/pack/models.py::StriplineImpedanceModel -->
<!-- frob:describes python/feldspar/pack/models.py::SeriesTerminationModel -->
<!-- frob:describes python/feldspar/pack/models.py::TheveninTerminationR1Model -->
<!-- frob:describes python/feldspar/pack/models.py::TheveninTerminationR2Model -->
<!-- frob:describes python/feldspar/pack/models.py::AcShuntResistorModel -->
<!-- frob:describes python/feldspar/pack/models.py::AcShuntCapacitorModel -->
<!-- frob:describes python/feldspar/pack/models.py::FluidsMdotModel -->
<!-- frob:describes python/feldspar/pack/models.py::FluidsFlowImbalanceModel -->
<!-- frob:describes python/feldspar/pack/models.py::FluidsDpModel -->

This is the whole family of regolith `Model` wrappers around feldspar's
engine solve directions (06 "Models", WO-27 deliverable). Every model
in this file is homogeneous in shape: a thin subclass implementing
regolith's `Model` protocol (`signature`, `version`, `cost`,
`estimate`) whose `estimate()` converts `DischargeRequest.inputs`
(regolith `Interval`s) into feldspar `Interval`s via `pack.converters`,
runs `feldspar.plan.solve.solve()` (the plan+execute facade, corner
sweep already inside it), and converts the resulting `Solution` back
into a regolith `Prediction`. Two shared bases do the actual engine
call so no per-model duplication is needed:

- `_FeaModel`: the base for FEA-discretized directions (`version`,
  `cost`, `estimate` implemented once here; stress/deflection variants
  differ only in which engine claim kind and geometry shape they wrap).
- `_ClosedFormEngineModel`: the base for every closed-form-only
  direction (`cost` implemented once; every mech/elec/fluids/heat
  closed-form model below inherits from it and only supplies its own
  `signature`).

One model class per physical claim the fleet's `Model` protocol
exposes: FEA statics (`FeaStaticStressModel`, `FeaStaticDeflectionModel`,
`FeaStaticDeflectionFromGeometryModel`), mechanical stiffness/capacity
(`MechStiffnessModel`, `MemberFlexuralCapacityModel`,
`MemberAxialCapacityModel`, `EulerBucklingLoadModel`), joints/welds/
bearings (`BoltLoadFactorModel`, `WeldUtilizationModel`,
`BearingRatingLifeModel`), fatigue (`FatigueGoodmanFactorOfSafetyModel`,
`FatigueGerberFactorOfSafetyModel`, `FatigueSnCyclesToFailureModel`,
`FatigueMinerDamageModel`), leadscrew/thermal-transient/dynamics
(`LeadscrewTorqueRaiseModel`, `ThermalTransientStepTemperatureModel`,
`ThermalTransientDutyCyclePeakTemperatureModel`,
`ShaftCriticalSpeedModel`, `DriveAccelTorqueModel`), plates
(`PlateMaxStressModel`, `PlateMaxDeflectionModel`), electrical signal
integrity (`MicrostripImpedanceModel`, `StriplineImpedanceModel`,
`SeriesTerminationModel`, `TheveninTerminationR1Model`,
`TheveninTerminationR2Model`, `AcShuntResistorModel`,
`AcShuntCapacitorModel`), and fluids network (`FluidsMdotModel`,
`FluidsFlowImbalanceModel`, `FluidsDpModel`). Each subclass's
`signature` (and, for the two non-`_ClosedFormEngineModel` bases'
subclasses, `version`/`cost`/`estimate`) declares exactly which claim
kind, inputs, and output it wraps. The module's `DEFAULT_*_CLAIM_KIND`
module-level string constants (one or two per model family, e.g.
`DEFAULT_STRESS_CLAIM_KIND`, `DEFAULT_RAIL_LO_CLAIM_KIND`/`_HI_`,
`DEFAULT_FLUIDS_MDOT_LO_CLAIM_KIND`/`_HI_`) are each model's default
regolith claim-kind string -- one named default per physical claim the
family above exposes, kept as named constants rather than inlined
literals so every model's default is greppable and each has exactly one
source of truth.
