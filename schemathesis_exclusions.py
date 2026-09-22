'''Derive Schemathesis exclusion lists from the quirks registry.

`kavita_quirks.yaml` is the single source of truth; the exclusion lists
for both modes are generated (never hand-edited) via
`exclusions(registry, mode)`. The Makefile `schemathesis-*` targets are
expected to render this into the TOML Schemathesis consumes.
'''

from __future__ import annotations

from typing import Any

from fix_spec import load_registry


def exclusions(registry: dict[str, Any], mode: str) -> dict[tuple[str, str], str]:
  '''Map (path, method) -> quirk id for the endpoints to exclude in `mode`.

  `mode` is `release` or `nightly`. Rules come from each quirk's
  `schemathesis` field:
  - `include`: never excluded,
  - `exclude-both`: excluded in both modes (dead quirks, destructive ops,
    the prototype-triaged buckets),
  - `exclude-nightly`: excluded only on nightly (the raw dev spec still
    carries the fix_spec bug).

  `exclude-both` entries are applied first and `exclude-nightly` last, so
  a fix-dependent endpoint always wins over a bucket that also contains it
  (e.g. `/api/Account/invite` is in both Q01 and the stateful-id bucket).
  '''
  excluded: dict[tuple[str, str], str] = {}
  for rule in ('exclude-both', 'exclude-nightly'):
    for quirk in registry['quirks']:
      if quirk.get('schemathesis', 'include') != rule:
        continue
      if rule == 'exclude-nightly' and mode != 'nightly':
        continue
      for endpoint in quirk.get('endpoints', []):
        excluded[(endpoint['path'], endpoint['method'])] = quirk['id']
  return excluded
