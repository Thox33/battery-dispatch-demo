# Workflow

Work is planned, built and reviewed in separate roles. Each role can be carried out by a
coding agent (for example Claude Code) or by a person, using only the files in this
repository and ordinary Git.

## Roles

| Role | Writes code | Output |
| --- | --- | --- |
| Orchestrator | No | Starts the other roles, keeps the plan status current, reports to the user |
| Planner | No | A plan file in [`plans/`](plans/README.md) with status `draft` |
| Builder | Yes | Changes on the feature branch, checked-off steps, implementation notes, handoff |
| Reviewer | No | One review round in the plan file: findings and verdict |

The user approves every plan, commit, push and pull request. The orchestrator is usually
the main agent session; planner and builder may run in that session or as sub-agents.

The reviewer always runs in a fresh context (a new session or an isolated sub-agent) that
has not seen the builder's reasoning. It works only from the repository, the plan file and
the diff.

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
