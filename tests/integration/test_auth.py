'''Authentication flow against a real Kavita server.

The session fixture registers the admin account; these tests verify the
registration/login contract the spec documents: both endpoints return a
`UserDto` whose `token` carries the JWT.
'''

from __future__ import annotations

import httpx
import pytest

from kavita_client import AuthenticatedClient, Client, errors
from kavita_client.api.account import (
  get_api_account_auth_keys,
  post_api_account_login,
  post_api_account_refresh_token,
  post_api_account_register,
)
from kavita_client.api.admin import get_api_admin_exists
from kavita_client.api.health import get_api_health
from kavita_client.api.users import get_api_users
from kavita_client.models import LoginDto, RegisterDto, TokenRequestDto, UserDto

from kavita_instance import KavitaInstance, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.release]


def test_health_endpoint(kavita_server: KavitaInstance) -> None:
  # Raw httpx: the server answers with a bare `Ok` body (see below).
  resp = httpx.get(f'{kavita_server.base_url}/api/Health', timeout=10.0)
  assert resp.status_code == 200
  assert resp.text == 'Ok'


def test_health_endpoint_via_generated_client(client: Client) -> None:
  # The fixed client reads the bare `Ok` body as text (fix_spec Fix 3). The
  # nightly client still parses it with response.json() and crashes; that is
  # the known upstream bug, recorded as xfail.
  try:
    resp = get_api_health.sync_detailed(client=client)
  except Exception as exc:  # noqa: BLE001
    expect_upstream_fix('Fix 3 (bare string bodies)', repr(exc))
    raise
  assert resp.status_code == 200
  assert resp.parsed == 'Ok'


def test_admin_exists_after_first_registration(client: Client) -> None:
  resp = get_api_admin_exists.sync_detailed(client=client)
  assert resp.status_code == 200
  assert resp.parsed is True


def test_login_returns_user_with_token(kavita_server: KavitaInstance) -> None:
  resp = post_api_account_login.sync_detailed(
    client=kavita_server.client,
    body=LoginDto(
      username=kavita_server.admin_username,
      password=kavita_server.admin_password,
    ),
  )
  assert resp.status_code == 200
  assert isinstance(resp.parsed, UserDto)
  assert isinstance(resp.parsed.token, str) and resp.parsed.token


def test_refresh_token(kavita_server: KavitaInstance) -> None:
  '''POST /api/Account/refresh-token takes the JWT + refresh token from a
  login and returns a fresh pair (the server consumes the old refresh
  token — nothing else in the suite uses it, so the rotation is safe).'''
  login = post_api_account_login.sync_detailed(
    client=kavita_server.client,
    body=LoginDto(
      username=kavita_server.admin_username,
      password=kavita_server.admin_password,
    ),
  )
  assert login.status_code == 200 and login.parsed is not None
  refreshed = post_api_account_refresh_token.sync_detailed(
    client=kavita_server.client,
    body=TokenRequestDto(token=login.parsed.token, refresh_token=login.parsed.refresh_token),
  )
  assert refreshed.status_code == 200, f'{refreshed.status_code} {refreshed.content!r}'
  assert isinstance(refreshed.parsed, TokenRequestDto)
  assert isinstance(refreshed.parsed.token, str) and refreshed.parsed.token
  assert isinstance(refreshed.parsed.refresh_token, str) and refreshed.parsed.refresh_token


def test_register_after_setup_is_rejected(kavita_server: KavitaInstance) -> None:
  # RegisterFirstUser on the server returns BadRequest once an admin exists,
  # so registration is first-user-only. The spec documents only 200; any
  # other status must not parse as a successful registration (the successful
  # first registration is exercised by the session fixture).
  client = Client(base_url=kavita_server.base_url)  # do not raise on unexpected status
  resp = post_api_account_register.sync_detailed(
    client=client,
    body=RegisterDto(
      username='it-second-user',
      password='it-second-user-password',
      email='second@example.com',
    ),
  )
  assert resp.status_code != 200
  assert resp.parsed is None


def test_authenticated_endpoint_accepts_token(
  admin_client: AuthenticatedClient,
  kavita_server: KavitaInstance,
) -> None:
  resp = get_api_users.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  usernames = {user.username for user in resp.parsed or []}
  assert kavita_server.admin_username in usernames


def test_auth_keys_endpoint(admin_client: AuthenticatedClient) -> None:
  resp = get_api_account_auth_keys.sync_detailed(client=admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, list)


def test_wrong_password_is_rejected(kavita_server: KavitaInstance) -> None:
  # The spec documents only 200 for login; anything else must not parse as
  # a successful login.
  client = Client(base_url=kavita_server.base_url)  # do not raise on unexpected status
  resp = post_api_account_login.sync_detailed(
    client=client,
    body=LoginDto(
      username=kavita_server.admin_username,
      password='wrong-password',
    ),
  )
  assert resp.status_code != 200
  assert resp.parsed is None


def test_anonymous_request_on_authenticated_endpoint_is_rejected(client: Client) -> None:
  with pytest.raises(errors.UnexpectedStatus) as excinfo:
    get_api_account_auth_keys.sync_detailed(client=client)
  assert excinfo.value.status_code in (401, 403)
