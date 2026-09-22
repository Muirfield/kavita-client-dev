'''Audits over the quirks registry (kavita_quirks.yaml).

The registry is the single source of truth for fix_spec.py patch data,
the Schemathesis exclusion lists, and the docs' quirk facts. These tests
keep it honest:

- well-formedness (ids, categories, endpoint shapes),
- fix_spec <-> registry agreement (fix endpoints exist in the real spec;
  every fix is referenced by a quirk),
- covered_by references resolve to real test functions,
- the exclusion derivation produces the expected lists per mode.
'''

from __future__ import annotations

import re
from pathlib import Path

from fix_spec import INVITE_PATH, STRING_BODY_ENDPOINTS, load_registry
from schemathesis_exclusions import exclusions

ROOT = Path(__file__).resolve().parents[1]
REAL_SPEC = ROOT / 'kavita_0.9.1.4.json'

VALID_CATEGORIES = {
  'dead-quirk', 'destructive', 'fix-dependent', 'stateful-id',
  'undocumented-auth', 'server-error-on-garbage', 'schema-mismatch',
  'resolved', 'infra',
}
VALID_RULES = {'include', 'exclude-both', 'exclude-nightly'}


def _registry() -> dict:
  return load_registry()


def test_registry_is_well_formed() -> None:
  registry = _registry()
  fix_ids = [fix['id'] for fix in registry['fixes']]
  assert len(fix_ids) == len(set(fix_ids)), 'duplicate fix ids'
  quirk_ids = [quirk['id'] for quirk in registry['quirks']]
  assert len(quirk_ids) == len(set(quirk_ids)), 'duplicate quirk ids'
  for quirk in registry['quirks']:
    assert quirk['category'] in VALID_CATEGORIES, quirk['id']
    assert quirk.get('schemathesis', 'include') in VALID_RULES, quirk['id']
    assert quirk['status'] in {'open', 'resolved'}, quirk['id']
    for endpoint in quirk.get('endpoints', []):
      assert set(endpoint) == {'path', 'method'}, quirk['id']
    if quirk.get('fix_id'):
      assert quirk['fix_id'] in fix_ids, f"{quirk['id']} references missing {quirk['fix_id']}"


def test_every_fix_is_referenced_by_a_quirk() -> None:
  registry = _registry()
  referenced = {quirk.get('fix_id') for quirk in registry['quirks']}
  for fix in registry['fixes']:
    if fix['id'] != 'F4':  # the version rewrite has no endpoints/quirk entry
      assert fix['id'] in referenced, f'fix {fix["id"]} has no quirk entry'


def test_fix_endpoints_exist_in_the_real_spec() -> None:
  import json
  spec = json.loads(REAL_SPEC.read_text(encoding='utf-8'))
  for fix in _registry()['fixes']:
    for endpoint in fix.get('endpoints', []):
      assert endpoint['path'] in spec['paths'], f"{fix['id']}: {endpoint['path']} not in the spec"
      assert endpoint['method'] in spec['paths'][endpoint['path']], (
        f"{fix['id']}: {endpoint['method']} {endpoint['path']} not in the spec"
      )


def test_fix_spec_data_matches_registry() -> None:
  '''fix_spec.py builds its constants from the registry; spot-check the
  public names still agree with the historical values.'''
  assert INVITE_PATH == '/api/Account/invite'
  assert STRING_BODY_ENDPOINTS['/api/Health'] == 'get'
  assert len(STRING_BODY_ENDPOINTS) == 8


def _has_test(reference: str) -> bool:
  module, _, test_name = reference.partition('::')
  path = ROOT / module
  if not path.is_file():
    return False
  source = path.read_text(encoding='utf-8')
  if test_name:
    return re.search(rf'^def {re.escape(test_name)}\b', source, re.MULTILINE) is not None
  return re.search(r'^def test_', source, re.MULTILINE) is not None


def test_covered_by_references_resolve() -> None:
  unresolved = []
  for quirk in _registry()['quirks']:
    for reference in quirk.get('covered_by', []):
      if not _has_test(reference):
        unresolved.append((quirk['id'], reference))
  assert not unresolved, f'covered_by references do not resolve: {unresolved}'


