'''Tests for the fix_spec.py command line interface.'''

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fix_spec import INVITE_PATH, INVITE_RESPONSE_REF, fix_spec, main

from spec_samples import RELEASE_TAG, SPEC_VERSION, make_spec


def test_usage_error_on_wrong_number_of_arguments(capsys: pytest.CaptureFixture[str]) -> None:
  assert main([]) == 2
  assert main(['only-input.json']) == 2
  assert main(['a', 'b', 'c', 'd']) == 2
  assert 'Usage:' in capsys.readouterr().err


def test_main_writes_patched_output(tmp_path: Path) -> None:
  src = tmp_path / 'in.json'
  dst = tmp_path / 'out.json'
  src.write_text(json.dumps(make_spec()), encoding='utf-8')

  assert main([str(src), str(dst)]) == 0

  raw = dst.read_text(encoding='utf-8')
  assert raw.endswith('\n')
  out = json.loads(raw)
  content = out['paths'][INVITE_PATH]['post']['responses']['200']['content']
  assert content['text/plain']['schema'] == {'$ref': INVITE_RESPONSE_REF}
  assert content['application/json']['schema'] == {'$ref': INVITE_RESPONSE_REF}
  assert content['text/json']['schema'] == {'$ref': INVITE_RESPONSE_REF}


def test_main_preserves_unrelated_content(tmp_path: Path) -> None:
  data = make_spec()
  src = tmp_path / 'in.json'
  dst = tmp_path / 'out.json'
  src.write_text(json.dumps(data), encoding='utf-8')

  main([str(src), str(dst)])

  out = json.loads(dst.read_text(encoding='utf-8'))
  assert out['paths']['/api/Other'] == data['paths']['/api/Other']
  assert out['components']['schemas']['Other'] == data['components']['schemas']['Other']


def test_main_warns_when_nothing_to_patch(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
  data = make_spec()
  fix_spec(data)  # consume the known issues so the next run has nothing to do

  src = tmp_path / 'in.json'
  dst = tmp_path / 'out.json'
  src.write_text(json.dumps(data), encoding='utf-8')

  assert main([str(src), str(dst)]) == 0
  assert 'warning' in capsys.readouterr().err
  assert json.loads(dst.read_text(encoding='utf-8')) == data


def test_main_warns_and_rewrites_version_when_tag_given(
  tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
  src = tmp_path / 'in.json'
  dst = tmp_path / 'out.json'
  src.write_text(json.dumps(make_spec()), encoding='utf-8')

  assert main([str(src), str(dst), RELEASE_TAG]) == 0

  err = capsys.readouterr().err
  assert 'warning' in err
  assert SPEC_VERSION in err and RELEASE_TAG in err
  assert json.loads(dst.read_text(encoding='utf-8'))['info']['version'] == RELEASE_TAG


def test_main_no_version_warning_when_tag_matches(
  tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
  data = make_spec()
  data['info']['version'] = RELEASE_TAG
  src = tmp_path / 'in.json'
  dst = tmp_path / 'out.json'
  src.write_text(json.dumps(data), encoding='utf-8')

  assert main([str(src), str(dst), RELEASE_TAG]) == 0
  assert 'rewriting' not in capsys.readouterr().err
