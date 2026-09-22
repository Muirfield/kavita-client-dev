'''Series endpoints unlocked by the richer media fixture (coverage-plan Phase 2).'''

from __future__ import annotations

import pathlib
import time
import zipfile

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.library import post_api_library_create, post_api_library_scan
from kavita_client.api.reader import post_api_reader_progress
from kavita_client.api.series import (
  get_api_series_age_rating,
  get_api_series_all_related,
  get_api_series_currently_reading,
  get_api_series_metadata,
  get_api_series_next_expected,
  get_api_series_related,
  get_api_series_series_with_annotations,
  get_api_series_volumes,
  post_api_series_on_deck,
  post_api_series_v_2,
)
from kavita_client.api.settings import get_api_settings, post_api_settings
from kavita_client.models import (
  FileTypeGroup,
  LibraryType,
  MetadataProvider,
  NextExpectedChapterDto,
  ProgressDto,
  RelatedSeriesDto,
  RelationKind,
  SeriesFilterV2Dto,
  SeriesMetadataDto,
  ServerSettingDto,
  UpdateLibraryDto,
)

from kavita_instance import KavitaInstance, MediaLibrary, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / 'tests' / 'data'


def test_related(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_related.sync_detailed(
    client=media_admin_client,
    series_id=media_library.comic_series_id,
    relation=RelationKind.ADAPTATION,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)


def test_all_related(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_all_related.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, RelatedSeriesDto)


def test_next_expected(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_next_expected.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, NextExpectedChapterDto)


# Dropped from the sweep (see docs/DESIGN.md quirks):
# - GET /api/Series/match-info: 403 (Kavita+ only).


def test_age_rating(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_age_rating.sync_detailed(client=media_admin_client, age_rating=0)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, str)


def test_series_metadata(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_metadata.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, SeriesMetadataDto)


def test_currently_reading(currently_reading_server: KavitaInstance) -> None:
  '''Dedicated throwaway server (coverage-plan pattern): the endpoint's
  filter only lists series whose last read is *older* than
  `OnDeckProgressDays` (flipped comparison in `SeriesFilter.HasReadLast`,
  DESIGN quirk #15) — with the setting at 0 the filter short-circuits and
  a partially-read series appears. Setting it to 0 empties on-deck, so
  this cannot run on the shared media fixture.'''
  admin = currently_reading_server.admin_client

  settings = get_api_settings.sync_detailed(client=admin)
  assert settings.status_code == 200 and settings.parsed is not None
  updated = settings.parsed.to_dict()
  updated['onDeckProgressDays'] = 0
  posted = post_api_settings.sync_detailed(client=admin, body=ServerSettingDto.from_dict(updated))
  assert posted.status_code == 200

  comics = pathlib.Path(currently_reading_server.media_dir) / 'Comics' / 'lorem'
  comics.mkdir(parents=True)
  cover = (DATA_DIR / 'cover.jpg').read_bytes()
  with zipfile.ZipFile(comics / 'Lorem v01.cbz', 'w') as archive:
    for page in range(1, 9):
      archive.writestr(f'page_{page:03d}.jpg', cover)

  created = post_api_library_create.sync_detailed(
    client=admin,
    body=UpdateLibraryDto(
      id=0, name='comics', type_=LibraryType.MANGA, folders=['/media/Comics'],
      folder_watching=False, include_in_dashboard=True, include_in_search=True,
      manage_collections=False, manage_reading_lists=False, allow_scrobbling=False,
      allow_metadata_matching=False, enable_metadata=True, remove_prefix_for_sort_name=False,
      inherit_web_links_from_first_chapter=False, file_group_types=[FileTypeGroup.ARCHIVE],
      exclude_patterns=[], metadata_provider=MetadataProvider.MANGABAKA,
    ),
  )
  assert created.status_code == 200 and created.parsed is not None and isinstance(created.parsed.id, int)
  library_id = created.parsed.id
  assert post_api_library_scan.sync_detailed(client=admin, library_id=library_id, force=True).status_code == 200

  series = []
  deadline = time.monotonic() + 120
  while time.monotonic() < deadline:
    try:
      listed = post_api_series_v_2.sync_detailed(
        client=admin, body=SeriesFilterV2Dto(), page_number=1, page_size=100,
      )
    except Exception as exc:  # noqa: BLE001
      # The nightly client crashes parsing the null `metadataProviderOverride`
      # (Fix 2); record the known upstream bug as xfail, as conftest does.
      expect_upstream_fix('Fix 2 (nullable enums)', repr(exc))
      raise
    series = listed.parsed or []
    if series:
      break
    time.sleep(3.0)
  assert series, 'scan did not populate the series'

  volumes = get_api_series_volumes.sync_detailed(client=admin, series_id=series[0].id)
  assert volumes.status_code == 200 and volumes.parsed
  volume = volumes.parsed[0]
  assert volume.chapters
  chapter_id = volume.chapters[0].id

  progress = post_api_reader_progress.sync_detailed(
    client=admin,
    body=ProgressDto(
      library_id=library_id, series_id=series[0].id, volume_id=volume.id,
      chapter_id=chapter_id, page_num=3,
    ),
  )
  assert progress.status_code == 200

  reading = get_api_series_currently_reading.sync_detailed(
    client=admin, user_id=currently_reading_server.admin_user_id,
  )
  assert reading.status_code == 200, f'{reading.status_code} {reading.content!r}'
  assert any(s.id == series[0].id for s in reading.parsed or [])


def test_on_deck_has_lorem(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = post_api_series_on_deck.sync_detailed(
    client=media_admin_client, library_id=media_library.manga_library_id,
  )
  assert resp.status_code == 200
  assert any(s.id == media_library.comic_series_id for s in resp.parsed or [])


def test_series_with_annotations(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_series_series_with_annotations.sync_detailed(client=media_admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
