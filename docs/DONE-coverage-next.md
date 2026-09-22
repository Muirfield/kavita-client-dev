# Coverage next — verified leftovers (TODO)

Implementation plan for the **verified leftovers**: the recoverable items in
`docs/spec-coverage.md` → "Why the rest is untested" → "Documented server
quirks". Each has already been verified live (or trivially is) and has a
concrete path into the suite. This is finishing work, not a new coverage
program — the broad expansion stops here (see `docs/spec-coverage.md`).

Expected gain: **up to +22 operations** (180 → ~202, 34.8% → ~39.1%),
before any drop-and-document from live verification.

*Status: **complete** (2026-09-21) — all three batches delivered (+22 ops:
coverage 180 → 202, 34.8% → 39.1%). New quirks found along the way are in
`docs/DESIGN.md` #8/#15/#18/#19.*

## Scope

| # | Item | Ops | Blocker (DESIGN quirk) | Approach |
|---|---|---:|---|---|
| A1 | OPDS `image` feed | 1 | #19 (was a bad-id artifact) | re-add to `test_opds.py` with fixture ids |
| A2 | 11 date-range Stats endpoints | 11 | #8 (400 on fresh server) | re-attempt against the populated fixture |
| A3 | `Library/delete-multiple` + `delete` | 2 | #18 (generator bug; `false`-for-fresh artifact) | raw `httpx` for multiple, generated client for single |
| B1 | `Stats/server/file-breakdown` | 1 | #9 (object vs array) | new `fix_spec.py` fix + live test |
| B2 | `Metadata/series-detail-plus` | 1 | #16 (null list field) | new `fix_spec.py` fix + live test |
| C1 | OPDS `favicon` feed | 1 | #19 (no `.ico` in container) | fixture mounts a `favicon.ico` |
| C2 | `Image/library-cover` + `user-cover` | 4 | #15 (404 without cover/avatar) | upload covers first (unlocks 2 Upload ops) |
| C3 | `Series/currently-reading` | 1 | #15 (empty for bare progress) | investigate source; fix fixture or document dead |

## Batch A — shelf items, no fixture or spec changes

