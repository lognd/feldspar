"""The regolith seam: what feldspar looks like from the host side.

TARGET-API sketch (requires the `regolith` extra + a local lithos checkout installed).
regolith code never names feldspar; discovery is the entry point.
"""

from regolith.harness.model import DischargeRequest
from regolith.harness.quantity import Interval as RInterval
from regolith.harness.quantity import bits_to_f64
from regolith.harness.registry import ModelRegistry, default_registry

from feldspar.pack.models import DEFAULT_DEFLECTION_CLAIM_KIND


# frob:doc docs/modules/examples.md#examples_top
def main() -> None:
    # `default_registry()` is register_all() (regolith's own built-ins)
    # + load_packs() (every discovered `regolith.plugins` model_pack, in
    # sorted order) in one call -- the same composition a real host does.
    registry: ModelRegistry = default_registry()
    loaded = registry.packs
    skipped = registry.plugin_errors
    print(f"packs loaded: {[p.name for p in loaded]}")
    if skipped:
        print(f"packs skipped: {skipped}")
    assert any(p.name == "feldspar" for p in loaded)

    request = DischargeRequest(
        claim_kind=DEFAULT_DEFLECTION_CLAIM_KIND,
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
    # missing gmsh/ccx -> honest indeterminate status, never a crash.
    value = bits_to_f64(evidence.value_bits)
    print(f"status={evidence.status} value={value} hash={evidence.hash}")


if __name__ == "__main__":
    main()
