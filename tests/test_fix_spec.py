'''Unit tests for fix_spec.py, built on small synthetic OpenAPI documents.'''

from __future__ import annotations

import copy
from typing import Any

from fix_spec import (
  ANNOTATION_ALL_FOR_SERIES_PATH,
  ANNOTATION_DTO_REF,
  FILE_BREAKDOWN_PATH,
  FILE_BREAKDOWN_REF,
  INVITE_PATH,
  INVITE_RESPONSE_REF,
  DEVICE_TYPE_PATH,
  PROMPT_REREAD_ENDPOINTS,
  STRING_BODY_CONTENT,
  STRING_BODY_ENDPOINTS,
  STRING_STAT_COUNT_REF,
  fix_annotation_response,
  fix_device_type_response,
  fix_file_breakdown_response,
  fix_invite_response,
  fix_nullable_enums,
  fix_nullable_refs,
  fix_nullable_response_refs,
  fix_spec,
  fix_spec_version,
  fix_string_bodies,
)

from spec_samples import RELEASE_TAG, make_spec


def _invite_content(data: dict[str, Any]) -> dict[str, Any]:
  return data['paths'][INVITE_PATH]['post']['responses']['200']['content']


# --- fix_invite_response ----------------------------------------------------


def test_fix_invite_response_rewrites_all_string_schemas() -> None:
  data = make_spec()
  assert fix_invite_response(data) is True
  for media in _invite_content(data).values():
    assert media['schema'] == {'$ref': INVITE_RESPONSE_REF}


def test_fix_invite_response_leaves_other_paths_alone() -> None:
  data = make_spec()
  fix_invite_response(data)
  other = data['paths']['/api/Other']['get']['responses']['200']['content']['text/plain']
  assert other['schema'] == {'type': 'string'}


def test_fix_invite_response_ignores_non_string_schemas() -> None:
  data = make_spec()
  content = _invite_content(data)
  content['application/json']['schema'] = {'type': 'object', 'properties': {}}
  assert fix_invite_response(data) is True
  assert content['application/json']['schema'] == {'type': 'object', 'properties': {}}
  assert content['text/plain']['schema'] == {'$ref': INVITE_RESPONSE_REF}
  assert content['text/json']['schema'] == {'$ref': INVITE_RESPONSE_REF}


def test_fix_invite_response_returns_false_when_nothing_to_patch() -> None:
  data = make_spec()
  for media in _invite_content(data).values():
    media['schema'] = {'$ref': INVITE_RESPONSE_REF}
  before = copy.deepcopy(data)
  assert fix_invite_response(data) is False
  assert data == before


def test_fix_invite_response_handles_missing_path() -> None:
  data: dict[str, Any] = {'paths': {}, 'components': {'schemas': {}}}
  before = copy.deepcopy(data)
  assert fix_invite_response(data) is False
  assert data == before


# --- fix_nullable_enums -----------------------------------------------------


def test_fix_nullable_enums_rewrites_known_fields() -> None:
  data = make_spec()
  assert fix_nullable_enums(data) is True
  series = data['components']['schemas']['SeriesDto']['properties']
  chapter = data['components']['schemas']['ChapterDto']['properties']
  settings = data['components']['schemas']['MetadataSettingsDto']['properties']
  tachiyomi = data['components']['schemas']['TachiyomiChapterDto']['properties']
  assert series['metadataProviderOverride'] == {
    'allOf': [{'$ref': '#/components/schemas/MetadataProvider'}],
    'nullable': True,
  }
  assert chapter['format'] == {
    'allOf': [{'$ref': '#/components/schemas/MangaFormat'}],
    'nullable': True,
  }
  assert settings['filterAboveWeight'] == {
    'allOf': [{'$ref': '#/components/schemas/TagWeight'}],
    'nullable': True,
  }
  assert tachiyomi['format'] == {
    'allOf': [{'$ref': '#/components/schemas/MangaFormat'}],
    'nullable': True,
  }


