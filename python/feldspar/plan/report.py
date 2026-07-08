from __future__ import annotations

"""`Solution.explain()`/`Solution.to_dict()` rendering (WO-10,
04-routing "Justification report", 01-interfaces `Solution.explain`).

PURE RENDERING: every function here reads only fields already carried
by a `Solution` (`execute()`/`solve()` stamped `step_eps`/
`step_citations`/`step_declared_domain`/`eps_budget` onto it precisely
so this module never needs the registry or a `SolveFn` -- there is
nothing here to recompute, so this report can never disagree with the
evidence (04). `render_explain`/`render_to_dict` build the SAME
intermediate step-record list so the string and dict forms can never
drift against each other (house rule: no duplication).

Determinism: step order is `route.steps` order (already deterministic,
04 "Determinism"); every float in `render_explain`'s text goes through
`feldspar.core.format_f64` (the one canonical float-formatting home,
AD-13) so the golden string is byte-stable across platforms."""

from typing import TYPE_CHECKING, Any, Dict, List

from feldspar.core import format_f64, total_error

if TYPE_CHECKING:
    from feldspar.plan.execute import AttemptRecord, Solution

__all__ = ["render_explain", "render_to_dict"]


def _domain_dict(domain: Any) -> "Dict[str, Any]":
    """`Domain` (box + tags) -> a JSON-safe, sorted dict -- shared by
    the declared and realized domain renderings for one step."""
    return {
        "box": {
            port: {"lo": iv.lo, "hi": iv.hi} for port, iv in sorted(domain.box.items())
        },
        "tags": sorted(domain.tags),
    }


def _step_records(solution: "Solution") -> "List[Dict[str, Any]]":
    """One record per `RouteStep`, joining `Route` (declared route
    shape) against the metadata `Solution.step_eps`/`step_citations`/
    `step_declared_domain` captured at execution time -- the single
    place both renderers pull step data from."""
    records: List[Dict[str, Any]] = []
    for step in solution.route.steps:
        citations = solution.step_citations.get(step.solver_id, ())
        declared = solution.step_declared_domain.get(step.solver_id)
        records.append(
            {
                "solver_id": step.solver_id,
                "citations": [
                    {"kind": c.kind, "ref": c.ref, "note": c.note} for c in citations
                ],
                "declared_domain": (
                    _domain_dict(declared) if declared is not None else None
                ),
                # NOTE (honest labeling): `RouteStep.realized_domain` is
                # the PLANNER's inflated-hull estimate at plan time
                # (04-routing "Algorithm (v1)": a sum surrogate over
                # hull corners), not the executor's exact corner-swept
                # hull for this step's inputs -- those two can differ
                # for any step past the first, and `Solution` carries
                # no separate "actual executed input hull" per step to
                # render instead (a WO-06 gap this report renders
                # honestly rather than papering over).
                "realized_domain": _domain_dict(step.realized_domain),
                "predicted_eps": step.predicted_eps,
                "charged_eps": solution.step_eps.get(step.solver_id),
                "cost": step.cost,
                "algebraic_form": solution.step_algebraic_form.get(step.solver_id),
                "admission_predicate": solution.step_admission_predicate.get(
                    step.solver_id
                ),
            }
        )
    return records


def _attempt_record(attempt: "AttemptRecord") -> "Dict[str, Any]":
    return {
        "excluded": list(attempt.excluded),
        "route_digest": attempt.route_digest,
        "failed_solver_id": attempt.failed_solver_id,
        "error_kind": attempt.error_kind,
        "error_detail": dict(attempt.error_detail),
    }


def render_to_dict(solution: "Solution") -> "Dict[str, Any]":
    """Machine-readable justification report (01-interfaces
    `Solution.to_dict`): the same data `render_explain` prints, as a
    JSON-safe dict."""
    realized = total_error(solution.value, solution.eps)
    budget = solution.eps_budget
    return {
        "target": solution.target,
        "value": {"lo": solution.value.lo, "hi": solution.value.hi},
        "eps": solution.eps,
        "realized_error": realized,
        "eps_budget": budget,
        "eps_remaining": (budget - realized) if budget is not None else None,
        "route": {
            "digest": solution.route.digest,
            "total_cost": solution.route.total_cost,
            "predicted_eps": solution.route.predicted_eps,
            "steps": _step_records(solution),
        },
        "settings_digest": solution.settings_digest,
        "solver_versions": dict(solution.solver_versions),
        "cache_hit": solution.cache_hit,
        "attempts": [_attempt_record(a) for a in solution.attempts],
    }


