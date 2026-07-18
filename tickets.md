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
state: queued
kind: feature
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope:
- design/** docs/workflow/strata-system-model.md
evidence: []
attachments: []
acceptance:
- given the committed design/feldspar.strata, when frob sys audit runs, then it exits
  with PROVED or a named-gap state documented in docs/workflow/strata-system-model.md
threat: null
```
Pilot agent task: model feldspar's real topology (pyo3 rust core, solver registry, planner, domain packages, FEA/spice engine subprocess boundaries, regolith pack bridge, dev key store) in strata and drive frob sys plan/doc/audit honestly.

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
state: queued
kind: security
origin: agent
created: '2026-07-18'
blocked_by: []
parent: null
scope: []
evidence: []
attachments: []
acceptance: []
threat: info-disclosure
```
sys-plan:dev_keys:unbound

secret `dev_keys` has no code binding; add `frob:secret dev_keys` at the enforcing site (docs/strata/surface.md#directives-t-0080).
