# WP3: Documentation and visible agent workflow

- Status: done
- Branch: `feature-wp3-docs-and-workflow`
- Sources: [workflow.md](../workflow.md), [problem.md](../problem.md),
  [ADR 0003](../decisions/0003-milp-for-battery-dispatch.md), the plans and review rounds of
  WP1 and WP2

## Objective

Make the documentation understandable for someone reading the repository for the first
time, starting from how the parts work together. State openly and factually that the
project was built with AI coding agents under a written workflow, and make that workflow
reproducible from a clone. No application behaviour changes.

## Requirements

| ID | Requirement | Covered by |
| --- | --- | --- |
| R1 | One index says which document answers which question | step 2; `docs/README.md` |
| R2 | A reader can follow an import and an optimisation request through the components | step 3; `docs/architecture.md`; cold read |
| R3 | The model, why it is well posed, its implementation and possible extensions are in one place | step 4; `docs/optimisation.md`; cold read |
| R4 | What the tests secure, and what they do not, is explained | step 5; `docs/testing.md`; cold read |
| R5 | README and `workflow.md` state how agents were used, what the author decides, what the reviews found, and the limits of that review | step 6; cold read |
| R6 | A clone contains neutral agent instructions and role definitions | step 7; `AGENTS.md`, `CLAUDE.md`, `.claude/agents/` |
| R7 | Personal references and local paths appear in no tracked file | steps 7, 9; scan |
| R8 | Outdated statements and the local path in the WP2 plan are gone | step 8; scan |

## Scope

- New documents: `docs/README.md`, `docs/architecture.md`, `docs/optimisation.md`,
  `docs/testing.md`.
- Revised: `README.md`, `docs/problem.md`, `docs/workflow.md`, `docs/development.md`,
  `docs/plans/README.md`, one line in `docs/plans/wp2-schedule-visualisation.md`.
- Public agent files: `AGENTS.md`, `CLAUDE.md`, three short role files.
- Keeping local instructions, not tracked, apart from the public `AGENTS.md`.

## Non-scope

- Any change to application code, tests, CI or container files.
- Automation: review bots in CI, more agents, generated documentation.
- Subfolders under `docs/`, a roadmap, a decisions log, test reports.
- Rewriting Git history.
- New ADRs; the existing three stay as they are.

## Design

### Documents

Every document answers one question. `docs/README.md` is a table of question, document.

| Document | Question it answers | Content |
| --- | --- | --- |
| `README.md` | What is this and how do I start it? | Stays compact; adds the paragraph below and links to `docs/README.md` instead of listing every document |
| `problem.md` | What problem is solved, with what data, within which limits? | Problem, scope, data source, known limitations. The model moves out. "If time permits" becomes a plain statement that a threshold comparison is not included |
| `architecture.md` | How do the parts work together? | Components and their dependencies, one Mermaid diagram, startup and shutdown, the flows of an import and an optimisation request, the table `day_ahead_prices`, error mapping by reference to `api.md` |
| `optimisation.md` | What is computed, and why can it be trusted? | See below |
| `api.md`, `ui.md` | How is it used? | Unchanged except links |
| `testing.md` | What do the tests secure? | Layout, markers, database behaviour, a table of risk and covering test, what is only checked by hand (browser), and that mutation checks were one-off review work and not part of CI |
| `development.md` | How do I work on it? | Unchanged except links; the structure tree stays |
| `workflow.md` | How was it built? | See below |
| `decisions/` | Why this way? | Unchanged |

`optimisation.md` has these sections:

- **Model:** the formulation moved from `problem.md`, with units.
- **Why it is well posed:** doing nothing is always feasible, because the API enforces
  `soc_min <= soc_initial <= soc_max`; all variables are bounded, so an optimum exists; the
  exclusivity constraint uses the real power limits instead of an arbitrary large constant;
  optima need not be unique, so another solver may return another schedule with the same
  revenue.
- **Implementation:** `optimize` as a pure function, the planner around it, the expressions
  built from coefficient lists and why that differs from usual PuLP style, the gap and the
  solver status.
- **How it is checked:** a short reference to `testing.md`.
- **Possible extensions:** self-discharge, cycle limit, value of the final energy, limits
  depending on the state of charge, depth-dependent ageing, co-located generation,
  reserve markets, forecasts with a rolling horizon. Marked as ideas, not plans.

### Stating how the project was built

Paragraph for the README, under the heading `How it was built`:

```markdown
Built with AI coding agents (Claude Code) under the author's direction. The author sets
goals and scope, reviews and approves the design and every plan, and decides what is merged;
agents write the code, tests and documents. Plans and review findings are in
[docs/plans/](docs/plans/), the process in [docs/workflow.md](docs/workflow.md).
```

The paragraph and the section below were reworded after review round 1, see Implementation
notes.

`workflow.md` gains a short opening section with:

- **What the author decides:** scope, architecture, approvals, trade-offs. Examples: the
  relative gap of 0.5 % instead of a solver change, 31 days and 1 hour, the battery bounds.
