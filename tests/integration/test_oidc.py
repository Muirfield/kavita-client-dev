'''OpenID Connect against a self-signed-TLS mock provider (coverage-plan Phase 3).

Recipe (verified against Kavita v0.9.1.4 source):
- the server requires an https authority and fetches its discovery document
  (`SettingsService.IsValidAuthority`) — a self-signed CA works because the
  Kavita container is started with `SSL_CERT_FILE` pointing at it;
- the authority must match the mock's issuer exactly (no trailing slash);
- the OIDC auth scheme registers at startup, so the container is recreated
  on the same config volume after configuration;
- the challenge redirect (`/Oidc/login`) reaches the mock — the mock
  (soluto/oidc-server-mock) then rejects every authorize request with empty
  `RequestedScopes` (its own scope-parsing bug), which is asserted via the
  mock's logs rather than a successful login page.
'''

from __future__ import annotations

import json
import os
import ssl
import subprocess
import tempfile
import time
import uuid

import httpx
import pytest

from kavita_client import Client
from kavita_client.api.account import (
  get_api_account_oidc_authenticated,
  post_api_account_login,
  post_api_account_register,
)
from kavita_client.api.settings import get_api_settings, get_api_settings_oidc, post_api_settings
from kavita_client.models import LoginDto, OidcConfigDto, RegisterDto

from kavita_instance import KavitaInstance

pytestmark = [pytest.mark.integration, pytest.mark.compat]

OIDC_IMAGE = 'ghcr.io/soluto/oidc-server-mock:latest'
CLIENT_ID = 'kavita-client-test'
CLIENT_SECRET = 'kavita-client-test-secret'
NETWORK = 'kavita-oidc-test-net'
SUBNET = '172.99.0.0/16'
MOCK_IP = '172.99.0.10'
KAVITA_IP = '172.99.0.11'
AUTHORITY = f'https://{MOCK_IP}'  # no trailing slash: must match the mock's issuer


def _docker(args: list[str]) -> subprocess.CompletedProcess[str]:
  return subprocess.run(['docker', *args], capture_output=True, text=True)


