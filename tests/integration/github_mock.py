'''TLS mock of the GitHub endpoints Kavita's version checker calls.

Runs inside a container on the test network (python:3-alpine, stdlib
only):

    python3 /github_mock.py --cert /certs/server.crt --key /certs/server.key

Serves, on api.github.com (any path not listed gets the csproj text):

- /repos/Kareadita/Kavita/releases        -> release metadata list
- /repos/Kareadita/Kavita/releases/latest -> one release
- /repos/Kareadita/Kavita/pulls/{n}       -> minimal PR info
- /repos/Kareadita/Kavita/commits         -> one non-release commit
'''

from __future__ import annotations

import argparse
import json
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

RELEASES = [
  {
    'tag_name': 'v0.9.1.4',
    'name': 'v0.9.1.4',
    'body': '# Added\n- Mock release for the test suite\n',
    'html_url': 'https://github.com/Kareadita/Kavita/releases/tag/v0.9.1.4',
    'published_at': '2026-09-01T00:00:00Z',
    'prerelease': False,
    'draft': False,
  },
  {
    'tag_name': 'v0.9.1.3',
    'name': 'v0.9.1.3',
    'body': '# Fixed\n- Previous mock release\n',
    'html_url': 'https://github.com/Kareadita/Kavita/releases/tag/v0.9.1.3',
    'published_at': '2026-08-01T00:00:00Z',
    'prerelease': False,
    'draft': False,
  },
]

CSPROJ = (
  '<Project>\n  <PropertyGroup>\n'
  '    <AssemblyVersion>0.9.1.4</AssemblyVersion>\n'
  '  </PropertyGroup>\n</Project>\n'
)


class Handler(BaseHTTPRequestHandler):
  def do_GET(self) -> None:  # noqa: N802
    path = self.path.split('?')[0]
    if path == '/repos/Kareadita/Kavita/releases':
      body = json.dumps(RELEASES)
      content_type = 'application/json'
    elif path == '/repos/Kareadita/Kavita/releases/latest':
      body = json.dumps(RELEASES[0])
      content_type = 'application/json'
    elif path.startswith('/repos/Kareadita/Kavita/pulls/'):
      body = json.dumps({'number': 1, 'title': 'mock'})
      content_type = 'application/json'
    elif path == '/repos/Kareadita/Kavita/commits':
      # One commit whose message does not look like a release, so the
      # nightly-enrichment loop finds nothing and finishes quickly.
      body = json.dumps([{'sha': 'abc123', 'commit': {'message': 'chore: mock commit'}}])
      content_type = 'application/json'
    else:
      # raw.githubusercontent.com paths and anything else: a csproj with a
      # stable-looking version (only consulted for nightly commits).
      body = CSPROJ
      content_type = 'text/plain'
    payload = body.encode('utf-8')
    self.send_response(200)
    self.send_header('Content-Type', content_type)
    self.send_header('Content-Length', str(len(payload)))
    self.end_headers()
    self.wfile.write(payload)

  def log_message(self, *args: object) -> None:  # noqa: ANN002, ARG002
    pass


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument('--cert', required=True)
  parser.add_argument('--key', required=True)
  parser.add_argument('--port', type=int, default=443)
  args = parser.parse_args()

  server = ThreadingHTTPServer(('0.0.0.0', args.port), Handler)
  context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
  context.load_cert_chain(args.cert, args.key)
  server.socket = context.wrap_socket(server.socket, server_side=True)
  server.serve_forever()


if __name__ == '__main__':
  main()
