'''Regression test: the checked-in fixed spec must be reproducible.

Applies fix_spec.py to the checked-in original Kavita document and asserts the
result matches the checked-in fixed document, so the two cannot drift apart.
'''

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import fix_spec

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'kavita_0.9.1.4.json'
FIXED = ROOT / 'kavita_0.9.1.4.fixed.json'

# The release tag the downloaded spec corresponds to (kavita_<TAG>.json).
# Derived from the filename on purpose: no version is hard-coded in the tests.
RELEASE_TAG = ORIGINAL.stem.removeprefix('kavita_')

pytestmark = pytest.mark.skipif(
  not (ORIGINAL.is_file() and FIXED.is_file()),
  reason='checked-in spec files are not present',
)


def test_fixed_spec_is_reproducible() -> None:
  data: dict[str, Any] = json.loads(ORIGINAL.read_text(encoding='utf-8'))
  assert fix_spec.fix_spec(data, version=RELEASE_TAG) is True

  expected = json.loads(FIXED.read_text(encoding='utf-8'))
  assert data == expected


def test_spec_version_matches_release_tag() -> None:
  '''The upstream document should carry the release tag as `info.version`.

  Upstream currently ships the version one step behind the tag (the
  v0.9.1.4 document declares 0.9.1.1). While that mismatch remains, this
  test records it as xfail; fix_spec.py rewrites the version in the
  meantime (the Makefile passes the tag on the command line). When upstream
  aligns them, the test starts passing.
  '''
  data: dict[str, Any] = json.loads(ORIGINAL.read_text(encoding='utf-8'))
  spec_version = data['info']['version']
  if spec_version != RELEASE_TAG:
    pytest.xfail(
      f'upstream spec version {spec_version} does not match the release '
      f'tag {RELEASE_TAG} (fix_spec.py rewrites it)'
    )
  assert spec_version == RELEASE_TAG
