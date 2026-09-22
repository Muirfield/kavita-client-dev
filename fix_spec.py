#!/usr/bin/env python3
'''Fix known issues in the Kavita OpenAPI document before code generation.

The patch *data* (endpoints and fields) lives in `kavita_quirks.yaml`, the
single source of truth shared with the Schemathesis exclusion lists and
the docs — this module only carries the patch *logic*. The quirks registry
documents each fix (F1–F6) and each known server behavior (Qxx/Dxx).

The transformations:

* F1 — `POST /api/Account/invite` is documented as returning a plain
  string, but the server returns an `InviteUserResponse` object. The
  response is pointed at the correct schema.

* F2/F6 — enum and object-ref fields the server may send as `null` but
  the document declares non-nullable, so the generated client crashes.
  `nullable: true` next to a plain `$ref` is ignored by
  openapi-python-client, so the fields are rewritten to the `allOf` +
  `nullable` form it honors.

* F3 — endpoints returning bare (non-JSON) text bodies even though the
  document declares JSON-ish media types. Combined with the generator's
  `text/plain` -> `application/json` content-type override, the generated
  client parses them with `response.json()` and crashes. The media type
  is rewritten so the generator reads `response.text` instead.

* F4 — `info.version` in the tagged release document does not match the
  tag itself, so the generated client would carry the wrong version.
  When the release tag is given on the command line, the version is
  rewritten to match it, with a warning on stderr.

* F5 — `GET /api/Stats/server/file-breakdown` documents its 200 response
  as an *array*, but the server sends a single object. The response
  schema is rewritten to the object ref.

* F7 — `GET /api/Annotation/all-for-series` documents its 200 response as
  one `AnnotationDto`, but the server sends a list (the controller
  declares `ActionResult<AnnotationDto>` while returning
  `List<AnnotationDto>`). The response schema is rewritten to an array.

* F8 — the three `Reader/prompt-reread/*` endpoints document a
  non-nullable `RereadDto`, but the server sends `null` when no reread is
  due. The response refs are marked nullable with the `allOf` form.
'''

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path(__file__).with_name('kavita_quirks.yaml')


def load_registry() -> dict[str, Any]:
  '''Load the quirks registry (single source of truth for patch data).'''
  with open(REGISTRY_PATH, encoding='utf-8') as handle:
    return yaml.safe_load(handle)


def _registry_fix(fix_id: str) -> dict[str, Any]:
  for fix in load_registry()['fixes']:
    if fix['id'] == fix_id:
      return fix
  raise KeyError(f'fix {fix_id} not found in {REGISTRY_PATH}')


def _fix_endpoints(fix_id: str) -> dict[str, str]:
  return {entry['path']: entry['method'] for entry in _registry_fix(fix_id).get('endpoints', [])}


def _fix_fields(fix_id: str) -> dict[str, list[str]]:
  '''Registry `fields` (schema/field pairs) grouped by schema.'''
  grouped: dict[str, list[str]] = {}
  for entry in _registry_fix(fix_id).get('fields', []):
    grouped.setdefault(entry['schema'], []).append(entry['field'])
  return grouped


INVITE_PATH = next(iter(_fix_endpoints('F1')))
INVITE_RESPONSE_REF = '#/components/schemas/InviteUserResponse'

# Schema name -> enum fields the server may send as null.
NULLABLE_ENUM_FIELDS = _fix_fields('F2')

# Fix 5: the file-breakdown response is a single object, not an array of
# objects (verified against the live server 2026-09-21).
FILE_BREAKDOWN_PATH = next(iter(_fix_endpoints('F5')))
FILE_BREAKDOWN_REF = '#/components/schemas/FileExtensionBreakdownDto'

# Fix 6: SeriesDetailPlusDto object-ref fields the server may send as null
# (verified against the live server 2026-09-21).
NULLABLE_REF_FIELDS = _fix_fields('F6')
# Fix 9: more nullable object refs found by the Schemathesis canary.
for _schema, _fields in _fix_fields('F9').items():
  NULLABLE_REF_FIELDS.setdefault(_schema, []).extend(_fields)

# Fix 7: the annotation list response is an array, not one object
# (found by the Schemathesis prototype 2026-09-21).
ANNOTATION_ALL_FOR_SERIES_PATH = next(iter(_fix_endpoints('F7')))
ANNOTATION_DTO_REF = '#/components/schemas/AnnotationDto'

