# Spec coverage

What the test suite exercises of the Kavita OpenAPI document
(`kavita_0.9.1.4.json`), and how much of the document that is.

## Summary

The spec describes **494 paths / 517 operations** (an operation = one HTTP
method on one path). The suite calls **211 operations (40.8%)**, all through
the generated client.

**Two modes:** with `KAVITA_MODE=release` (default, the patched client) the
suite must be fully green. With `KAVITA_MODE=nightly` (the raw-spec client)
the tests that depend on a `fix_spec.py` fix record the still-present
upstream bug as xfail, so the run stays green while the bug remains and the
test starts passing once upstream fixes it.

Coverage is deliberately shallow but strategic:

- the **auth flow** (the precondition for every authenticated endpoint),
- the **invite endpoint** (the primary reason `fix_spec.py` exists),
- a **fresh-install sweep** of cheap, read-only endpoints that later doubles
  as the regression probe against dev builds,
- a **populated-library flow**: sample books/comics are generated from
  `tests/data`, scanned, and read back through the Series/Book/Search/Stats
  endpoints.

The remaining ~59% covers media-dependent, destructive, or stateful behavior
(see [Why the rest is untested]).


## Coverage by controller

| Controller | Spec ops | Covered | % |
|---|---:|---:|---:|
| Account | 28 | 15 | 53.6 |
| Server | 18 | 11 | 61.1 |
| Library | 23 | 5 | 21.7 |
| Series | 33 | 13 | 39.4 |
| Book | 4 | 2 | 50.0 |
| Search | 4 | 3 | 75.0 |
| Upload | 13 | 3 | 23.1 |
| Admin | 1 | 1 | 100 |
| Email | 1 | 1 | 100 |
| Health | 1 | 1 | 100 |
| Users | 10 | 7 | 70.0 |
| Settings | 20 | 12 | 60.0 |
| Stats | 34 | 34 | 100 |
| Metadata | 14 | 14 | 100 |
| Device | 10 | 3 | 30.0 |
| License | 13 | 5 | 38.5 |
| Theme | 7 | 1 | 14.3 |
| Font | 5 | 1 | 20.0 |
| Locale | 1 | 1 | 100 |
| Reader | 39 | 16 | 41.0 |
| Download | 12 | 6 | 50.0 |
| Image | 15 | 5 | 33.3 |
| Chapter | 5 | 3 | 60.0 |
| Person | 10 | 5 | 50.0 |
| Tachiyomi | 2 | 1 | 50.0 |
| Panels | 2 | 1 | 50.0 |
| ColorScape | 3 | 3 | 100 |
| Opds | 22 | 18 | 81.8 |
| Collection | 12 | 5 | 41.7 |
| ReadingList | 27 | 4 | 14.8 |
| WantToRead | 4 | 4 | 100 |
| Rating | 4 | 4 | 100 |
| Review | 5 | 1 | 20.0 |
| Oidc | 2 | 1 | 50.0 |
| Scrobbling | 19 | 0 | 0 |
| Stream | 17 | 0 | 0 |
| ReadingProfile | 16 | 0 | 0 |
| Cbl | 14 | 0 | 0 |
| Annotation | 12 | 1 | 8.3 |
| Filter | 12 | 0 | 0 |
| Plugin | 5 | 0 | 0 |
| Volume | 4 | 0 | 0 |
| Koreader | 3 | 0 | 0 |
| Manage | 2 | 0 | 0 |
| OAuth | 2 | 0 | 0 |
| Activity | 1 | 0 | 0 |
| KavitaPlusAudit | 6 | 0 | 0 |
| **Total** | **517** | **211** | **40.8** |

## Why the rest is untested

The remaining 306 operations split as **112 in controllers the suite never
touches** (Scrobbling 19, Stream 17, ReadingProfile 16, Cbl 14, Annotation
11, Filter 12, Plugin 5, Volume 4, Koreader 3, Manage 2, OAuth 2, Activity
1, KavitaPlusAudit 6) and **194 leftovers in partially covered
controllers** (Reader 23, ReadingList 23, Series 20, Library 18, Account
13, Upload 10, Image 10, …). By reason:

- **Hard blockers (~60–70)** — no fixture can exercise them:
  - *Subscription-bound*: KavitaPlusAudit (6), the paid License actions
    (renew/resend/delete), `Users/tokens` and `Series/match-info` (403,
    Kavita+ only).
  - *Third-party services / devices*: Scrobbling (providers), Cbl (CBL
    export files), Plugin (installed plugins), Koreader and Device push
    (client devices). OAuth/Oidc configuration and the login challenge are
    covered over self-signed TLS (see `docs/DESIGN.md` quirks); only the
    mock's final login page is blocked by its own scope-parsing bug. Email
    sending is covered via Mailpit.
- **Truly dead quirks (~2)** — verified live, server behavior will never
  match the spec: `License/info` (204), `Plugin/authkey-expires` (400).
- **The long tail (~240)** — reachable, just state-heavy; the
  mutation/self-contained-lifecycle patterns from Phase 3 apply directly.
  This is the leftovers listed above plus the never-touched state-heavy
  controllers (Stream, Annotation, Filter, Volume, ReadingProfile, Manage).
  `Filter/create` + `rename` were planned for Phase 3 but not delivered.

