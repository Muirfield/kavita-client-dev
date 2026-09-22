'''Session-ending destructive operations (coverage-plan Phase 3).

`test_zz_*` runs after every other module (pytest's alphabetical ordering),
so these tests can tear down the shared media fixture. Everything here is
safe because the server is throwaway.
'''

from __future__ import annotations

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.server import post_api_server_backup_db, post_api_server_cleanup
from kavita_client.api.series import post_api_series_delete_multiple, post_api_series_v_2
from kavita_client.api.settings import post_api_settings_reset
from kavita_client.models import DeleteSeriesDto, SeriesFilterV2Dto

from kavita_instance import MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_zz_server_backup_db(media_admin_client: AuthenticatedClient) -> None:
  assert post_api_server_backup_db.sync_detailed(client=media_admin_client).status_code == 200


def test_zz_server_cleanup(media_admin_client: AuthenticatedClient) -> None:
  assert post_api_server_cleanup.sync_detailed(client=media_admin_client).status_code == 200


def test_zz_series_delete_multiple(media_library: MediaLibrary, media_admin_client: AuthenticatedClient) -> None:
  series_id = media_library.second_series_id
  deleted = post_api_series_delete_multiple.sync_detailed(
    client=media_admin_client, body=DeleteSeriesDto(series_ids=[series_id]),
  )
  assert deleted.status_code == 200

  listing = post_api_series_v_2.sync_detailed(
    client=media_admin_client, body=SeriesFilterV2Dto(), page_number=1, page_size=100,
  )
  assert listing.status_code == 200
  assert all(series.id != series_id for series in listing.parsed or [])


def test_zzz_settings_reset(media_admin_client: AuthenticatedClient) -> None:
  '''Must be the very last test of the session.'''
  assert post_api_settings_reset.sync_detailed(client=media_admin_client).status_code == 200
