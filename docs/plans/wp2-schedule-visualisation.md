# WP2: Schedule visualisation

- Status: done
- Branch: `feature-wp2-schedule-visualisation`
- Sources: [api.md](../api.md), [problem.md](../problem.md),
  [ADR 0001](../decisions/0001-controller-and-components.md),
  [ADR 0003](../decisions/0003-milp-for-battery-dispatch.md),
  [uPlot](https://github.com/leeoniya/uPlot) 1.6.32 (MIT),
  [SMARD terms of use](https://www.smard.de/home/datennutzung) (CC BY 4.0)

## Objective

Add a small, clean web page that lets a visitor pick a day or range and battery
parameters, runs the optimisation, and shows prices, the charge and discharge schedule
and the state of charge in two linked charts with the key figures above them. The page is
served by the existing FastAPI application, without a separate frontend build.

## Requirements

| ID | Requirement | Covered by |
| --- | --- | --- |
| R1 | The page is reachable at `/ui/` from `docker compose up`; `/` redirects to it | steps 2, 7; route tests, live check |
| R2 | Range and battery parameters can be entered; defaults give a sensible result for today | step 3; live check |
| R3 | Missing prices are imported automatically, then the optimisation is repeated once | step 4; live check with an empty range |
| R4 | Key figures: revenue, degradation cost, charged and discharged energy, cycles, solver time | step 5 |
| R5 | Chart 1: price as a step line, charge and discharge power as bars; chart 2: state of charge with its limits; cursors linked | step 6 |
| R6 | API errors (409, 422, 500, 502, 503) are shown as readable messages, never as raw JSON | step 4; live check with invalid input |
| R7 | Times are shown in Europe/Berlin, including days with 92 or 100 quarter hours | steps 3, 6; live check for 2026-10-25 |
| R8 | SMARD data is attributed as required by CC BY 4.0, on the page and in the docs | steps 5, 8 |
| R9 | Works without internet access in the browser apart from the API; no CDN at runtime | step 1 |

## Scope

- Static page under `battery_dispatch/communication/http/frontend/`: `index.html`,
  `app.js`, `style.css`, vendored `vendor/uPlot.iife.min.js` and `vendor/uPlot.min.css`
  with their licence.
- Mounting the page at `/ui/`, redirect from `/`.
- Route tests for the mount and the redirect.
- Documentation: README (screenshot and link), `development.md` (structure), new
  `docs/ui.md`, data attribution.

## Non-scope

- Any change to the optimisation, the price import or the existing API contracts.
- Comparison with a threshold strategy.
- Build tooling, TypeScript, frameworks, npm in the repository.
- User accounts, saved scenarios, export.
- Automated browser tests (Playwright or similar); the page is checked manually.

## Design

### Delivery

- `server.py` mounts `StaticFiles(directory=<package>/communication/http/frontend,
  html=True)` at `/ui` after the API routers, and adds `GET /` that answers
  `307` to `/ui/`. The API keeps its paths; the OpenAPI docs stay at `/docs`.
- The frontend directory is located relative to the module file, so it works from the
  source tree, the installed wheel and the Docker image. Hatch already includes non-Python
  files in the package; the builder verifies the file is present in the wheel.
- No caching headers beyond Starlette defaults.

### Libraries

- uPlot 1.6.32, files `dist/uPlot.iife.min.js` and `dist/uPlot.min.css` from
  `https://cdn.jsdelivr.net/npm/uplot@1.6.32/`, stored under `frontend/vendor/` together
  with uPlot's `LICENSE`. The SHA-256 of both files is recorded in the Implementation
  notes. uPlot is chosen because it is small (about 50 kB), made for time series and
  handles 3,000 points without effort.
- Everything else is plain HTML, CSS and JavaScript (ES2020, no modules bundler, one
  `app.js` loaded with `defer`).

### Layout

```
+--------------------------------------------------------------+
| Battery dispatch            DE-LU day-ahead     (o) API ok   |
+--------------------------------------------------------------+
| From [2026-10-26]  To [2026-10-27]                [Optimise] |
| Capacity kWh [1000]  Charge kW [500]  Discharge kW [500]     |
| Eff. charge [0.95]  Eff. discharge [0.95]                    |
| SoC min [0.10]  SoC max [0.90]  SoC start [0.50]  Degr. [0]  |
| status line: "Importing prices ..." / error message          |
+--------------------------------------------------------------+
| Revenue | Degradation | Charged | Discharged | Cycles | Solver |
+--------------------------------------------------------------+
| Chart 1: price EUR/MWh (step line, left axis)                |
|          charge (below 0) / discharge (above 0) kW bars,     |
|          right axis                                          |
+--------------------------------------------------------------+
| Chart 2: state of charge kWh (area), dashed lines at the     |
|          SoC limits                                          |
+--------------------------------------------------------------+
| Data: Bundesnetzagentur | SMARD.de, CC BY 4.0                |
+--------------------------------------------------------------+
```

- One column, maximum width about 1100 px, system font stack, generous white space, thin
  borders, no shadows. Light and dark theme through `prefers-color-scheme` and CSS custom
  properties. Two accent colours: charging blue, discharging orange; price line in the
  neutral text colour. Negative prices visible through a zero line.
- The battery parameters sit in a collapsible `<details>` element, open by default on wide
  screens. On narrow screens (below 640 px) the form stacks into one column and the charts
  take the full width.
- Charts resize with the window (`ResizeObserver`), share one cursor and one x-axis range
  (uPlot `cursor.sync`).
- The health dot polls `GET /health` once on load: green for `ok`, red otherwise, with the
  state as tooltip.

### Behaviour

- Dates are Europe/Berlin calendar days; `To` is the last day included. Default: today
  and today, so `end` is tomorrow 00:00. The page converts a Berlin date to an ISO string
  with the correct offset using `Intl.DateTimeFormat` with `timeZone: "Europe/Berlin"`
  and `timeZoneName: "longOffset"`; this handles the daylight saving change.
- `Optimise` posts to `/dispatch/optimize`. On 409 it posts the same range to
  `/prices/import`, shows "Importing prices from SMARD ...", and retries the optimisation
  once. A second 409 shows the API's message (prices not yet published).
- Error messages: for 422 the first `detail[].msg` with its field; for other statuses the
  `detail` string or a fixed sentence per status. The button is disabled while a request
  runs.
- Number formats with `Intl.NumberFormat("en-GB")`: EUR with two decimals, kWh and kW
  without decimals, cycles with two.
- Tooltip/legend shows the hovered time in Berlin time with price, power and state of
  charge.

### Content rules

- Texts on the page are English, short and factual.
- The attribution line links to smard.de and names the licence.

## Changes

| Path | Change |
| --- | --- |
| `battery_dispatch/communication/http/frontend/index.html` | create |
| `battery_dispatch/communication/http/frontend/style.css` | create |
| `battery_dispatch/communication/http/frontend/app.js` | create |
| `battery_dispatch/communication/http/frontend/vendor/` | create: uPlot JS, CSS, `LICENSE` |
| `battery_dispatch/communication/http/server.py` | mount `/ui`, redirect `/` |
| `tests/communication/http/test_frontend.py` | create |
| `.pre-commit-config.yaml` | exclude `frontend/vendor/` from whitespace hooks |
| `docs/ui.md` | create: what the page does, how it maps to the API |
| `docs/images/ui.png` | create: screenshot |
| `README.md`, `docs/development.md`, `docs/problem.md` | link, structure, attribution |
| `docs/plans/README.md`, this plan | status, notes, handoff |

## Steps

- [x] 1. Create the branch from `develop`, set this plan to `in progress`; vendor uPlot with licence and record the checksums.
- [x] 2. Mount the frontend at `/ui` and add the redirect from `/`; add route tests.
- [x] 3. Write `index.html` and `style.css`: header, form with defaults, key figures, two chart containers, attribution, light and dark theme, narrow layout.
- [x] 4. Write the request flow in `app.js`: Berlin date conversion, optimise, automatic import on 409 with one retry, error messages, disabled button while busy, health dot.
- [x] 5. Render the key figures.
- [x] 6. Render both charts with uPlot: step price line, signed power bars, state of charge area with limit lines, linked cursor, Berlin time axis, resize.
- [x] 7. Run all checks and the live check; take the screenshot.
- [x] 8. Write `docs/ui.md`, update README, `development.md` and `problem.md` (attribution); complete the Handoff; set status to `review`.

## Verification

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`
- `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` with `docker compose up -d db`
- `uv run pre-commit run --all-files`, plus the untracked files
- `uv build` and a check that the wheel contains `frontend/index.html` and the vendored files
- Route tests: `/ui/` returns the HTML page, `/ui/app.js` and the vendored files are served
  with JavaScript and CSS content types, `/` answers 307 to `/ui/`, API paths and `/docs`
  still work.
- Live check with `docker compose up --build`, in a browser at <http://localhost:8000/ui/>:
  - default (today) gives a schedule and charts
  - 2026-10-25 shows 100 quarter hours and the 02:00 to 03:00 hour twice on the axis
  - a range without stored prices triggers the import and then shows the result
  - an invalid value (for example SoC min above SoC max) shows a readable message
  - stopping the database turns the health dot red and the optimise request shows the
    503 message
  - narrow window (about 400 px) stays usable, dark theme is readable
  - screenshot saved as `docs/images/ui.png` (light theme, 2026-10-25, about 1200 px wide)

## Assumptions, open questions, and risks

- The builder sub-agent may not have a browser. Then the orchestrator runs the browser
  part of the live check and takes the screenshot, and the builder records that in the
  Handoff.
- The automatic import on 409 is a convenience of the page, not of the API; the API stays
  explicit.
- Today's prices are published the day before, so the default always has data; tomorrow's
  appear around noon. A request for a future day without published prices ends with the
  409 message after the import, which is the intended behaviour.
- `longOffset` in `Intl.DateTimeFormat` is supported by current Chrome, Edge, Firefox and
  Safari; older browsers are not a target.
- Vendoring a minified third-party file is a deliberate exception to "no copied code"; it
  is a published MIT library with its licence kept next to it.
- Larger ranges (up to 31 days, about 3,000 points) are expected to render smoothly with
  uPlot; bars may become thin and are acceptable as such.

## Implementation notes

Clarification of the plan by the orchestrator, 2026-10-26: the page runs the optimisation
once on load with its defaults, and accepts the optional query parameters `from` and `to`
(Berlin dates, `YYYY-MM-DD`) that prefill the form before that first run. A visitor sees a
result immediately, and the screenshot is reproducible. Invalid values are ignored (today
is used); `to` defaults to `from`.

Vendored files, downloaded on 2026-10-26 from `https://cdn.jsdelivr.net/npm/uplot@1.6.32/`
into the new directory `frontend/vendor/`, nothing executed from them:

| File | SHA-256 |
| --- | --- |
| `dist/uPlot.iife.min.js` (51,081 bytes) | `19c8d4c6ad88929a79f4ae49d6f7161566dfd0ba3d15cc495e974f787eb78f1f` |
| `dist/uPlot.min.css` (1,857 bytes) | `df630c6a8d6f8eeaff264b50f73ce5b114f646ffd9a0bb74f049b0a00135fa04` |
| `LICENSE` (1,078 bytes) | `8f989229699b4fe2f1a0432d0e9edc338a8a911e250e2d1b01ecd770a5f5b1bd` |

Deviations from the plan:

- Step 1: the branch already existed (created from `develop` at `82e21b5` before the
  builder started).
- No `.gitattributes` change. The first handoff added a `-text` rule for `vendor/` on the
  claim that the files use CRLF; that was wrong (a faulty byte count in Git Bash). The
  files contain no CR byte, and `git hash-object` gives the same blob with and without
  filters under the repository rule `* text=auto eol=lf`, so the checksums above hold
  for a checkout. The rule was removed after review round 1.
- `vendor/LICENSE` has no extension and is served as `application/octet-stream`. The file
  keeps its upstream name; the route test checks status and content, not the type.
- 409 after the import: the message is composed from the fields of the 409 detail
  (`found`, `expected`, `first_missing`) instead of the API's `message`, which asks to
  import first, which the page has just done. Example: "Prices are incomplete: 0 of 96
  quarter hours are available, the first missing one starts Tue 1 Jan 2030, 00:00 CET.
  SMARD may not have published them yet."
- Error texts: 500 and 502 show a fixed sentence followed by the `detail` string; 503 and
  network failures show a fixed sentence. For 422, the API's field names inside the
  message are replaced by the form labels and the prefix `Value error, ` is removed, for
  example "Battery: SoC min must be below SoC max."
- The health indicator is checked on load as planned and again after every optimisation
  attempt, so that it does not contradict the result below it.
- uPlot's built-in legend is replaced by one readout line above the first chart. It
  names the hovered quarter hour with its zone abbreviation (CEST or CET) and shows
  price, charge, discharge and state of charge for both charts.
- Dragging across a chart zooms the time axis, a double click resets it. uPlot's
  `cursor.sync` carries both to the other chart, so the shared x range holds. The x scale
  has no `range` function, since uPlot applies it after every `setScale` and would undo
  the zoom; the data already run from the start to the end of the range.
- Price and power scales are computed so that their zero lies at the same height, and one
  zero line serves both. The share of the height below zero follows the lowest price and
  is kept between 40 % and 60 %, so that charge bars always have room.
- The state of charge chart has a right axis in percent of the capacity. Both charts then
  have axes of equal width on both sides, and the cursor lines up vertically.
- The first chart gets one closing point at the end of the range, so that the last
  quarter hour is drawn in full; the second chart starts with the initial energy.
- While a request runs and after a failed one, the previous figures and charts are dimmed.
- The form uses `novalidate`; empty fields are sent as `null`, so that the API names them.
- `server.py` exposes the directory as `FRONTEND_DIR`; the route tests use it.
- Additional route tests beyond the plan: `/ui` without slash redirects, unknown file
  gives 404, every script and stylesheet referenced by `index.html` is local and served,
  OpenAPI does not list `/`.
- README also names uPlot's licence and the SMARD attribution in its licence section; the
  page footer links to `/docs`.

### After review round 1

Decided by the orchestrator on 2026-10-26:

- Finding 2 is fixed in this work package as the reviewer suggests, although the
  non-scope says "no change to the existing API contracts": the fix restores the
  documented 503 contract, and R6 needs it. It is kept separable for its own
  `fix(storage)` commit: only storage files, the mapping in `server.py` and their tests.
  `StorageUnavailableError` lives in `storage/`, one context manager on `StorageManager`
  translates `OSError` and `TimeoutError`, there is no application-wide `OSError`
  handler.
- Finding 1: fix zoom as suggested and verify it in headless Edge as far as possible;
  docs and Handoff state only what was verified.
- Finding 3: refresh the health indicator after every optimisation attempt.
- Finding 4: drop the `.gitattributes` rule and correct the note.
- Finding 5: fix the contrast of unit text and input borders in both themes.
- Finding 6: leave the degradation cost out of the request when the field is empty.
- Finding 7: add `role="img"` to the chart containers.
- Re-take `docs/images/ui.png` with the same parameters.

Changes and deviations:

- `StorageManager.session()` still raises `RuntimeError` immediately when the manager is
  not started; it now returns an async context manager instead of an `AsyncSession`.
  Both callers use it with `async with`, unchanged. The error message names the cause,
  for example `database unavailable: gaierror`; it appears in the server log, while the
  response body stays `{"detail": "database unavailable"}`.
- Additional test beyond the decision: an error other than `OSError` or `TimeoutError`
  inside a session passes through unchanged.
- The fakes `FakePriceRepository` and `FakePriceImporter` get an `error` attribute that
  is raised when set.
- Zoom showed point markers on the series once few points were visible; markers are now
  off for every series.
- Verification of zoom and hover used a scratch Node script that starts headless Edge
  with a DevTools port and sends real mouse events; no debug hook in the repository.

### After review round 2

- The session scope keeps its `try` around the `yield`: the connection opens lazily on
  the first statement inside the block, and connecting earlier would break
  `session.begin()` in `upsert`. It now catches `OSError` alone (which includes
  `TimeoutError`), and the docstring states the actual contract: any `OSError` raised
  inside the block counts as unavailability, so the block holds only database work, and a
  timeout belongs around the whole `async with`, where it is not translated.
- Two tests pin this: `test_os_errors_inside_a_session_count_as_unavailable` and
  `test_timeout_around_a_session_is_not_translated`.

## Handoff

- Branch: `feature-wp2-schedule-visualisation`
- Base: `develop` at `82e21b5`
- Diff to review: `git diff develop` plus the untracked files from `git status --short`:
  `battery_dispatch/communication/http/frontend/` (`index.html`, `style.css`, `app.js`,
  `vendor/uPlot.iife.min.js`, `vendor/uPlot.min.css`, `vendor/LICENSE`),
  `battery_dispatch/storage/errors.py`, `tests/communication/http/test_frontend.py`,
  `docs/ui.md`, `docs/images/ui.png`, and this plan. Nothing is staged or committed.
- First handed over: 2026-10-26. Updated after review rounds 1 and 2: 2026-10-26.

Split into two commits:

- `fix(storage)`, exactly the changes in the patch
  `C:\Users\Thorg\AppData\Local\Temp\claude\C--Users-Thorg-IdeaProjects-battery-dispatch-demo\2d3e5df5-5a72-474a-bc12-f1702eab40cf\scratchpad\fix-storage.patch`
  (outside the repository, regenerated after review round 2). Stage it with
  `git apply --cached <patch>`, not with `git add -p`: both hunks of `server.py` mix
  storage and page lines (the first one the storage import with `Path`,
  `RedirectResponse`, `StaticFiles` and `FRONTEND_DIR`; the second one the exception
  handler with the route for `/` and the mount). The patch contains:
  - `battery_dispatch/storage/errors.py` (new file)
  - `battery_dispatch/storage/storage_manager.py`, all changes
  - `battery_dispatch/communication/http/server.py`, only two lines: the import
    `from battery_dispatch.storage.errors import StorageUnavailableError` and
    `app.add_exception_handler(StorageUnavailableError, _database_error)`
  - `tests/fakes.py`, `tests/communication/http/api/test_dispatch_routes.py`,
    `tests/communication/http/api/test_price_routes.py`,
    `tests/storage/test_storage_manager.py`, all changes
- `feat`: everything else, staged after the first commit.

Checked after round 2: the patch applied with `git apply` to an export of `develop` in a
scratch directory gives the six storage and test files identical to the working tree
(ignoring the CR that `git archive` adds with `core.autocrlf=true` on this machine), and
`server.py` differs from the working tree only by the page lines. There `ruff check`,
`ruff format --check` (73 files), `pyright` and `BATTERY_DISPATCH_REQUIRE_DB=1 pytest`
(114 tests, database password passed as environment variable) pass.
`git apply --cached --check` of the patch against this working tree succeeds; nothing is
staged.

Checks after the round 2 fixes (live rows from round 1 unless marked):

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 76 files already formatted |
| `uv run pyright` | passed, 0 errors |
| `uv lock --check` | passed |
| `docker compose up -d db`, then `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` | passed, 126 tests, none skipped (7 new since round 1: 3 route tests for 503, 4 storage tests) |
| `uv run pre-commit run --all-files` | passed (tracked files) |
| `uv run pre-commit run --files <untracked files>` | passed; vendored files unchanged afterwards |
| `uv build` | passed; the wheel contains `frontend/index.html`, `app.js`, `style.css`, the three vendored files and `storage/errors.py` |
| Vendored files | SHA-256 unchanged; `git hash-object` equal with and without filters, without any `.gitattributes` rule |
| Live: `docker compose up --build -d` | api and db up, `GET /health` 200 |
| Live: `GET /` and `GET /ui` | 307 to `/ui/` |
| Live: `/ui/`, `/ui/app.js`, `/ui/style.css`, `/ui/vendor/uPlot.iife.min.js`, `/ui/vendor/uPlot.min.css` | 200 with `text/html`, `text/javascript`, `text/css`, `text/javascript`, `text/css` |
| Live: `/ui/vendor/LICENSE`, `/ui/missing.js`, `/docs`, `/openapi.json` | 200 (`application/octet-stream`), 404, 200, 200 |
| Live: `docker compose stop db` | `GET /health` 503 (storage `TimeoutError`); `POST /dispatch/optimize`, `GET /prices`, `POST /prices/import` 503 `{"detail": "database unavailable"}`, logged as `database unavailable: gaierror`; page shows "The database is unavailable. ..." and the red indicator "API down" |
| Live: `docker compose start db` | `/health` 200, `POST /dispatch/optimize` 200 again without restarting the API |
| Live after round 2, `docker compose up --build -d` | optimise 200; with the database stopped optimise, `GET /prices` and import 503 `{"detail": "database unavailable"}`; database started again, `/health` 200, optimise 200 |
| Edge headless over the DevTools protocol, 2026-10-25, real mouse events | hover at 02:15 gives "Sun 25 Oct 2026, 02:15 CEST" and "... 02:15 CET"; a drag over 0 to 6 h zooms both charts (30-minute ticks, 02:00 and 02:30 labelled twice), hovering in the zoomed chart matches the zoomed range; a double click resets both charts to the full day |
| Same session, form changes | Degradation empty: request without the field, 200; SoC min 0.95: "Battery: SoC min must be below SoC max." as error; a `GET /health` follows every optimise in the API log |
| Screenshot `docs/images/ui.png` | re-taken, 1200 x 1330 px, 82,558 bytes, light theme, `--lang=en-GB`, 2026-10-25 |

From the first handoff, not repeated after the fixes: a day without stored prices (2025-06-02) gave optimise 409, import 200, optimise 200 and "96 quarter hours, prices imported from SMARD."; a day without published prices (2030-01-01) gave the 409 message after the import; dark theme and 520 px width were readable in headless Edge.

Not done by the builder: the interactive check in a normal browser (drag and double click
by hand, about 400 px width, dark theme). Headless Edge does not go below a viewport of
492 px. The stack is left running (`docker compose up -d`).

Browser check after the round 1 fixes, run by the orchestrator on 2026-10-26 in the
built-in browser against the rebuilt stack:

| Check | Result |
| --- | --- |
| 2026-10-25, mouse drag over the first hours of the price chart | both charts zoom; the axis labels 02:00 and 02:30 twice; readout follows the zoomed range |
| Double click on the chart | both charts back to the full day |
| Database stopped, Optimise clicked | optimise 503, then `GET /health` 503; page shows "The database is unavailable. ..." and "API down" |
| Database started again, Optimise clicked | 200, "100 quarter hours.", indicator "API ok" |

Attention points for the reviewer:

- At full width 2026-10-25 has 2-hour ticks (02:00 CEST, then 04:00 CET); the repeated
  hour is labelled on the axis only when zoomed in. `docs/ui.md` says so.
- The page and the storage fix share both hunks of `server.py`; stage the fix with the patch, see the split above.

## Review

### Round 1

- Reviewer: Claude Code, sub-agent in a fresh context, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-10-26
- Inputs: this plan (including the orchestrator clarification and browser check), `AGENTS.md`,
  `docs/workflow.md`, `docs/api.md`, `docs/problem.md`, `docs/development.md`, `docs/ui.md`,
  `docs/decisions/0001` to `0003`; diff `git diff develop` (base `develop` at `82e21b5`,
  working tree of `feature-wp2-schedule-visualisation`, nothing committed) plus all untracked
  files from `git status --short`, read in full except `vendor/uPlot.iife.min.js`. Upstream
  reference: `https://cdn.jsdelivr.net/npm/uplot@1.6.32/dist/` (`uPlot.iife.min.js`,
  `uPlot.min.css`, and `uPlot.esm.js` for reading only) and `.../uplot@1.6.32/LICENSE`,
  downloaded into the scratchpad, not executed.
- Checks performed:

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 75 files already formatted |
| `uv run pyright` | passed, 0 errors, 0 warnings |
| `uv lock --check` | passed |
| `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` (db up) | passed, 119 tests |
| `uv run pre-commit run --all-files` | passed |
| `uv run pre-commit run --files <untracked files>` | passed, no file changed |
| `uv build --out-dir <scratchpad>` | passed; wheel and sdist contain `frontend/index.html`, `app.js`, `style.css`, `vendor/LICENSE`, `vendor/uPlot.iife.min.js`, `vendor/uPlot.min.css`; the sdist contains no `AGENTS.md`, `.env` or `config/config.yaml` |
| Vendored files against upstream 1.6.32 | SHA-256 of all three files equal upstream and the values recorded above |
| `git hash-object` of the vendored files, with the new rule and with `--path` outside `vendor/` | identical blobs; the files contain no CR byte (see finding 4) |
| `berlinMidnight` and `isDate` from `app.js`, evaluated in Node 24 with `TZ` set to UTC, America/Los_Angeles, Asia/Tokyo and Europe/Berlin | every day 2020 to 2030 maps to 00:00 Berlin time; 2026-03-29 gives 92, 2026-10-25 and 2027-10-31 give 100, ordinary days 96 quarter hours; 2026-02-30, 2026-13-01, 0099-01-01 and `2026-1-1` rejected, 2024-02-29 accepted |
| Static mount traversal with `curl --path-as-is`: `/ui/../pyproject.toml`, `/ui/%2e%2e/server.py`, `/ui/..%2fserver.py`, `/ui/vendor/..%2f..%2fserver.py`, `/ui/..%5cserver.py` | all 404 |
| Runtime requests and DOM writes | `app.js` fetches only `/health`, `/dispatch/optimize` and `/prices/import`; no `innerHTML`, `insertAdjacentHTML`, `eval` or `new Function`; API and user data reach the DOM only through `textContent` and `title`; the only URL in the vendored files is a comment link to GitHub |
| API 422 bodies the page translates (curl) | long range: `loc ["body"]`; SoC rules: `loc ["body","battery"]`; field errors: `loc [..., "<field>"]`; all map to entries of `FIELD_LABELS` |
| Database stopped (`docker compose stop db`), then started again | `/health` 503 (storage `TimeoutError`); `POST /dispatch/optimize` and `GET /prices` 500 `Internal Server Error`; API log `socket.gaierror: [Errno -2] Name or service not known`, re-raised by `_handle_exception_no_connection` of the asyncpg dialect. Database started again, `/health` 200 |
| Edge headless, dark theme, `--lang=de-DE`, `/ui/?from=2026-03-29&to=2026-03-29` | 92 quarter hours, figures and both charts drawn, inputs show `0,95`, readable |
| Built-in browser (Chromium, locale `de`), 2026-10-25 | `0,8` typed into SoC max gives `input.value` `0.8`, Enter submits, result redrawn with the upper limit at 800 kWh; hover readout names CEST and CET; a drag across the chart does not zoom (finding 1) |
| `docs/images/ui.png` | present, 1200 x 1330 px, light theme, 2026-10-25 with figures and both charts |
| Contrast (WCAG formula on the CSS custom properties, light / dark) | text 16.4:1 / 13.6:1, muted 5.7:1 / 6.7:1, error box 5.8:1 / 7.3:1; units and input borders see finding 5 |

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | major | `battery_dispatch/communication/http/frontend/app.js:448` | Drag zoom, documented in `docs/ui.md:47` and in the Implementation notes, does not work. The x scale has `range: () => [t0, t1]`, and uPlot 1.6.32 applies the range function of the x scale also after explicit `setScale` calls (`uPlot.esm.js:4053`, `wsc.range(self, wsc.min, wsc.max, k)` for series 0), so every zoom is reset to the full range. Reproduced in the page with the vendored uPlot: a chart with this range function stays at `[0, 86400]` after `setScale('x', {min: 3600, max: 7200})`, the same chart without it moves to `[3600, 7200]`; a drag in the built-in browser leaves the axis unchanged. The Handoff's statement that the repeated 02:00 hour is labelled twice after zooming in therefore cannot hold, and the R7 live check item (02:00 hour twice on the axis) is met only through the readout. | Remove the `range` option from `xScale` (the data already span `t0` to `t1`, so the default time range is the same), or use `range: (u, min, max) => [min ?? t0, max ?? t1]`. Then check in a browser: a drag zooms both charts, a double click resets them, hourly ticks show 02:00 twice on 2026-10-25. | fixed: `range` removed from the x scale (`app.js`), point markers turned off for all series (they appeared once zoomed in). Verified in headless Edge with real mouse events over the DevTools protocol: a drag over 0 to 6 h zooms both charts to 30-minute ticks that label 02:00 and 02:30 twice; a double click resets both. `docs/ui.md` states exactly that |
| 2 | major | `battery_dispatch/communication/http/server.py:46` | With the database down, `POST /dispatch/optimize`, `POST /prices/import` and `GET /prices` answer 500 with a plain-text body instead of the 503 that `docs/api.md:150` promises, and the page shows "The optimisation did not finish." (orchestrator check, reproduced above). Root cause confirmed: asyncpg raises `socket.gaierror` (stopped container, name not resolvable), `ConnectionRefusedError` or `TimeoutError` while connecting. These are `OSError` subclasses, not DBAPI errors, so SQLAlchemy 2.1.5 re-raises them unwrapped (`_handle_dbapi_exception_noconnection` wraps only `dialect.loaded_dbapi.Error`) and the `SQLAlchemyError` handler does not apply. `StorageManager.health` already catches `OSError` and `TimeoutError`, which is why `/health` is correct. The defect predates this change, but R6 and the plan's live check require the 503 message, so the work package cannot pass its own verification without it. The fix restores the documented contract rather than changing it, so it does not conflict with the non-scope. | Fix it in this work package, as a separate `fix(storage)` commit. Translate connection failures at the storage boundary, not with an application-wide `OSError` handler: add `StorageUnavailableError` in `battery_dispatch/storage/`, raise it with `from exc` where sessions are used (`PriceRepository.upsert` and `list_range`, or one async context manager on `StorageManager` that both use) when `OSError` or `TimeoutError` escapes, and map it to the existing 503 body in `server.py` next to `SQLAlchemyError`. Tests: a route test where the fake planner or repository raises `StorageUnavailableError` and the response is 503 `database unavailable`; an integration-style test with a `StorageManager` pointed at an unused local port (for example `127.0.0.1:1`) whose `list_range` raises `StorageUnavailableError`. Re-run the live check with `docker compose stop db`. | fixed as separate `fix(storage)` part, see Handoff: `StorageUnavailableError` in `storage/errors.py`, raised `from exc` by the session scope of `StorageManager.session()` for `OSError` and `TimeoutError`, mapped to the existing 503 body in `server.py`. Route tests for optimise, import and `GET /prices`; repository against `127.0.0.1:1`. Live with the database stopped: all three 503 `database unavailable` |
| 3 | minor | `battery_dispatch/communication/http/frontend/app.js:273` | The health indicator is refreshed only on load, after 503 and after network errors (`app.js:273`, `app.js:282`). If the database was down at load and recovers, a successful optimisation leaves the dot red; after a 500 caused by the database (finding 2) it stays green. The indicator can contradict the result shown below it. | Call `checkHealth()` after every optimisation attempt, for example in the `finally` block of `optimise()`, and drop the two special cases. One extra `GET /health` per click is negligible. Update the Implementation note and `docs/ui.md` ("on load") accordingly. | fixed: `checkHealth()` in the `finally` block of `optimise()`, special cases removed; verified in the API log (one `GET /health` after each optimise); `docs/ui.md` updated |
| 4 | minor | `.gitattributes:4` | The Implementation note says the published files use CRLF and would otherwise be stored with LF, so that the checksums would no longer match a checkout. That is not the case: none of the three files contains a CR byte, and `git hash-object` gives the same blob with the new rule and with the default `* text=auto eol=lf` rule (`--path` outside `vendor/`). The rule is harmless, but its recorded reason is wrong, and `.gitattributes` is not in the Changes table. | Either drop the rule, or keep it with a corrected reason (byte-for-byte storage of third-party files regardless of their line endings) and correct the Implementation note. | fixed: rule dropped, `.gitattributes` unchanged against `develop`; blobs and SHA-256 unchanged; Implementation note corrected |
| 5 | minor | `battery_dispatch/communication/http/frontend/style.css:173` | Low contrast for small text and control borders. The units in the field labels (`.unit`, 12 px, `opacity: 0.75` on `--muted`) reach 3.3:1 in the light and 4.4:1 in the dark theme, below the 4.5:1 of WCAG AA for normal text. Input borders (`--border` on `--surface`, `style.css:181`) reach 1.3:1 in both themes, below the 3:1 for component boundaries, so the fields are hard to make out on the panel. | Drop the opacity on `.unit` (muted alone is 5.7:1 / 6.7:1) and give inputs a dedicated border colour with at least 3:1 against `--surface` in both themes. | fixed: `.unit` without opacity (5.65:1 light, 6.69:1 dark); new `--input-border` `#868f9a` light (3.28:1 on surface, 3.06:1 on page) and `#6b7480` dark (3.57:1, 3.89:1) |
| 6 | note | `battery_dispatch/communication/http/frontend/app.js:235` | Clearing the optional Degradation field sends `null`, and the API answers "Degradation: Input should be a valid number." although `docs/api.md` documents the field as optional with default 0 (verified with curl). The message is readable, so this is a usability point only. | Omit `degradation_cost_eur_per_mwh` from the request when the field is empty, or keep the behaviour and say in `docs/ui.md` that every field is required. | fixed: an empty Degradation field is left out of the request, the API default applies; verified live (200); `docs/ui.md` says so |
| 7 | note | `battery_dispatch/communication/http/frontend/app.js:574` | The chart containers get an `aria-label` but no role, so assistive technology usually ignores the label; the values are reachable only by pointer hover. Acceptable for a demo page, but the label currently has no effect. | Add `role="img"` to both chart containers in `index.html`, or remove the `aria-label` calls. | fixed: `role="img"` and the `aria-label` are set in `index.html`; the `setAttribute` calls in `app.js` are removed |

Verdict: changes required

### Round 2

- Reviewer: Claude Code, sub-agent in a fresh context, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-10-26
- Inputs: this plan (Implementation notes including the orchestrator decisions after round 1,
  Handoff including both orchestrator browser checks, round 1 with its Resolution column),
  `AGENTS.md`, `docs/workflow.md`, `docs/api.md`, `docs/ui.md`, `docs/development.md`,
  `docs/problem.md`, `docs/decisions/0001` to `0003`; diff `git diff develop` (base `develop`
  at `82e21b5`, which is also `HEAD`; working tree of `feature-wp2-schedule-visualisation`,
  nothing staged or committed) plus all untracked files from `git status --short`, read in
  full except the two minified vendored files; the orchestrator's storage patch
  `fix-storage.patch` in the session scratchpad, read and applied only to a scratch export
  of `develop`.
- Checks performed:

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 76 files already formatted |
| `uv run pyright` | passed, 0 errors, 0 warnings |
| `uv lock --check` | passed |
| `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` (db up) | passed, 124 tests, none skipped |
| `uv run pre-commit run --all-files` | passed |
| `uv run pre-commit run --files <11 untracked files>` | passed; SHA-256 of the vendored files unchanged afterwards |
| `uv build --out-dir <scratchpad>` | passed; the wheel contains `frontend/index.html`, `app.js`, `style.css`, `vendor/LICENSE`, `vendor/uPlot.iife.min.js`, `vendor/uPlot.min.css` and `storage/errors.py`; the vendored files in the wheel have the SHA-256 recorded above; the sdist contains the same files and no `AGENTS.md`, `.env` or `config/config.yaml` |
| Vendored files in the working tree | SHA-256 of all three equal the values in the Implementation notes; `.gitattributes` unchanged against `develop` |
| Session scope, scratch script against the running TimescaleDB | `OSError`, `FileNotFoundError` and an `asyncio.timeout` expiring inside `async with storage.session()` all become `StorageUnavailableError` (finding 1); `asyncio.wait_for` around a repository call raises a plain `TimeoutError`; `asyncio.CancelledError` and `ValueError` pass through unchanged; `upsert` writes 4 rows, a repeat writes 0; an exception inside `session.begin()` rolls back (`ValueError` and `OSError` both leave the 4 rows); a session without commit leaves the rows; `127.0.0.1:1` gives `StorageUnavailableError` from `ConnectionRefusedError`, an unresolvable host from `gaierror` |
| 503 mapping in `server.py` | one handler for `StorageUnavailableError` next to `SQLAlchemyError`; no handler for `OSError`, `TimeoutError` or `Exception` |
| Storage patch against the Handoff list | the patch touches exactly the listed files; applied to `git archive develop`, the six storage and test files are byte-identical with the working tree, and `server.py` differs from the working tree only by the page lines (`Path`, `RedirectResponse`, `StaticFiles`, `FRONTEND_DIR`, route for `/`, mount, `_redirect_to_ui`); there `ruff check`, `ruff format --check` (73 files) and `pyright` pass, and `BATTERY_DISPATCH_REQUIRE_DB=1 pytest` passes with 112 tests (database password passed as environment variable, no file copied); `git apply --cached --check` against this working tree succeeds, the index stays empty |
| Live, `docker compose stop db` | `/health` 503 (storage `TimeoutError`); `POST /dispatch/optimize`, `GET /prices`, `POST /prices/import` 503 `{"detail": "database unavailable"}`, logged as `Database error: database unavailable: gaierror`. Once, the log also showed asyncio's `Future exception was never retrieved` with a `gaierror`; it did not recur when `/health` and `GET /prices` were repeated one by one, and it cannot be attributed to this change |
| Live, `docker compose start db` | `/health` 200, `POST /dispatch/optimize` 200 without restarting the API; stack left running |
| Built-in browser (Chromium), `/ui/?from=2026-10-25&to=2026-10-25`, 1024 px, light | a mouse drag over the first hours zooms both charts, the axis labels 02:00 twice; hovering the zoomed chart gives "02:00 CEST" and "02:00 CET" with the values of the API response (02:00 CET: discharge 500 kW, 100 kWh, consistent with 231.58 kWh minus 125 kWh / 0.95); a double click resets both charts to the full day |
| Built-in browser, 375 x 812 mobile emulation, dark | no horizontal scrolling (`scrollWidth` 375), charts 313 px wide, Battery closed by default, opens into one column, all texts readable; `.unit` opacity 1, input border `#6b7480`; both chart containers have `role="img"` and their label |
| Same session, Degradation cleared, Enter | optimise 200, "100 quarter hours."; the network log shows a `GET /health` after every optimise |
| Contrast (WCAG formula) | `.unit` 5.65:1 / 6.69:1; `--input-border` 3.28:1 on surface and 3.06:1 on page (light), 3.57:1 and 3.89:1 (dark), as stated in the Resolution |
| Secrets and style | the pre-publication pattern finds nothing in `git diff develop`; no em dash in the changed docs and page files |

Round 1 findings against their Resolution: 1 to 7 are fixed as described. For finding 2 the
translation is wider than its docstring says, see finding 1 below. The claim in
`docs/ui.md` that the page works down to about 400 px was not verified by the builder; it
holds at 375 px in this round. The Handoff states only what was checked.

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | minor | `battery_dispatch/storage/storage_manager.py:68` | The `try` in `_session_scope` encloses the `yield`, so every `OSError` or `TimeoutError` raised by caller code inside `async with storage.session()` is reported as `StorageUnavailableError`, not only connection failures as the docstring (`storage_manager.py:51`) says. Reproduced: a `FileNotFoundError` in the block and an `asyncio.timeout(0.01)` expiring in the block both become `StorageUnavailableError("database unavailable: ...")`, which `server.py` turns into 503 "database unavailable". The current callers (`PriceRepository.upsert` and `list_range`) do only database work in the block, so no request is affected today; a future caller that adds file I/O or a timeout inside the block would get a misleading 503. Narrowing the `try` to connection setup is not straightforward: the connection is opened lazily on the first `execute`, and connecting eagerly would make `session.begin()` in `upsert` fail because a transaction would already be in progress. `TimeoutError` is a subclass of `OSError`, so the tuple is redundant. | Keep the scope and state its actual contract in the docstring: any `OSError` or `TimeoutError` raised inside the block counts as unavailability, so the block holds only database work, and timeouts wrap the whole `async with` (as `asyncio.wait_for` outside does, which is not translated). Optionally add a test that pins this, and catch `OSError` alone with a comment that it includes `TimeoutError`. | fixed: `try` kept around the `yield`, catches `OSError` only with a comment that it includes `TimeoutError`; docstring states that any `OSError` inside the block counts as unavailability and timeouts belong around the whole `async with`; pinned by `test_os_errors_inside_a_session_count_as_unavailable` and `test_timeout_around_a_session_is_not_translated` |
| 2 | note | `docs/plans/wp2-schedule-visualisation.md:313` | The Handoff says only the hunk with the mount needs a split under `git add -p`. With the default three context lines, the first hunk of `server.py` (`@@ -4,21 +4,27 @@`) also mixes the storage import with `Path`, `RedirectResponse`, `StaticFiles` and `FRONTEND_DIR`, so it needs a split as well. The patch itself is correct and complete (see checks). | Stage the `fix(storage)` commit with `git apply --cached` of the checked patch instead of `git add -p`, or mention that both hunks of `server.py` need a split. | fixed: Handoff says both `server.py` hunks mix storage and page lines and that the `fix(storage)` commit is staged with `git apply --cached` of the patch; patch regenerated and re-verified (standalone checks, `git apply --cached --check`) |

Verdict: approve with minor findings
