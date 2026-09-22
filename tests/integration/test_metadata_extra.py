'''Metadata endpoints unlocked by ComicInfo data (coverage-plan Phase 2).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.annotation import get_api_annotation_all_for_series
from kavita_client.api.metadata import (
  get_api_metadata_people,
  get_api_metadata_series_detail_plus,
  post_api_metadata_genres_with_counts,
  post_api_metadata_tags_with_counts,
)
from kavita_client.api.person import (
  get_api_person,
  get_api_person_chapters_by_role,
  get_api_person_roles,
  get_api_person_search,
  get_api_person_series_known_for,
)
from kavita_client.models import (
  LibraryType,
  PersonDto,
  PersonRole,
  SeriesDetailPlusDto,
  UserParams,
)

from kavita_instance import MediaLibrary, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def _person_id(client: AuthenticatedClient, name: str) -> int:
  people = get_api_metadata_people.sync_detailed(client=client)
  assert people.status_code == 200
  match = [person for person in people.parsed or [] if person.name == name]
  assert match, f'person {name!r} not found in {people.parsed}'
  assert isinstance(match[0].id, int)
  return match[0].id


def test_tags_with_counts(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = post_api_metadata_tags_with_counts.sync_detailed(client=media_admin_client, body=UserParams())
  assert resp.status_code == 200
  titles = {tag.title for tag in resp.parsed or []}
  assert {'sample', 'comic'} <= titles  # ComicInfo Tags


def test_genres_with_counts(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = post_api_metadata_genres_with_counts.sync_detailed(client=media_admin_client, body=UserParams())
  assert resp.status_code == 200
  titles = {genre.title for genre in resp.parsed or []}
  assert {'sample', 'comic'} <= titles  # ComicInfo Genre


def test_people_list(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_metadata_people.sync_detailed(client=media_admin_client)
  assert resp.status_code == 200
  names = {person.name for person in resp.parsed or []}
  assert {'Jon Doe', 'Claude Press'} <= names  # ComicInfo Writer/Publisher


def test_person_by_name(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_person.sync_detailed(client=media_admin_client, name='Jon Doe')
  assert resp.status_code == 200
  assert isinstance(resp.parsed, PersonDto)
  assert resp.parsed.name == 'Jon Doe'


def test_person_roles(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  person_id = _person_id(media_admin_client, 'Jon Doe')
  resp = get_api_person_roles.sync_detailed(client=media_admin_client, person_id=person_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)


def test_person_series_known_for(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  person_id = _person_id(media_admin_client, 'Jon Doe')
  resp = get_api_person_series_known_for.sync_detailed(client=media_admin_client, person_id=person_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
  assert resp.parsed, 'expected the ComicInfo writer to be known for a series'


def test_person_chapters_by_role(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  person_id = _person_id(media_admin_client, 'Jon Doe')
  resp = get_api_person_chapters_by_role.sync_detailed(
    client=media_admin_client, person_id=person_id, role=PersonRole.WRITER,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)


def test_person_search(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_person_search.sync_detailed(client=media_admin_client, query_string='Jon')
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
  assert any(person.name == 'Jon Doe' for person in resp.parsed)


def test_series_detail_plus(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  '''The server sends `recommendations`/`series` as null; the raw spec
  declares them non-nullable (Fix 6). With the patched client they parse
  as None; on nightly the parse crash is the recorded upstream bug.'''
  try:
    resp = get_api_metadata_series_detail_plus.sync_detailed(
      client=media_admin_client,
      series_id=media_library.comic_series_id,
      library_type=LibraryType.MANGA,
    )
  except Exception as exc:  # noqa: BLE001
    expect_upstream_fix('Fix 6 (nullable refs)', repr(exc))
    raise
  assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
  assert isinstance(resp.parsed, SeriesDetailPlusDto)
  assert resp.parsed.recommendations is None
  assert resp.parsed.series is None


def test_annotation_all_for_series(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  '''The server returns the annotation list; the raw spec declares a single
  AnnotationDto (Fix 7, found by the Schemathesis prototype). The patched
  client parses the array; nightly crashes and records the upstream bug.'''
  try:
    resp = get_api_annotation_all_for_series.sync_detailed(
      client=media_admin_client, series_id=media_library.comic_series_id,
    )
  except Exception as exc:  # noqa: BLE001
    expect_upstream_fix('Fix 7 (annotation list response)', repr(exc))
    raise
  assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
  assert isinstance(resp.parsed, list)
