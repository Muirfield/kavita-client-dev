# Coverage expansion plan

Roadmap for growing the live API coverage beyond the current **180/517
operations (34.8%)** (see `docs/spec-coverage.md` for the baseline).

**Status: all three phases delivered (2026-09-21).** The document is now
the record of what was planned vs. delivered; the remaining work is the
long tail and the recoverable server quirks, tracked in
`docs/spec-coverage.md`.

## Principles

- **Contract-first**: assert only what the spec documents; quirks that force
  deviation get documented in `docs/DESIGN.md` → "Live-server quirks".
- **Throwaway servers**: mutations *and destructive endpoints* are fine; the
  containers are `--rm`'d. The only constraint is test ordering within a
  session (see [Destructive endpoints]).
- **Same suite, both modes**: everything here doubles as the nightly
  regression probe (stable and dev images).
- **One endpoint = one line** where possible: a shared sweep helper keeps
  marginal cost near zero.

### Destructive endpoints

Admin-destructive operations are in scope — the server is discarded after
the session. Three patterns keep them from interfering with other tests:

1. *Self-contained*: create an entity, mutate it, delete it, assert it is
   gone (e.g. create a library, `Library/delete`, verify it disappeared).
2. *Destructive last*: run session-ending operations (user deletion,
   `Settings/reset`, `Server/cleanup`) in a dedicated `test_zz_*` module so
   pytest's alphabetical ordering puts them after everything else.
3. *Dedicated fixture*: for truly disruptive cases (deleting the admin
   account), a third throwaway container isolates them entirely (~25s).

## Phase 1 — Fresh-install read-only sweep

*Goal: ~40–60 more operations for the least effort. Both existing fixtures
(`kavita_server`, `media_kavita_server`) can host these.*

*Status: **done** (2026-09-20) — `tests/integration/test_sweep.py` adds 68
verified read-only operations (coverage 4.4% → 17.6%). Entries are
parametrized tuples instead of the `_sweep` helper sketched below: per-entry
pytest reporting turned out more useful than a loop. Endpoints that failed
live verification were dropped and documented in `docs/DESIGN.md` →
"Live-server quirks".*

Build a parametrized helper, e.g. `_sweep(client, [('module.fn', kwargs), ...])`,
that calls each endpoint and asserts the documented 200 (and, where the
schema is meaningful, parseability). Each entry must be verified once against
the live server and annotated with the client to use (admin/anonymous) and
any quirks.

Candidate families (with spec op counts):

| Controller | Ops | Candidates / notes |
|---|---|---|
| Settings | 20 | `library-types`, `log-levels`, `base-url`, `is-email-setup`, `task-frequencies`, `opds-enabled`, `metadata-settings` |
| Metadata | 14 | `age-ratings`, `all-languages`, `all-bcp47-languages`, `genres`, `tags`, `publication-status`, `people-by-role` (empty ok) |
| Stats | 34 | the GETs that return empty-but-valid data: `day-breakdown`, `reading-counts`, `file-breakdown`, `popular-*`… (list to verify per endpoint) |
| Account | 28 | `refresh-token`, `refresh-account`, `email-confirmed`, `is-email-valid`, `update` (prefs), `opds-url` |
| Users | 10 | `names`, `profile-info`, `get-preferences`, `has-library-access`, `has-profile-shared` |
| Server | 18 | `media-errors`, `is-task-running`, `logs` (binary zip), `changelog` (server-side network) |
| Device | 10 | `devices`, `all-devices` |
| License | 13 | `has-license`, `info`, `products`, `provider-health` (no subscription needed for GETs — verify) |
| Plugin | 5 | `version`, `authkey-expires` |
| Theme | 7 | `browse`, `download-content` (network) |
| Font | 5 | `all` |
| Email | 1 | done |
| Locale | 1 | `GET /api/Locale` |
| Admin | 1 | done |

*Delivered*: +68 ops (coverage 17.6%).

## Phase 2 — Richer media fixture

*Goal: unlock the big media families (~120+ ops). Prerequisite for Phase 3.*

*Status: **done** (2026-09-20) — +42 operations (coverage 17.6% → 25.7%).
The fixture upgrades below landed; the per-family estimates were optimistic
(only the verified subsets are swept — see the per-module notes in
`docs/spec-coverage.md`). Live verification found: ComicInfo.xml and
embedded epub metadata are only parsed with metadata processing enabled
(libraries now enable it, matching off); the Reader image/thumbnail and
Panels endpoints require an API key; `match-info` is Kavita+ only;
`currently-reading` stays empty for a bare progress call.*

