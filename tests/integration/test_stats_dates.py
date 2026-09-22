'''Date-ranged Stats endpoints against the populated media fixture
(TODO-coverage-next Batch A2).

DESIGN quirk #8 dropped these for 400 on a fresh server; the media fixture
provides real reading history (progress on page 3 of the first comic
chapter), so each is re-attempted with a date range covering the fixture's
progress. Entries that still fail live verification get dropped here and
recorded in DESIGN quirk #8.
'''

from __future__ import annotations

import datetime

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.stats import (
  get_api_stats_avg_time_by_hour,
  get_api_stats_favorite_authors,
  get_api_stats_genre_breakdown,
  get_api_stats_page_spread,
  get_api_stats_pages_per_year,
  get_api_stats_reading_activity,
  get_api_stats_reading_history_series_series_id,
  get_api_stats_reading_pace,
  get_api_stats_reads_by_month,
  get_api_stats_tag_breakdown,
  get_api_stats_word_spread,
  get_api_stats_words_per_year,
)

from kavita_instance import KavitaInstance, MediaLibrary

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def _date_range(instance: KavitaInstance) -> dict[str, object]:
  '''Date range covering the fixture's reading progress.'''
  now = datetime.datetime.now(datetime.timezone.utc)
  return {
    'user_id': instance.admin_user_id,
    'start_date': now - datetime.timedelta(days=7),
    'end_date': now,
  }


def _user_id(instance: KavitaInstance) -> dict[str, int]:
  return {'user_id': instance.admin_user_id}


def _reading_activity(instance: KavitaInstance) -> dict[str, object]:
  '''reading-activity also needs the year: with it unset the server
  constructs DateTime(year=0, …) and 500s (verified live).'''
  kwargs = _date_range(instance)
  kwargs['year'] = datetime.date.today().year
  return kwargs


# (operation, endpoint fn, kwargs or kwargs-builder)
DATE_RANGED: list[tuple[str, object, object]] = [
  ('GET /api/Stats/avg-time-by-hour', get_api_stats_avg_time_by_hour.sync_detailed, _date_range),
  ('GET /api/Stats/favorite-authors', get_api_stats_favorite_authors.sync_detailed, _date_range),
  ('GET /api/Stats/genre-breakdown', get_api_stats_genre_breakdown.sync_detailed, _date_range),
  ('GET /api/Stats/page-spread', get_api_stats_page_spread.sync_detailed, _date_range),
  ('GET /api/Stats/pages-per-year', get_api_stats_pages_per_year.sync_detailed, _user_id),
  ('GET /api/Stats/reading-activity', get_api_stats_reading_activity.sync_detailed, _reading_activity),
  ('GET /api/Stats/reading-pace', get_api_stats_reading_pace.sync_detailed, _date_range),
  ('GET /api/Stats/reads-by-month', get_api_stats_reads_by_month.sync_detailed, _date_range),
  ('GET /api/Stats/tag-breakdown', get_api_stats_tag_breakdown.sync_detailed, _date_range),
  ('GET /api/Stats/word-spread', get_api_stats_word_spread.sync_detailed, _date_range),
  ('GET /api/Stats/words-per-year', get_api_stats_words_per_year.sync_detailed, _user_id),
]


@pytest.mark.parametrize(
  ('op', 'fn', 'kwargs'),
  DATE_RANGED,
  ids=[entry[0] for entry in DATE_RANGED],
)
def test_date_ranged_stats(
  media_kavita_server: KavitaInstance,
  op: str,
  fn: object,
  kwargs: object,
) -> None:
  call_kwargs = kwargs(media_kavita_server) if callable(kwargs) else kwargs
  assert isinstance(call_kwargs, dict)
  resp = fn(client=media_kavita_server.admin_client, **call_kwargs)  # type: ignore[misc]
  assert resp.status_code == 200, f'{op}: HTTP {resp.status_code} {resp.content!r}'
  assert resp.parsed is not None, f'{op}: HTTP 200 but no parsed body'


def test_reading_history_for_series(
  media_library: MediaLibrary,
  media_admin_client: AuthenticatedClient,
) -> None:
  '''The last uncovered Stats operation: per-series reading session
  history. The fixture posts progress on the first comic chapter, so the
  list parses (it may still be empty if no reading sessions were
  generated — the contract only documents the 200 + list). `tzId` is
  required despite the spec marking it optional (verified live).'''
  resp = get_api_stats_reading_history_series_series_id.sync_detailed(
    series_id=media_library.comic_series_id, tz_id='UTC', client=media_admin_client,
  )
  assert resp.status_code == 200, f'{resp.status_code} {resp.content!r}'
  assert resp.parsed is not None