def test_fix_nullable_enums_leaves_unlisted_fields_alone() -> None:
  data = make_spec()
  fix_nullable_enums(data)
  assert data['components']['schemas']['SeriesDto']['properties']['untouchedField'] == {
    '$ref': '#/components/schemas/Other'
  }


def test_fix_nullable_enums_leaves_already_nullable_fields_unchanged() -> None:
  data = make_spec()
  props = data['components']['schemas']['SeriesDto']['properties']
  props['metadataProviderOverride'] = {
    'allOf': [{'$ref': '#/components/schemas/MetadataProvider'}],
    'nullable': True,
  }
  fix_nullable_enums(data)  # ChapterDto.format still gets patched here
  assert props['metadataProviderOverride'] == {
    'allOf': [{'$ref': '#/components/schemas/MetadataProvider'}],
    'nullable': True,
  }


def test_fix_nullable_enums_returns_false_when_everything_already_nullable() -> None:
  data = make_spec()
  series = data['components']['schemas']['SeriesDto']['properties']
  chapter = data['components']['schemas']['ChapterDto']['properties']
  settings = data['components']['schemas']['MetadataSettingsDto']['properties']
  tachiyomi = data['components']['schemas']['TachiyomiChapterDto']['properties']
  series['metadataProviderOverride'] = {
    'allOf': [{'$ref': '#/components/schemas/MetadataProvider'}],
    'nullable': True,
  }
  chapter['format'] = {
    'allOf': [{'$ref': '#/components/schemas/MangaFormat'}],
    'nullable': True,
  }
  settings['filterAboveWeight'] = {
    'allOf': [{'$ref': '#/components/schemas/TagWeight'}],
    'nullable': True,
  }
  tachiyomi['format'] = {
    'allOf': [{'$ref': '#/components/schemas/MangaFormat'}],
    'nullable': True,
  }
  before = copy.deepcopy(data)
  assert fix_nullable_enums(data) is False
  assert data == before


def test_fix_nullable_enums_handles_missing_schemas() -> None:
  data: dict[str, Any] = {'components': {'schemas': {}}}
  assert fix_nullable_enums(data) is False


# --- fix_string_bodies ------------------------------------------------------


def _string_body_content(data: dict[str, Any], path: str, method: str) -> dict[str, Any]:
  return data['paths'][path][method]['responses']['200']['content']


def test_fix_string_bodies_rewrites_known_endpoints() -> None:
  data = make_spec()
  assert fix_string_bodies(data) is True
  for path, method in STRING_BODY_ENDPOINTS.items():
    assert _string_body_content(data, path, method) == STRING_BODY_CONTENT


def test_fix_string_bodies_leaves_other_paths_alone() -> None:
  data = make_spec()
  fix_string_bodies(data)
  other = data['paths']['/api/Other']['get']['responses']['200']['content']
  assert other == {'text/plain': {'schema': {'type': 'string'}}}


def test_fix_string_bodies_ignores_non_string_schemas() -> None:
  data = make_spec()
  for path, method in STRING_BODY_ENDPOINTS.items():
    content = _string_body_content(data, path, method)
    for media in content.values():
      media['schema'] = {'$ref': '#/components/schemas/Other'}
  before = copy.deepcopy(data)
  assert fix_string_bodies(data) is False
  assert data == before


def test_fix_string_bodies_returns_false_when_already_rewritten() -> None:
  data = make_spec()
  fix_string_bodies(data)
  before = copy.deepcopy(data)
  assert fix_string_bodies(data) is False
  assert data == before


def test_fix_string_bodies_handles_missing_paths() -> None:
  data: dict[str, Any] = {'paths': {}}
  assert fix_string_bodies(data) is False


# --- fix_spec_version -------------------------------------------------------


def test_fix_spec_version_rewrites_mismatched_version() -> None:
  data = make_spec()
  assert fix_spec_version(data, RELEASE_TAG) is True
  assert data['info']['version'] == RELEASE_TAG


def test_fix_spec_version_returns_false_when_matching() -> None:
  data = make_spec()
  data['info']['version'] = RELEASE_TAG
  before = copy.deepcopy(data)
  assert fix_spec_version(data, RELEASE_TAG) is False
  assert data == before


