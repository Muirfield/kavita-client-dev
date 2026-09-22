'''Mutation endpoints, self-contained (coverage-plan Phase 3).

Every test creates its own entities and cleans them up, so the shared
fixture stays intact for the read-only suites.
'''

from __future__ import annotations

import time
import uuid

import httpx
import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.account import post_api_account_invite
from kavita_client.api.collection import (
  delete_api_collection,
  get_api_collection,
  get_api_collection_name_exists,
  get_api_collection_single,
  post_api_collection_update_for_series,
)
from kavita_client.api.library import (
  delete_api_library_delete,
  get_api_library_libraries,
  post_api_library_create,
  post_api_library_scan,
)
from kavita_client.api.rating import (
  get_api_rating_overall_chapter,
  get_api_rating_overall_series,
  post_api_rating_chapter,
  post_api_rating_series,
)
from kavita_client.api.reader import post_api_reader_mark_read, post_api_reader_mark_unread
from kavita_client.api.reading_list import (
  delete_api_reading_list,
  get_api_reading_list,
  post_api_reading_list_create,
  post_api_reading_list_update,
)
from kavita_client.api.review import post_api_review_series
from kavita_client.api.series import post_api_series_update, post_api_series_v_2
from kavita_client.api.users import (
  delete_api_users_delete_user,
  get_api_users,
  get_api_users_get_preferences,
  post_api_users_update_preferences,
)
from kavita_client.api.want_to_read import (
  get_api_want_to_read,
  post_api_want_to_read_add_series,
  post_api_want_to_read_remove_series,
  post_api_want_to_read_v2,
)
from kavita_client.models import (
  AgeRating,
  AgeRestrictionDto,
  AppUserCollectionDto,
  CollectionTagBulkAddDto,
  CreateReadingListDto,
  FileTypeGroup,
  InviteUserDto,
  LibraryType,
  MarkReadDto,
  MetadataProvider,
  SeriesFilterV2Dto,
  UpdateLibraryDto,
  UpdateRatingDto,
  UpdateReadingListDto,
  UpdateSeriesDto,
  UpdateUserReviewDto,
  UpdateWantToReadDto,
  UserPreferencesDto,
)