Upgrades to `tests/data` + the `media_library` fixture:

1. **Volume-patterned comic** — `lorem v01.cbz` (instead of / next to the
   loose-leaf one) so volumes/chapters are real, not `specials`. Unlocks:
   - `Reader` (39): `chapter-info`, `image`, `get-progress`,
     `mark-read`, `bookmark`…
   - `Download` (12): `chapter/series/volume[-size]`, `bookmarks`
   - `Image` (15): series/volume/chapter covers (chapter covers need
     actual pages)
   - `Chapter` (5): `chapter-detail-plus`, `update`, `delete-multiple`
   - `Tachiyomi` (2), `Panels` (2), `ColorScape` (3)
2. **Multiple series** — tweak `loremipsum.md` (e.g. title/volume) into a
   second folder. Unlocks `Series/related`, `all-related`, `match-info`,
   `series-by-collection`, and gives **Collection** (12) and
   **ReadingList** (27) real data.
3. **ComicInfo.xml metadata** — `pdf-to-cbz` already contains the
   `generate_comic_info()` function (currently commented out); feed the
   sample metadata through it. Unlocks `Metadata/genres-with-counts`,
   `tags-with-counts`, **Person** (10), **Manage** (2).
4. **epub series/volume metadata** — run `ebook-meta` (calibre) on the
   sample epub to embed `series` + `series_index`, so the book parser gets
   real series/volume data from the file metadata instead of the "Series
   vNN" filename pattern (DESIGN quirk #5). This also reactivates the
   dormant calibre dependency (see `docs/dependencies.md`). *Verified:
   with metadata processing on, the bare-named epub parses from its
   embedded metadata.*
5. **Reading activity** — mark chapters read with progress via
   `Reader/progress`/`mark-read` in the fixture. Makes the Stats history
   endpoints (`reading-history`, `user-read`, `day-breakdown`…) return
   real data and unlocks `Reader/has-progress`, `continue-point`,
   `Series/currently-reading`, `on-deck`.

*Delivered*: +42 ops (coverage 25.7%), plus the nullable-enum
`TachiyomiChapterDto.format` (Fix 2) and `Series/age-rating` bare body
(Fix 3) found and fixed along the way.

Risks: per-family server quirks (e.g. parser naming rules, pagination,
admin-only rules) — same investigative approach as before; document each in
`docs/DESIGN.md`.

## Phase 3 — OPDS + mutations

*Prerequisites: Phase 2.*

*Status: **done** (2026-09-20/21) — +47 operations (coverage 25.7% → 34.8%):
OPDS feeds via the fixture API key, self-contained mutation lifecycles
(collections, reading lists, want-to-read, ratings, reviews, preferences,
mark-read/unread, user/library create-delete), the session-ending
destructive module (`test_zz_destructive.py`: backup-db, cleanup,
series delete-multiple, settings reset), and the Mailpit email flows
(forgot-password → real mail → reset link; invite with `emailSent: true`),
and OIDC configuration over self-signed TLS (`test_oidc.py`) — see the
OIDC bullet below.*

- **OPDS** (22): `Account/create-auth-key` → anonymous calls to
  `/api/Opds/{apiKey}/…` (series, collections, on-deck, download).
- **Mutations**: `Series/update` (name locks), `Rating/series|chapter`,
  `Reader/mark-read`/`progress`, `Users/update-preferences`,
  `Collection/create` + `update`, `ReadingList/create` + `update-*`,
  `WantToRead/add-series`. (`Filter/create` + `rename` were planned here
  but not delivered — Filter stays 0/12, see the long tail.)
- **Destructive endpoints** (see [Destructive endpoints]):
  `Series/delete-multiple`, `Library/delete[-multiple]`, `Users/delete-user`,
  `Collection/delete`, `ReadingList/delete-multiple`, `Settings/reset`,
  `Server/cleanup`, `Server/backup-db`. *Delivered*: series
  delete-multiple, user delete, collection delete, settings reset, cleanup,
  backup-db. *Not delivered*: `Library/delete[-multiple]` (DESIGN quirk 18
  — `false` for a fresh library / generator crash) and
  `ReadingList/delete-multiple` (the lifecycle test uses the single
  delete).
- **Font upload**: `Font/upload` with a font file (or reuse an existing
  theme asset) if the server accepts it without network. *Not delivered* —
  Font stays 1/5.
