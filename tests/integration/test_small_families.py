'''Small endpoint families unlocked by the richer media fixture (Phase 2).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.color_scape import (
  get_api_color_scape_chapter,
  get_api_color_scape_series,
  get_api_color_scape_volume,
)
from kavita_client.api.panels import get_api_panels_get_progress
from kavita_client.api.tachiyomi import get_api_tachiyomi_latest_chapter
from kavita_client.models import ColorScapeDto, ProgressDto, TachiyomiChapterDto

from kavita_instance import MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_tachiyomi_latest_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_tachiyomi_latest_chapter.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, TachiyomiChapterDto)


def test_panels_get_progress(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_panels_get_progress.sync_detailed(
    client=media_admin_client, chapter_id=media_library.read_chapter_id, api_key=media_library.api_key,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ProgressDto)


def test_color_scape_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_color_scape_chapter.sync_detailed(client=media_admin_client, id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ColorScapeDto)


def test_color_scape_series(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_color_scape_series.sync_detailed(client=media_admin_client, id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ColorScapeDto)


def test_color_scape_volume(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_color_scape_volume.sync_detailed(client=media_admin_client, id=media_library.comic_volume_ids[0])
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ColorScapeDto)
