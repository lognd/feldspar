from __future__ import annotations

"""The materials-selection justification surface (T-0018 slice 5,
lithos design-log D270 ruling 3): a solver route from requirements
(hardness target, required ideal critical diameter for the section/
quench-severity combination, and a cost-class ceiling) to a ranked
candidate list, with the calc chain (which criterion each candidate
met or missed, and by how much) carried in the result as the
justification artifact the owner asked for.

Scope note (honesty over reach, matching every other direction in this
package): this direction does NOT itself run the kinetics/
hardenability calc chain that PRODUCES `achievable_hardness_hv` and
`ideal_critical_diameter_m` for a candidate -- a caller composes those
from `materials.kinetics`/`materials.hardenability` (e.g. Koistinen-
Marburger martensite fraction -> hardness correlation, Grossmann D_I)
before calling this route, and this direction's OWN job is the ranking
composition over already-computed per-candidate figures, each
candidate carrying its own name/cost_class for the justification
report. A full requirements-to-candidates search that also re-derives
each candidate's hardness/diameter from raw composition inline is a
named cut (would duplicate the kinetics/hardenability directions
rather than composing them, violating NO DUPLICATION)."""

import json
from typing import Dict, List

from typani import Err, Ok

from feldspar.core import Domain, Interval, PortDecl, Rank
from feldspar.logging_setup import get_logger
from feldspar.solve import (
    EXACT,
    Citation,
    SolveOutput,
    SolverRegistry,
    make_direction,
)
from feldspar.solve.digest import canonical_digest
from feldspar.solve.errors import SolveError
from feldspar.solve.payload import PayloadResolver, resolver_cache_identity

_log = get_logger(__name__)

__all__ = ["CANDIDATES_PORT", "RANKED_CANDIDATES_PORT", "COST_CLASS_RANK", "register"]

#: The candidate-pool payload port (kind "table"):
#: `[{"name": str, "achievable_hardness_hv": float,
#: "ideal_critical_diameter_m": float, "cost_class": "low"|"medium"|
#: "high"|"specialty"}, ...]` -- one entry per candidate material,
#: each already run through the kinetics/hardenability calc chain by
#: the caller (see module docstring). Same JSON-payload convention
#: `mech.fatigue`'s `MINER_SPECTRUM_PORT` uses.
# frob:doc docs/modules/materials.md#materials_selection
CANDIDATES_PORT = "materials.selection.candidates"

#: The ranked-result payload port (kind "table"):
#: `[{"name", "cost_class", "meets_hardness", "meets_diameter",
#: "meets_cost", "eligible", "hardness_margin_hv",
#: "diameter_margin_m", "rank"}, ...]` -- the full calc chain per
#: candidate (the justification artifact), sorted eligible-first by
#: descending hardness margin then ascending cost rank; ineligible
#: candidates carry `rank: null`.
# frob:doc docs/modules/materials.md#materials_selection
RANKED_CANDIDATES_PORT = "materials.selection.ranked_candidates"

#: Ordinal cost-class ranks (lithos D269/D266 licensing posture: cost
#: enters as a cited public-domain CLASS -- see
#: `materials.records.CostClass` -- never a scraped vendor price).
#: This is the ONE home for the class-to-rank mapping (NO DUPLICATION
#: -- `materials.records.CostClass`'s Literal values are the source of
#: truth for the class NAMES; this dict is the ordering over them).
# frob:doc docs/modules/materials.md#materials_selection
COST_CLASS_RANK: Dict[str, int] = {"low": 0, "medium": 1, "high": 2, "specialty": 3}

_SELECTION_CITATIONS = (
    Citation(
        kind="handbook",
        ref=(
            "lithos design-log D270 ruling 3 (owner directive "
            "2026-07-19): a solver route from requirements (hardness "
            "target, section size, quench severity class, cost class) "
            "to ranked candidate materials with the full calc chain as "
            "evidence."
        ),
        note=(
            "This direction composes ALREADY-COMPUTED per-candidate "
            "figures (see module docstring) into a ranked, evidenced "
            "result -- it is not itself a cited physical law, so its "
            "citation is the owner directive that scopes it, matching "
            "how `solve/registry.py` internal-composition directions "
            "elsewhere in this codebase cite their governing ruling "
            "rather than a physics paper."
        ),
    ),
)


