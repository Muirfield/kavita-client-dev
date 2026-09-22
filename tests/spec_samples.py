'''Small synthetic OpenAPI documents used by the fix_spec unit tests.'''

from __future__ import annotations

from typing import Any

from fix_spec import (
  ANNOTATION_ALL_FOR_SERIES_PATH,
  ANNOTATION_DTO_REF,
  DEVICE_TYPE_PATH,
  FILE_BREAKDOWN_PATH,
  FILE_BREAKDOWN_REF,
  INVITE_PATH,
  PROMPT_REREAD_ENDPOINTS,
  STRING_BODY_CONTENT,
  STRING_BODY_ENDPOINTS,
  STRING_STAT_COUNT_REF,
)

# Synthetic values only — deliberately NOT the real release versions, so
# these tests never need updating when KAVITA_VERSION changes. They only
# pin the rewrite mechanism.
RELEASE_TAG = '9.9.9'  # the tag the tests patch info.version to
SPEC_VERSION = '9.9.8'  # what the sample document declares (one step behind, like upstream)


def _string_body_endpoint(method: str) -> dict[str, Any]:
  '''A bare-text endpoint as the real spec declares it (JSON-ish media types).'''
  return {
    method: {
      'responses': {
        '200': {
          'description': 'OK',
          'content': {
            'text/plain': {'schema': {'type': 'string'}},
            'application/json': {'schema': {'type': 'string'}},
            'text/json': {'schema': {'type': 'string'}},
          },
        }
      }
    }
  }


def _file_breakdown_endpoint() -> dict[str, Any]:
  '''The file-breakdown endpoint as the real spec declares it (an array of
  `FileExtensionBreakdownDto` in three media types; the server sends one
  object).'''
  array_schema = {'type': 'array', 'items': {'$ref': FILE_BREAKDOWN_REF}}
  return {
    'get': {
      'responses': {
        '200': {
          'description': 'OK',
          'content': {
            'text/plain': {'schema': array_schema},
            'application/json': {'schema': array_schema},
            'text/json': {'schema': array_schema},
          },
        }
      }
    }
  }


def _ref_endpoint(method: str, ref: str) -> dict[str, Any]:
  '''An endpoint whose 200 response is a bare ref in three media types.'''
  return {
    method: {
      'responses': {
        '200': {
          'description': 'OK',
          'content': {
            'text/plain': {'schema': {'$ref': ref}},
            'application/json': {'schema': {'$ref': ref}},
            'text/json': {'schema': {'$ref': ref}},
          },
        }
      }
    }
  }


def make_spec() -> dict[str, Any]:
  '''A minimal document containing everything fix_spec.py knows about.'''
  paths: dict[str, Any] = {
    INVITE_PATH: {
      'post': {
        'responses': {
          '200': {
            'description': 'OK',
            'content': {
              'text/plain': {'schema': {'type': 'string'}},
              'application/json': {'schema': {'type': 'string'}},
              'text/json': {'schema': {'type': 'string'}},
            },
          }
        }
      }
    },
    '/api/Other': {
      'get': {
        'responses': {
          '200': {
            'description': 'OK',
            'content': {
              'text/plain': {'schema': {'type': 'string'}},
            },
          }
        }
      }
    },
    FILE_BREAKDOWN_PATH: _file_breakdown_endpoint(),
    ANNOTATION_ALL_FOR_SERIES_PATH: _ref_endpoint('get', ANNOTATION_DTO_REF),
    DEVICE_TYPE_PATH: _ref_endpoint('get', STRING_STAT_COUNT_REF),
  }
  for path, method in STRING_BODY_ENDPOINTS.items():
    paths[path] = _string_body_endpoint(method)
  for path, method in PROMPT_REREAD_ENDPOINTS.items():
    paths[path] = _ref_endpoint(method, '#/components/schemas/RereadDto')

  return {
    'info': {
      'title': 'Kavita',
      'version': SPEC_VERSION,
    },
    'paths': paths,
    'components': {
      'schemas': {
        'InviteUserResponse': {
          'type': 'object',
          'properties': {'emailSent': {'type': 'boolean'}},
        },
        'SeriesDto': {
          'type': 'object',
          'properties': {
            'metadataProviderOverride': {
              '$ref': '#/components/schemas/MetadataProvider'
            },
            'untouchedField': {'$ref': '#/components/schemas/Other'},
          },
        },
        'ChapterDto': {
          'type': 'object',
          'properties': {'format': {'$ref': '#/components/schemas/MangaFormat'}},
        },
        'MetadataSettingsDto': {
          'type': 'object',
          'properties': {
            'filterAboveWeight': {'$ref': '#/components/schemas/TagWeight'},
            'untouchedField': {'$ref': '#/components/schemas/Other'},
          },
        },
        'TachiyomiChapterDto': {
          'type': 'object',
          'properties': {'format': {'$ref': '#/components/schemas/MangaFormat'}},
        },
        'SeriesDetailPlusDto': {
          'type': 'object',
          'properties': {
            'recommendations': {'$ref': '#/components/schemas/Other'},
            'series': {'$ref': '#/components/schemas/Other'},
            'untouchedField': {'$ref': '#/components/schemas/Other'},
          },
        },
        'RereadDto': {
          'type': 'object',
          'properties': {
            'chapterOnContinue': {'$ref': '#/components/schemas/Other'},
            'chapterOnReread': {'$ref': '#/components/schemas/Other'},
          },
        },
        'SideNavStreamDto': {
          'type': 'object',
          'properties': {'externalSource': {'$ref': '#/components/schemas/Other'}},
        },
        'FileExtensionBreakdownDto': {
          'type': 'object',
          'properties': {'totalFileSize': {'type': 'integer', 'format': 'int64'}},
        },
        'MetadataProvider': {'type': 'integer', 'enum': [0, 1, 2]},
        'MangaFormat': {'type': 'integer', 'enum': [0, 1]},
        'TagWeight': {'type': 'integer', 'enum': [0, 1, 2]},
        'Other': {'type': 'string'},
      }
    },
  }