from kavita_instance import KavitaInstance, MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_collection_lifecycle(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  title = 'phase3-coll'
  assert get_api_collection_name_exists.sync_detailed(
    client=media_admin_client, name=title,
  ).parsed is False

  created = post_api_collection_update_for_series.sync_detailed(
    client=media_admin_client,
    body=CollectionTagBulkAddDto(collection_tag_id=0, collection_tag_title=title, series_ids=[media_library.second_series_id]),
  )
  assert created.status_code == 200

  all_collections = get_api_collection.sync_detailed(client=media_admin_client)
  assert all_collections.status_code == 200
  match = [collection for collection in all_collections.parsed or [] if collection.title == title]
  assert match and isinstance(match[0].id, int)
  collection_id = match[0].id

  single = get_api_collection_single.sync_detailed(client=media_admin_client, collection_id=collection_id)
  assert single.status_code == 200
  assert isinstance(single.parsed, AppUserCollectionDto)
  assert single.parsed.title == title

  assert delete_api_collection.sync_detailed(client=media_admin_client, tag_id=collection_id).status_code == 200
  assert get_api_collection_name_exists.sync_detailed(
    client=media_admin_client, name=title,
  ).parsed is False


def test_reading_list_lifecycle(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  title = 'phase3-rl'
  created = post_api_reading_list_create.sync_detailed(
    client=media_admin_client, body=CreateReadingListDto(title=title),
  )
  assert created.status_code == 200 and created.parsed is not None and isinstance(created.parsed.id, int)
  reading_list_id = created.parsed.id

  updated = post_api_reading_list_update.sync_detailed(
    client=media_admin_client,
    body=UpdateReadingListDto(reading_list_id=reading_list_id, title=f'{title}-renamed'),
  )
  assert updated.status_code == 200

  fetched = get_api_reading_list.sync_detailed(client=media_admin_client, reading_list_id=reading_list_id)
  assert fetched.status_code == 200
  assert fetched.parsed is not None and fetched.parsed.title == f'{title}-renamed'

  assert delete_api_reading_list.sync_detailed(
    client=media_admin_client, reading_list_id=reading_list_id,
  ).status_code == 200


def test_want_to_read_add_and_remove(
  media_library: MediaLibrary,
  media_kavita_server: KavitaInstance,
  media_admin_client: AuthenticatedClient,
) -> None:
  series_id = media_library.second_series_id
  added = post_api_want_to_read_add_series.sync_detailed(
    client=media_admin_client, body=UpdateWantToReadDto(series_ids=[series_id]),
  )
  assert added.status_code == 200

  # GET is a membership check; the list is the v2 endpoint.
  member = get_api_want_to_read.sync_detailed(client=media_admin_client, series_id=series_id)
  assert member.status_code == 200
  assert member.parsed is True
  listing = post_api_want_to_read_v2.sync_detailed(
    client=media_admin_client,
    body=SeriesFilterV2Dto(),
    user_id=media_kavita_server.admin_user_id,
  )
  assert listing.status_code == 200
  assert any(series.id == series_id for series in listing.parsed or [])

  removed = post_api_want_to_read_remove_series.sync_detailed(
    client=media_admin_client, body=UpdateWantToReadDto(series_ids=[series_id]),
  )
  assert removed.status_code == 200
  member = get_api_want_to_read.sync_detailed(client=media_admin_client, series_id=series_id)
  assert member.parsed is False


def test_rating_series_and_chapter(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  series = post_api_rating_series.sync_detailed(
    client=media_admin_client,
    body=UpdateRatingDto(series_id=media_library.second_series_id, user_rating=5.0),
  )
  assert series.status_code == 200
  overall_series = get_api_rating_overall_series.sync_detailed(
    client=media_admin_client, series_id=media_library.second_series_id,
  )
  assert overall_series.status_code == 200
  assert overall_series.parsed is not None  # the score is recalculated asynchronously

  chapter = post_api_rating_chapter.sync_detailed(
    client=media_admin_client,
    body=UpdateRatingDto(
      series_id=media_library.comic_series_id,  # required alongside the chapter
      chapter_id=media_library.read_chapter_id,
      user_rating=4.0,
    ),
  )
  assert chapter.status_code == 200
  overall_chapter = get_api_rating_overall_chapter.sync_detailed(
    client=media_admin_client, chapter_id=media_library.read_chapter_id,
  )
  assert overall_chapter.status_code == 200
  assert overall_chapter.parsed is not None


def test_series_update_name_lock(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  '''Lock then unlock the name (name changes are server-locked; we don't rename).'''
  series_id = media_library.second_series_id
  locked = post_api_series_update.sync_detailed(
    client=media_admin_client, body=UpdateSeriesDto(id=series_id, name_locked=True),
  )
  assert locked.status_code == 200
  unlocked = post_api_series_update.sync_detailed(
    client=media_admin_client, body=UpdateSeriesDto(id=series_id, name_locked=False),
  )
  assert unlocked.status_code == 200


def test_users_update_preferences(media_admin_client: AuthenticatedClient) -> None:
  '''Most preference fields are required, so fetch, flip one, and post back.'''
  current = get_api_users_get_preferences.sync_detailed(client=media_admin_client)
  assert current.status_code == 200 and current.parsed is not None
  prefs = current.parsed
  flipped = not bool(prefs.blur_unread_summaries)
  updated = post_api_users_update_preferences.sync_detailed(
    client=media_admin_client,
    body=UserPreferencesDto(
      theme=prefs.theme,
      blur_unread_summaries=flipped,
      prompt_for_download_size=prefs.prompt_for_download_size,
      no_transitions=prefs.no_transitions,
      collapse_series_relationships=prefs.collapse_series_relationships,
      locale=prefs.locale,
      color_scape_enabled=prefs.color_scape_enabled,
      data_saver=prefs.data_saver,
      prompt_for_rereads_after=prefs.prompt_for_rereads_after,
      custom_key_binds=prefs.custom_key_binds,
      book_reader_highlight_slots=prefs.book_reader_highlight_slots,
      social_preferences=prefs.social_preferences,
      opds_preferences=prefs.opds_preferences,
      global_page_layout_mode=prefs.global_page_layout_mode,
      ani_list_scrobbling_enabled=prefs.ani_list_scrobbling_enabled,
      want_to_read_sync=prefs.want_to_read_sync,
    ),
  )
  assert updated.status_code == 200
  assert updated.parsed is not None
  assert updated.parsed.blur_unread_summaries is flipped


def test_reader_mark_read_and_unread(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  series_id = media_library.second_series_id
  assert post_api_reader_mark_read.sync_detailed(
    client=media_admin_client, body=MarkReadDto(series_id=series_id),
  ).status_code == 200
  assert post_api_reader_mark_unread.sync_detailed(
    client=media_admin_client, body=MarkReadDto(series_id=series_id),
  ).status_code == 200


def test_review_series(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  review = post_api_review_series.sync_detailed(
    client=media_admin_client,
    body=UpdateUserReviewDto(series_id=media_library.second_series_id, body='Phase 3 review'),
  )
  assert review.status_code == 200
  assert review.parsed is not None


def test_delete_pending_user(media_admin_client: AuthenticatedClient) -> None:
  '''Self-contained: invite a throwaway user, then delete it.'''
  email = f'zz-{uuid.uuid4().hex[:8]}@example.com'
  invite = post_api_account_invite.sync_detailed(
    client=media_admin_client,
    body=InviteUserDto(
      email=email,
      roles=[],
      age_restriction=AgeRestrictionDto(age_rating=AgeRating.NOT_APPLICABLE, include_unknowns=False),
    ),
  )
  assert invite.status_code == 200

  users = get_api_users.sync_detailed(client=media_admin_client, include_pending=True)
  assert users.status_code == 200
  pending = [user for user in users.parsed or [] if user.email == email]
  assert pending and pending[0].username
  username = pending[0].username

  deleted = delete_api_users_delete_user.sync_detailed(client=media_admin_client, username=username)
  assert deleted.status_code == 200
  users = get_api_users.sync_detailed(client=media_admin_client, include_pending=True)
  assert users.status_code == 200
  assert all(user.username != username for user in users.parsed or [])


def test_library_create_and_delete(media_admin_client: AuthenticatedClient) -> None:
  '''Create two throwaway libraries on an existing folder, delete one via
  the generated single delete and the other via raw-httpx delete-multiple.

  DESIGN quirk #18, re-verified against the v0.9.1.4 source: single delete
  returns `false` only when a scan task is running for the library (or the
  id does not exist) — the earlier "false for a fresh unscanned library"
  observation was a scan-in-progress artifact, and the endpoint deletes
  fine otherwise. The generated delete-multiple crashes
  (`isinstance(body, list[int])` — generator bug), so it goes over raw
  httpx, and the server answers it with an empty body where the spec
  declares a boolean.
  '''

  # The server is throwaway, so the created libraries are left behind on
  # any failure path — no cleanup assertion beyond the deletes themselves.
  names = ['it-zz-lib-1', 'it-zz-lib-2']
  created_ids: list[int] = []
  for name in names:
    created = post_api_library_create.sync_detailed(
      client=media_admin_client,
      body=UpdateLibraryDto(
        id=0,
        name=name,
        type_=LibraryType.MANGA,
        folders=['/media/comics/ipsum'],
        folder_watching=False,
        include_in_dashboard=False,
        include_in_search=True,
        manage_collections=False,
        manage_reading_lists=False,
        allow_scrobbling=False,
        allow_metadata_matching=False,
        enable_metadata=True,
        remove_prefix_for_sort_name=False,
        inherit_web_links_from_first_chapter=False,
        file_group_types=[FileTypeGroup.ARCHIVE],
        exclude_patterns=[],
        metadata_provider=MetadataProvider.MANGABAKA,
      ),
    )
    assert created.status_code == 200 and created.parsed is not None and isinstance(created.parsed.id, int)
    created_ids.append(created.parsed.id)

  libraries = get_api_library_libraries.sync_detailed(client=media_admin_client)
  assert libraries.status_code == 200
  for name in names:
    assert any(library.name == name for library in libraries.parsed or []), name

  # Single delete via the generated client (the spec declares a boolean).
  single = delete_api_library_delete.sync_detailed(
    client=media_admin_client, library_id=created_ids[0],
  )
  assert single.status_code == 200, f'{single.status_code} {single.content!r}'
  if single.parsed is False:
    # A scan task was running for the library (DESIGN quirk #18) — retry.
    time.sleep(5.0)
    single = delete_api_library_delete.sync_detailed(
      client=media_admin_client, library_id=created_ids[0],
    )
    assert single.status_code == 200, f'{single.status_code} {single.content!r}'
  assert single.parsed is True

  # Multiple delete over raw httpx.
  deleted = _delete_multiple_libraries(media_admin_client, [created_ids[1]])
  assert deleted.status_code == 200, f'HTTP {deleted.status_code} {deleted.content!r}'
  # The spec documents a boolean body; the server sends none (DESIGN quirk
  # #18) — assert the library list instead.
  libraries = get_api_library_libraries.sync_detailed(client=media_admin_client)
  assert libraries.status_code == 200
  remaining = [library for library in libraries.parsed or [] if library.name == names[1]]

  if remaining:
    # A scan task was running for the library (DESIGN quirk #18); scan it
    # so it has content, then retry.
    scan = post_api_library_scan.sync_detailed(
      client=media_admin_client, library_id=created_ids[1], force=True,
    )
    assert scan.status_code == 200
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
      series = post_api_series_v_2.sync_detailed(
        client=media_admin_client, body=SeriesFilterV2Dto(), page_number=1, page_size=100,
      )
      if series.status_code == 200 and any(s.library_id == created_ids[1] for s in series.parsed or []):
        break
      time.sleep(3.0)

    deleted = _delete_multiple_libraries(media_admin_client, [created_ids[1]])
    assert deleted.status_code == 200, f'HTTP {deleted.status_code} {deleted.content!r}'

  libraries = get_api_library_libraries.sync_detailed(client=media_admin_client)
  assert libraries.status_code == 200
  for name in names:
    assert all(library.name != name for library in libraries.parsed or []), name


def _delete_multiple_libraries(admin_client: AuthenticatedClient, library_ids: list[int]) -> httpx.Response:
  '''Raw-httpx workaround for the generated delete-multiple crash
  (`isinstance(body, list[int])` — generator bug, DESIGN quirk #18).'''
  return httpx.request(
    'DELETE',
    f'{admin_client._base_url}/api/Library/delete-multiple',  # noqa: SLF001
    json=library_ids,
    headers={'Authorization': f'Bearer {admin_client.token}'},
  )