def _fmt_domain(label: str, d: "Dict[str, Any] | None", indent: str) -> "List[str]":
    if d is None:
        return [f"{indent}{label}: (not carried)"]
    box = ", ".join(
        f"{port}=[{format_f64(iv['lo'])}, {format_f64(iv['hi'])}]"
        for port, iv in d["box"].items()
    )
    tags = ", ".join(d["tags"]) if d["tags"] else "(none)"
    return [f"{indent}{label}: box=({box}) tags=({tags})"]


def render_explain(solution: "Solution") -> str:
    """Human-readable step-by-step justification report (01-interfaces
    `Solution.explain`, 04-routing "Justification report"): per step
    the solver, its method citations, the domain admission (declared
    box+tags and the realized hull), the predicted and charged eps;
    route-level cost, the eps-vs-budget decomposition, the reroute
    trail, and cache provenance."""
    lines: List[str] = []
    lines.append(f"Solution for target={solution.target!r}")
    lines.append(
        f"  value=[{format_f64(solution.value.lo)}, {format_f64(solution.value.hi)}]"
        f"  eps={format_f64(solution.eps)}"
    )
    realized = total_error(solution.value, solution.eps)
    lines.append(f"  realized_error(worst-case)={format_f64(realized)}")
    if solution.eps_budget is not None:
        remaining = solution.eps_budget - realized
        lines.append(
            f"  eps_budget={format_f64(solution.eps_budget)}"
            f"  spent={format_f64(realized)}"
            f"  remaining={format_f64(remaining)}"
        )
    else:
        lines.append("  eps_budget: (no budget context -- execute() called directly)")
    lines.append(f"  cache_hit={solution.cache_hit}")
    lines.append(f"  settings_digest={solution.settings_digest}")
    lines.append(f"  route_digest={solution.route.digest}")
    lines.append(f"  route_total_cost={format_f64(solution.route.total_cost)}")

    steps = _step_records(solution)
    if not steps:
        lines.append("  route: zero-step (target already known)")
    else:
        lines.append(f"  route: {len(steps)} step(s)")
        for i, rec in enumerate(steps, start=1):
            lines.append(f"  step {i}: solver={rec['solver_id']!r}")
            if rec["citations"]:
                for c in rec["citations"]:
                    note = f" -- {c['note']}" if c["note"] else ""
                    lines.append(f"    citation: {c['kind']}: {c['ref']}{note}")
            else:
                lines.append("    citation: (none carried)")
            lines.extend(_fmt_domain("declared_domain", rec["declared_domain"], "    "))
            lines.extend(_fmt_domain("realized_domain", rec["realized_domain"], "    "))
            charged = rec["charged_eps"]
            charged_s = format_f64(charged) if charged is not None else "(not carried)"
            lines.append(
                f"    predicted_eps={format_f64(rec['predicted_eps'])}"
                f"  charged_eps={charged_s}"
                f"  cost={format_f64(rec['cost'])}"
            )
            form = rec["algebraic_form"] or "(not carried -- hand-written direction)"
            lines.append(f"    algebraic_form: {form}")
            lines.append(
                f"    admission_predicate: {rec['admission_predicate'] or '(none)'}"
            )

    if solution.attempts:
        lines.append(f"  reroute trail: {len(solution.attempts)} attempt(s)")
        for i, attempt in enumerate(solution.attempts, start=1):
            excl = ", ".join(attempt.excluded) if attempt.excluded else "(none)"
            failed = attempt.failed_solver_id or "(plan itself)"
            lines.append(
                f"    attempt {i}: excluded=({excl}) failed_step={failed}"
                f" error={attempt.error_kind}"
            )
    else:
        lines.append("  reroute trail: (none -- solved on the first attempt)")

    return "\n".join(lines)