@pytest.fixture(scope='module')
def oidc_env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
  '''Static network + TLS mock + a Kavita container that trusts the CA.'''
  if _docker(['info']).returncode != 0:
    pytest.skip('docker is not available')
  if _docker(['image', 'inspect', OIDC_IMAGE]).returncode != 0:
    pytest.skip(f'{OIDC_IMAGE} is not pulled')
  if _docker(['image', 'inspect', 'jvmilazz0/kavita:latest']).returncode != 0:
    pytest.skip('kavita image is not pulled')

  certs_dir = tmp_path_factory.mktemp('oidc-certs')
  subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                  '-keyout', str(certs_dir / 'ca.key'), '-out', str(certs_dir / 'ca.crt'),
                  '-days', '7', '-subj', '/CN=kavita-test-ca',
                  # Python's ssl rejects CAs without the CA:TRUE/keyCertSign
                  # extensions (curl is laxer about this).
                  '-addext', 'basicConstraints=critical,CA:TRUE',
                  '-addext', 'keyUsage=critical,keyCertSign'],
                 check=True, capture_output=True)
  subprocess.run(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes',
                  '-keyout', str(certs_dir / 'server.key'), '-out', str(certs_dir / 'server.csr'),
                  '-subj', f'/CN={MOCK_IP}',
                  '-addext', f'subjectAltName=IP:{MOCK_IP},DNS:oidc-mock.test'],
                 check=True, capture_output=True)
  subprocess.run(['openssl', 'x509', '-req', '-in', str(certs_dir / 'server.csr'),
                  '-CA', str(certs_dir / 'ca.crt'), '-CAkey', str(certs_dir / 'ca.key'),
                  '-CAcreateserial', '-out', str(certs_dir / 'server.crt'),
                  '-days', '7', '-copy_extensions', 'copyall'], check=True, capture_output=True)

  _docker(['network', 'rm', NETWORK])
  if _docker(['network', 'create', '--subnet', SUBNET, NETWORK]).returncode != 0:
    pytest.skip('could not create the oidc test network')

  clients = json.dumps([{
    'ClientId': CLIENT_ID,
    'Description': 'kavita client test',
    'ClientSecrets': [CLIENT_SECRET],
    'AllowedGrantTypes': ['authorization_code'],  # Kavita uses the code flow
    'AllowedScopes': ['openid', 'profile', 'email', 'offline_access', 'roles'],
    'RedirectUris': ['*'],  # the random host port makes an exact list impossible
    'PostLogoutRedirectUris': [],
    'AllowedCorsOrigins': [],
    'Claims': [],
  }])
  mock_name = f'kavita-oidc-mock-{uuid.uuid4().hex[:8]}'
  mock_run = _docker(['run', '-d', '--rm', '--name', mock_name,
                      '--network', NETWORK, '--ip', MOCK_IP,
                      '-v', f'{certs_dir}:/certs:ro',
                      '-e', 'ASPNETCORE_URLS=https://+:443',
                      '-e', 'ASPNETCORE_Kestrel__Certificates__Default__Path=/certs/server.crt',
                      '-e', 'ASPNETCORE_Kestrel__Certificates__Default__KeyPath=/certs/server.key',
                      '-e', f'CLIENTS_CONFIGURATION_INLINE={clients}',
                      OIDC_IMAGE])
  if mock_run.returncode != 0:
    pytest.skip(f'oidc mock start failed: {mock_run.stderr.strip()}')

  config_dir = tmp_path_factory.mktemp('oidc-kavita-config')
  config_dir.chmod(0o777)
  kavita_name = f'kavita-oidc-{uuid.uuid4().hex[:8]}'

  def run_kavita() -> None:
    run = _docker(['run', '-d', '--rm', '--name', kavita_name,
                   '--user', f'{os.getuid()}:{os.getgid()}',
                   '--network', NETWORK, '--ip', KAVITA_IP,
                   '-p', '127.0.0.1::5000',
                   '-v', f'{config_dir}:/kavita/config',
                   '-v', f'{certs_dir}/ca.crt:/etc/kavita-ca.crt:ro',
                   '-e', 'SSL_CERT_FILE=/etc/kavita-ca.crt',
                   'jvmilazz0/kavita:latest'])
    if run.returncode != 0:
      pytest.fail(f'kavita run failed: {run.stderr.strip()}')

  def wait_ready() -> str:
    host_port = ''
    for line in _docker(['port', kavita_name, '5000/tcp']).stdout.splitlines():
      _, _, host_port = line.rpartition(':')
      if host_port.isdigit():
        break
    base = f'http://127.0.0.1:{host_port}'
    for _ in range(150):
      try:
        if httpx.get(f'{base}/api/Health', timeout=5).status_code == 200:
          return base
      except httpx.HTTPError:
        pass
      time.sleep(2)
    raise RuntimeError('kavita did not become ready')

  try:
    # wait for the mock's discovery document over TLS (trusting our CA)
    discovery = f'{AUTHORITY}/.well-known/openid-configuration'
    verify = ssl.create_default_context(cafile=str(certs_dir / 'ca.crt'))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
      try:
        if httpx.get(discovery, verify=verify, timeout=5).status_code == 200:
          break
      except httpx.HTTPError:
        pass
      time.sleep(2)
    else:
      pytest.skip('oidc mock did not become ready')

    run_kavita()
    base = wait_ready()
    client = Client(base_url=base, raise_on_unexpected_status=True)
    registered = post_api_account_register.sync_detailed(
      client=client,
      body=RegisterDto(username='it-admin', password='it-admin-password', email='it-admin@example.com'),
    )
    if registered.status_code != 200:
      pytest.fail(f'admin registration failed: HTTP {registered.status_code}')

    login = post_api_account_login.sync_detailed(
      client=client,
      body=LoginDto(username='it-admin', password='it-admin-password'),
    )
    assert login.status_code == 200 and login.parsed is not None and login.parsed.token
    admin_client = Client(base_url=base, raise_on_unexpected_status=True)
    admin_client._headers['Authorization'] = f'Bearer {login.parsed.token}'

    # Configure OIDC through the generated client. customScopes must be
    # empty: Kavita appends them unfiltered and the mock rejects duplicates.
    settings = get_api_settings.sync_detailed(client=admin_client)
    assert settings.status_code == 200 and settings.parsed is not None
    settings.parsed.oidc_config = OidcConfigDto(
      enabled=True,
      provider_name='Test OIDC',
      authority=AUTHORITY,
      client_id=CLIENT_ID,
      secret=CLIENT_SECRET,
      provision_accounts=True,
      require_verified_email=False,
      sync_user_settings=False,
      custom_scopes=[],
    )
    updated = post_api_settings.sync_detailed(client=admin_client, body=settings.parsed)
    assert updated.status_code == 200

    # The OIDC scheme registers at startup: recreate the container on the
    # same config volume (docker restart would delete a --rm container).
    _docker(['rm', '-f', kavita_name])
    run_kavita()
    base = wait_ready()

    yield {
      'base_url': base,
      'mock_name': mock_name,
      'ca': str(certs_dir / 'ca.crt'),
      'discovery': discovery,
      'inner_base': f'http://{KAVITA_IP}:5000',
    }
  finally:
    _docker(['rm', '-f', mock_name, kavita_name])
    _docker(['network', 'rm', NETWORK])


