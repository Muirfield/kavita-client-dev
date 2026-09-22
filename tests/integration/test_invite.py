'''The invite endpoint is the reason fix_spec.py exists: the server returns an
`InviteUserResponse` object, but the raw spec declares a plain string, which
makes the generated client choke at runtime. These tests pin that fix against
the live server.

Server-side quirks the tests have to accommodate (Kavita v0.9.1.4 source):

- `InviteUser` dereferences `dto.Roles` and `dto.AgeRestriction` without null
  checks, so a payload that omits them fails with a generic 400. Both must be
  sent explicitly.
- When email is not configured the response is `emailSent: false`,
  `invalidEmail: true` — and `emailLink` still carries a working invite link.
'''

from __future__ import annotations

import uuid

import httpx
import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.account import get_api_account_invite_url, post_api_account_invite
from kavita_client.api.users import get_api_users
from kavita_client.models import AgeRating, AgeRestrictionDto, InviteUserDto, InviteUserResponse

from kavita_instance import KavitaInstance, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.release]


def _invite_body() -> tuple[InviteUserDto, str]:
  '''Build an invite payload the server can actually process.'''
  email = f'it-invitee-{uuid.uuid4().hex[:8]}@example.com'
  body = InviteUserDto(
    email=email,
    roles=[],
    age_restriction=AgeRestrictionDto(age_rating=AgeRating.NOT_APPLICABLE, include_unknowns=False),
  )
  return body, email


def test_invite_returns_invite_user_response(
  admin_client: AuthenticatedClient,
  kavita_server: KavitaInstance,
) -> None:
  body, _ = _invite_body()
  resp = post_api_account_invite.sync_detailed(client=admin_client, body=body)
  # The nightly client still has the raw string schema, so the response does
  # not parse as InviteUserResponse; that is the known upstream bug that
  # fix_spec Fix 1 works around, recorded as xfail.
  if not isinstance(resp.parsed, InviteUserResponse):
    expect_upstream_fix('Fix 1 (invite response schema)', f'parsed as {type(resp.parsed).__name__}')
  assert resp.status_code == 200
  assert isinstance(resp.parsed, InviteUserResponse)
  assert isinstance(resp.parsed.email_sent, bool)
  assert isinstance(resp.parsed.invalid_email, bool)
  # No email service is configured on the test server: nothing can be sent
  # and the address is flagged invalid, but the invite link is still usable.
  assert resp.parsed.email_sent is False
  assert resp.parsed.invalid_email is True
  assert isinstance(resp.parsed.email_link, str) and resp.parsed.email_link

  link = resp.parsed.email_link
  url = link if link.startswith('http') else f'{kavita_server.base_url}{link}'
  assert httpx.get(url, follow_redirects=True, timeout=10.0).status_code == 200


def test_invite_url_for_pending_user(admin_client: AuthenticatedClient) -> None:
  '''The invite-url endpoint re-generates the setup link for a *pending*
  (unconfirmed) user and requires that user's id.'''
  body, email = _invite_body()
  invite = post_api_account_invite.sync_detailed(client=admin_client, body=body)
  assert invite.status_code == 200

  users = get_api_users.sync_detailed(client=admin_client, include_pending=True)
  assert users.status_code == 200
  pending = [user for user in users.parsed or [] if user.email == email]
  assert pending, f'pending user {email} not found'
  assert isinstance(pending[0].id, int)

  # The fixed client reads the bare URL body as text (fix_spec Fix 3). The
  # nightly client parses it with response.json() and crashes; that is the
  # known upstream bug, recorded as xfail.
  try:
    resp = get_api_account_invite_url.sync_detailed(
      client=admin_client,
      user_id=pending[0].id,
      with_base_url=True,
    )
  except Exception as exc:  # noqa: BLE001
    expect_upstream_fix('Fix 3 (bare string bodies)', repr(exc))
    raise
  assert resp.status_code == 200
  assert isinstance(resp.parsed, str)
  link = resp.parsed
  assert link.startswith('http')

  assert httpx.get(link, follow_redirects=True, timeout=10.0).status_code == 200
