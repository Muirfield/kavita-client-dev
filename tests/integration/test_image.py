'''Image (cover) endpoints against the populated library (coverage-plan Phase 2).'''

from __future__ import annotations

import base64
import pathlib

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.image import (
  get_api_image_chapter_cover,
  get_api_image_library_cover,
  get_api_image_series_cover,
  get_api_image_user_cover,
  get_api_image_volume_cover,
)
from kavita_client.api.upload import (
  post_api_upload_library,
  post_api_upload_user,
)
from kavita_client.models import UploadCoverFileDto

from kavita_instance import KavitaInstance, MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / 'tests' / 'data'


def _cover_b64() -> str:
  return base64.b64encode((DATA_DIR / 'cover.jpg').read_bytes()).decode('ascii')


def test_chapter_cover(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_image_chapter_cover.sync_detailed(client=media_admin_client, chapter_id=media_library.read_chapter_id)
  assert resp.status_code == 200
  assert resp.content


def test_series_cover(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_image_series_cover.sync_detailed(client=media_admin_client, series_id=media_library.comic_series_id)
  assert resp.status_code == 200
  assert resp.content


def test_volume_cover(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  resp = get_api_image_volume_cover.sync_detailed(client=media_admin_client, volume_id=media_library.comic_volume_ids[0])
  assert resp.status_code == 200
  assert resp.content


def test_library_cover_upload_and_get(
  media_library: MediaLibrary,
  media_kavita_server: KavitaInstance,
  media_admin_client: AuthenticatedClient,
) -> None:
  '''Both GETs 404 until a cover is set (DESIGN quirk #15); the Upload
  endpoints take the image as a plain base64 payload in `url` (verified
  against the v0.9.1.4 source — `CreateThumbnailFromBase64`).'''
  upload = post_api_upload_library.sync_detailed(
    client=media_admin_client,
    body=UploadCoverFileDto(id=media_library.manga_library_id, url=_cover_b64(), lock_cover=True),
  )
  assert upload.status_code == 200, f'{upload.status_code} {upload.content!r}'

  cover = get_api_image_library_cover.sync_detailed(
    client=media_admin_client, library_id=media_library.manga_library_id,
  )
  assert cover.status_code == 200, f'{cover.status_code} {cover.content!r}'
  assert cover.content
  assert cover.headers.get('content-type', '').startswith('image/')


def test_user_cover_upload_and_get(
  media_library: MediaLibrary,
  media_kavita_server: KavitaInstance,
  media_admin_client: AuthenticatedClient,
) -> None:
  '''The user endpoint must be called for yourself (`Id == UserId`), so the
  admin uploads their own avatar and reads it back.'''
  upload = post_api_upload_user.sync_detailed(
    client=media_admin_client,
    body=UploadCoverFileDto(id=media_kavita_server.admin_user_id, url=_cover_b64(), lock_cover=True),
  )
  assert upload.status_code == 200, f'{upload.status_code} {upload.content!r}'

  cover = get_api_image_user_cover.sync_detailed(
    client=media_admin_client, user_id=media_kavita_server.admin_user_id,
  )
  assert cover.status_code == 200, f'{cover.status_code} {cover.content!r}'
  assert cover.content
  assert cover.headers.get('content-type', '').startswith('image/')