# Fix 10: the device-type response is an array, not one object
# (found by the Schemathesis canary 2026-09-21).
DEVICE_TYPE_PATH = next(iter(_fix_endpoints('F10')))
STRING_STAT_COUNT_REF = '#/components/schemas/StringStatCount'

# Fix 8: the prompt-reread responses may be null (found by the
# Schemathesis prototype 2026-09-21).
PROMPT_REREAD_ENDPOINTS = _fix_endpoints('F8')

# Endpoints whose 200 response body is bare (non-JSON) text even though the
# document declares JSON-ish media types for it. The generator's
# content-type override (openapi-client-config.yml) maps `text/plain` to
# `application/json`, so the generated client calls response.json() and
# crashes on these bodies. Rewriting the media type to a parametrized
# `text/plain` dodges the override (which matches exact keys) and makes the
# generator read `response.text` instead.
STRING_BODY_ENDPOINTS = _fix_endpoints('F3')
STRING_BODY_CONTENT = {'text/plain; charset=utf-8': {'schema': {'type': 'string'}}}


def fix_invite_response(data: dict[str, Any]) -> bool:
  '''Patch the invite response schema. Return `True` if anything was patched.'''
  responses = (
    data.get('paths', {})
    .get(INVITE_PATH, {})
    .get('post', {})
    .get('responses', {})
  )
  patched = False
  for response in responses.values():
    for media in response.get('content', {}).values():
      if media.get('schema') == {'type': 'string'}:
        media['schema'] = {'$ref': INVITE_RESPONSE_REF}
        patched = True
  return patched


def _mark_nullable_ref(prop: dict[str, Any]) -> bool:
  '''Rewrite a property to the `allOf` + `nullable` form the generator
  honors (a bare `$ref` with `nullable: true` is ignored by
  openapi-python-client). Return `True` if the property was rewritten.'''
  ref = prop.get('$ref') if isinstance(prop, dict) else None
  if not isinstance(ref, str) or prop.get('nullable'):
    return False
  prop.clear()
  prop.update({'allOf': [{'$ref': ref}], 'nullable': True})
  return True


def fix_nullable_enums(data: dict[str, Any]) -> bool:
  '''Mark known nullable enum fields as nullable. Return `True` if anything was patched.'''
  schemas = data.get('components', {}).get('schemas', {})
  patched = False
  for schema_name, fields in NULLABLE_ENUM_FIELDS.items():
    properties = schemas.get(schema_name, {}).get('properties', {})
    for field in fields:
      prop = properties.get(field)
      if isinstance(prop, dict):
        patched |= _mark_nullable_ref(prop)
  return patched


def fix_nullable_refs(data: dict[str, Any]) -> bool:
  '''Mark known nullable object-ref fields as nullable (Fix 6).

  Same `allOf` mechanism as the enum fields (Fix 2). Return `True` if
  anything was patched.
  '''
  schemas = data.get('components', {}).get('schemas', {})
  patched = False
  for schema_name, fields in NULLABLE_REF_FIELDS.items():
    properties = schemas.get(schema_name, {}).get('properties', {})
    for field in fields:
      prop = properties.get(field)
      if isinstance(prop, dict):
        patched |= _mark_nullable_ref(prop)
  return patched


def fix_file_breakdown_response(data: dict[str, Any]) -> bool:
  '''Rewrite the file-breakdown response from an array to the object the
  server actually sends (Fix 5). Return `True` if anything was patched.'''
  responses = (
    data.get('paths', {})
    .get(FILE_BREAKDOWN_PATH, {})
    .get('get', {})
    .get('responses', {})
  )
  patched = False
  for response in responses.values():
    for media in response.get('content', {}).values():
      if media.get('schema') == {'type': 'array', 'items': {'$ref': FILE_BREAKDOWN_REF}}:
        media['schema'] = {'$ref': FILE_BREAKDOWN_REF}
        patched = True
  return patched


def fix_annotation_response(data: dict[str, Any]) -> bool:
  '''Rewrite the annotation list response from one object to the array the
  server actually sends (Fix 7). Return `True` if anything was patched.'''
  return _rewrite_response_ref_to_array(data, ANNOTATION_ALL_FOR_SERIES_PATH, 'get', ANNOTATION_DTO_REF)


def fix_device_type_response(data: dict[str, Any]) -> bool:
  '''Rewrite the device-type response from one object to the array the
  server actually sends (Fix 10). Return `True` if anything was patched.'''
  return _rewrite_response_ref_to_array(data, DEVICE_TYPE_PATH, 'get', STRING_STAT_COUNT_REF)


