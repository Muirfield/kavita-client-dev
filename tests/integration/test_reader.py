'''Reader endpoints against the populated library (coverage-plan Phase 2).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.reader import (
  get_api_reader_chapter_info,
  get_api_reader_continue_point,
  get_api_reader_get_progress,
  get_api_reader_has_progress,
  get_api_reader_image,
  get_api_reader_next_chapter,
  get_api_reader_prev_chapter,
  get_api_reader_prompt_reread_chapter,
  get_api_reader_prompt_reread_series,
  get_api_reader_prompt_reread_volume,
  get_api_reader_thumbnail,
  get_api_reader_time_left,
  get_api_reader_time_left_for_chapter,
)
from kavita_client.models import ChapterInfoDto, ChapterDto, ProgressDto, RereadDto

from kavita_instance import MediaLibrary, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_chapter_info_comic(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_chapter_info.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ChapterInfoDto)
  assert isinstance(resp.parsed.pages, int) and resp.parsed.pages > 0


def test_chapter_info_epub(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_chapter_info.sync_detailed(client=media_admin_client, chapter_id=media_library.epub_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ChapterInfoDto)
  assert isinstance(resp.parsed.pages, int) and resp.parsed.pages > 0


def test_reader_image(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  # The image endpoints require an API key even with a JWT.
  resp = get_api_reader_image.sync_detailed(
    client=media_admin_client, chapter_id=media_library.read_chapter_id, page=0, api_key=media_library.api_key,
  )
  assert resp.status_code == 200
  assert resp.content


def test_reader_thumbnail(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_thumbnail.sync_detailed(
    client=media_admin_client, chapter_id=media_library.read_chapter_id, page_num=1, api_key=media_library.api_key,
  )
  assert resp.status_code == 200
  assert resp.content


def test_get_progress(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_get_progress.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ProgressDto)
  assert resp.parsed.page_num == 3  # set by the media fixture


def test_has_progress(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_has_progress.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert resp.parsed is True


def test_continue_point(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_continue_point.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ChapterDto)
  assert resp.parsed.id == media_library.read_chapter_id


def test_next_and_prev_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  series_id = media_library.comic_series_id
  volume_id = media_library.comic_volume_ids[0]
  chapter_id = media_library.read_chapter_id
  nxt = get_api_reader_next_chapter.sync_detailed(
    client=media_admin_client, series_id=series_id, volume_id=volume_id, current_chapter_id=chapter_id,
  )
  assert nxt.status_code == 200
  assert isinstance(nxt.parsed, int) and nxt.parsed != chapter_id
  prev = get_api_reader_prev_chapter.sync_detailed(
    client=media_admin_client, series_id=series_id, volume_id=volume_id, current_chapter_id=chapter_id,
  )
  assert prev.status_code == 200
  assert isinstance(prev.parsed, int)


def test_time_left(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_reader_time_left.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert resp.parsed is not None
  resp2 = get_api_reader_time_left_for_chapter.sync_detailed(
    client=media_admin_client, series_id=media_library.comic_series_id, chapter_id=media_library.read_chapter_id,
  )
  assert resp2.status_code == 200
  assert resp2.parsed is not None


def test_prompt_reread(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  '''The reread checks return null when no reread is due; the raw spec
  declares a non-nullable RereadDto (Fix 8, found by the Schemathesis
  prototype). The patched client parses null as None; nightly crashes and
  records the upstream bug.'''
  calls = [
    (get_api_reader_prompt_reread_chapter.sync_detailed, dict(
      library_id=media_library.manga_library_id,
      series_id=media_library.comic_series_id,
      chapter_id=media_library.read_chapter_id,
    )),
    (get_api_reader_prompt_reread_volume.sync_detailed, dict(
      library_id=media_library.manga_library_id,
      series_id=media_library.comic_series_id,
      volume_id=media_library.comic_volume_ids[0],
    )),
    (get_api_reader_prompt_reread_series.sync_detailed, dict(
      library_id=media_library.manga_library_id,
      series_id=media_library.comic_series_id,
    )),
  ]
  for fn, kwargs in calls:
    try:
      resp = fn(client=media_admin_client, **kwargs)  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
      expect_upstream_fix('Fix 8 (nullable reread response)', repr(exc))
      raise
    assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
    assert resp.parsed is None or isinstance(resp.parsed, RereadDto)