- **What the process found:**

  | Work package | Finding | Found by |
  | --- | --- | --- |
  | WP1 | Valid requests on real prices hit the 30 s solver limit and answered 500 | Reviewer, round 1 |
  | WP2 | Drag zoom snapped back although the docs claimed it worked | Reviewer, round 1 |
  | WP2 | Unreachable database answered 500 instead of the documented 503 | Orchestrator's browser check; root cause confirmed by the reviewer |

- **Limits:** independence means a fresh context without the builder's reasoning, not a
  different model or vendor. Browser behaviour is checked by hand. The author remains
  responsible for the result.
- Why commits carry no agent attribution: this statement is the disclosure.

The existing role, flow and status sections stay as they are.

### Agent files

Tracked:

- `AGENTS.md`: purpose, pointer to `docs/README.md` and `workflow.md`, the checks to run,
  conventions (English, no em dashes, sober language, Conventional Commits, no agent
  attribution lines, plan numbers stay out of code), approval rule for commits and pull
  requests, and the rule that everything is written new, with nothing copied from other
  projects.
- `CLAUDE.md`: the single line `@AGENTS.md`.
- `.claude/agents/planner.md`, `builder.md`, `reviewer.md`: frontmatter plus a pointer to
  the matching section of `workflow.md`. They do not redefine the roles; the reviewer file
  states the fresh context.

Local instructions, not tracked, stay in files of their own.

Order matters. `AGENTS.md` was ignored by name until now, so the local instructions move first,
the neutral text follows, and `.gitignore` changes only after that. `.gitignore` also lists
`.claude/settings.local.json`.

### Writing rules

English, no em dashes, sober language, no marketing terms. Short sentences. Each document
starts with what it answers. Facts are checked against the code, not taken from older docs.
No document contains personal references or local paths.

## Changes

| Path | Change |
| --- | --- |
| `docs/README.md` | create: index |
| `docs/architecture.md` | create |
| `docs/optimisation.md` | create: model moved from `problem.md`, the rest new |
| `docs/testing.md` | create |
| `docs/problem.md` | modify: remove the model, link to it, fix outdated statement |
| `docs/workflow.md` | modify: opening section |
| `docs/development.md` | modify: links |
| `docs/api.md`, `docs/ui.md`, `docs/decisions/0003-milp-for-battery-dispatch.md` | modify only if a link to the moved section breaks |
| `README.md` | modify: paragraph, link to the index, status line |
| `docs/plans/README.md` | modify: WP3 row, column with the review result per work package |
| `docs/plans/wp2-schedule-visualisation.md` | modify: replace the local path in the Handoff |
| `AGENTS.md` | replace with neutral text, now tracked |
| `CLAUDE.md` | create |
| `.claude/agents/planner.md`, `builder.md`, `reviewer.md` | create |
| `.gitignore` | modify: stop ignoring `AGENTS.md`, ignore the local files |
| Local instructions, not tracked | create |

## Steps

- [x] 1. Create the branch from `develop`, set this plan to `in progress`.
- [x] 2. Write `docs/README.md`.
- [x] 3. Write `docs/architecture.md` from the current code.
- [x] 4. Write `docs/optimisation.md` and reduce `docs/problem.md`.
- [x] 5. Write `docs/testing.md` from the current tests.
- [x] 6. Add the paragraph to the README and the opening section to `workflow.md`.
- [x] 7. Move the local instructions in the order above, then add the public agent files and change `.gitignore`.
- [x] 8. Fix the WP2 path, update `docs/plans/README.md` and the links.
- [x] 9. Run all checks and the leak scan, complete the Handoff, set status to `review`.

