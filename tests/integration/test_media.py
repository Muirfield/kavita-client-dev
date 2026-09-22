'''Tests against a Kavita server with a populated library.

The `media_library` fixture generates sample content from
`tests/data/loremipsum.md` (see `conftest.py`): two comic series, a book
series with an epub whose metadata is embedded via ebook-meta plus a pdf,
and `tests/data/cover.jpg` as the comic's folder cover. It creates one
manga and one book library (metadata processing enabled) and scans them.

These are the first tests that exercise the *second* fix_spec.py fix: the
server returns `metadataProviderOverride: null` for a normal series, which
crashed the client before the field was marked nullable.
'''

from __future__ import annotations

import io
from pathlib import Path

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.book import get_api_book_chapter_id_book_info, get_api_book_chapter_id_chapters
from kavita_client.api.search import (
  get_api_search_chapters_by_series,
  get_api_search_search,
  get_api_search_series_for_chapter,
)
from kavita_client.api.series import get_api_series_series_detail, get_api_series_volumes, post_api_series_v_2
from kavita_client.api.stats import get_api_stats_server_stats
from kavita_client.api.upload import post_api_upload_upload_by_file
from kavita_client.models import (
  BookInfoDto,
  ChapterDto,
  MangaFormat,
  PostApiUploadUploadByFileBody,
  SeriesDto,
  SeriesFilterV2Dto,
)
from kavita_client.types import File

from kavita_instance import MediaLibrary, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]

ROOT = Path(__file__).resolve().parents[2]
COVER = ROOT / 'tests' / 'data' / 'cover.jpg'


def _find_series(admin_client: AuthenticatedClient, series_id: int) -> SeriesDto:
  resp = post_api_series_v_2.sync_detailed(
    client=admin_client,
    body=SeriesFilterV2Dto(),
    page_number=1,
    page_size=100,
  )
  assert resp.status_code == 200
  match = [s for s in resp.parsed or [] if s.id == series_id]
  assert match, f'series {series_id} not found'
  return match[0]


def _chapters_of(admin_client: AuthenticatedClient, series_id: int) -> list[ChapterDto]:
  resp = get_api_series_volumes.sync_detailed(client=admin_client, series_id=series_id)
  assert resp.status_code == 200
  return [chapter for volume in resp.parsed or [] for chapter in volume.chapters or []]


def test_comic_series_found_with_nullable_metadata_provider(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  series = _find_series(media_admin_client, media_library.comic_series_id)
  assert series.name == media_library.comic_series_name
  assert series.library_id == media_library.manga_library_id
  # The nullable-enum fix (fix_spec.py): the server sends null here, and the
  # generated client must parse it as None instead of crashing.
  assert series.metadata_provider_override is None
  # The scan picked up the folder cover (tests/data/cover.jpg).
  assert isinstance(series.cover_image, str) and series.cover_image


def test_comic_volumes_and_chapters(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  chapters = _chapters_of(media_admin_client, media_library.comic_series_id)
  assert chapters, 'the comic series has no chapters'
  # ChapterDto.format is one of the nullable enum fields; accept the value
  # the server sends (ARCHIVE for a cbz) or null without crashing.
  assert {chapter.format_ for chapter in chapters} <= {MangaFormat.ARCHIVE, MangaFormat.IMAGE, None}


def test_series_detail(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_series_series_detail.sync_detailed(
    client=media_admin_client,
    series_id=media_library.comic_series_id,
  )
  assert resp.status_code == 200
  assert resp.parsed is not None
  # The loose-leaf cbz is parsed as a "special" chapter, so the data is in
  # `specials` rather than `chapters`/`volumes`.
  assert resp.parsed.specials, 'series detail reports no chapters'
  assert resp.parsed.specials[0].format_ == MangaFormat.ARCHIVE


def test_book_library_chapters_and_book_info(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  assert media_library.book_series_ids, 'the book library has no series'
  chapters: list[ChapterDto] = []
  for series_id in media_library.book_series_ids:
    chapters += _chapters_of(media_admin_client, series_id)
  assert chapters
  formats = {chapter.format_ for chapter in chapters}
  assert formats <= {MangaFormat.EPUB, MangaFormat.PDF, None}
  assert formats & {MangaFormat.EPUB, MangaFormat.PDF}, f'unexpected formats {formats}'

  epub = next((chapter for chapter in chapters if chapter.format_ == MangaFormat.EPUB), None)
  if epub is not None and isinstance(epub.id, int):
    info = get_api_book_chapter_id_book_info.sync_detailed(chapter_id=epub.id, client=media_admin_client)
    assert info.status_code == 200
    assert isinstance(info.parsed, BookInfoDto)


def test_search_finds_series(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_search_search.sync_detailed(
    client=media_admin_client,
    query_string=media_library.comic_series_name,
    include_chapter_and_files=False,
  )
  assert resp.status_code == 200
  assert resp.parsed is not None
  assert resp.parsed.series, 'search found no series'
  assert any(result.series_id == media_library.comic_series_id for result in resp.parsed.series)


def test_search_series_for_chapter(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_search_series_for_chapter.sync_detailed(
    client=media_admin_client, chapter_id=media_library.read_chapter_id,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, SeriesDto)
  assert resp.parsed.id == media_library.comic_series_id


def test_search_chapters_by_series(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_search_chapters_by_series.sync_detailed(
    client=media_admin_client, series_id=media_library.comic_series_id,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
  assert any(isinstance(chapter.id, int) and chapter.id == media_library.read_chapter_id for chapter in resp.parsed)


def test_book_chapters(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_book_chapter_id_chapters.sync_detailed(
    chapter_id=media_library.epub_chapter_id, client=media_admin_client,
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)


def test_stats_after_scan(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  resp = get_api_stats_server_stats.sync_detailed(client=media_admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed.series_count, int) and resp.parsed.series_count >= 2
  assert isinstance(resp.parsed.chapter_count, int) and resp.parsed.chapter_count >= 3
  assert isinstance(resp.parsed.total_files, int) and resp.parsed.total_files >= 3


def test_cover_upload_by_file(media_admin_client: AuthenticatedClient) -> None:
  '''POST /api/Upload/upload-by-file stages an uploaded cover image (the
  only multipart upload the spec documents).

  The server answers with the bare staged filename; the fixed client reads
  it as text (fix_spec Fix 3). The nightly client parses it with
  response.json() and crashes; that is the known upstream bug, recorded as
  xfail.
  '''
  body = PostApiUploadUploadByFileBody(
    file=File(
      payload=io.BytesIO(COVER.read_bytes()),
      file_name='cover.jpg',
      mime_type='image/jpeg',
    )
  )
  try:
    resp = post_api_upload_upload_by_file.sync_detailed(client=media_admin_client, body=body)
  except Exception as exc:  # noqa: BLE001
    expect_upstream_fix('Fix 3 (bare string bodies)', repr(exc))
    raise
  assert resp.status_code == 200
  assert isinstance(resp.parsed, str) and resp.parsed.strip()
