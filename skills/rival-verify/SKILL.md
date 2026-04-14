---
name: rival-verify
description: Adversarial code verification with Codex CLI or Claude skeptical-reviewer fallback.
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Verify v1.0 — Adversarial Code Verification Orchestrator

You are the Rival verification orchestrator. Your job is to get an independent adversarial review of the BUILT CODE from Codex CLI (primary) or the Claude skeptical-reviewer fallback. The plan IS the spec. You run inline in the current conversation.

## Phase 1: State Validation

### 1.1 Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured. Run `/rival:rival-init` first."

### 1.2 Resolve Workstream

Standard resolution priority (same as other skills).

### 1.3 Validate Phase

Read `state.json`. Phase must be `build-complete` or `verified` (re-verify).

- If earlier: Guide to correct next step
- If `archived`: "This workstream is already complete and archived."
- If `build-complete` or `verified`: proceed

Update state to `verifying`.

## Phase 2: Gather Verification Context

Collect everything the verifier needs. For multi-repo workstreams this is per-repo; for single-repo it's just one entry.

1. **Plan:** `.rival/workstreams/<id>/plan.md` — the single source of truth for what was supposed to be built.

2. **Branches and commits per repo:** read `state.json`. The relevant fields:
   - `state.branches` — map of `{repo-path: { name, role, default_branch }}`. Tells you which branch in which repo, and what its base is for the diff.
   - `state.build.commits` — map of `{repo-path: { first, last, count }}`. The first/last commit hashes per repo. **Do NOT grep git log for the workstream id — execute records these in state.json directly.**
   - `state.build.repos_touched` — flat array of repo paths that actually received commits. (Repos in `state.branches` with `count: 0` are pruned.)

3. **Git diff per repo:** for each repo in `state.build.repos_touched`:
```bash
REPO="<repo-path>"
DEFAULT=$(jq -r ".branches[\"$REPO\"].default_branch" .rival/workstreams/<id>/state.json)
BRANCH=$(jq -r ".branches[\"$REPO\"].name" .rival/workstreams/<id>/state.json)

# Full diff for this repo's branch vs its default
git -C "$REPO" diff "origin/$DEFAULT...$BRANCH"

# Or, equivalently, between first commit's parent and last commit:
FIRST=$(jq -r ".build.commits[\"$REPO\"].first" .rival/workstreams/<id>/state.json)
LAST=$(jq  -r ".build.commits[\"$REPO\"].last"  .rival/workstreams/<id>/state.json)
git -C "$REPO" diff "${FIRST}~1..${LAST}"
```

4. **Test results per repo:** run the test commands from the plan's Validation Plan section. In multi-repo, the plan should specify per-repo test commands (or fall back to each repo's `index.repos[*].test_framework`).

5. **Fallback if state is incomplete:** if `state.build.commits` is missing or empty (e.g., the workstream was built by an older version of execute), fall back to:
   - Try grepping recent git log for `(ws: <workstream-id>)` in commit messages — newer execute embeds this defensively in every commit
   - If still nothing, ask the user: "I can't find a recorded commit range. What range should I review? (e.g., `HEAD~5..HEAD` for single-repo, or specify per-repo)"

**Auto-suggestion for LARGE workstreams:** If the git diff exceeds 2000 lines or touches more than 20 files, warn the user:
> "This is a large workstream. Verification will take longer and may benefit from being split. Proceeding anyway."

## Phase 3: Build Verification Prompt

Assemble the verification prompt:

```markdown
You are performing adversarial code verification.

## Implementation Plan (what was supposed to be built):
$(cat .rival/workstreams/<id>/plan.md)

## Actual Code Changes:
$(git diff <first-workstream-commit>~1..HEAD)

## Test Results:
$(<test command from plan>)

## Your Task:
1. **Read the "Feature Request & Clarifications" section at the top of plan.md carefully** — this is the authoritative user intent. Verify the code actually delivers the clarified scope, not just what's literally in the tasks.
2. Read the actual source files, not just the diff
3. Verify each task was implemented correctly
4. Verify NO scope violations — nothing was added that the user marked "out of scope"
5. Verify success criteria from Clarifications section are met
6. Check for security issues not in the plan
7. Check test quality — are tests meaningful?
8. Check for regressions in existing functionality

## Output:
### Verdict: PASS | PASS WITH NOTES | NEEDS FIXES | FAIL
### Scope Adherence: (Did the implementation stay within clarified scope? Any violations?)
### Success Criteria Met: (From Clarifications section — yes/no with evidence)
### Task Verification: (for each task: verified or issue)
### Issues Found: (severity, description, file:line, suggestion)
### Security Check: PASS or CONCERNS with details
```

Write the assembled prompt to `.rival/workstreams/<id>/codex-verify-prompt.md`.

## Phase 4: Execute Verification

### Path A: Codex Available

Check if `codex` is on PATH.

