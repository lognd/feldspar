# Tickets

Central ledger managed by `frob ticket` -- one section per ticket.

<!-- ticket:T-0001 -->
```yaml
id: T-0001
title: Add doc edges for public symbols missing frob:doc anchors (COV001, 643 warnings)
state: queued
kind: docs
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/feldspar/**
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0002 -->
```yaml
id: T-0002
title: Add unit test coverage for public symbols with no frob:tests edge (TEST001,
  497 warnings)
state: queued
kind: feature
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/feldspar/**
- tests/**
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0003 -->
```yaml
id: T-0003
title: Add integration tests for interfaces below min_integration floor (TEST003,
  26 warnings)
state: queued
kind: feature
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/feldspar/**
- tests/**
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0004 -->
```yaml
id: T-0004
title: Record coverage stamp for TEST006 (run make coverage; frob check --stamp-coverage)
state: queued
kind: feature
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- .frob/coverage-stamp
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0005 -->
```yaml
id: T-0005
title: Clear ruff/ty legacy debt so [check] skip=[ruff,ty] can be removed from frob.toml
state: queued
kind: bug
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/feldspar/**
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0006 -->
```yaml
id: T-0006
title: Retrofit docs-index links / frob:describes anchors across docs/spec and docs/workflow,
  then re-enable DOC001 (gates.docs.include)
state: queued
kind: docs
origin: human
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- docs/**
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0007 -->
```yaml
id: T-0007
title: 'frob compliance: zero warnings'
state: in-progress
kind: feature
origin: agent
created: '2026-07-17'
blocked_by: []
parent: null
scope:
- python/,crates/,scripts/,docs/
evidence: []
attachments: []
acceptance: []
threat: null
```

<!-- ticket:T-0008 -->
```yaml
id: T-0008
title: 'strata pilot: design/feldspar.strata system model wired into frob sys'
state: done
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- design/** docs/workflow/strata-system-model.md
evidence:
- tests/unit/test_dev_scripts.py::test_gen_keys_main_writes_and_refuses_overwrite
attachments: []
acceptance:
- given the committed design/feldspar.strata, when frob sys audit runs, then it exits
  with PROVED or a named-gap state documented in docs/workflow/strata-system-model.md
threat: null
```
Pilot agent task: model feldspar's real topology (pyo3 rust core, solver registry, planner, domain packages, FEA/spice engine subprocess boundaries, regolith pack bridge, dev key store) in strata and drive frob sys plan/doc/audit honestly.
## Done report

Changed: design/feldspar.strata (16 nodes, 28 flows, 7 claims: 5
proved, 2 assumed CWE-78 discharges), docs/workflow/
strata-system-model.md (model doc + audit end state), commit b6f39ed.
Evidence: frob sys audit evaluates 7 claims with 0 refuted; frob check
exits 0 with zero SYS00x findings. The 5 residual named gaps are all
frob-side (foreign-less THREAT003 contract, docstring/method-name
scanner false positives, missing pyo3 ffi needle) and are documented
in docs/workflow/strata-system-model.md#audit-end-state. Follow-ups
T-0009/T-0010 (CWE-78 discharge) stay queued pending the upstream
THREAT003 contract fix. The attached pytest id exercises the dev_keys
secret-handling path bound by frob:secret.

<!-- ticket:T-0009 -->
```yaml
id: T-0009
title: Discharge CWE-78 at elec
state: queued
kind: security
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/feldspar/elec/**
evidence: []
attachments: []
acceptance: []
threat: null
```
sys-plan:elec:CWE-78:threat

claim 'weakness:CWE-78:elec' does not prove a mitigation chokepoint -- body must be NoFlow(src=<foreign source>, dst='elec')

<!-- ticket:T-0010 -->
```yaml
id: T-0010
title: Discharge CWE-78 at fea
state: queued
kind: security
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- python/feldspar/fea/**
evidence: []
attachments: []
acceptance: []
threat: null
```
sys-plan:fea:CWE-78:threat

claim 'weakness:CWE-78:fea' does not prove a mitigation chokepoint -- body must be NoFlow(src=<foreign source>, dst='fea')

<!-- ticket:T-0011 -->
```yaml
id: T-0011
title: Bind secret dev_keys in code
state: done
kind: security
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope: []
evidence:
- tests/unit/test_dev_scripts.py::test_gen_keys_main_writes_and_refuses_overwrite
attachments: []
acceptance: []
threat: info-disclosure
```
sys-plan:dev_keys:unbound

secret `dev_keys` has no code binding; add `frob:secret dev_keys` at the enforcing site (docs/strata/surface.md#directives-t-0080).
## Done report

Changed: scripts/gen_keys.py -- `frob:secret dev_keys` bound at main
(the one site that creates/handles the private key), commit b6f39ed.
Evidence: frob check no longer reports the SYS002 unbound-secret
finding; the attached pytest id exercises the overwrite-refusal
contract protecting the existing private key.
