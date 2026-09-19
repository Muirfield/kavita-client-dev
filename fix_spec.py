#!/usr/bin/env python3
'''Fix known issues in the Kavita OpenAPI document before code generation.

* `POST /api/Account/invite` is documented as returning a plain string, but
  the server actually returns an `InviteUserResponse` object (the schema
  exists in the document, it is just never referenced). Point the response
  at the correct schema so the generated client parses it properly.

* A few enum fields are `Nullable<T>` in the server code, but the document
  declares them as non-nullable, so the generated client crashes when the
  server sends `null` for them. Mark them nullable.
'''

from __future__ import annotations

import json
import sys
from typing import Any

INVITE_PATH = '/api/Account/invite'
INVITE_RESPONSE_REF = '#/components/schemas/InviteUserResponse'

# Schema name -> enum fields the server may send as null.
NULLABLE_ENUM_FIELDS = {
  'SeriesDto': ['metadataProviderOverride'],
  'ChapterDto': ['format'],
}


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


def fix_nullable_enums(data: dict[str, Any]) -> bool:
  '''Mark known nullable enum fields as nullable. Return `True` if anything was patched.

  `nullable: true` next to a plain `$ref` is ignored by openapi-python-client,
  so the field is rewritten to the equivalent `allOf` form it does honor.
  '''
  schemas = data.get('components', {}).get('schemas', {})
  patched = False
  for schema_name, fields in NULLABLE_ENUM_FIELDS.items():
    properties = schemas.get(schema_name, {}).get('properties', {})
    for field in fields:
      prop = properties.get(field)
      ref = prop.get('$ref') if isinstance(prop, dict) else None
      if ref and not prop.get('nullable'):
        prop.clear()
        prop.update({'allOf': [{'$ref': ref}], 'nullable': True})
        patched = True
  return patched


def fix_spec(data: dict[str, Any]) -> bool:
  '''Patch the document in place. Return `True` if anything was patched.'''
  return fix_invite_response(data) | fix_nullable_enums(data)


def main(argv: list[str] | None = None) -> int:
  args = sys.argv[1:] if argv is None else argv
  if len(args) != 2:
    print(f'Usage: {sys.argv[0]} INPUT.json OUTPUT.json', file=sys.stderr)
    return 2

  src, dst = args
  with open(src, encoding='utf-8') as handle:
    data = json.load(handle)

  if not fix_spec(data):
    print(f'warning: did not find anything to patch', file=sys.stderr)

  with open(dst, 'w', encoding='utf-8') as handle:
    json.dump(data, handle, indent=2)
    handle.write('\n')
  return 0


if __name__ == '__main__':
  raise SystemExit(main())
