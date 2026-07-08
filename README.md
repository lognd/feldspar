# feldspar

External FEA solver pack for the regolith toolchain (lithos project):
reduced-tier static stress/deflection models discharging regolith
obligations via CalculiX + gmsh, with signed evidence.

Contract: ../lithos/docs/implementation/20-solver-abstraction.md and
WO-27 (../lithos/docs/implementation/WO-27-reference-fea-pack.md).
Depends on regolith; regolith never depends on feldspar.

## Core Ideas

Every solution to a problem goes through a "pipeline" of sorts: different
methods to find answers of varying degrees of accuracy. Traditionally, the
solution-finding process is delegated to an intelligent engineer who finds
solutions via their own knowledge and constructs a sequence of solution steps
to reach the answer.

The core idea of `feldspar` is to take a graph-theoretic approach to this.
Every model knows its inputs and outputs, the allowable domain it may operate
in, and the degree of certainty it produces. For instance, the following
example carries the *spirit* of what we are after (pay no attention to syntax):

```python
@solver(namespace="thermo")  # optionally specify inputs/outputs, may wrap a single function
class TableLookup(Solver):
    @override
    def __call__(self, *, pressure: ..., temperature: ...) -> Result[specific_volume, ...]: ...
    @override
    def __call__(self, *, temperature: ..., specific_volume: ...) -> Result[pressure, ...]: ...
    # ... and so forth

    @override
    def get_domain(self) -> Domain: ...  # the domain the function is valid over

    @override
    def get_accuracy(self, *args, **kwargs) -> Accuracy: ...  # model accuracy vs. measurement uncertainty

@solver(namespace="thermo")
class IdealGasLaw(Solver):
    @override
    def __call__(self, ...): ...  # and so forth
```

The solver chooses the cheapest valid solution path able to determine a
solution within the required margin of safety, accounting for potential error.

## Interfaces

The solver must be highly performant while still interfacing with pre-existing
solutions. The core is built in Rust via PyO3 and maturin, with additional
primitives available in `lithos/`. It is designed to interface with external
binaries and external Python libraries, but the bulk of the work is native to
this package, as this is the FEA workhorse. Data validation and errors-as-values
follow Rust idioms and the `typani/` package (not a typo).

Organization and ZERO DUPLICATION are core mantras.

## Capabilities

`feldspar` targets reduced-tier static FEA across the standard mechanical,
civil, and aerospace structural problem classes, including:

- Static stress and deflection of beams, trusses, frames, and plates
- Axial, torsional, and bending analysis of structural members
- Thermal-mechanical coupling for steady-state loads
- Fluid- and pressure-induced structural loading
- Vibration and modal analysis for linear systems
- Material response modeling for isotropic and orthotropic materials

Each capability is exposed as one or more `Solver` implementations with a
declared domain and accuracy, so the solver graph can select and compose them
to reach an answer within the requested margin of safety.
