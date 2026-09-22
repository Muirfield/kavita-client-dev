'''Broad sweep of endpoints that work on a fresh server install.

Used for release verification and, against `:nightly`, as the regression probe
for Kavita dev builds. Assertions are limited to what the spec documents
(status codes and response shapes), so a failure means the server no longer
honors the client's contract.

Set `KAVITA_EXPECTED_VERSION` to additionally assert the server reports that
exact version (via `GET /api/Server/server-info-slim`).
'''

from __future__ import annotations

import os

import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.account import get_api_account_roles
from kavita_client.api.email import get_api_email_all
from kavita_client.api.library import get_api_library_libraries
from kavita_client.api.server import get_api_server_jobs, get_api_server_server_info_slim
from kavita_client.api.settings import get_api_settings
from kavita_client.api.stats import get_api_stats_server_stats

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def test_server_info_slim_reports_version(admin_client: AuthenticatedClient) -> None:
  resp = get_api_server_server_info_slim.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed.kavita_version, str) and resp.parsed.kavita_version
  expected = os.environ.get('KAVITA_EXPECTED_VERSION')
  if expected:
    assert resp.parsed.kavita_version == expected


def test_account_roles(admin_client: AuthenticatedClient) -> None:
  resp = get_api_account_roles.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
  assert all(isinstance(role, str) for role in resp.parsed)


def test_settings(admin_client: AuthenticatedClient) -> None:
  resp = get_api_settings.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert resp.parsed is not None


def test_libraries_empty_on_fresh_install(admin_client: AuthenticatedClient) -> None:
  resp = get_api_library_libraries.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert resp.parsed == []


def test_server_stats(admin_client: AuthenticatedClient) -> None:
  resp = get_api_stats_server_stats.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert resp.parsed is not None


def test_email_history_empty(admin_client: AuthenticatedClient) -> None:
  resp = get_api_email_all.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert resp.parsed == []


def test_jobs(admin_client: AuthenticatedClient) -> None:
  resp = get_api_server_jobs.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)
