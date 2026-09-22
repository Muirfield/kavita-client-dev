#!/usr/bin/env python3
'''Run the Schemathesis canary (docs/TODO-schemathesis.md).

    schemathesis_canary.py SPEC MODE STATE REPORT

- SPEC: OpenAPI document to test (patched for release, raw for nightly).
- MODE: `release` or `nightly` — selects the registry exclusion list.
- STATE: the JSON written by `schemathesis_stack.py up`.
- REPORT: JUnit XML path for the run.

The exclusion lists are generated from `kavita_quirks.yaml`
(`schemathesis_exclusions.py`); the date-time tolerance (Q29a/Q29b) comes
from `schemathesis.toml` (validate-formats = false). Exit code mirrors
Schemathesis: non-zero when failures are found.
'''

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from schemathesis_exclusions import exclusions
from fix_spec import load_registry

ROOT = Path(__file__).resolve().parent
CHECKS = 'status_code_conformance,response_schema_conformance,content_type_conformance,not_a_server_error'

# Parameter names Schemathesis generates valid values for on its own —
# everything else on a bucket op must be provider-covered to be re-included.
ALLOWED_GENERIC = {
  'pageNumber', 'pageSize', 'count', 'year', 'booksOnly', 'saveProgress',
  'includeChapterAndFiles', 'force', 'withBaseUrl', 'authKeyName',
}
# Bucket quirks the value providers can re-include (never fix-dependent ones).
BUCKET_QUIRKS = {'Q26', 'Q27', 'Q28'}


def _provider_names() -> set[str]:
  registry = yaml.safe_load((ROOT / 'kavita_providers.yaml').read_text(encoding='utf-8'))
  return set(registry.get('values', {})) | set(registry.get('static', {}))


def _reinclude(spec: dict, registry: dict) -> set[tuple[str, str]]:
  '''Bucket ops whose every parameter is provider-covered (phase 2).'''
  provider_names = _provider_names()
  registry_data = yaml.safe_load((ROOT / 'kavita_providers.yaml').read_text(encoding='utf-8'))
  no_provider = {
    (entry['path'], entry['method']) for entry in registry_data.get('no-provider', [])
  }
  reinclude: set[tuple[str, str]] = set()
  for quirk in registry['quirks']:
    if quirk['id'] not in BUCKET_QUIRKS:
      continue
    for endpoint in quirk.get('endpoints', []):
      path, method = endpoint['path'], endpoint['method']
      op = spec['paths'].get(path, {}).get(method)
      if op is None or op.get('requestBody'):
        continue
      parameter_names = {p['name'] for p in op.get('parameters', [])}
      if (path, method) in no_provider:
        continue
      if parameter_names <= (provider_names | ALLOWED_GENERIC):
        reinclude.add((path, method))
  return reinclude


def main() -> None:
  if len(sys.argv) != 5:
    sys.exit('usage: schemathesis_canary.py SPEC MODE STATE REPORT')
  spec_path, mode, state_path, report = sys.argv[1:5]
  if mode not in ('release', 'nightly'):
    sys.exit(f'unknown mode {mode}')
  state = json.loads(Path(state_path).read_text(encoding='utf-8'))
  registry = load_registry()
  spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
  excluded = exclusions(registry, mode)

  reinclude = _reinclude(spec, registry)
  for endpoint in reinclude:
    # Only lift bucket exclusions (Q26/Q27/Q28); a fix-dependent entry for
    # the same endpoint (nightly raw spec) must stay excluded.
    if excluded.get(endpoint) in BUCKET_QUIRKS:
      excluded.pop(endpoint, None)

  args = [
    x
    for path in sorted({path for (path, _method) in excluded})
    for x in ('--exclude-path', path)
  ]
  command = [
    'schemathesis', 'run', spec_path,
    '--url', f"http://127.0.0.1:{state['port']}",
    '--header', f"Authorization: Bearer {state['token']}",
    '--phases', 'coverage',
    '--checks', CHECKS,
    '--max-examples', '1',
    '--workers', '4',
    '--request-timeout', '20',
    '--report', 'junit',
    '--report-junit-path', report,
    *args,
  ]
  executable = shutil.which('schemathesis')
  if executable is None:
    sys.exit('schemathesis not found on PATH (run through ./pys.sh)')
  Path(report).parent.mkdir(parents=True, exist_ok=True)
  env = os.environ.copy()
  env['SCHEMATHESIS_STATE'] = state_path
  print(f'exclusions: {len(excluded)}, provider re-included: {len(reinclude)} ops')
  result = subprocess.run([executable, *command[1:]], cwd=ROOT, env=env)
  sys.exit(result.returncode)


if __name__ == '__main__':
  main()
