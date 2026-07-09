from __future__ import annotations

"""ngspice discretized-tier stage pattern for `elec` (WO-17, M7):
`deck.py` (pure text) -> `ngspice.py` (find/run the external binary)
-> `results.py` (parse -> Result) -> `solver.py` (registration + eps).
Mirrors `feldspar.fea`'s shape exactly (05 pattern instantiated a
second time) -- proof the pattern generalizes, not an FEA one-off."""
