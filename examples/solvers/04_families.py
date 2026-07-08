"""Complexity rung 4 -- solver families by plain factory (F9).

Many near-identical solvers (section properties per shape; a
convection correlation per geometry; a record edge per material).
REJECTED: a class-based "SolverFamily" abstraction -- a plain
function returning (SolverInfo, SolveFn) plus a loop is already
minimal, debuggable, and needs no new concepts. DX-SETTLED: factories
are the blessed pattern; the spec only demands the id embeds the
family member (deterministic, greppable).
"""

from feldspar.solve import EXACT, SolverRegistry, make_direction

SHAPES = {
    # name -> (I(b, h) formula, citation)
    "rect": (lambda b, h: b * h**3 / 12.0,
             "handbook: Gere 9e, App. E"),
    "tube": (lambda d_o, d_i: 3.14159265358979 * (d_o**4 - d_i**4) / 64.0,
             "handbook: Gere 9e, App. E"),
}


def _section_solver(name, formula, cite):
    a, b = f"mech.section.{name}.dim_a", f"mech.section.{name}.dim_b"
    out = f"mech.section.{name}.second_moment"
    return make_direction(
        solver_id=f"mech.section_properties.{name}",
        namespace="mech",
        inputs=(a, b),
        outputs=(out,),
        domain={a: (1e-4, 1.0), b: (1e-4, 1.0)},
        cost=1e-7,
        accuracy=EXACT,
        citations=(cite,),
        version="1",
        fn=lambda x, f=formula, a=a, b=b: f(x[a], x[b]),
    )
    # make_direction is the decorator's function-call twin (same
    # coercions, same lowering) for code that builds solvers rather
    # than writing them longhand.


def register(registry: SolverRegistry) -> None:
    for name, (formula, cite) in sorted(SHAPES.items()):
        registry.register(*_section_solver(name, formula, cite)).danger_ok