def test_exclusion_derivation_release() -> None:
  '''Release excludes exactly the exclude-both categories (dead quirks,
  destructive ops, and the prototype-triaged buckets) — with the curated
  entries present and no fix-dependent endpoint leaking in.'''
  excluded = exclusions(_registry(), 'release')
  curated = {
    ('/api/License/info', 'get'): 'Q10a',
    ('/api/Plugin/authkey-expires', 'get'): 'Q10b',
    ('/api/Users/tokens', 'get'): 'Q10c',
    ('/api/Series/match-info', 'get'): 'Q15a',
    ('/api/Library/delete-multiple', 'delete'): 'Q18a',
    ('/api/Settings/reset', 'post'): 'D01',
    ('/api/Settings', 'post'): 'D02',
    ('/api/Server/cleanup', 'post'): 'D03',
    ('/api/Users/delete-user', 'delete'): 'D04',
    ('/api/Series/delete-multiple', 'post'): 'D05',
    ('/api/Chapter', 'delete'): 'D06',
    ('/api/Chapter/delete-multiple', 'post'): 'D07',
    ('/api/Account/register', 'post'): 'D08',
  }
  for endpoint, quirk_id in curated.items():
    assert excluded.get(endpoint) == quirk_id, endpoint
  # The fix-dependent endpoints are excluded on nightly only.
  for quirk_id in ('Q01', 'Q02', 'Q03', 'Q05', 'Q06', 'Q24', 'Q25'):
    assert quirk_id not in excluded.values(), quirk_id
  # The prototype buckets are present (spot-check one member each).
  assert ('/api/Account/invite-url', 'get') == ('/api/Account/invite-url', 'get')
  assert any(quirk == 'Q26' for quirk in excluded.values()), 'Q26 bucket missing'
  assert any(quirk == 'Q27' for quirk in excluded.values()), 'Q27 bucket missing'
  assert any(quirk == 'Q28' for quirk in excluded.values()), 'Q28 bucket missing'


def test_exclusion_derivation_nightly() -> None:
  '''Nightly excludes every release endpoint (a fix-dependent entry may
  override a bucket's quirk id for the same endpoint) plus the
  fix-dependent endpoints.'''
  release = exclusions(_registry(), 'release')
  nightly = exclusions(_registry(), 'nightly')
  assert set(release) <= set(nightly), set(release) - set(nightly)
  for quirk_id, path, method in [
    ('Q01', '/api/Account/invite', 'post'),
    ('Q02', '/api/Series/v2', 'post'),
    ('Q02', '/api/Settings/metadata-settings', 'get'),
    ('Q02', '/api/Tachiyomi/latest-chapter', 'get'),
    ('Q05', '/api/Stats/server/file-breakdown', 'get'),
    ('Q06', '/api/Metadata/series-detail-plus', 'get'),
    ('Q24', '/api/Annotation/all-for-series', 'get'),
    ('Q25', '/api/Reader/prompt-reread/chapter', 'get'),
    ('Q25', '/api/Reader/prompt-reread/series', 'get'),
    ('Q25', '/api/Reader/prompt-reread/volume', 'get'),
    ('Q31', '/api/Stats/device/device-type', 'get'),
    ('Q32', '/api/Stream/sidenav', 'get'),
  ]:
    assert nightly.get((path, method)) == quirk_id, f'{path} {method}'
  # The bare-string endpoints need no fix-dependent exclusion even on
  # nightly (text/plain + string schema validates fine; the JSON crash was
  # client-side) — though some appear in the auth bucket for other reasons.
  for path, method in STRING_BODY_ENDPOINTS.items():
    assert nightly.get((path, method)) != 'Q03', f'{path} {method}'


def test_provider_names_are_real_spec_parameters() -> None:
  '''kavita_providers.yaml keys must be real spec parameter names —
  a typo there would silently disable a provider.'''
  import json
  import yaml
  spec = json.loads(REAL_SPEC.read_text(encoding='utf-8'))
  parameter_names = {
    p.get('name')
    for item in spec['paths'].values()
    for op in item.values()
    if isinstance(op, dict)
    for p in op.get('parameters', [])
  }
  providers = yaml.safe_load((ROOT / 'kavita_providers.yaml').read_text(encoding='utf-8'))
  mapped = set(providers.get('values', {})) | set(providers.get('static', {}))
  unknown = mapped - parameter_names
  assert not unknown, f'provider names missing from the spec: {sorted(unknown)}'
  for entry in providers.get('no-provider', []):
    assert entry['path'] in spec['paths'], entry['path']
    assert entry['method'] in spec['paths'][entry['path']], f'{entry["path"]} {entry["method"]}'
