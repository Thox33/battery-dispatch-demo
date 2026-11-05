# Workflow

This document answers how the project was built: what agents did, what the author decided,
and how the work moves from plan to review.

Work is planned, built and reviewed in separate roles. Each role can be carried out by a
coding agent (for example Claude Code) or by a person, using only the files in this
repository and ordinary Git. [AGENTS.md](../AGENTS.md) holds the rules for agents, and
[.claude/agents/](../.claude/agents/) makes the roles available in Claude Code.

## How this project was built

AI coding agents did the planning, implementation and review, each in a role described under
[Roles](#roles). They also wrote the scaffold and the price import, before this process existed;
the author decided on their merge. Since the first work package, plans, commits, pushes and pull
requests went through the author's approval. A work package (WP) is one numbered plan under
[`plans/`](plans/README.md).

### What the author decides

The author sets goals and scope, reviews and approves the design and every plan, and decides
what is merged. Examples, with the reasoning in the plans:

- A relative solver gap of 0.5 % instead of changing the solver, after a review showed that
  valid requests ran into the time limit.
- A request limit of 31 days and 1 hour, so that every calendar month in Europe/Berlin fits.
- The bounds on battery parameters that the API accepts.

### What agents decide

Within an approved plan, the orchestrator and the builder take smaller decisions and record them
in the plan's Implementation notes. Examples:

- In WP2 the orchestrator had the page compute a schedule on load.
- In WP1 the builder decided that `revenue_eur` does not include the degradation cost.

One decision went further: in WP2 the orchestrator took the fix for an unreachable database into
the work package, although the plan excluded changes to API contracts and the rule under
[Rules](#rules) asks a role to stop and report. The fix restored the documented 503, and the page
needed it to show its error message. The decision is recorded in the plan. The author approved it
knowingly at the commit approval, as its own commit `85041f1`.

### What the process found

| Work package | Finding | Found by |
| --- | --- | --- |
| WP1 | Valid requests on real prices hit the 30 s solver limit and answered 500 | Reviewer, round 1 |
| WP2 | Drag zoom snapped back although the docs claimed it worked | Reviewer, round 1 |
| WP2 | Unreachable database answered 500 instead of the documented 503 | Orchestrator's browser check; root cause confirmed by the reviewer |

All three were fixed before merging. The full rounds are in the [plans](plans/README.md).

### Limits

- Independence means a fresh context without the builder's session, not a different model or
  vendor. The reviewer does read the builder's written notes. Builder and reviewer can share the
  same blind spots.
- Browser behaviour has no automated test. Agents checked it in one-off runs, driving a browser.
- The author remains responsible for the result.

### Attribution

Commits and pull requests carry no agent attribution lines. The section above and the README
are the disclosure.

## Roles

| Role | Writes code | Output |
| --- | --- | --- |
| Orchestrator | No | Starts the other roles, keeps the plan status current, takes smaller decisions within an approved plan and records them there, reports to the user |
| Planner | No | A plan file in [`plans/`](plans/README.md) with status `draft` |
| Builder | Yes | Changes on the feature branch, checked-off steps, implementation notes, handoff |
| Reviewer | No | One review round in the plan file: findings and verdict |

The user, here the author, approves every plan, commit, push and pull request. The
orchestrator is usually the main agent session; planner and builder may run in that session or
as sub-agents.

The reviewer always runs in a fresh context (a new session or an isolated sub-agent) without
the builder's session. It works only from the repository, the plan file including the
builder's written notes, and the diff.

## Flow

```text
work package
  -> Planner drafts plan               -> user approves plan
  -> Builder implements and verifies   -> Reviewer reviews diff against plan
  -> Builder fixes actionable findings (repeat only for actionable defects)
  -> user approves commit, push and pull request
```

## Rules

- State lives in files: the plan file and the Git diff. No role relies on another role's
  conversation.
- Every role starts by reading the plan file and the documents it references.
- A role that finds the plan wrong or incomplete stops and reports instead of widening the
  scope.
- Plan numbers and process terms stay out of code, comments and product documentation.
  Planning history belongs in the plan files.

## Planner

- Fills header, Objective, Requirements, Scope, Non-scope, Design, Changes, Steps
  (unchecked), Verification, and Assumptions, open questions, and risks.
- Leaves Implementation notes, Handoff and Review empty.
- Keeps each plan small enough to review in one sitting.
- Does not start implementation.

## Builder

- Starts only on a plan with status `approved`; sets it to `in progress`.
- Works on the branch named in the plan, limited to the plan's scope.
- Checks off steps, records every deviation in Implementation notes ("None" if there is
  none).
- Runs all checks from [development.md](development.md) and reports failures as they are.
- Completes the Handoff (branch, base commit, diff range, check results, attention points)
  and sets the status to `review`.
- After review: fixes actionable findings, fills the Resolution column, re-runs the checks.

## Reviewer

Checks the result against the plan:

1. Plan conformance: every step done, nothing outside the scope changed.
2. Correctness: logic errors, unhandled error paths, resource leaks, concurrency.
3. Architecture: package boundaries and the accepted [decisions](decisions/).
4. Security: secrets, input validation.
5. Tests: changed behaviour is covered, including failure cases.
6. Checks: re-runs the checks from [development.md](development.md).
7. Documentation: affected docs and the plan are up to date.

Writes one new `Round <n>` under Review and changes nothing else. Severities: `blocker`
(wrong, insecure or against an accepted decision), `major` (likely defect or significant
gap), `minor`, `note`. Any blocker or major finding means `changes required`; otherwise
`approve` or `approve with minor findings`. Only findings that can be substantiated are
reported; an empty table with `approve` is a valid result.

## Status

| From | To | Set by |
| --- | --- | --- |
| - | `draft` | Planner |
| `draft` | `approved` | User (recorded by any role) |
| `approved` | `in progress` | Builder |
| `in progress` | `review` | Builder, after the Handoff is complete |
| `review` | `in progress` | Builder, when the verdict is `changes required` |
| `review` | `done` | Builder, after the user approved and the change is merged |
