'''Fresh-install read-only sweep (docs/coverage-plan.md, Phase 1).

Parametrized entries, one per read-only operation that works on a fresh
server. Each entry was verified once against the live server and annotated
with the client to use (`use_admin`) and its quirks (see the comments and
docs/DESIGN.md). Assertions are contract-first: the documented 200 and,
where the spec documents a body, a parsed one. Failures report the
operation, status, and body.

`kwargs` may be a plain dict or a callable that builds it from the running
instance (e.g. endpoints that need the admin's user id). `fix_id` marks an
entry whose parsing depends on a fix_spec.py fix: on the nightly (raw spec)
build the known upstream bug is recorded as xfail instead of failing.

Verified and dropped from the sweep (see docs/DESIGN.md quirks):
- GET /api/License/info: 204 No Content when no license (spec documents 200).
- GET /api/Plugin/authkey-expires: 400 (server requires context not in spec).
- GET /api/Users/tokens: 403, restricted to Kavita+ (non-goal).
- The date-range Stats endpoints formerly dropped here (400 on a fresh
  server) are covered by `test_stats_dates.py` against the populated
  fixture (TODO-coverage-next Batch A2).
- GET /api/Stats/server/file-breakdown was dropped for the object-vs-array
  parse crash; now swept with the Fix 5 client (xfails on nightly).
'''

from __future__ import annotations

import datetime

import pytest

from kavita_client.api.account import (
  get_api_account,
  get_api_account_email_confirmed,
  get_api_account_is_email_valid,
  get_api_account_oidc_authenticated,
  get_api_account_opds_url,
  get_api_account_refresh_account,
)
from kavita_client.api.device import (
  get_api_device,
  get_api_device_client_all_devices,
  get_api_device_client_devices,
)
from kavita_client.api.font import get_api_font_all
from kavita_client.api.license_ import (
  get_api_license_has_license,
  get_api_license_products,
  get_api_license_provider_health,
  get_api_license_stats,
  get_api_license_valid_license,
)
from kavita_client.api.locale import get_api_locale
from kavita_client.api.metadata import (
  get_api_metadata_age_ratings,
  get_api_metadata_all_bcp_47_languages,
  get_api_metadata_all_languages,
  get_api_metadata_genres,
  get_api_metadata_language_title,
  get_api_metadata_languages,
  get_api_metadata_people,
  get_api_metadata_people_by_role,
  get_api_metadata_publication_status,
  get_api_metadata_readinglist_tags,
  get_api_metadata_tags,
)
from kavita_client.api.server import (
  get_api_server_changelog,
  get_api_server_check_for_updates,
  get_api_server_check_out_of_date,
  get_api_server_check_update,
  get_api_server_is_task_running,
  get_api_server_logs,
  get_api_server_media_errors,
)
from kavita_client.api.settings import (
  get_api_settings_base_url,
  get_api_settings_is_email_setup,
  get_api_settings_is_valid_cron,
  get_api_settings_library_types,
  get_api_settings_log_levels,
  get_api_settings_metadata_settings,
  get_api_settings_oidc,
  get_api_settings_opds_enabled,
  get_api_settings_task_frequencies,
)
from kavita_client.api.stats import (
  get_api_stats_day_breakdown,
  get_api_stats_device_client_type,
  get_api_stats_device_device_type,
  get_api_stats_files_added_over_time,
  get_api_stats_most_active_users,
  get_api_stats_popular_decades,
  get_api_stats_popular_genres,
  get_api_stats_popular_libraries,
  get_api_stats_popular_people,
  get_api_stats_popular_reading_list,
  get_api_stats_popular_series,
  get_api_stats_popular_tags,
  get_api_stats_reading_counts,
  get_api_stats_reading_history,
  get_api_stats_server_count_manga_format,
  get_api_stats_server_count_publication_status,
  get_api_stats_server_file_breakdown,
  get_api_stats_server_file_extension,
  get_api_stats_total_reads,
  get_api_stats_user_read,
  get_api_stats_user_stats,
)
from kavita_client.api.theme import get_api_theme
from kavita_client.api.users import (
  get_api_users_get_preferences,
  get_api_users_has_profile_shared,
  get_api_users_names,
  get_api_users_profile_info,
)
from kavita_client.models.person_role import PersonRole

from kavita_instance import KavitaInstance, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def _admin_id(instance: KavitaInstance) -> dict[str, int]:
  return {'user_id': instance.admin_user_id}


