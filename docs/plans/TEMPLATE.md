# WP<n>: <title>

<!--
Section ownership (see ../workflow.md):
- Planner: header, Objective to Assumptions; leaves Steps unchecked.
- Builder: checks off Steps, writes Implementation notes and Handoff, fills the
  Resolution column of review findings.
- Reviewer: writes one Review round per review; never edits other sections.
Remove this comment and all <placeholders> when filling in the plan.
-->

- Status: draft | approved | in progress | review | done
- Branch: `feature-wp<n>-<short-name>`
- Sources: <ADRs, docs, external references>

## Objective

<What this work package achieves, in two or three sentences.>

## Requirements

| ID | Requirement | Covered by |
| --- | --- | --- |
| R1 | <one line> | <step or test> |

## Scope

- <in scope>

## Non-scope

- <explicitly out of scope>

## Design

<Model, interfaces, data flow; only what the builder needs to implement without guessing.>

## Changes

| Path | Change |
| --- | --- |
| `<path>` | <create / modify / delete: what and why> |

## Steps

- [ ] <ordered, verifiable step>

## Verification

- <checks from development.md>
- <focused tests added or changed>

## Assumptions, open questions, and risks

- <assumption>

## Implementation notes

- <Builder: each deviation from the plan and its reason; "None" if there is none.>

## Handoff

- Branch: `<feature branch>`
- Base: `<base branch>` at `<commit SHA>`
- Diff to review: `<for example: git diff develop...HEAD>`
- Ready for review: <date>

| Check | Result |
| --- | --- |
| `<command>` | <passed / failed: short summary> |

Attention points for the reviewer:

- <areas of uncertainty, or "None">

## Review

### Round 1

- Reviewer: <tool or person, model if applicable>, <date>
- Inputs: <plan, diff range, sources consulted>
- Checks performed: <re-run commands and their results>

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | <blocker / major / minor / note> | `<path:line>` | <concrete failure scenario> | <fix or "-"> | <Builder: fixed / not fixed, with reason> |

Verdict: <approve / approve with minor findings / changes required>