def _oidc_admin_client(base_url: str) -> Client:
  client = Client(base_url=base_url, raise_on_unexpected_status=True)
  login = post_api_account_login.sync_detailed(
    client=client,
    body=LoginDto(username='it-admin', password='it-admin-password'),
  )
  assert login.status_code == 200 and login.parsed is not None and login.parsed.token
  client._headers['Authorization'] = f'Bearer {login.parsed.token}'
  return client


def test_oidc_provider_discovery(oidc_env: dict[str, str]) -> None:
  '''The mock serves its discovery document over self-signed TLS.'''
  verify = ssl.create_default_context(cafile=oidc_env['ca'])
  resp = httpx.get(oidc_env['discovery'], verify=verify, timeout=10)
  assert resp.status_code == 200
  assert 'authorization_endpoint' in resp.json()


def test_oidc_configure_and_public_config(oidc_env: dict[str, str]) -> None:
  '''Self-signed TLS accepted: OIDC is enabled and the public config reflects it.'''
  public = get_api_settings_oidc.sync_detailed(
    client=_oidc_admin_client(oidc_env['base_url']),
  )
  assert public.status_code == 200
  assert public.parsed is not None
  assert public.parsed.enabled is True
  assert public.parsed.provider_name == 'Test OIDC'


def test_oidc_login_challenge_reaches_provider(oidc_env: dict[str, str]) -> None:
  '''`/Oidc/login` challenges the provider: the mock logs our authorize request.

  The mock then rejects the request with empty `RequestedScopes` (its own
  scope-parsing bug — see docs/DESIGN.md quirks), so the full login page
  cannot complete; the challenge hop is what this asserts.
  '''
  token = _oidc_admin_client(oidc_env['base_url'])._headers['Authorization']
  resp = httpx.get(
    f"{oidc_env['inner_base']}/Oidc/login",
    headers={'Authorization': token},
    follow_redirects=False,
    timeout=30,
  )
  # Kavita has challenged and the mock answered (its scope bug yields 500).
  assert resp.status_code in (302, 500)

  logs = _docker(['logs', oidc_env['mock_name']]).stdout
  # Duende advertises PAR, so Kavita pushes the authorization request there;
  # its validation then fails on the mock's scope-parsing bug. Either way the
  # challenge hop reached the provider.
  assert 'PushedAuthorizationEndpoint' in logs or 'AuthorizeRequestValidationLog' in logs


def test_account_oidc_authenticated(
  kavita_server: KavitaInstance,
) -> None:
  '''JWT sessions are not OIDC sessions: the check is a documented bool.'''
  resp = get_api_account_oidc_authenticated.sync_detailed(client=kavita_server.admin_client)
  assert resp.status_code == 200
  assert isinstance(resp.parsed, bool)
