# CI/CD plan (TODO)

Status: **planned, not yet implemented**. The test suite this describes exists;
the workflows do not.

## Goals

- **Tagged releases**: verify the generated client against a *pinned* Kavita
  version, then publish the built client on this repo's GitHub Release page as
  the "verified/working" artifact other developers can reuse.
- **Nightly tracking**: detect regressions in (a) hotfix releases of the stable
  line and (b) the Kavita dev branch / our own pipeline, and flag them.

The test suite (`make test-release` / `make test-nightly`,
`make test-fix_spec`) is
the shared machinery; CI only changes *what* runs against *which* container,
via environment variables the suite already honors:

| Variable | Meaning | Default |
|---|---|---|
| `KAVITA_IMAGE` | container image under test | `jvmilazz0/kavita:latest` |
| `KAVITA_PULL` | image refresh policy: `missing`/`never`/`always` | `missing` |
| `KAVITA_EXPECTED_VERSION` | if set, a test asserts the server reports exactly this version | unset |
| `KAVITA_READY_TIMEOUT` | seconds to wait for first boot | `240` |
| `KAVITA_SCAN_TIMEOUT` | seconds to wait for a library scan to finish | `180` |
| `KAVITA_MODE` | client under test: `release` (patched) or `nightly` (raw spec; known upstream bugs recorded as xfail) | `release` |

Image/tag conventions (verified 2026-09):

- `jvmilazz0/kavita:latest` and `jvmilazz0/kavita:0.9.1` are the same digest
  (the v0.9.1.4 stable build). Kavita's Docker stable tags use 3 components
  (`0.9.1`) while GitHub releases use 4 (`v0.9.1.4`).
- `jvmilazz0/kavita:nightly` = `nightly-0.9.1`, the dev build from `develop`.
- All of these are *movable* tags. Pinning for a release therefore means
  recording the digest at release time (`:0.9.1@sha256:…`).

## Workflow 1 — Release (on tag)

Trigger: tag push, e.g. `0.9.1.4` (this repo's tags mirror Kavita's release
tags).