## Verification

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv lock --check`
- `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` with `docker compose up -d db`
- `uv run pre-commit run --all-files`, plus the untracked files
- `git diff develop --stat` shows no change under `battery_dispatch/`, `tests/`, `.github/`
  or in the container files.
- All relative links in Markdown files resolve; checked with a throwaway script outside the
  repository.
- `git check-ignore` confirms that the local instruction files are ignored and `AGENTS.md` is
  not.
- Scan over every file that would be committed, before anything is staged for good, for personal
  references and local paths. Every hit is explained in the Handoff or removed. The name of the
  author is allowed.
- Facts in the new documents are compared with the code: test names, limits, defaults,
  status codes, runtimes from ADR 0003.
- Cold read by the reviewer: from the documents alone, without the code, answer how an
  optimisation request flows, what the model is and why a solution always exists, what the
  tests do not cover, and what the agents did and what the author decided. Then check the
  answers against the code.

## Assumptions, open questions, and risks

- The user decides how prominently agent use is stated; the paragraph above is a proposal
  and can be reworded with the approval.
- The wording "the author sets the scope and approves" must match what happened; the user
  confirms it with the approval.
- `.claude/agents/` is optional and small. If the frontmatter format differs from what the
  installed Claude Code expects, the builder checks that a role can be started and reports.
- Tracking `AGENTS.md` is the riskiest step: a mistake publishes local content. Hence the
  order above and the scan. Nothing is committed without the user's approval.
- Agents starting in this repository read the public `AGENTS.md`; local instructions, not
  tracked, apply on top of it. Other tools may not read them.

## Implementation notes

Deviations from the plan as approved:

- R7, Verification and the writing rules are worded more generally than in the approved plan.
- The README paragraph in this plan is a code block instead of a quotation. Its links are relative
  to the repository root and were broken in this file.
- `docs/development.md` gained one opening sentence besides the links, because each document
  starts with what it answers.
- `docs/problem.md`: "can be computed exactly" became "can be computed", since results are
  optimal within a gap. Day-ahead price and bidding zone are explained here, state of charge
  links to `optimisation.md`.
- `docs/workflow.md`, beyond the listed content: a pointer to `AGENTS.md` and `.claude/agents/`,
  that the three findings were fixed before merging, and that builder and reviewer can share
  blind spots.
- `docs/testing.md` has a short CI section that the plan does not list.
- `docs/optimisation.md` has a worked example in Model and a paragraph "Key figures" in
  Implementation, which the plan's section list does not name. The example matches
  `test_two_steps_by_hand`.
- `.claude/agents/`: the frontmatter holds only `name` and `description`, so tools and model
  are inherited. The reviewer needs write access to add its round to the plan.

### After review round 1

Decided by the user on 2026-11-03:

- The README paragraph under "How it was built" is the one now in Design, replacing the approved
  proposal.
- `docs/workflow.md` states that the author sets goals and scope, reviews and approves the design
  and every plan, and decides what is merged; that the orchestrator and the builder take smaller
  decisions within an approved plan and record them; and that agents also wrote the scaffold and
  the price import, on whose merge the author decided. This replaces the sentence "Agents propose
  options and report results" and the list of decisions in Design.
- This plan refers to local instructions, not tracked, in general terms only.
- The local scratch path in old commits stays; history is not rewritten.
- The user checks in a logged-in session that a role can be started and that the local
  instructions load.

Decided by the builder:

- One list of checks, in `docs/development.md`, with a new section Setup. `AGENTS.md` points to it
  instead of listing the checks as Design says.
- The opening section of `workflow.md` stays first, as Design says, with a short explanation of
  the terms instead of moving it behind Roles.
- The bullet on the exclusivity constraint in `optimisation.md` is renamed, because the
  constraint uses the real limits and the bound stays weak all the same.
- "Browser behaviour is checked by hand" and "the fresh context without the builder's reasoning"
  in Design are superseded by the wording in `workflow.md` and `testing.md`.

### After review round 2

- `docs/workflow.md` has a heading "What agents decide". The database fix stands apart from the
  ordinary examples, with its reason and its end: the author approved it knowingly at the commit
  approval, as its own commit. This statement was given to the builder by the orchestrator.
- Some cells of rounds 1 and 2 are reworded in general terms by the builder, keeping each finding's
  meaning. This is a deliberate exception to the rule that only the reviewer edits a round, decided
  by the user's choice of neutral wording, 2026-11-03.
- `docs/development.md`: the paragraph on tests is one sentence linking to `testing.md`, as the
  finding suggests; the suggested relative path was adjusted to the file's location.

## Handoff

- Branch: `feature-wp3-docs-and-workflow`
- Base: `develop` at `88f9fb5`
- Diff to review: `git diff develop` plus the untracked files from
  `git ls-files -o --exclude-standard`. Nothing is staged or committed.
- Ready for review: 2026-11-03. Updated after review rounds 1 and 2: 2026-11-03.

Checks after the round 2 fixes:

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 86 files |
| `uv run pyright` | passed, 0 errors |
| `uv lock --check` | passed |
| `docker compose up -d db`, then `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` | passed, 126 tests, none skipped |
| `uv run pre-commit run --all-files` | passed |
| `uv run pre-commit run --files` on modified and untracked files | passed |
| `git diff develop --stat` on `battery_dispatch/`, `tests/`, `.github/`, container files | empty |
| After round 1, not repeated since Setup and Checks did not change: fresh clone in a scratch directory with another directory name, working tree changes applied and staged there, no local files, setup from `development.md`, its own compose project | every check from `development.md` passed, 126 tests, none skipped; `docker compose down -v` removed its volume, the volume of this checkout is untouched |
| Relative links and anchors, throwaway script outside the repository | all resolve |
| Test names in `docs/testing.md` against `tests/` | all exist |
| Class and function names in `architecture.md`, `optimisation.md` against the code | all exist |
| Em and en dashes, CRLF, trailing whitespace, plan numbers outside `docs/plans/` and the `workflow.md` table | none |
| `git check-ignore` on the local instruction files and `.claude/settings.local.json` | all ignored |
| `git check-ignore AGENTS.md CLAUDE.md .claude/agents/reviewer.md` | none ignored, exit code 1 |
| Scan for personal references and local paths, command corrected and tested against a throwaway file with a local path in both spellings | no hits in modified, untracked and tracked files |
| Extra scan for user names | author's name in `LICENSE` and `pyproject.toml` (allowed); the word "scratchpad" in the WP2 plan, generic |
| Mermaid diagram, not changed since round 1 | parsed and rendered with Mermaid 11.4.1 in a browser; a broken diagram was rejected as a control |
| `.claude/agents/` with Claude Code 2.1.197 | `builder`, `planner`, `reviewer` listed in the session's `init` message; a probe outside the repository showed that files without `description` or without frontmatter are not listed |

Facts compared with the code: limits, defaults, status codes, the table definition, startup
order, the error mapping, and the examples in `workflow.md` against the plans of WP1 and WP2.
Runtimes are not repeated except the one in `problem.md`, which matches ADR 0003.

Attention points for the reviewer:

- Starting a role was not possible here: the CLI answers "Not logged in", so neither a role run nor
  the loading of the local instructions is confirmed. The user checks both, see finding 17 of
  round 1.
- The README paragraph and the author's role in `workflow.md` are the user's wording and decision.
  Please check them against the plans, not for style.

## Review

### Round 1

- Reviewer: Claude Code, sub-agent in a fresh context, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-03
- Inputs: first, for the cold read, `README.md`, `docs/README.md`, `problem.md`, `architecture.md`,
  `optimisation.md`, `testing.md`, `workflow.md`, `api.md`, `ui.md`, `development.md`, before any
  code or this plan. Then this plan in full, `AGENTS.md`, `CLAUDE.md`, the local instructions,
  not tracked, `.claude/agents/*`, `docs/plans/README.md`, `TEMPLATE.md`, ADR 0003, the WP1 plan
  from Design on and the WP2 plan from Assumptions on, including all their review rounds; all of
  `tests/`, `battery_dispatch/` except the vendored files (`app.js` only for its API calls), CI
  workflows, pre-commit configuration and container files. Diff: `git diff develop` (base `develop`
  at `88f9fb5`, which is also `HEAD`; nothing staged or committed) plus the 10 untracked files from
  `git ls-files -o --exclude-standard`, read in full.
- Checks performed:

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 86 files already formatted |
| `uv run pyright` | passed, 0 errors, 0 warnings |
| `uv lock --check` | passed |
| `docker compose up -d db`, then `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest`, then `docker compose stop db` | passed, 126 tests, none skipped, 14.7 s |
| `uv run pre-commit run --all-files` | passed |
| `uv run pre-commit run --files` on all modified and untracked files | passed; Python hooks skipped, no Python file in the set |
| Fingerprint of diff, untracked files and local files before and after the hooks | identical |
| `git diff develop --stat` on `battery_dispatch/`, `tests/`, `.github/`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `pyproject.toml`, `uv.lock` | empty, and no untracked file there. Whole diff: 8 files, 84 insertions, 57 deletions |
| Relative Markdown links and heading anchors, throwaway script outside the repository | 77 links in 23 files, none broken |
| Test names in `docs/testing.md` against `tests/` | all 41 exist |
| Identifiers in backticks in `architecture.md`, `optimisation.md`, `testing.md` against the code | all exist; only the model symbol `p_t` and the workflow file name `tests.yml` have no match, as expected |
| The scan for personal references and local paths over every file that would be committed | no hits; positive control: hits. The path pattern was repeated as a byte-level scan, since backslash quoting proved unreliable in this shell: no hits in the tree |
| The same scan over the history of all branches | no hits; a local scratch path is in one commit, see finding 16 |
| Secrets pattern over diff and untracked files, and over the history | only field names, documentation and the example values `change-me` and `hunter2` |
| `git check-ignore` on the two local instruction files and `.claude/settings.local.json` | all three ignored |
| `git check-ignore` on `AGENTS.md`, `CLAUDE.md`, `.claude/agents/*` | none ignored, exit code 1 |
| `uv build --sdist` into a scratch directory | contains `AGENTS.md`, `CLAUDE.md` and the role files; no local file, no `.env`, no `config/config.yaml` |
| Screenshot metadata, em and en dashes in changed files, plan numbers outside `docs/plans/` | no text chunks in the PNG; no dashes; plan numbers only in the `workflow.md` table |
| Attribution lines: all commit messages, the bodies of all 6 pull requests | none |
| Worked example of `optimisation.md`, run through the real `optimize` | 100 kW, 0 kW, 72.5 kWh, then 0 kW, 81 kW, 50 kWh, revenue 2.025 EUR, as stated |
| Clone without local files: `docker compose config` without `.env`; integration tests with an empty database password | compose stops with "POSTGRES_PASSWORD is missing a value"; tests error at setup, see finding 7 |
| Starting a role: `claude -p --agent reviewer`, CLI 2.1.197 | "Not logged in", see finding 17 |
| Mermaid diagram | read, 12 nodes as stated; not rendered again |

Cold read, answered from the documents alone and then compared with the code:

1. Optimisation request: `DispatchRequest` validates (422), the route calls `DispatchPlanner.plan`,
   which loads prices through `PriceRepository.list_range` and compares them with every expected
   quarter hour (`PricesIncompleteError`, 409). `optimize` then runs in a worker thread, starts CBC
   as a subprocess with time limit and gap, and raises `OptimizationError` (500) unless the solution
   status is optimal. Values below 1e-6 become zero, key figures come from the cleaned schedule, the
   route builds the response. Correct in every step; this was the easiest of the four.
2. Model: `c_t`, `d_t`, `e_t`, binary `u_t`; bounds, balance, exclusivity, final energy; revenue minus
   degradation cost. A solution always exists because doing nothing is feasible (the API enforces
   `soc_min <= soc_initial <= soc_max`) and all variables are bounded. Correct. What can still fail
   is the proof within the time limit. When that happens is only in `problem.md` and ADR 0003.
3. Tests: `testing.md` answers this directly. Correct, apart from one row that claims more than the
   test shows (finding 4). Not covered: browser, the whole chain, SMARD itself, the container,
   runtimes on real prices, a second solver.
4. Agents and author: agents plan, build, review; the author decides scope, architecture, approvals
   and trade-offs, and agents only propose and report. This answer turned out partly wrong against the
   plans (finding 1). I also took "by hand" to mean a person, which the plans do not show (finding 2).
   I had to guess who wrote the scaffold and the price import (finding 10).

The reader path through `docs/README.md` works, and nothing was too long. Small friction: the term
Orchestrator before its definition, and `development.md` repeating the database notes of
`testing.md`. The file `optimisation.md` and the package `optimization/` differ in spelling, but
this confused nothing.

Result of the seven checks:

1. Plan conformance: all steps done, nothing outside the scope changed. R1 to R4 and R6 to R8 are
   met. R5 is not fully met because of finding 1. The README paragraph matches the plan word for
   word.
2. Correctness: limits, defaults, status codes, the table, migrations, startup and shutdown, import
   and optimisation flow, error mapping, CI, the three findings and three decision examples in
   `workflow.md`, the review results in `plans/README.md` and the mutation checks in `testing.md`
   all match the code and the WP1 and WP2 plans. Exceptions are in the table below.
3. Architecture: no code change; the ADRs are untouched.
4. Security: no secrets and no personal references in anything that would be committed. The role files
   and `AGENTS.md` are neutral. For the plan's own wording see finding 9.
5. Tests: no behaviour changed, so none are needed.
6. Checks: all pass, see above.
7. Documentation: the plan is current except for the unrecorded additions in findings 1 and 15.

Role files: all three hold only `name` and `description` and point to the matching section of
`workflow.md`. They reference and do not redefine; the reviewer file states the fresh context, as the
plan asks. The builder's recorded deviations are all justified. Wording the scan in general terms
was necessary for R7, and the others are small and correct. The Handoff figures (126 tests, 86 files,
41 test names, the ignore results) were reproduced.

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | major | `docs/workflow.md:18` | "The author decides scope, architecture, approvals and trade-offs. Agents propose options and report results." is contradicted by the plans it links to. WP2 records "Decided by the orchestrator" (`wp2-schedule-visualisation.md:258`), including a fix that widens the scope against the non-scope of that plan (`:260`), and a behaviour added by the orchestrator: the page runs on load and takes query parameters (`:196`). The builder of WP1 settled open details itself, such as `revenue_eur` without degradation cost (`wp1-dispatch-optimization.md:258`). The role table (`workflow.md:52`) also gives the orchestrator no deciding role, and the rule at `workflow.md:79` says a role reports instead of widening the scope. A reader who follows the link finds the contradiction, in the statement that R5 is about. The second sentence is not in the approved plan or the Implementation notes, so the user's confirmation under Assumptions does not cover it. Overstated in the direction of author control. | State what happened, for example: agents also decide details within an approved plan and record them there; in WP2 the orchestrator took a fix into the work package that its non-scope excluded; the author accepts or rejects such decisions when approving the commit. Align the orchestrator row. The user confirms the wording. | Fixed, wording decided by the user. `workflow.md` states the author's role as in the new README paragraph, that the orchestrator and builder take smaller decisions within an approved plan and record them, with the examples of the page computing on load and the database fix beyond the non-scope (WP2) and `revenue_eur` (WP1). "Agents propose options and report results" removed; orchestrator row aligned. |
| 2 | minor | `docs/workflow.md:40` | "Browser behaviour is checked by hand", and `docs/testing.md:66` "were checked by hand", in a document about who did what, read as a person. The plans record agents driving a browser: a scratch script with headless Edge and real mouse events (`wp2-schedule-visualisation.md:289`), the orchestrator in the built-in browser (`:372`), the reviewer (`:467`). The Handoff lists the check in a normal browser by hand as not done by the builder (`:368`), and no plan records it later. | Say "one-off, not automated" and name who ran it, for example "by agents driving a browser, not by an automated test". If the author also checked by hand, say so separately. | Fixed. `workflow.md` and `testing.md` say one-off runs by agents driving a browser, not automated. The whole-chain requests and the mutation checks no longer say "by hand" either. |
| 3 | minor | `docs/workflow.md:38` | "a fresh context without the builder's reasoning" overstates the independence. Reviewers read the plan including Implementation notes and Handoff (`wp1-dispatch-optimization.md:433`, `wp2-schedule-visualisation.md:393`), which hold the builder's written reasoning. What they lack is the builder's session. The same wording is at `workflow.md:61` and in `.claude/agents/reviewer.md`. | "without the builder's session; the reviewer does read the builder's written notes." | Fixed. "Without the builder's session" and that the reviewer reads the written notes, in `workflow.md` (Limits, Roles) and `.claude/agents/reviewer.md`. |
| 4 | minor | `docs/testing.md:46` | The row claims days with 92 or 100 quarter hours. `test_daylight_saving_day` uses 100 steps and `test_optimize_accepts_calendar_month_with_daylight_saving_change` the October span; no test in `tests/` uses a day of 92 quarter hours. The check of 2026-03-29 in WP2 was a one-off in Node. Likewise `docs/testing.md:56` names logs as the risk, while `test_password_is_not_shown_in_repr` checks `repr(config)` only. | Write "Days with 100 quarter hours" and add the 92 case to the uncovered list or add a test in a later package. Word the second row as "shows up in the `repr` of the configuration". | Fixed. The row says 100 quarter hours, days with 92 are listed as not covered; the password row names the `repr` of the configuration. |
| 5 | minor | `docs/problem.md:85` | "it does happen ... a week or more at -500 EUR/MWh" disagrees with ADR 0003, where about one week at -500 took 27 s, inside the limit, and two weeks stopped at the limit. Same figures in WP1 round 2 finding 1 (672 steps 27.3 s, 1,344 steps failed). The line predates this package, but the file is in scope and R8 asks for outdated statements to go. | "for example two weeks at -500 EUR/MWh; one week takes about 27 s". | Fixed. `problem.md` says two weeks at -500 EUR/MWh or a month at -0.01 EUR/MWh, and about 27 s for one week, as in ADR 0003. |
| 6 | minor | `docs/architecture.md:55` | "the application also starts while the database is down" holds for `battery-dispatch` itself, not for the container. `Dockerfile:27` runs `alembic upgrade head && battery-dispatch`, and `migrations/env.py` connects, so with an unreachable database the application process never starts in the container. The next paragraph mentions Alembic but does not connect the two. The real behaviour in compose is that a database going down later does not stop a running API. | Add: "In the container the migrations run first, so there the database must be reachable at start; a later outage does not stop the application." | Fixed. `architecture.md`: in the container the migrations run first, so the database must be reachable at start; a later outage does not stop the application. |
| 7 | minor | `AGENTS.md:27` | The check list is meant to run from a clone (Objective), but it fails there. `docker compose up -d db` stops without `.env` ("POSTGRES_PASSWORD is missing a value"), and with `.env` but no `config/config.yaml` the integration tests error at setup, reproduced with an empty password. It works on this machine because both local files exist. `docs/testing.md:21` has the same gap; `development.md` mentions the password further down. | Add one line before the block: `cp .env.example .env`, `cp config/config.yaml.example config/config.yaml`, or pass the password as `BATTERY_DISPATCH_DATABASE__PASSWORD`. Mention it in `testing.md`. | Fixed. `development.md` has a section Setup with `cp .env.example .env` and `cp config/config.yaml.example config/config.yaml`; `AGENTS.md` and `testing.md` link to it. Verified from a fresh clone, see Handoff. |
| 8 | minor | `docs/workflow.md:98` | Builder and reviewer (`:112`) are told to run "all checks from development.md", which lists `ruff check`, `pyright` and `pytest`. `AGENTS.md:22` lists seven commands, including `ruff format --check`, `uv lock --check` and pre-commit, and the plans ran that longer list. Following `workflow.md` from a clone runs fewer checks than the plans record. | Keep one list and point to it from the other place, for example the full list in `development.md`. | Fixed. One list of checks under Checks in `development.md`, the place `workflow.md` names; `AGENTS.md` points to it. |
| 9 | minor | `docs/plans/wp3-docs-and-workflow.md:209` | This plan refers to local instructions in more detail than a reader needs, and holds a note of no use to a reader. No private fact is disclosed and the scan finds nothing, so R7 holds. The `.gitignore` entries are unavoidable. | Word it generally and drop the note. The user decides how much of this stays. | Fixed, decided by the user. This plan refers to local instructions, not tracked, in general terms. |
| 10 | note | `docs/workflow.md:14` | "came before this process" leaves open who wrote the scaffold and the price import, while the README says the project as a whole was built with agents. The repository does not answer this; a reader has to guess. | One clause stating who wrote them, confirmed by the user. | Fixed, wording decided by the user. `workflow.md`: agents also wrote the scaffold and the price import, before this process existed; the author decided on their merge. |
| 11 | note | `docs/workflow.md:32` | The table uses Orchestrator and WP numbers before the Roles section defines the first and without saying what the second means. | Move "How this project was built" after Roles, or add a short gloss. | Fixed. A short explanation of work package and of the Roles section before the table; the section stays first, as Design says. |
| 12 | note | `docs/architecture.md:44` | "No other package imports `communication/http/`": `battery_dispatch/main.py:5` does. The intent is clear from line 51, but the sentence is not exact. | "Apart from `main`, nothing imports ...". | Fixed. "Apart from `main`, nothing imports `communication/http/`". |
| 13 | note | `docs/optimisation.md:68` | "The exclusivity constraint is tight" is true of the constant, but the relaxation stays weak: at `u_t = 0.5` a step may still charge and discharge at half power. That is why long negative runs are hard to prove, which WP1 round 1 finding 1 and ADR 0003 state. Under the heading "Why it is well posed", a reader may conclude the opposite, and this section gives no hint of when the time limit is reached. | Add one sentence with the link to the residual case in ADR 0003. | Fixed. The bullet is renamed and says that the bound stays weak at fractions of `u_t`, with a link to the consequences in ADR 0003. |
| 14 | note | `docs/problem.md:82` | The edit left a line of 146 characters here, and `docs/architecture.md:101` has one of 102; prose in these files wraps at 100 or less. In `architecture.md:101`, "these two endpoints" also spans the previous section. | Rewrap; name the endpoints. | Fixed. Both lines rewrapped; `architecture.md` names the endpoints. The long lines left in `workflow.md` are table rows. |
| 15 | note | `docs/optimisation.md:54` | The worked example and the paragraph "Key figures" (`:102`) are in neither the plan's section list nor the Implementation notes, although the builder records every deviation. Both are correct and useful. | Add them to the Implementation notes. | Fixed. Both are in the Implementation notes. |
| 16 | note | `docs/plans/wp3-docs-and-workflow.md:278` | As the Handoff says, a local scratch path remains in the history of `develop`, in one line of commit `7dbb8ea`. It holds nothing else personal and no credential. Rewriting history is out of scope, so R8 holds for the tree only. | User decision, outside this package. | Not fixed, decided by the user: harmless, not worth rewriting history. |
| 17 | note | `.claude/agents/reviewer.md:1` | The Handoff asks for a role to be run and for the loading of the local instructions to be confirmed in a logged-in session. This was not possible here either: the CLI answers "Not logged in", and `claude agents --json` prints an empty list, which proves nothing either way. `workflow.md:9` ("makes the roles available") therefore rests on the listing in the Handoff. | The user starts one role and checks `/memory` in a logged-in session before committing. | Partly confirmed on 2026-11-04: a restarted logged-in session loaded the local instructions and offered the planner, builder and reviewer roles. A role has not yet been run from start to finish. |

Verdict: changes required

### Round 2

- Reviewer: Claude Code, sub-agent in a fresh context, model Claude Opus 5.5 (`claude-opus-5-5`), 2026-11-03
- Inputs: this plan in full including Implementation notes, Handoff and round 1 with its Resolution
  column; `AGENTS.md`, `CLAUDE.md`, the local instructions, not tracked, `docs/workflow.md`,
  `README.md`, `docs/README.md`, `architecture.md`, `optimisation.md`, `testing.md`, `problem.md`,
  `development.md`, `plans/README.md`, `TEMPLATE.md`, ADR 0003, `.claude/agents/*`; the WP1 and WP2
  plans at the places `workflow.md` relies on; `tests/storage/conftest.py`, the configuration
  examples, CI workflows and container files. Diff: `git diff develop` (base `develop` at `88f9fb5`,
  which is also `HEAD`; nothing staged or committed) plus the 10 untracked files from
  `git ls-files -o --exclude-standard`.
- Checks performed:

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 86 files already formatted |
| `uv run pyright` | passed, 0 errors, 0 warnings |
| `uv lock --check` | passed |
| `docker compose up -d db`, then `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest`, then `docker compose stop db` | passed, 126 tests, none skipped, 10.6 s |
| `uv run pre-commit run --all-files` | passed |
| `uv run pre-commit run --files` on all modified and untracked files | passed; YAML, TOML and Python hooks skipped, no such file in the set |
| Fingerprint of diff, untracked files and local files before and after the hooks | identical |
| `git diff develop --stat` on `battery_dispatch/`, `tests/`, `.github/`, `config/`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `alembic.ini`, `pyproject.toml`, `uv.lock` | empty, and no untracked file there. Whole diff: 8 files, 124 insertions, 69 deletions |
| Relative Markdown links and heading anchors, throwaway script outside the repository | 84 links in 23 files, none broken |
| Setup and Checks of `development.md`, followed in order in a throwaway clone with the working tree changes staged, no local files, its own compose project and a new volume | every check passed, 126 tests, none skipped, also with pytest started right after `docker compose up -d db`; `docker compose down -v` removed only that volume |
| `BATTERY_DISPATCH_DATABASE__PASSWORD` without `config.yaml`, `ConfigManager` on a scratch copy of the defaults | password set; without the variable it stays empty, as `development.md` implies |
| Scan for personal references and local paths, over every file that would be committed, before and after adding this round | no hits, exit code 123 |
| The same scan on a throwaway file outside the repository with a local path in both spellings and one clean line | both spellings found, clean line not, exit code 0 |
| Extra scan for user names, temporary paths and mail addresses | only the author's name and address in `LICENSE` and `pyproject.toml`, allowed |
| `git check-ignore` on the two local instruction files and `.claude/settings.local.json` | all three ignored |
| `git check-ignore` on `AGENTS.md`, `CLAUDE.md`, `.claude/agents/*` | none ignored, exit code 1 |
| Em and en dashes in all Markdown files that would be committed; plan numbers outside `docs/plans/` | no dashes; plan numbers only in `workflow.md` |
| Starting a role, loading of the local instructions | not repeated, still open as in finding 17 of round 1 |
| Mermaid diagram | read, not rendered |

Round 1 findings against their Resolution:

- Findings 1 to 8 and 10 to 15: the fix is in the tree as the Resolution says, and matches the user
  decisions in Implementation notes. Details below where they touch the focus of this round.
- Finding 9: fixed for the sections the builder owns, with one leftover, and the review rounds still
  carry the matter, see findings 2 and 3 below.
- Findings 16 and 17: not fixed, as recorded. Finding 17 stays a step for the user before committing.

How the project was built:

- `workflow.md` agrees with the README paragraph: same statement of the author's role, and "agents
  did the planning, implementation and review" fits "agents write the code, tests and documents".
  The scaffold and the price import predate the workflow in the history (`0474d19` comes after
  `c0f093c`), as `workflow.md` and `plans/README.md` say.
- The three decisions of the author are recorded as "Decided by the user" in
  `wp1-dispatch-optimization.md:280` to `:291`. The page computing on load is
  `wp2-schedule-visualisation.md:196`, the database fix `:258`, `revenue_eur`
  `wp1-dispatch-optimization.md:260`. All three are under Implementation notes, as the text says.
  The table of findings matches both plans.
- `wp2-schedule-visualisation.md:446` calls the patch the orchestrator's. The Handoff there describes
  it as a split of the changes into two commits, so this does not contradict "Writes code: No".
- The tension between the opening section and the rule under Rules: the text is honest. It names the
  exception, and it reads the plan more strictly than the plan's own reviewer did, who saw no conflict
  with the non-scope (`wp2-schedule-visualisation.md:428`). It is not yet clear, see finding 1.

New text against the code: `development.md` Setup and Checks, the password and example values, the
fixture behaviour in `testing.md`, the days with 92 quarter hours (no such day in `tests/`, one-off
in review at `wp2-schedule-visualisation.md:415`), the container start in `architecture.md`
(`Dockerfile:27`), `main` as the only importer of `communication/http/`, the runtimes in
`problem.md` (ADR 0003) and the weak bound in `optimisation.md` (ADR 0003, WP1 round 1 finding 1) all
hold. There is one list of checks: `AGENTS.md`, `workflow.md`, `testing.md` and `TEMPLATE.md` point
to `development.md`, and no other document lists the commands.

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | minor | `docs/workflow.md:33` | The database fix stands in a list introduced by "Within an approved plan, the orchestrator and the builder take smaller decisions" (`:29`), and the bullet itself says it went beyond the plan and the rule. So the example contradicts its lead-in, under the heading "What the author decides" (`:19`). The reader also does not learn how the exception ended, or why it was taken: `:91` still says a role stops and reports, while `wp2-schedule-visualisation.md:258` records that the fix restores the documented 503 and that R6 needs it, kept apart as its own commit (`85041f1`). "Beyond the plan's non-scope" is also an odd phrase for a first reader; the plan's words are "no change to the existing API contracts" (`wp2-schedule-visualisation.md:261`). | Give the two ordinary examples their own short heading, and set the exception apart, for example: "One decision went further: in WP2 the orchestrator took the fix for an unreachable database into the work package, although the plan excluded changes to API contracts and the rule under Rules asks a role to stop and report. The fix restored the documented 503. It is recorded in the plan and was merged as its own commit." If the user approved that commit knowingly, add it; the repository shows only the commit and the merge. The user confirms the wording. | Fixed, statement on the approval as given by the orchestrator. `workflow.md` has a heading "What agents decide" with the two ordinary examples. The database fix stands apart as "One decision went further", with its reason and how it ended: the author approved it knowingly at the commit approval, as its own commit `85041f1`. |
| 2 | note | `docs/plans/wp3-docs-and-workflow.md:210` | Leftover from the rewording: the bullet at `:210` and `:211` points at something the plan no longer names and is more specific than the user decision at `:241` asks for. | Reduce the bullet to "R7, Verification and the writing rules are worded more generally than in the approved plan." | Fixed. The bullet is reduced as suggested. |
| 3 | minor | `docs/plans/wp3-docs-and-workflow.md:400` | The Resolution of finding 9 and the user decision at `:241` say this plan refers to local instructions in general terms. Some cells of round 1 are more specific (`:330`, `:386`, `:400`, `:408`). No private fact is disclosed and the scan is clean, so R7 holds. Nobody may change these cells under the section ownership in `TEMPLATE.md`. | User decision: accept them as the record, or have these cells reworded in general terms and record that in Implementation notes as an exception to the ownership rule. | Fixed, decided by the user. The cited cells of round 1 and the matching cells of this round are reworded in general terms, keeping each finding's meaning. Recorded in Implementation notes as an exception to the ownership rule. |
| 4 | note | `docs/plans/README.md:14` | Still says "round 2 pending". The builder updates it after this round, as announced. | Enter the result of this round. | Fixed. `plans/README.md` holds the result of this round. |
| 5 | note | `docs/development.md:37` | "Start it with `docker compose up -d db`" follows directly on a block that contains this command. The rest of the paragraph repeats `testing.md:25` to `:30`, as round 1 already remarked in its reader notes. | Replace `:37` to `:40` with one sentence linking to [testing.md](../testing.md#markers-and-the-database). | Fixed. One sentence linking to `testing.md#markers-and-the-database`, path relative to `docs/`. |
| 6 | note | `docs/workflow.md:16` | Two small wording points. "The user's approval. The user is the author." introduces a second term in passing, in a section otherwise written about the author. In `:57`, "This section" sits in a two-line subsection and means its parent. | "went through the author's approval", and move the gloss to `:69`: "The user, here the author, approves ...". In `:57`, write "The section above and the README". | Fixed. "The author's approval" in the opening, "The user, here the author, approves" under Roles, "The section above and the README" under Attribution. |

Verdict: approve with minor findings
