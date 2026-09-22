'''Chapter endpoints against the populated library (coverage-plan Phase 2).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.chapter import (
  get_api_chapter,
  get_api_chapter_chapter_detail_plus,
  post_api_chapter_update,
)
from kavita_client.models import ChapterDetailPlusDto, ChapterDto, UpdateChapterDto

from kavita_instance import MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_get_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_chapter.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ChapterDto)
  # ComicInfo metadata is parsed (metadata-enabled library).
  assert resp.parsed.tags, 'expected ComicInfo tags on the chapter'


def test_chapter_detail_plus(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_chapter_chapter_detail_plus.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, ChapterDetailPlusDto)
  # The DTO carries rating/reviews data, not the chapter itself.
  assert isinstance(resp.parsed.has_been_rated, bool)


def test_update_chapter_summary(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  '''Self-contained mutation: set a summary on the special (loose-leaf) chapter.'''
  chapter_id = media_library.comic_special_ids[0]
  resp = post_api_chapter_update.sync_detailed(
    client=media_admin_client,
    body=UpdateChapterDto(id=chapter_id, summary='Phase 2 test summary'),
  )
  assert resp.status_code == 200

  after = get_api_chapter.sync_detailed(client=media_admin_client, chapter_id=chapter_id)
  assert after.status_code == 200
  assert after.parsed.summary == 'Phase 2 test summary'
