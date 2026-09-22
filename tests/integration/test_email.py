'''Email flows against Mailpit (coverage-plan Phase 3).

The `mail_kavita_server` fixture boots a fresh Kavita server with its SMTP
pointed at a Mailpit sidecar (configured through the generated Settings
POST); the tests assert the mail was actually delivered via Mailpit's HTTP
API.
'''

from __future__ import annotations

import re
import time
import uuid

import httpx
import pytest

from kavita_client import AuthenticatedClient
from kavita_client.api.account import (
  post_api_account_forgot_password,
  post_api_account_invite,
  post_api_account_login,
)
from kavita_client.models import AgeRating, AgeRestrictionDto, InviteUserDto, InviteUserResponse, LoginDto

from kavita_instance import KavitaInstance, expect_upstream_fix

pytestmark = [pytest.mark.integration, pytest.mark.compat]


def _mailpit_messages(mailpit: dict[str, str]) -> list[dict]:
  resp = httpx.get(f"http://127.0.0.1:{mailpit['api_port']}/api/v1/messages", timeout=10)
  assert resp.status_code == 200
  return resp.json().get('messages', [])


def _wait_for_mail(mailpit: dict[str, str], to: str, timeout: float = 30.0) -> dict:
  deadline = time.monotonic() + timeout
  while time.monotonic() < deadline:
    for message in _mailpit_messages(mailpit):
      addresses = ' '.join(address.get('Address', '') for address in message.get('To', []))
      if to in addresses:
        return message
    time.sleep(1)
  raise AssertionError(f'no mail to {to} within {timeout}s')


def test_forgot_password_sends_mail(
  mail_kavita_server: KavitaInstance,
  mailpit: dict[str, str],
) -> None:
  admin_email = 'it-admin@example.com'
  try:
    forgot = post_api_account_forgot_password.sync_detailed(
      client=mail_kavita_server.client, email=admin_email,
    )
  except Exception as exc:  # noqa: BLE001
    # The nightly client still parses the bare "Email sent" body as JSON.
    expect_upstream_fix('Fix 3 (bare string bodies)', repr(exc))
    raise
  assert forgot.status_code == 200
  # With SMTP configured the server sends the mail itself and confirms.
  assert forgot.parsed == 'Email sent'

  message = _wait_for_mail(mailpit, admin_email)
  full = httpx.get(
    f"http://127.0.0.1:{mailpit['api_port']}/api/v1/message/{message['ID']}", timeout=10,
  ).json()
  body = (full.get('Text') or '') + (full.get('HTML') or '')
  link = re.search(r'https?://\S+', body)
  assert link, f'no reset link in captured mail: {body[:200]!r}'
  assert httpx.get(link.group(0), follow_redirects=True, timeout=10).status_code == 200


def test_invite_sends_mail(
  mail_kavita_server: KavitaInstance,
  mailpit: dict[str, str],
) -> None:
  email = f'it-mailpit-{uuid.uuid4().hex[:8]}@example.com'
  invite = post_api_account_invite.sync_detailed(
    client=mail_kavita_server.admin_client,
    body=InviteUserDto(
      email=email,
      roles=[],
      age_restriction=AgeRestrictionDto(age_rating=AgeRating.NOT_APPLICABLE, include_unknowns=False),
    ),
  )
  if not isinstance(invite.parsed, InviteUserResponse):
    # The nightly client still has the raw string schema (Fix 1 absent).
    expect_upstream_fix('Fix 1 (invite response schema)', f'parsed as {type(invite.parsed).__name__}')
  assert invite.status_code == 200
  assert isinstance(invite.parsed, InviteUserResponse)
  # With SMTP configured the invite mail goes out for real.
  assert invite.parsed.email_sent is True
  assert invite.parsed.invalid_email is False
  assert _wait_for_mail(mailpit, email)
