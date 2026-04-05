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

Read `state.json`. Phase must be `build-complete`.

- If earlier: Guide to correct next step
- If `archived`: "This workstream is already complete and archived."
- If `build-complete`: proceed

Update state to `verifying`.

## Phase 2: Gather Verification Context

Collect everything the verifier needs:

1. **Plan:** `.rival/workstreams/<id>/plan.md` — this is the spec, the single source of truth for what was supposed to be built
2. **Git diff:** All code changes since the workstream started
3. **Test results:** Run the test suite and capture output

```bash
# Get the first workstream commit
FIRST_COMMIT=$(git log --oneline --all --grep="<workstream-id>" --reverse | head -1 | awk '{print $1}')

# Full diff of all workstream changes
git diff ${FIRST_COMMIT}~1..HEAD

# Run tests (command from plan.md or config)
<test command from plan or config>
```

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
> 1. **Ship it** — archive workstream, you're done!
> 2. **Fix issues** — address the findings and re-verify
> 3. **Accept as-is** — acknowledge issues but ship anyway"

On **Ship it** or **Accept as-is**:
- Update state to `archived`
- Print:
> "Workstream **<id>** archived. All artifacts preserved in `.rival/workstreams/<id>/`.
> Great work! Consider running `/rival:rival-retro` to capture learnings."

On **Fix issues**: Keep state at `build-complete`, user fixes and re-runs `/rival:rival-verify`.

## Important Notes

- This reviews CODE, not the plan — focus on what was actually built
- The plan.md is the spec — it defines what "correct" means
- The git diff should capture all changes from the workstream, not just the last commit
- Do NOT set a timeout on Codex — let it run to completion
- If Codex's verification is clearly wrong (hallucinated files, etc.), note it to the user
- Archiving preserves all artifacts — workstreams are a permanent record