def test_fix_spec_version_handles_missing_info() -> None:
  data: dict[str, Any] = {'paths': {}}
  before = copy.deepcopy(data)
  assert fix_spec_version(data, RELEASE_TAG) is False
  assert data == before


# --- fix_spec ---------------------------------------------------------------


def test_fix_spec_patches_all_known_issues() -> None:
  data = make_spec()
  assert fix_spec(data, version=RELEASE_TAG) is True
  for media in _invite_content(data).values():
    assert media['schema'] == {'$ref': INVITE_RESPONSE_REF}
  series = data['components']['schemas']['SeriesDto']['properties']
  assert series['metadataProviderOverride']['nullable'] is True
  for path, method in STRING_BODY_ENDPOINTS.items():
    assert _string_body_content(data, path, method) == STRING_BODY_CONTENT
  assert data['info']['version'] == RELEASE_TAG


def test_fix_spec_is_idempotent_and_leaves_document_unchanged() -> None:
  data = make_spec()
  assert fix_spec(data, version=RELEASE_TAG) is True
  after_first = copy.deepcopy(data)
  assert fix_spec(data, version=RELEASE_TAG) is False
  assert data == after_first


# --- fix_file_breakdown_response ---------------------------------------------


def _file_breakdown_content(data: dict[str, Any]) -> dict[str, Any]:
  return data['paths'][FILE_BREAKDOWN_PATH]['get']['responses']['200']['content']


def test_fix_file_breakdown_rewrites_all_media_types() -> None:
  data = make_spec()
  assert fix_file_breakdown_response(data) is True
  for media in _file_breakdown_content(data).values():
    assert media['schema'] == {'$ref': FILE_BREAKDOWN_REF}


def test_fix_file_breakdown_leaves_other_paths_alone() -> None:
  data = make_spec()
  fix_file_breakdown_response(data)
  other = data['paths']['/api/Other']['get']['responses']['200']['content']
  assert other == {'text/plain': {'schema': {'type': 'string'}}}


def test_fix_file_breakdown_returns_false_when_already_rewritten() -> None:
  data = make_spec()
  fix_file_breakdown_response(data)
  before = copy.deepcopy(data)
  assert fix_file_breakdown_response(data) is False
  assert data == before


def test_fix_file_breakdown_ignores_non_array_schemas() -> None:
  data = make_spec()
  for media in _file_breakdown_content(data).values():
    media['schema'] = {'$ref': '#/components/schemas/Other'}
  before = copy.deepcopy(data)
  assert fix_file_breakdown_response(data) is False
  assert data == before


def test_fix_file_breakdown_handles_missing_paths() -> None:
  data: dict[str, Any] = {'paths': {}}
  assert fix_file_breakdown_response(data) is False


# --- fix_nullable_refs -------------------------------------------------------


def test_fix_nullable_refs_rewrites_known_fields() -> None:
  data = make_spec()
  assert fix_nullable_refs(data) is True
  props = data['components']['schemas']['SeriesDetailPlusDto']['properties']
  assert props['recommendations'] == {
    'allOf': [{'$ref': '#/components/schemas/Other'}], 'nullable': True,
  }
  assert props['series'] == {
    'allOf': [{'$ref': '#/components/schemas/Other'}], 'nullable': True,
  }
  assert props['untouchedField'] == {'$ref': '#/components/schemas/Other'}


def test_fix_nullable_refs_leaves_already_nullable_fields_unchanged() -> None:
  data = make_spec()
  fix_nullable_refs(data)
  before = copy.deepcopy(data)
  assert fix_nullable_refs(data) is False
  assert data == before


def test_fix_nullable_refs_returns_false_when_nothing_to_patch() -> None:
  data = make_spec()
  for schema in ('SeriesDetailPlusDto', 'RereadDto', 'SideNavStreamDto'):
    del data['components']['schemas'][schema]
  before = copy.deepcopy(data)
  assert fix_nullable_refs(data) is False
  assert data == before


