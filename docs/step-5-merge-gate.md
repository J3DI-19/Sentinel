# Step 5 - Enforced integration merge gate (TV5-14)

This document covers the two halves of the merge gate: the **workflow**
side (committed in this repo) and the **branch-ruleset** side (configured
once in GitHub by a maintainer). It ends with a verification procedure
that maps 1:1 to the acceptance criteria.

## Workflow side (done in-repo)

Two workflows produce the required checks, and **both run on every pull
request** so a required check is never left unreported:

| Workflow file | Job / check name | Runs on |
| --- | --- | --- |
| `.github/workflows/backend-tests.yml` | `pytest-clean-exit` | every PR + push to main/Aarya |
| `.github/workflows/backend-tests.yml` | `frontend-contract-and-tests` | every PR + push to main/Aarya |
| `.github/workflows/step5-integration.yml` | `backend-step5` | every PR + push to main/Aarya |
| `.github/workflows/step5-integration.yml` | `bridge-broker` | every PR + push to main/Aarya |
| `.github/workflows/step5-integration.yml` | `native-cpp` | every PR + push to main/Aarya |
| `.github/workflows/step5-integration.yml` | `esp32-compile` | every PR + push to main/Aarya |

**Why the Step 5 workflow no longer uses `pull_request.paths`.** A
required status check that is path-filtered is never reported on a PR
that touches no matching file, and a ruleset requiring it then blocks
that PR permanently ("Expected - Waiting for status to be reported").
The workflow therefore runs on all PRs, and a small `changes` job
(using `dorny/paths-filter`) decides whether Step 5 files were actually
affected:

- **Affected** -> each job runs its real work (pytest, mosquitto + mTLS
  + ACL + real bridge, native C++ tests, ESP32 compile).
- **Not affected** -> each job runs a one-line "gate passes" step and
  reports success in seconds.

Either way all four check names report on every PR, so the ruleset can
require them without deadlocking unrelated PRs, and unrelated PRs do not
pay the full (esp32-compile ~20 min) cost.

## Branch-ruleset side (configure once in GitHub)

A maintainer must do this in the GitHub UI - it cannot be committed to
the repo:

1. **Settings -> Rules -> Rulesets -> New branch ruleset.**
2. **Name:** `main protection`. **Enforcement status:** Active.
3. **Target branches:** add `main` (Include default branch). Repeat for
   `Aarya` if it is also protected.
4. **Enable these rules:**
   - Require a pull request before merging.
     - Required approvals: **1**.
     - Dismiss stale pull request approvals when new commits are pushed.
   - Require status checks to pass.
     - Require branches to be up to date before merging.
     - Add the required checks **by these exact names**:
       - `pytest-clean-exit`
       - `frontend-contract-and-tests`
       - `backend-step5`
       - `bridge-broker`
       - `native-cpp`
       - `esp32-compile`
   - Block force pushes.
   - Restrict deletions (block branch deletion).
5. **Bypass list:** leave empty, or add only explicitly approved
   maintainers for a documented emergency bypass. Do **not** exempt
   administrators by default - set the ruleset to apply to everyone
   (in classic Branch protection this is the "Do not allow bypassing
   the above settings" / "Include administrators" checkbox).

Notes:
- The exact required-check names must match the **job ids** above. If you
  rename a job, update the ruleset, or the old name will hang as
  "Expected".
- The first time a check name appears in the UI picker is after it has
  run at least once, so push the branch and let the workflows run once,
  then add the names.

## Verification procedure (maps to the acceptance criteria)

Run these on a scratch branch/PR before trusting the gate:

1. **A deliberately failing Step 5 check blocks Merge.** On a branch,
   edit `tests/step5/ack_buffer_test.cpp` to assert something false (e.g.
   change an expected value), open a PR. `native-cpp` goes red and the
   Merge button is disabled. Revert.
2. **A failing full backend test blocks Merge.** Temporarily break a
   backend test (e.g. a wrong assertion in `tests/test_phase3_api.py`),
   open a PR. `pytest-clean-exit` goes red; Merge is disabled. Revert.
3. **A PR changing unrelated files still gets all required results.**
   Change only `README.md`, open a PR. `backend-step5`, `bridge-broker`,
   `native-cpp`, `esp32-compile` each report success via the "gate
   passes" path (seconds), and `pytest-clean-exit` /
   `frontend-contract-and-tests` run normally. Merge is allowed once
   approved. This is the case the old path filter would have deadlocked.
4. **A new commit dismisses an earlier approval.** Get the PR approved,
   push one more commit; the approval is dismissed and Merge is disabled
   until re-approved. (Requires "Dismiss stale approvals".)
5. **Direct/force pushes to main are blocked.** `git push origin main`
   (non-fast-forward or direct) is rejected; `git push --force` is
   rejected. (Requires "Require a pull request before merging" + "Block
   force pushes".)
6. **The real PR is green + approved.** Confirm all six checks are green
   and at least one approval is present before merging Step 5.

## What is in-repo vs. what a maintainer must still do

- In-repo (this change): both workflows report their checks on every PR;
  the Step 5 workflow no longer deadlocks unrelated PRs; all six jobs are
  operational.
- Maintainer action (cannot be committed): creating the ruleset, adding
  the six required check names, approvals/dismissal/force-push settings,
  and the bypass list. Until that ruleset exists, GitHub does not
  actually block anything - the workflows only *report* status; the
  ruleset is what *enforces* it.