- **Email (Mailpit)** — run the `axllent/mailpit` container as a companion
  service, point Kavita's SMTP settings at it, and drive the real email
  flows: `Account/forgot-password` + `reset-password`,
  `confirm-email[-update]`, `resend-confirmation-email`, invite with
  `emailSent: true`. Mailpit's HTTP API lets the tests assert the mail was
  actually delivered; the invite/email assertions become conditional on the
  fixture (email configured vs not). *Status: **done** —
  `mail_kavita_server` configures SMTP through the generated Settings POST
  (`IsEmailSetup()` needs hostName + SMTP host + sender address);
  forgot-password and invite flows assert real delivery via Mailpit's API.*
- **OIDC (mock provider)** — run `oidc-server-mock` (or
  `mock-oidc-provider`) as a companion service and exercise the **OAuth**
  (2) and **Oidc** (2) controllers, plus the account-side
  `oidc-authenticated` check, against a real (mock) identity provider.
  *Delivered: only the `/Oidc/login` challenge hop — Oidc 1/2, OAuth 0/2.*
  `test_oidc.py` runs `ghcr.io/soluto/oidc-server-mock`
  behind a self-signed TLS certificate on a static docker network, the
  Kavita container trusts the generated CA via `SSL_CERT_FILE`, OIDC is
  configured through the generated Settings POST (authority must match the
  mock's issuer exactly, `customScopes` empty), the container is recreated
  so the auth scheme registers, and `/Oidc/login` is asserted to reach the
  provider. The last hop (the mock's login page) is blocked by the mock's
  own scope/PAR parsing bugs — see `docs/DESIGN.md` quirks.*

*Delivered*: +47 ops (coverage 34.8%); the email flows are delivered and the
OIDC configuration + challenge hop are verified over self-signed TLS — only
the mock's final login page is blocked by its own scope-parsing bug.*

## Non-goals (documented, not planned)

- **Scrobbling** (19) and **Kavita+/License actions** (License 13 +
  KavitaPlusAudit 6): paid subscription / provider config.
- **CBL** (14): needs CBL export files (deep rabbit hole; revisit if the
  export-as-cbl → import loop ever becomes cheap).
- **Koreader sync / Device push**: client devices required.

(Email sending and OAuth/OIDC *were* non-goals; they are now covered via
the mock companion services — Mailpit and the self-signed-TLS
oidc-server-mock — see Phase 3.)

## Infrastructure notes

- **Sweep helper**: implemented as parametrized entries in
  `tests/integration/test_sweep.py` (operation, callable, kwargs, client,
  parseability, fix id); failures report endpoint + status + body.
- **Companion containers** (Phase 3): Mailpit and the OIDC mock run as
  `--rm`'d sidecar containers like the Kavita server; fixtures skip the
  dependent tests when the images are unavailable (same pattern as the
  media tooling).
- **Runtime**: each fixture adds ~20–30s; `pytest-xdist` (2 workers, so the
  two session containers boot in parallel) was considered and not adopted —
  still an option if runtime matters.
- **Docs to update per phase**: `spec-coverage.md` (tables + numbers),
  `DESIGN.md` (quirks), `fixup-coverage.md` (static side unchanged unless
  `fix_spec.py` grows).
- **Quirk log discipline**: every deviation from the documented contract
  lands in `DESIGN.md` with the Kavita source reference, as done so far.

## Sequencing / sizes

| Phase | Effort | Coverage after |
|---|---|---|
| 1 — read-only sweep | done (2026-09-20) | 17.6% (actual) |
| 2 — richer media fixture | done (2026-09-20) | 25.7% (actual) |
| 3 — OPDS + mutations + email (Mailpit) + OIDC mock | done (2026-09-21) | 34.8% (actual) |

With destructive endpoints in scope the practical mature target is
**~60–70%**; the remaining gap to the hard ceiling is the long tail of
state-dependent and quirky endpoints, not prohibited territory.

Order is dependency-driven: all three phases are done. What remains is the
long tail of state-dependent families (see `docs/spec-coverage.md`); the
only incomplete companion flow is the mock's final OIDC login page, blocked
by its own scope-parsing bug (see `docs/DESIGN.md` quirks). Next steps:
the verified leftovers (`docs/TODO-coverage-next.md`) and the
auto-generated Schemathesis contract layer
(`docs/TODO-schemathesis.md`).

*Status: phases 1–3 delivered (2026-09); the long tail and the recoverable
server quirks remain — see `docs/spec-coverage.md`.*
