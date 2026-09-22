'''OPDS feed endpoints, exercised anonymously with the fixture's API key
(coverage-plan Phase 3).'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient, Client
from kavita_client.api.collection import (
  delete_api_collection,
  get_api_collection,
  post_api_collection_update_for_series,
)
from kavita_client.api.opds import (
  get_api_opds_api_key,
  get_api_opds_api_key_collections,
  get_api_opds_api_key_collections_collection_id,
  get_api_opds_api_key_favicon,
  get_api_opds_api_key_image,
  get_api_opds_api_key_libraries,
  get_api_opds_api_key_libraries_library_id,
  get_api_opds_api_key_on_deck,
  get_api_opds_api_key_reading_list,
  get_api_opds_api_key_reading_list_reading_list_id,
  get_api_opds_api_key_recently_added,
  get_api_opds_api_key_recently_updated,
  get_api_opds_api_key_series,
  get_api_opds_api_key_series_series_id,
  get_api_opds_api_key_series_series_id_volume_volume_id,
  get_api_opds_api_key_series_series_id_volume_volume_id_chapter_chapter_id,
  get_api_opds_api_key_smart_filters,
  get_api_opds_api_key_want_to_read,
)
from kavita_client.api.reading_list import (
  delete_api_reading_list,
  post_api_reading_list_create,
)
from kavita_client.models import CollectionTagBulkAddDto, CreateReadingListDto

from kavita_instance import KavitaInstance, MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


@pytest.fixture()
def opds_client(media_kavita_server: KavitaInstance) -> Client:
  '''OPDS feeds are anonymous: only the API key in the URL matters.'''
  return Client(base_url=media_kavita_server.base_url)


@pytest.mark.parametrize(
  ('fn', 'kwargs'),
  [
    (get_api_opds_api_key, {}),
    (get_api_opds_api_key_series, {'query': 'Lorem'}),
    (get_api_opds_api_key_on_deck, {}),
    (get_api_opds_api_key_recently_added, {}),
    (get_api_opds_api_key_recently_updated, {}),
    (get_api_opds_api_key_want_to_read, {}),
    (get_api_opds_api_key_collections, {}),
    (get_api_opds_api_key_reading_list, {}),
    (get_api_opds_api_key_smart_filters, {}),
    (get_api_opds_api_key_libraries, {}),
  ],
  ids=['root', 'series', 'on-deck', 'recently-added', 'recently-updated',
       'want-to-read', 'collections', 'reading-list', 'smart-filters',
       'libraries'],
)
def test_opds_feeds(
  opds_client: Client,
  media_library: MediaLibrary,
  fn: object,
  kwargs: dict,
) -> None:
  resp = fn.sync_detailed(media_library.api_key, client=opds_client, **kwargs)  # type: ignore[operator]
  assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
  assert resp.content  # OPDS XML


def test_opds_library_feed(opds_client: Client, media_library: MediaLibrary) -> None:
  resp = get_api_opds_api_key_libraries_library_id.sync_detailed(
    media_library.api_key, library_id=media_library.manga_library_id, client=opds_client,
  )
  assert resp.status_code == 200
  assert resp.content


def test_opds_series_feed(opds_client: Client, media_library: MediaLibrary) -> None:
  resp = get_api_opds_api_key_series_series_id.sync_detailed(
    media_library.api_key, series_id=media_library.comic_series_id, client=opds_client,
  )
  assert resp.status_code == 200
  assert resp.content


def test_opds_volume_and_chapter_feed(opds_client: Client, media_library: MediaLibrary) -> None:
  volume_id = media_library.comic_volume_ids[0]
  chapter_id = media_library.read_chapter_id
  volume = get_api_opds_api_key_series_series_id_volume_volume_id.sync_detailed(
    media_library.api_key, series_id=media_library.comic_series_id, volume_id=volume_id, client=opds_client,
  )
  assert volume.status_code == 200
  assert volume.content
  chapter = get_api_opds_api_key_series_series_id_volume_volume_id_chapter_chapter_id.sync_detailed(
    media_library.api_key,
    series_id=media_library.comic_series_id,
    volume_id=volume_id,
    chapter_id=chapter_id,
    client=opds_client,
  )
  assert chapter.status_code == 200
  assert chapter.content


def test_opds_image_feed(opds_client: Client, media_library: MediaLibrary) -> None:
  '''Page stream (DESIGN quirk #19): with a valid chapterId the page cache
  is populated on demand and the admin API key passes ChapterAccess, so the
  endpoint streams the page (the earlier 400 was a bad-id artifact).

  Progress: the server saves reading progress unless the User-Agent starts
  with "Panels" AND saveProgress is true (the source checks
  `!UA.StartsWith("Panels") || !saveProgress` — with saveProgress=false it
  still saves). A Panels-styled UA keeps the fixture's progress intact.'''
  resp = get_api_opds_api_key_image.sync_detailed(
    media_library.api_key,
    library_id=media_library.manga_library_id,
    series_id=media_library.comic_series_id,
    volume_id=media_library.comic_volume_ids[0],
    chapter_id=media_library.read_chapter_id,
    page_number=0,
    client=opds_client.with_headers({'User-Agent': 'Panels test'}),
  )
  assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
  assert resp.content
  assert resp.headers.get('content-type', '').startswith('image/')


def test_opds_favicon_feed(opds_client: Client, media_library: MediaLibrary) -> None:
  '''The endpoint lists `*.ico` in the parent of the app dir; the media
  fixture mounts `tests/data/favicon.ico` there (DESIGN quirk #19 —
  without the mount the container has none and the endpoint 400s).'''
  resp = get_api_opds_api_key_favicon.sync_detailed(
    media_library.api_key, client=opds_client,
  )
  assert resp.status_code == 200, f'{resp.status_code} {resp.content[:200]!r}'
  assert resp.content
  assert resp.headers.get('content-type', '').startswith('image/')


def test_opds_reading_list_feed(
  opds_client: Client,
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  '''Self-contained: create a reading list, fetch its OPDS feed, delete it.'''
  created = post_api_reading_list_create.sync_detailed(
    client=media_admin_client, body=CreateReadingListDto(title='opds rl'),
  )
  assert created.status_code == 200 and created.parsed is not None and isinstance(created.parsed.id, int)
  try:
    resp = get_api_opds_api_key_reading_list_reading_list_id.sync_detailed(
      media_library.api_key, reading_list_id=created.parsed.id, client=opds_client,
    )
    assert resp.status_code == 200
    assert resp.content
  finally:
    assert delete_api_reading_list.sync_detailed(
      client=media_admin_client, reading_list_id=created.parsed.id,
    ).status_code == 200


def test_opds_collection_feed(
  opds_client: Client,
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  '''Self-contained: create a collection, fetch its OPDS feed, delete it.'''
  # Collections are created by bulk-adding a tag to series.
  created = post_api_collection_update_for_series.sync_detailed(
    client=media_admin_client,
    body=CollectionTagBulkAddDto(
      collection_tag_id=0,
      collection_tag_title='opds coll',
      series_ids=[media_library.second_series_id],
    ),
  )
  assert created.status_code == 200
  all_collections = get_api_collection.sync_detailed(client=media_admin_client)
  assert all_collections.status_code == 200
  match = [collection for collection in all_collections.parsed or [] if collection.title == 'opds coll']
  assert match and isinstance(match[0].id, int)
  try:
    resp = get_api_opds_api_key_collections_collection_id.sync_detailed(
      media_library.api_key, collection_id=match[0].id, client=opds_client,
    )
    assert resp.status_code == 200
    assert resp.content
  finally:
    assert delete_api_collection.sync_detailed(
      client=media_admin_client, tag_id=match[0].id,
    ).status_code == 200