# --- fix_annotation_response (Fix 7) -----------------------------------------


def _annotation_content(data: dict[str, Any]) -> dict[str, Any]:
  return data['paths'][ANNOTATION_ALL_FOR_SERIES_PATH]['get']['responses']['200']['content']


def test_fix_annotation_rewrites_all_media_types() -> None:
  data = make_spec()
  assert fix_annotation_response(data) is True
  for media in _annotation_content(data).values():
    assert media['schema'] == {'type': 'array', 'items': {'$ref': ANNOTATION_DTO_REF}}


def test_fix_annotation_leaves_other_paths_alone() -> None:
  data = make_spec()
  fix_annotation_response(data)
  other = data['paths']['/api/Other']['get']['responses']['200']['content']
  assert other == {'text/plain': {'schema': {'type': 'string'}}}


def test_fix_annotation_returns_false_when_already_rewritten() -> None:
  data = make_spec()
  fix_annotation_response(data)
  before = copy.deepcopy(data)
  assert fix_annotation_response(data) is False
  assert data == before


def test_fix_annotation_handles_missing_paths() -> None:
  data: dict[str, Any] = {'paths': {}}
  assert fix_annotation_response(data) is False


# --- fix_nullable_response_refs (Fix 8) --------------------------------------


def test_fix_nullable_response_refs_rewrites_all_endpoints() -> None:
  data = make_spec()
  assert fix_nullable_response_refs(data) is True
  for path, method in PROMPT_REREAD_ENDPOINTS.items():
    content = data['paths'][path][method]['responses']['200']['content']
    for media in content.values():
      assert media['schema'] == {'allOf': [{'$ref': '#/components/schemas/RereadDto'}], 'nullable': True}


def test_fix_nullable_response_refs_leaves_other_paths_alone() -> None:
  data = make_spec()
  fix_nullable_response_refs(data)
  other = data['paths']['/api/Other']['get']['responses']['200']['content']
  assert other == {'text/plain': {'schema': {'type': 'string'}}}


def test_fix_nullable_response_refs_returns_false_when_already_rewritten() -> None:
  data = make_spec()
  fix_nullable_response_refs(data)
  before = copy.deepcopy(data)
  assert fix_nullable_response_refs(data) is False
  assert data == before


def test_fix_nullable_response_refs_handles_missing_paths() -> None:
  data: dict[str, Any] = {'paths': {}}
  assert fix_nullable_response_refs(data) is False


# --- F9 nullable fields + F10 device-type (canary findings) -------------------


def test_fix_nullable_refs_covers_canary_fields() -> None:
  '''F9 shares the F6 mechanism: the canary-found fields are rewritten too.'''
  data = make_spec()
  fix_nullable_refs(data)
  reread = data['components']['schemas']['RereadDto']['properties']
  assert reread['chapterOnContinue'] == {'allOf': [{'$ref': '#/components/schemas/Other'}], 'nullable': True}
  assert reread['chapterOnReread'] == {'allOf': [{'$ref': '#/components/schemas/Other'}], 'nullable': True}
  sidenav = data['components']['schemas']['SideNavStreamDto']['properties']
  assert sidenav['externalSource'] == {'allOf': [{'$ref': '#/components/schemas/Other'}], 'nullable': True}


def test_fix_device_type_rewrites_all_media_types() -> None:
  data = make_spec()
  assert fix_device_type_response(data) is True
  content = data['paths'][DEVICE_TYPE_PATH]['get']['responses']['200']['content']
  for media in content.values():
    assert media['schema'] == {'type': 'array', 'items': {'$ref': STRING_STAT_COUNT_REF}}


def test_fix_device_type_returns_false_when_already_rewritten() -> None:
  data = make_spec()
  fix_device_type_response(data)
  before = copy.deepcopy(data)
  assert fix_device_type_response(data) is False
  assert data == before


def test_fix_device_type_handles_missing_paths() -> None:
  data: dict[str, Any] = {'paths': {}}
  assert fix_device_type_response(data) is False