def _user_stats(instance: KavitaInstance) -> dict[str, object]:
  '''user-stats needs a date range and a user id.'''
  now = datetime.datetime.now(datetime.timezone.utc)
  return {
    'user_id': instance.admin_user_id,
    'start_date': now - datetime.timedelta(days=30),
    'end_date': now,
  }


FIX2 = 'Fix 2 (nullable enums)'
FIX3 = 'Fix 3 (bare string bodies)'
FIX5 = 'Fix 5 (file-breakdown response)'

# (operation, endpoint fn, kwargs or kwargs-builder, use_admin, expect_parsed, fix_id)
SWEEP: list[tuple[str, object, object, bool, bool, str | None]] = [
  # --- Account (admin)
  ('GET /api/Account', get_api_account.sync_detailed, {}, True, True, None),
  ('GET /api/Account/refresh-account', get_api_account_refresh_account.sync_detailed, {}, True, True, None),
  ('GET /api/Account/email-confirmed', get_api_account_email_confirmed.sync_detailed, {}, True, True, None),
  ('GET /api/Account/is-email-valid', get_api_account_is_email_valid.sync_detailed, {}, True, True, None),
  ('GET /api/Account/oidc-authenticated', get_api_account_oidc_authenticated.sync_detailed, {}, True, True, None),
  ('GET /api/Account/opds-url', get_api_account_opds_url.sync_detailed, {}, True, True, FIX3),

  # --- Settings (admin)
  ('GET /api/Settings/base-url', get_api_settings_base_url.sync_detailed, {}, True, True, FIX3),
  ('GET /api/Settings/is-email-setup', get_api_settings_is_email_setup.sync_detailed, {}, True, True, None),
  ('GET /api/Settings/is-valid-cron', get_api_settings_is_valid_cron.sync_detailed, {'cron_expression': '0 0 * * *'}, True, True, None),
  ('GET /api/Settings/library-types', get_api_settings_library_types.sync_detailed, {}, True, True, None),
  ('GET /api/Settings/log-levels', get_api_settings_log_levels.sync_detailed, {}, True, True, None),
  ('GET /api/Settings/metadata-settings', get_api_settings_metadata_settings.sync_detailed, {}, True, True, FIX2),
  ('GET /api/Settings/oidc', get_api_settings_oidc.sync_detailed, {}, True, True, None),
  ('GET /api/Settings/opds-enabled', get_api_settings_opds_enabled.sync_detailed, {}, True, True, None),
  ('GET /api/Settings/task-frequencies', get_api_settings_task_frequencies.sync_detailed, {}, True, True, None),

  # --- Metadata (admin: the server rejects anonymous metadata calls with 401)
  ('GET /api/Metadata/age-ratings', get_api_metadata_age_ratings.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/all-languages', get_api_metadata_all_languages.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/all-bcp47-languages', get_api_metadata_all_bcp_47_languages.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/genres', get_api_metadata_genres.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/tags', get_api_metadata_tags.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/languages', get_api_metadata_languages.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/publication-status', get_api_metadata_publication_status.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/readinglist-tags', get_api_metadata_readinglist_tags.sync_detailed, {}, True, True, None),
  ('GET /api/Metadata/language-title', get_api_metadata_language_title.sync_detailed, {'code': 'en'}, True, True, FIX3),
  ('GET /api/Metadata/people-by-role', get_api_metadata_people_by_role.sync_detailed, {'role': PersonRole.WRITER}, True, True, None),
  ('GET /api/Metadata/people', get_api_metadata_people.sync_detailed, {}, True, True, None),

  # --- Stats (admin; empty-but-valid on a fresh server)
  ('GET /api/Stats/day-breakdown', get_api_stats_day_breakdown.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/device/client-type', get_api_stats_device_client_type.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/device/device-type', get_api_stats_device_device_type.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/files-added-over-time', get_api_stats_files_added_over_time.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/most-active-users', get_api_stats_most_active_users.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-decades', get_api_stats_popular_decades.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-genres', get_api_stats_popular_genres.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-libraries', get_api_stats_popular_libraries.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-people', get_api_stats_popular_people.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-reading-list', get_api_stats_popular_reading_list.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-series', get_api_stats_popular_series.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/popular-tags', get_api_stats_popular_tags.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/reading-counts', get_api_stats_reading_counts.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/reading-history', get_api_stats_reading_history.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/server/count/manga-format', get_api_stats_server_count_manga_format.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/server/count/publication-status', get_api_stats_server_count_publication_status.sync_detailed, {}, True, True, None),
  ('GET /api/Stats/server/file-extension', get_api_stats_server_file_extension.sync_detailed, {'file_extension': '.cbz'}, True, False, None),
  ('GET /api/Stats/server/file-breakdown', get_api_stats_server_file_breakdown.sync_detailed, {}, True, True, FIX5),
  ('GET /api/Stats/total-reads', get_api_stats_total_reads.sync_detailed, _admin_id, True, True, None),
  ('GET /api/Stats/user-read', get_api_stats_user_read.sync_detailed, _admin_id, True, True, None),
  ('GET /api/Stats/user-stats', get_api_stats_user_stats.sync_detailed, _user_stats, True, True, None),

  # --- Server (admin)
  ('GET /api/Server/media-errors', get_api_server_media_errors.sync_detailed, {}, True, True, None),
  ('GET /api/Server/is-task-running', get_api_server_is_task_running.sync_detailed, {'method_name': 'Scan'}, True, True, None),
  ('GET /api/Server/logs', get_api_server_logs.sync_detailed, {}, True, False, None),
  ('GET /api/Server/changelog', get_api_server_changelog.sync_detailed, {}, True, True, None),
  ('GET /api/Server/check-for-updates', get_api_server_check_for_updates.sync_detailed, {}, True, False, None),
  ('GET /api/Server/check-out-of-date', get_api_server_check_out_of_date.sync_detailed, {}, True, True, None),
  ('GET /api/Server/check-update', get_api_server_check_update.sync_detailed, {}, True, True, None),

  # --- Device (admin; empty lists on a fresh server)
  ('GET /api/Device', get_api_device.sync_detailed, {}, True, True, None),
  ('GET /api/Device/client/all-devices', get_api_device_client_all_devices.sync_detailed, {}, True, True, None),
  ('GET /api/Device/client/devices', get_api_device_client_devices.sync_detailed, {}, True, True, None),

  # --- License (admin; GETs need no subscription)
  ('GET /api/License/has-license', get_api_license_has_license.sync_detailed, {}, True, True, None),
  ('GET /api/License/products', get_api_license_products.sync_detailed, {}, True, True, None),
  ('GET /api/License/provider-health', get_api_license_provider_health.sync_detailed, {}, True, True, None),
  ('GET /api/License/stats', get_api_license_stats.sync_detailed, {}, True, True, None),
  ('GET /api/License/valid-license', get_api_license_valid_license.sync_detailed, {}, True, True, None),

  # --- Theme (admin; the browse/download endpoints hit the network)
  ('GET /api/Theme', get_api_theme.sync_detailed, {}, True, True, None),

  # --- Font (admin: anonymous calls get 401)
  ('GET /api/Font/all', get_api_font_all.sync_detailed, {}, True, True, None),

  # --- Locale (anonymous)
  ('GET /api/Locale', get_api_locale.sync_detailed, {}, False, True, None),

  # --- Users (admin)
  ('GET /api/Users/names', get_api_users_names.sync_detailed, {}, True, True, None),
  ('GET /api/Users/profile-info', get_api_users_profile_info.sync_detailed, _admin_id, True, True, None),
  ('GET /api/Users/get-preferences', get_api_users_get_preferences.sync_detailed, {}, True, True, None),
  ('GET /api/Users/has-profile-shared', get_api_users_has_profile_shared.sync_detailed, _admin_id, True, True, None),
]


@pytest.mark.parametrize(
  ('op', 'fn', 'kwargs', 'use_admin', 'expect_parsed', 'fix_id'),
  SWEEP,
  ids=[entry[0] for entry in SWEEP],
)
def test_read_only_sweep(
  kavita_server: KavitaInstance,
  op: str,
  fn: object,
  kwargs: object,
  use_admin: bool,
  expect_parsed: bool,
  fix_id: str | None,
) -> None:
  client = kavita_server.admin_client if use_admin else kavita_server.client
  call_kwargs = kwargs(kavita_server) if callable(kwargs) else kwargs
  assert isinstance(call_kwargs, dict)
  try:
    resp = fn(client=client, **call_kwargs)  # type: ignore[misc]
  except Exception as exc:  # noqa: BLE001
    if fix_id is not None:
      expect_upstream_fix(fix_id, repr(exc))
    raise
  assert resp.status_code == 200, f'{op}: HTTP {resp.status_code} {resp.content!r}'
  if expect_parsed:
    assert resp.parsed is not None, f'{op}: HTTP 200 but no parsed body'
