'''Shared types for the docker-backed integration tests.'''

from __future__ import annotations

import dataclasses
import os

import pytest

from kavita_client import AuthenticatedClient, Client

# `KAVITA_MODE=release` (default) tests the patched client; `nightly` tests
# the client generated from the raw upstream spec.
NIGHTLY_BUILD = os.environ.get('KAVITA_MODE', 'release') == 'nightly'


def expect_upstream_fix(fix_id: str, detail: str = '') -> None:
  '''Record a still-present upstream spec bug as xfail on nightly builds.

  `fix_id` names the fix_spec.py fix that the released client has but the
  nightly client does not. On the nightly build this marks the test as an
  expected failure (the bug is still there upstream); once upstream fixes
  it, this is never reached and the test runs normally, signalling that the
  fix can be retired. On the release build this does nothing, so the
  caller's subsequent failure is real.
  '''
  if NIGHTLY_BUILD:
    message = f'known upstream spec bug still present ({fix_id} not applied)'
    if detail:
      message += f': {detail}'
    pytest.xfail(message)


@dataclasses.dataclass
class KavitaInstance:
  '''Everything the tests need to talk to a running Kavita server.'''

  image: str
  base_url: str
  admin_username: str
  admin_password: str
  admin_user_id: int
  token: str
  server_version: str
  media_dir: str
  client: Client
  admin_client: AuthenticatedClient


@dataclasses.dataclass
class MediaLibrary:
  '''A populated library on a running server: sample books and comics.'''

  manga_library_id: int
  book_library_id: int
  comic_series_id: int
  comic_series_name: str
  second_series_id: int
  book_series_ids: list[int]
  comic_volume_ids: list[int]
  comic_chapter_ids: list[int]
  comic_special_ids: list[int]
  epub_chapter_id: int
  read_chapter_id: int
  api_key: str