*Status: **done** (2026-09-21) — +14 ops. New quirks found and recorded:
`reading-activity` 500s unless `year` is sent (DESIGN quirk #8),
`delete-multiple` returns an empty body where the spec declares a boolean,
and the single-delete "`false` for a fresh library" observation was a
scan-in-progress artifact (DESIGN quirk #18; upstream issue draft in
`docs/issue-draft-library-delete-multiple.md`).*

### A1 — OPDS image feed

Verified live (2026-09-21): with a valid `chapterId` the endpoint streams
the JPEG page — the page cache is populated on demand
(`CacheService.Ensure`) and the admin API key passes `ChapterAccess`
(DESIGN quirk #19). The earlier `400` was a bad-id artifact.

- Add a test to `tests/integration/test_opds.py`: `opds_client` +
  `GET /api/Opds/{apiKey}/image` with `libraryId`, `seriesId`, `volumeId`,
  `chapterId` from `media_library` and `pageNumber=0`.
- Assert `200`, `image/*` content type, non-empty bytes.

### A2 — date-range Stats endpoints

DESIGN quirk #8 dropped 11 endpoints for `400` on a fresh server; the
populated Phase 2 fixture now provides the reading history they need
(progress page 3 + mark-read flows). Re-attempt each with the admin client:

`avg-time-by-hour`, `favorite-authors`, `genre-breakdown`, `page-spread`,
`pages-per-year`, `reading-activity`, `reading-pace`, `reads-by-month`,
`tag-breakdown`, `word-spread`, `words-per-year`.

- New module `tests/integration/test_stats_dates.py` (`compat` tier,
  parametrized, one entry per op) on the `media_kavita_server` fixture.
- Query params: `StartDate`/`EndDate` covering the fixture's progress
  (e.g. today − 7 days → today; verify the accepted date format live).
- Assert the documented `200` and, where the spec declares a body,
  parseability — same contract-first shape as `test_sweep.py`.
- Drop-and-document any still-400 endpoint: update DESIGN quirk #8 with
  the re-verification result.

### A3 — Library delete-multiple

DESIGN quirk #18: the generated code crashes on
`isinstance(body, list[int])`. Call it over raw `httpx` instead, like the
`/api/Health` readiness probe.

- Extend `test_library_create_and_delete` in
  `tests/integration/test_mutations.py` (it already creates a throwaway
  library).
- `DELETE /api/Library/delete-multiple` with `[library_id]` as JSON via
  `httpx` + the admin token; assert `200` and record the boolean result
  (single `delete` returns `false` for an unscanned library — try
  scan-then-delete if it matters).

## Batch B — fix_spec rescues

*Status: **done** (2026-09-21) — +2 ops. `file-breakdown` response
rewritten from array to the object the server sends (Fix 5), and
`SeriesDetailPlusDto.recommendations`/`series` marked nullable (Fix 6) —
both with unit tests, regenerated fixed spec, and live tests that xfail on
nightly while upstream keeps the old schemas. The live bodies confirmed
the earlier "null list field" diagnosis was imprecise: the nulls are two
object refs, and `ratings` (an inline array already marked nullable)
parses fine.*

Both are the same class of spec bug as Fix 2/3 and follow the documented
extension procedure (`docs/fixup-coverage.md` → "How to extend static
coverage"):

1. **Capture the live bodies** against the media fixture: `file-breakdown`
   (object keyed by extension?) and `series-detail-plus` (find the exact
   null list field — likely inside the nested
   `ExternalSeriesDetailDto`/`ALMediaTitle`; Schemathesis will surface it
   independently, see `docs/TODO-schemathesis.md`).
2. **Add the fix** to `fix_spec.py` (e.g. Fix 5): rewrite
   `file-breakdown`'s response from `array` of `FileExtensionBreakdownDto`
   to the observed object shape, and make the null list field nullable in
   the `allOf` + `nullable` form the generator honors.
3. **Static tests**: extend `tests/spec_samples.py` + `tests/test_fix_spec.py`
   (rewrite, no-op, idempotence, unrelated-paths-untouched).
4. **Regenerate** `kavita_0.9.1.4.fixed.json` (`make
   kavita_0.9.1.4.fixed.json`) — the whole-document regression test pins
   it.
5. **Live tests**: `file-breakdown` as a sweep entry (`test_sweep.py`,
   Stats section, `fix_id` so the nightly build xfails the upstream bug);
   `series-detail-plus` in `tests/integration/test_metadata_extra.py`.
6. Update `docs/fixup-coverage.md` and the `spec-coverage.md` tables
   (Metadata reaches 14/14).

## Batch C — fixture unlocks

*Status: **done** (2026-09-21) — +6 ops. C1: the media fixture mounts
`tests/data/favicon.ico` at `/favicon.ico` (the endpoint only checks the
extension; content is unvalidated) and `test_opds_favicon_feed` asserts the
`200`. C2: the Upload endpoints take plain base64 in the DTO's `url`
(`CreateThumbnailFromBase64` / `SetUserCoverByUrl`) — both uploads and
both cover GETs covered. C3: the emptiness is an upstream logic bug — the
`ReadLast > OnDeckProgressDays` statement is flipped in
`SeriesFilter.HasReadLast` (`GreaterThan` selects
`MaxDate < now - N`), so a fresh read never matches; with
`OnDeckProgressDays = 0` the filter short-circuits, but that setting also
empties on-deck, so the test runs on a dedicated container
(`currently_reading_server` fixture).*

### C1 — OPDS favicon

DESIGN quirk #19: the endpoint lists `*.ico` in the parent of the app dir
(`TopDirectoryOnly`) and the container ships none. Verified: mounting any
file at `/favicon.ico` returns `200` (content is never validated).

- Add `tests/data/favicon.ico` (a minimal real ICO; a dummy file also
  works — the server checks extension only).
- Mount it in the OPDS host fixture via the existing `extra_volumes`
  parameter (`/favicon.ico:/favicon.ico:ro`) — do not add it to every
  fixture.
- Add a `test_opds.py` test: `200` + `image/x-icon`.

### C2 — Image library/user covers

DESIGN quirk #15: both GETs `404` until a cover/avatar is set. The Upload
controller has the setters: `POST /api/Upload/upload-library` and
`POST /api/Upload/upload-user` (uncovered, so they count too).

- Investigate the upload DTO/multipart shape (reuse `tests/data/cover.jpg`).
- New tests in `tests/integration/test_image.py`: upload library cover →
  `GET /api/Image/library-cover` (`200` + image bytes); upload user avatar
  → `GET /api/Image/user-cover`. Net +4 ops (2 Upload + 2 Image).

### C3 — Series currently-reading

DESIGN quirk #15: stays empty for a bare progress call while `on-deck`
lists the series. Before conceding it:

- Read the v0.9.1.4 source (`SeriesController`, the repository query) for
  the emptiness condition (dashboard flag? progress device/fields?
  recency window?).
- Try to satisfy it with fixture changes (library dashboard setting is
  already on; check the progress payload fields).
- If satisfiable: add to `tests/integration/test_series_extra.py`. If not:
  move it to the truly-dead list and update quirk #15.

## Definition of done (per item)

- Green in `KAVITA_MODE=release`; fix-dependent entries xfail on nightly
  via `expect_upstream_fix` while the upstream bug remains.
- DESIGN quirk entries #8/#9/#15/#16/#18/#19 updated or removed.
- `docs/spec-coverage.md` tables, counts, and bucket text updated
  (recompute the controller table and the 180 → new total).
- `docs/DONE-coverage-plan1.md` touched only if a phase note changes.

## Sequencing

| Batch | Effort | Notes |
|---|---|---|
| A (A1→A3) | **done** | +14 ops: `test_opds.py::test_opds_image_feed`, `test_stats_dates.py` (11), single + multiple library delete in `test_mutations.py` |
| B (B1→B2) | **done** | +2 ops: Fix 5 (`file-breakdown`) + Fix 6 (`series-detail-plus`) |
| C (C1→C3) | **done** | +6 ops: favicon mount, cover uploads + GETs, `currently-reading` on a dedicated container |

Total: ~7–10 h, one batched session each for A and C; B is the
fix_spec pipeline drill.

## Out of scope

- The long tail (~244 ops) — expansion stops here by design.
- `Filter/create` + `rename` and `Font/upload` — planned-but-not-delivered,
  need investigation, not shelf items.
- Subscription-bound and third-party families — hard blockers.

*Status: **complete** (2026-09-21). The plan is delivered; it remains as
the record of the +22 ops and the quirks they surfaced. A follow-on
5-op round-number pass took the suite to 207/517 (40.0%) — see
`docs/spec-coverage.md`.*
