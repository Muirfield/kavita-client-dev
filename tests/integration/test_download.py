'''Download endpoints against the populated library (coverage-plan Phase 2).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.download import (
  get_api_download_chapter,
  get_api_download_chapter_size,
  get_api_download_series,
  get_api_download_series_size,
  get_api_download_volume,
  get_api_download_volume_size,
)

from kavita_instance import MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_download_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_download_chapter.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert resp.content  # zip of the chapter pages


def test_download_volume(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_download_volume.sync_detailed(client=media_admin_client, volume_id=media_library.comic_volume_ids[0])
  assert resp.status_code == 200
  assert resp.content


def test_download_series(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_download_series.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert resp.content


def test_download_sizes(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  chapter = get_api_download_chapter_size.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert chapter.status_code == 200
  assert isinstance(chapter.parsed, int) and chapter.parsed > 0
  volume = get_api_download_volume_size.sync_detailed(client=media_admin_client, volume_id=media_library.comic_volume_ids[0])
  assert volume.status_code == 200
  assert isinstance(volume.parsed, int) and volume.parsed > 0
  series = get_api_download_series_size.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert series.status_code == 200
  assert isinstance(series.parsed, int) and series.parsed > 0