def _rewrite_response_ref_to_array(
  data: dict[str, Any], path: str, method: str, ref: str,
) -> bool:
  responses = (
    data.get('paths', {})
    .get(path, {})
    .get(method, {})
    .get('responses', {})
  )
  patched = False
  for response in responses.values():
    for media in response.get('content', {}).values():
      if media.get('schema') == {'$ref': ref}:
        media['schema'] = {'type': 'array', 'items': {'$ref': ref}}
        patched = True
  return patched


def fix_nullable_response_refs(data: dict[str, Any]) -> bool:
  '''Mark prompt-reread response refs nullable (Fix 8) — the server sends
  `null` when no reread is due. Return `True` if anything was patched.'''
  patched = False
  for path, method in PROMPT_REREAD_ENDPOINTS.items():
    responses = (
      data.get('paths', {})
      .get(path, {})
      .get(method, {})
      .get('responses', {})
    )
    for response in responses.values():
      for media in response.get('content', {}).values():
        schema = media.get('schema')
        ref = schema.get('$ref') if isinstance(schema, dict) else None
        if isinstance(ref, str) and not schema.get('nullable'):
          media['schema'] = {'allOf': [{'$ref': ref}], 'nullable': True}
          patched = True
  return patched


def fix_string_bodies(data: dict[str, Any]) -> bool:
  '''Rewrite bare-text string responses so the generated client reads text.

  Return `True` if anything was patched.
  '''
  patched = False
  for path, method in STRING_BODY_ENDPOINTS.items():
    responses = (
      data.get('paths', {})
      .get(path, {})
      .get(method, {})
      .get('responses', {})
    )
    for response in responses.values():
      content = response.get('content')
      if not content:
        continue
      # Only rewrite responses the document declares as plain strings.
      if not any(media.get('schema') == {'type': 'string'} for media in content.values()):
        continue
      if content != STRING_BODY_CONTENT:
        response['content'] = STRING_BODY_CONTENT
        patched = True
  return patched


def fix_spec_version(data: dict[str, Any], version: str) -> bool:
  '''Rewrite `info.version` to the release tag. Return `True` if patched.

  Upstream ships `info.version` one step behind the release tag (e.g.
  `0.9.1.1` in the `v0.9.1.4` document), so the generated client's version
  would not match the tag it was built from.
  '''
  info = data.get('info')
  if not isinstance(info, dict) or info.get('version') == version:
    return False
  info['version'] = version
  return True


def fix_spec(data: dict[str, Any], version: str | None = None) -> bool:
  '''Patch the document in place. Return `True` if anything was patched.

  `version`, when given, is the release tag: if the document's
  `info.version` differs from it, it is rewritten to match.
  '''
  patched = (
    fix_invite_response(data)
    | fix_nullable_enums(data)
    | fix_nullable_refs(data)
    | fix_file_breakdown_response(data)
    | fix_annotation_response(data)
    | fix_device_type_response(data)
    | fix_nullable_response_refs(data)
    | fix_string_bodies(data)
  )
  if version is not None:
    patched |= fix_spec_version(data, version)
  return patched


def main(argv: list[str] | None = None) -> int:
  args = sys.argv[1:] if argv is None else argv
  if len(args) not in (2, 3):
    print(f'Usage: {sys.argv[0]} INPUT.json OUTPUT.json [RELEASE_TAG]', file=sys.stderr)
    return 2

  src, dst = args[:2]
  version = args[2] if len(args) == 3 else None
  with open(src, encoding='utf-8') as handle:
    data = json.load(handle)

  info = data.get('info')
  spec_version = info.get('version') if isinstance(info, dict) else None

  version_patched = version is not None and fix_spec_version(data, version)
  patched = (
    fix_invite_response(data)
    | fix_nullable_enums(data)
    | fix_nullable_refs(data)
    | fix_file_breakdown_response(data)
    | fix_annotation_response(data)
    | fix_device_type_response(data)
    | fix_nullable_response_refs(data)
    | fix_string_bodies(data)
    | version_patched
  )

  if version_patched:
    print(
      f'warning: spec version is {spec_version}, rewriting info.version '
      f'to the release tag {version}',
      file=sys.stderr,
    )
  if not patched:
    print('warning: did not find anything to patch', file=sys.stderr)

  with open(dst, 'w', encoding='utf-8') as handle:
    json.dump(data, handle, indent=2)
    handle.write('\n')
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