def _rank_candidates(
    candidates: List[dict],
    hardness_target_hv: float,
    required_diameter_m: float,
    cost_class_ceiling_rank: int,
) -> List[dict]:
    """The ranking composition itself: evaluates each candidate
    against the three requirements, then sorts eligible candidates
    first (descending hardness margin, ascending cost rank),
    ineligible candidates last (stable, original order preserved
    within each group)."""
    evaluated = []
    for candidate in candidates:
        name = candidate["name"]
        hardness = candidate["achievable_hardness_hv"]
        diameter = candidate["ideal_critical_diameter_m"]
        cost_class = candidate["cost_class"]
        cost_rank = COST_CLASS_RANK[cost_class]
        meets_hardness = hardness >= hardness_target_hv
        meets_diameter = diameter >= required_diameter_m
        meets_cost = cost_rank <= cost_class_ceiling_rank
        eligible = meets_hardness and meets_diameter and meets_cost
        evaluated.append(
            {
                "name": name,
                "cost_class": cost_class,
                "meets_hardness": meets_hardness,
                "meets_diameter": meets_diameter,
                "meets_cost": meets_cost,
                "eligible": eligible,
                "hardness_margin_hv": hardness - hardness_target_hv,
                "diameter_margin_m": diameter - required_diameter_m,
                "cost_rank": cost_rank,
            }
        )
    # frob:waive PERF004 reason="false positive: frob's PERF004 loop-gate is function-scoped (any earlier top-level for/while anywhere in the function triggers it -- see _loop_gate in frob's perf/_rules.py), not true AST containment. This sorted() runs ONCE, after the `for candidate in candidates:` loop above has already finished building `evaluated`; there is no repeated per-iteration sort to hoist."
    eligible_sorted = sorted(
        (c for c in evaluated if c["eligible"]),
        key=lambda c: (-c["hardness_margin_hv"], c["cost_rank"]),
    )
    ineligible = [c for c in evaluated if not c["eligible"]]
    ranked = []
    for i, candidate in enumerate(eligible_sorted, start=1):
        candidate = dict(candidate)
        candidate["rank"] = i
        ranked.append(candidate)
    for candidate in ineligible:
        candidate = dict(candidate)
        candidate["rank"] = None
        ranked.append(candidate)
    return ranked


def _make_selection_direction(resolver: PayloadResolver):
    def selection_fn(x):
        candidates_result = resolver.resolve(x[CANDIDATES_PORT])
        if candidates_result.is_err:
            _log.warning(
                "materials.selection: candidates payload unresolvable: %r",
                candidates_result.err,
            )
            return candidates_result
        candidates = json.loads(candidates_result.danger_ok)
        if not candidates:
            return Err(
                SolveError.OutOfDomain(
                    violation="materials.selection: empty candidate pool"
                )
            )
        for candidate in candidates:
            if candidate.get("cost_class") not in COST_CLASS_RANK:
                return Err(
                    SolveError.OutOfDomain(
                        violation=(
                            "materials.selection: candidate "
                            f"{candidate.get('name')!r} has unknown "
                            f"cost_class={candidate.get('cost_class')!r}"
                        )
                    )
                )
        hardness_target_hv = x["materials.selection.hardness_target_hv"]
        required_diameter_m = x["materials.selection.required_diameter_m"]
        cost_class_ceiling_rank = int(x["materials.selection.cost_class_ceiling_rank"])
        ranked = _rank_candidates(
            candidates,
            hardness_target_hv,
            required_diameter_m,
            cost_class_ceiling_rank,
        )
        n_eligible = sum(1 for c in ranked if c["eligible"])
        _log.info(
            "materials.selection: %d/%d candidates eligible",
            n_eligible,
            len(ranked),
        )
        payload_bytes = json.dumps(ranked).encode("utf-8")
        ref = resolver.store(
            kind="table",
            content=payload_bytes,
            origin="materials.selection.rank_candidates_for_requirements",
        )
        return Ok(SolveOutput(values={}, payloads={RANKED_CANDIDATES_PORT: ref}))

    info, fn = make_direction(
        solver_id="materials.selection.rank_candidates_for_requirements",
        namespace="materials.selection",
        inputs=(
            "materials.selection.hardness_target_hv",
            "materials.selection.required_diameter_m",
            "materials.selection.cost_class_ceiling_rank",
            CANDIDATES_PORT,
        ),
        outputs=(RANKED_CANDIDATES_PORT,),
        domain=Domain(
            box={
                "materials.selection.hardness_target_hv": Interval(50.0, 1000.0),
                "materials.selection.required_diameter_m": Interval(1e-4, 1.0),
                "materials.selection.cost_class_ceiling_rank": Interval(0.0, 3.0),
            },
            tags={"selection"},
        ),
        cost=1e-5,
        accuracy=EXACT,
        citations=_SELECTION_CITATIONS,
        version="1",
        tier="closed_form",
        settings=canonical_digest({"resolver": resolver_cache_identity(resolver)}),
        fn=selection_fn,
    )
    return info, fn


_PORT_DECLS = (
    PortDecl("materials.selection.hardness_target_hv", "1"),
    PortDecl("materials.selection.required_diameter_m", "m"),
    PortDecl("materials.selection.cost_class_ceiling_rank", "1"),
    PortDecl(CANDIDATES_PORT, "", Rank.payload("table")),
    PortDecl(RANKED_CANDIDATES_PORT, "", Rank.payload("table")),
)


# frob:doc docs/modules/materials.md#materials_selection
def register(registry: SolverRegistry, resolver: PayloadResolver) -> None:
    """Registers `materials.selection.rank_candidates_for_requirements`
    (T-0018 slice 5) against `registry`, resolving/storing its payload
    ports through `resolver` (same convention as `mech.fatigue.
    register`'s Miner-damage direction)."""
    _ = registry.declare_ports(*_PORT_DECLS).danger_ok
    info, fn = _make_selection_direction(resolver)
    result = registry.register(info, fn)
    _ = result.danger_ok
    _log.info("materials.selection: registered 1 solver direction")