1. Extract the Kavita version from the tag name.
2. Fetch `https://raw.githubusercontent.com/Kareadita/Kavita/v<VER>/openapi.json`.
3. `fix_spec.py` (invoked with `<VER>` as the tag argument, so the generated
   client's version matches the tag) → `openapi-python-client generate`
   (generator version to be pinned — see open decisions).
4. Build the client (`make build` → wheel + sdist); `make test-release`
   installs it in the test environment, so the suite tests the exact
   artifact that will be published.
5. Resolve the server image: `docker pull jvmilazz0/kavita:latest`, record the
   resulting digest, run `make test-release` against `latest@sha256:…`
   with `KAVITA_IMAGE` set to the digest form and
   `KAVITA_EXPECTED_VERSION=<VER>`. A test asserts the running server reports
   `<VER>` (via `GET /api/Server/server-info-slim` → `kavitaVersion`), which
   is the digest/version cross-check.
6. If green: attach the built artifacts (zip containing the wheel/sdist, i.e.
   the installable `kavita-client`) to the GitHub Release, and record the
   verified image digest in the release body.
7. Failures block the release.

## Workflow 2 — Nightly, stable line (cron)

Trigger: nightly cron + `workflow_dispatch`.

- Client: the released client (checkout of the latest release tag, or `main`),
  run via `make test-release`.
- Image: `jvmilazz0/kavita:latest`, `KAVITA_PULL=always` — catches hotfix
  releases that move the `latest` tag and regress the API.
- Failure handling: **do not block anything**. Open/update a tracking issue
  with the JUnit breakdown (`--junitxml`) listing exactly which endpoints
  broke. This is the "flag regressions in the stable line" signal.

## Workflow 3 — Nightly, dev line (cron)

Trigger: nightly cron + `workflow_dispatch`.

- Client: generated fresh from the `develop` branch (`kavita_DEV.json` +
  `make build-nightly`, run via `make test-nightly`); generator version may
  be unpinned here — nothing is committed or published, so drift is
  irrelevant.
- Image: `jvmilazz0/kavita:nightly`, `KAVITA_PULL=always`.
- The tests that depend on a `fix_spec.py` fix record the still-present
  upstream bug as xfail (`expect_upstream_fix`), and the offline suite
  records the spec-version/tag mismatch as xfail too — so a green run means
  "the known bugs are still there, nothing changed". When upstream fixes
  one, the corresponding test stops xfailing and starts passing — review
  and retire the fix. Any *other* failure is a real regression.
- Failure handling: same as Workflow 2 (tracking issue, non-blocking). This is
  the "track what the Kavita developer is doing" signal.

## Workflow 4 — PR / push (fast gate)

- Offline unit tests only (`make test-fix_spec`, i.e. the `fix_spec` tests).
- Docker integration runs optionally (labels / `workflow_dispatch`) to save CI
  minutes; the image pull alone is ~250 MB.

## Regression drift check (open discussion)

The original idea was for CI to fail when a fresh generation differs from the
released client. Observations:

- A diff check is only meaningful when the generator is pinned; the dev-line
  job generates from `develop`, which is intentionally ahead of the released
  stable client, so a naive check there would always "drift".
- Therefore: no drift gate on dev jobs. On tags, the clean generation from the
  pinned spec *is* the build (step 3 above); comparing it against the released
  client is optional belt-and-braces and would require the pinning decision
  below to be made first.

## Open decisions

- [ ] Pin `openapi-python-client` (and pytest) in `requirements.txt` or use a
      lock file. Currently unpinned.
- [ ] Release artifact format: the plan is a zip of wheel + sdist on the
      GitHub Release (Workflow 1, step 6); still open whether to also publish
      to PyPI.
- [ ] This repo's tag naming convention (`0.9.1.4` vs `v0.9.1.4`).
- [ ] Nightly failures: one persistent tracking issue that gets updated vs. a
      new issue per failure.

## Known live-server quirks (from test runs, v0.9.1.4 source)

Confirmed against the live server; the tests accommodate all of them (see
`docs/DESIGN.md` → "Live-server quirks"):

- String-schema endpoints (`/api/Health`, `/api/Account/invite-url`,
  `/api/Upload/upload-by-file`, `/api/Account/opds-url`,
  `/api/Settings/base-url`, `/api/Metadata/language-title`,
  `/api/Series/age-rating`, `/api/Account/forgot-password`) return bare
  (non-JSON) text bodies, which the generated client parses with
  `response.json()` — it crashes. `fix_spec.py` Fix 3 (added 2026-09-20)
  rewrites their media types so the client reads `response.text`; the
  nightly build records the still-present upstream bug as xfail.
- Nullable enum fields (`SeriesDto.metadataProviderOverride`,
  `ChapterDto.format`, `MetadataSettingsDto.filterAboveWeight`,
  `TachiyomiChapterDto.format`) are `null` on the server but declared
  non-nullable in the spec. `fix_spec.py` Fix 2 rewrites them to the
  `allOf` + `nullable` form the generator honors; the nightly build xfails
  the dependent tests while upstream keeps the fields non-nullable.
- `info.version` in the tagged document is one step behind the tag
  (`0.9.1.1` in the `v0.9.1.4` document). `fix_spec.py` Fix 4 (added
  2026-09-20) rewrites it, with a warning on stderr, and the offline suite
  records the mismatch as xfail until upstream aligns them.
- `POST /api/Account/register` is first-user-only (`400` once an admin
  exists).
- `POST /api/Account/invite` null-derefs `roles`/`ageRestriction` if omitted
  (`400` generic). With email unconfigured it returns `emailSent: false`,
  `invalidEmail: true` plus a working `emailLink`; with SMTP configured
  (Mailpit fixture) it sends real mail (`emailSent: true`).
- `GET /api/Account/invite-url` needs the id of a *pending* user (the
  admin's is already email-confirmed) and `withBaseUrl`.
- `POST /api/Library/create` needs a `metadataProvider` valid for the
  library type; `scan-all` silently skips libraries; overlapping scans are
  queued hours out (scan sequentially and wait).
- Book libraries only parse files in series subfolders. With metadata
  processing off, the epub parser needs the "Series vNN" filename pattern;
  with it on (the fixture's setting), embedded ebook-meta metadata is
  honored and the bare filename parses.
- A loose-leaf cbz (no volume marker) lands in `SeriesDetailDto.specials`,
  not `chapters`/`volumes`; the tests read it from there.
- The container must run with `--user` (the test fixture does), otherwise
  root-owned files accumulate in the mounted config dir and temp cleanup
  fails with warnings.
