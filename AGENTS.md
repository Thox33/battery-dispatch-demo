# AGENTS.md

Instructions for coding agents working in this repository.

## Purpose

A small demonstration of battery dispatch planning against day-ahead electricity prices. It is
not a product, so keep it small. [docs/README.md](docs/README.md) says which document answers
which question.

## How work runs

Every work package runs through planner, builder and reviewer, with a plan file under
`docs/plans/`. Read [docs/workflow.md](docs/workflow.md) before starting. The reviewer always
runs in a fresh context.

The user approves every plan, commit, push and pull request. Do not do any of these without
that approval.

## Checks

The setup and the list of checks are in [docs/development.md](docs/development.md#checks). Run
all of them and report failures as they are.

## Conventions

- Everything in the repository is in English: code, comments, configuration, documents, commit
  messages, pull requests.
- No em dashes. Sober language, no marketing terms.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- No agent attribution lines such as `Co-Authored-By` or "Generated with" in commits and pull
  requests. The README and `docs/workflow.md` state how agents were used.
- Plan numbers and process terms stay out of code, comments and product documentation.
- The README stays short; details go under `docs/`. Decisions go into short ADRs under
  `docs/decisions/`.
- Facts in documents are checked against the code.

## Original work

Everything here is written new. Do not copy code, configuration, schemas or parameters from
other projects. Third-party code comes in only as a declared dependency, or vendored with its
licence.
