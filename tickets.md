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
