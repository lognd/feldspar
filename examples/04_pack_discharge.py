"""The regolith seam: what feldspar looks like from the host side.

TARGET-API sketch (requires the `regolith` extra + ../lithos installed).
regolith code never names feldspar; discovery is the entry point.
"""

from regolith.harness import DischargeRequest, Interval as RInterval, ModelRegistry
from regolith.harness.plugin import load_packs


def main() -> None:
    registry = ModelRegistry()
    packs = load_packs(registry).unwrap()  # finds ("feldspar", <version>)
    assert any(p.name == "feldspar" for p in packs)

    request = DischargeRequest(
        claim_kind="mech.fea.static_deflection",  # OPEN-6 interim kind
        # NOTE (audit A-9/A-10): DischargeRequest carries NO sense and
        # NO tags fields. The sense lives on the model's own
        # ModelSignature (the pack passes it into plan(sense=...));
        # regime tags are guaranteed by the claim kind per 06's v1
        # rule -- the request-side tag channel is the sec. 7 item 4
        # ask, regolith-side.
        limit=2.0e-3,  # m
        inputs={
            "mech.geom.cantilever.length": RInterval(lo=0.50, hi=0.50),
            "mech.geom.cantilever.width": RInterval(lo=0.040, hi=0.042),
            "mech.geom.cantilever.height": RInterval(lo=0.060, hi=0.060),
            "mech.material.youngs_modulus": RInterval(lo=6.8e10, hi=7.1e10),
            "mech.material.poisson": RInterval(lo=0.33, hi=0.33),
            "mech.load.tip_force": RInterval(lo=1.0e3, hi=1.2e3),
        },
    )
    evidence = registry.discharge(request)
    # discharged iff value + eps <= limit (the ONE margin rule);
    # missing ccx -> honest indeterminate DomainError, never a crash.
    print(evidence.status, evidence.value, evidence.hash)


if __name__ == "__main__":
    main()