```bash
codex exec "$(cat .rival/workstreams/<id>/codex-verify-prompt.md)" --full-auto -o .rival/workstreams/<id>/verification.md
```

Do NOT set a timeout. Let Codex run as long as it needs. Codex will explore the codebase, read source files, and produce its verdict.

### Path B: Codex Unavailable

If `codex` is not found on PATH, fall back immediately. Warn the user:

> "Codex CLI not available. Falling back to Claude skeptical-reviewer (single-model mode)."

Spawn the skeptical reviewer:

```
Agent(
  subagent_type="rival:skeptical-reviewer",
  description="Code Verification: <feature name>",
  prompt=<verification prompt from codex-verify-prompt.md>
)
```

Write result to `.rival/workstreams/<id>/verification.md`.

### Path C: Codex Fails or Crashes

If the `codex exec` command exits with a non-zero status or produces no output, fall back to Path B. Warn the user:

> "Codex crashed or failed (exit code: <code>). Falling back to Claude skeptical-reviewer."

Then proceed exactly as Path B.

## Phase 4.5: Compute Recommended Merge Order (multi-repo only)

For multi-repo workstreams, the order in which you merge matters. Merging the primary repo first activates new code paths before connected repos have caught up — that's a runtime breakage window. Merging connected repos first is almost always safer because they're additive (new types, new fields, new endpoints) without anyone calling them yet.

Read the plan's "System Map" section plus `state.connected_repos` to determine the dependency direction:

- **Tier 1 (merge first):** repos that EXPORT contracts/types others import (e.g., shared-models, schemas, protocol definitions). Branch role: `connected`.
- **Tier 2 (merge second):** repos that CONSUME the new contracts but aren't the user-facing entry point. Branch role: `connected`.
- **Tier 3 (merge LAST):** the primary repo — the one whose feature this is. Once this is merged, users can hit the new feature, so all dependencies must already be live. Branch role: `primary`.

Append a section to `.rival/workstreams/<id>/verification.md`:

```markdown
## Recommended Merge Order

1. **Rival.CentralSchema.API** (chore/<ws-id>) — Tier 1, exports new types
   PR: `gh -R <owner>/Rival.CentralSchema.API pr ...`
   Why first: downstream services import the new type. Merging shared schema first means consumers can pick it up cleanly.

2. **Rival.Customer.API** (chore/<ws-id>) — Tier 2, consumer
   PR: `gh -R <owner>/Rival.Customer.API pr ...`
   Why second: depends on Rival.CentralSchema.API@new. Once shared schema is merged and a new package version is published, customer API can update.

3. **Rival.Apps.API** (feature/<ws-id>) — Tier 3, primary
   PR: `gh -R <owner>/Rival.Apps.API pr ...`
   Why LAST: this is what activates the user-facing feature. Merging it before customer API would create a window where the new code path exists but the consumer isn't ready, causing 5xx errors.

## Compatibility Window

Between merging Tier 1 and merging Tier 3, the system is in a "ready but not activated" state. This is safe — no user-facing change has happened yet. The window collapses the moment Tier 3 merges. If you need to roll back, roll back in REVERSE order (Tier 3 → Tier 2 → Tier 1).
```

For single-repo workstreams, skip this phase — there's only one PR to merge.

## Phase 5: Human Gate (Final)

Read `.rival/workstreams/<id>/verification.md` and present results:

> "**Verification complete.**
>
> Reviewer: <Codex CLI / Claude Skeptical Reviewer>
> Verdict: **<verdict>**
>
> **Tasks: <N>/<N> verified**
> **Issues found: <N>** <one-line summary of each with severity, if any>
> **Security: <PASS/CONCERNS>**
>
> Full verification: `.rival/workstreams/<id>/verification.md`
>
> **What would you like to do?**
> 1. **Ship it** — mark as verified, run retro to capture lessons
> 2. **Fix issues** — address the findings and re-verify
> 3. **Accept as-is** — acknowledge issues but mark as verified anyway"

On **Ship it** or **Accept as-is**:
- Update state to `verified` (NOT `archived` — retro is the one that archives, so it can still find this workstream)
- Append to history with timestamp
- Print:
> "Workstream **<id>** marked as **verified**. All artifacts preserved in `.rival/workstreams/<id>/`.
> Next: run `/rival:rival-retro` to capture lessons learned. The retro will archive this workstream once it's done."

On **Fix issues**: Keep state at `build-complete`, user fixes and re-runs `/rival:rival-verify`.

## Important Notes

- This reviews CODE, not the plan — focus on what was actually built
- The plan.md is the spec — it defines what "correct" means
- The git diff should capture all changes from the workstream, not just the last commit
- Do NOT set a timeout on Codex — let it run to completion
- If Codex's verification is clearly wrong (hallucinated files, etc.), note it to the user
- Archiving preserves all artifacts — workstreams are a permanent record
