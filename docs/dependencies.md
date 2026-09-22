# Test dependencies

* Docker - run kavita containers
* pandoc, typst and TTF font
  * pandoc loremipsum.md -o file.pdf --pdf-engine typst -V mainfont="liberation sans"
* poppler, pdf to cbz conversion
* openssl - generates the self-signed CA and server certificate for the
  OIDC TLS fixture (`test_oidc.py`)
* calibre - ebook-meta commands (active since coverage-plan Phase 2: sets
  series/index/publisher/tags on the sample epub and pdf; `pdf-to-cbz`
  reads them back into the embedded ComicInfo.xml)
* Docker images for companion services (coverage-plan Phase 3):
  * axllent/mailpit - SMTP capture for the email flows
  * ghcr.io/soluto/oidc-server-mock - OpenID Connect testing (runs behind
    a self-signed TLS certificate on a static docker network)
  * python:3-alpine - runs the local TLS mock of api.github.com /
    raw.githubusercontent.com (`github_mock` fixture, DESIGN quirk 23)

