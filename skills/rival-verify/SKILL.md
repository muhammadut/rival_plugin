---
name: rival-verify
description: Get adversarial verification of built code from Gemini CLI (or Claude fallback).
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Verify — Adversarial Code Verification Orchestrator

You are the Rival verification orchestrator. Your job is to get an independent adversarial review of the BUILT CODE (not the plan) — either from Gemini CLI or the skeptical reviewer fallback. This mirrors the review phase but focuses on actual implementation. You run inline in the current conversation.

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

1. **Context briefing:** `.rival/workstreams/<id>/context-briefing.md`
2. **Blueprint:** `.rival/workstreams/<id>/blueprint.md`
3. **Review decisions:** `.rival/workstreams/<id>/review-decisions.md`
4. **Git diff:** Run `git diff` to capture all code changes since the workstream started
5. **Test results:** Run the test suite and capture output
6. **Coverage:** Run coverage report if available

```bash
# Get git diff (from first workstream commit)
git log --oneline --all | head -20
# Identify the first commit of this workstream and diff from there
git diff <base-commit>..HEAD

# Run tests
<test command based on config>

# Coverage (if available)
<coverage command based on config>
```

## Phase 3: Build Verification Prompt

Assemble the verification prompt:

```markdown
# Rival Verification Assignment

## Your Role
You are a skeptical senior engineer performing a CODE REVIEW of a completed implementation. You have the blueprint (what was supposed to be built), the actual code changes, and full codebase access. Your job is to verify that what was planned is what was built — and that it was built well.

You have NOT been involved in the planning or building process. You are seeing this code for the first time. Be thorough.

## What You Received

### Context Briefing (Original Spec)
<content of context-briefing.md>

### Blueprint (What Was Supposed to Be Built)
<content of blueprint.md>

### Review Items That Were Accepted
<accepted items from review-decisions.md>

### Code Changes (Git Diff)
<git diff output>

### Test Results
<test output>

### Coverage Report
<coverage output, if available>

## Your Process
1. Read the blueprint to understand what was supposed to be built
2. Read the code diff to see what was actually built
3. **Go explore the actual source files** — don't just read the diff
4. For each blueprint task, verify it was implemented correctly
5. Check that every accepted review item was actually addressed
6. Look for issues the blueprint didn't anticipate

## Verification Dimensions
1. **Spec Compliance** — Does the code match the blueprint? Any tasks incomplete?
2. **Code Quality** — Clean code, proper error handling, no obvious bugs?
3. **Security** — Injection vulnerabilities, auth bypasses, secrets in code?
4. **Test Coverage** — Are tests meaningful? Missing edge cases?
5. **Review Follow-Through** — Were accepted review items actually implemented?
6. **Stack-Specific** — <inject stack-specific criteria>

### Stack-Specific Verification Criteria

**TypeScript/Node:** Check for type safety (no `any` leaks), proper async/await error handling, N+1 queries in new ORM calls, proper middleware error propagation.

**C#/.NET:** Check for DI lifetime correctness, disposed DbContext access, async/await throughout (no .Result or .Wait()), proper nullable handling.

**Python/Django:** Check for migration safety, proper queryset usage (no N+1), CSRF protection on new views, proper form validation.

**Go:** Check for goroutine leaks, context propagation, error wrapping consistency, race conditions in new concurrent code.

## Output Format

### Verdict
PASS | PASS WITH NOTES | NEEDS FIXES | FAIL

### Blueprint Task Verification
For each task: [x] verified or [ ] issue found
<with notes on what was checked>

### Review Follow-Through
For each accepted review item: [x] implemented or [ ] not addressed
<with evidence>

### Issues Found
For each issue:
#### <SEVERITY>: <Issue Title>
<Description>
**Evidence:** <file:line reference>
**Suggestion:** <fix>

### Security Check
PASS | CONCERNS
<details>

### Test Coverage Assessment
<coverage %, assessment of test quality>

### Backward Compatibility
CONFIRMED | CONCERNS
<details>
```

Write to `.rival/workstreams/<id>/gemini-verify-prompt.md`.

## Phase 4: Execute Verification

### Path A: Gemini Available

```bash
gemini -p "$(cat .rival/workstreams/<id>/gemini-verify-prompt.md)" \
  --include-directories . \
  --yolo \
  --output-format json \
  > .rival/workstreams/<id>/verification-raw.json
```

Add `--allowed-mcp-server-names serena` if Serena is available.

Parse JSON response, extract `.response` field, write to `.rival/workstreams/<id>/verification.md`.

### Path B: Fallback

Warn user about single-model mode. Spawn skeptical reviewer:

```
Task(
  subagent_type="rival:skeptical-reviewer",
  description="Code Verification: <feature name>",
  prompt=<verification prompt>
)
```

Write result to `.rival/workstreams/<id>/verification.md`.

## Phase 5: Human Gate (Final)

Update state to `verification-ready`.

Present verification results:

> "**Verification complete.**
>
> Reviewer: <Gemini CLI / Claude Skeptical Reviewer>
> Verdict: **<verdict>**
>
> **Blueprint tasks: <N>/<N> verified**
> **Review items: <N>/<N> confirmed addressed**
> **Security: <PASS/CONCERNS>**
> **Test coverage: <assessment>**
>
> <If issues found:>
> **Issues: <N>**
> <one-line summary of each with severity>
>
> Full verification: `.rival/workstreams/<id>/verification.md`
>
> **What would you like to do?**
> 1. **Ship it** — archive workstream, you're done!
> 2. **Fix issues** — address the findings and re-verify
> 3. **Accept as-is** — acknowledge issues but ship anyway"

On **Ship it** or **Accept as-is**: Update state to `archived`.
> "Workstream **<id>** archived. All artifacts preserved in `.rival/workstreams/<id>/`.
> Great work! The full planning-review-build-verify cycle is complete."

On **Fix issues**: Keep state at `build-complete`, user fixes and re-runs `/rival:rival-verify`.

## Important Notes

- This reviews CODE, not the plan — focus on what was actually built
- The git diff should capture all changes from the workstream, not just the last commit
- Stack-specific criteria should catch real issues, not theoretical ones
- If Gemini's verification is clearly wrong (hallucinated files, etc.), note it to the user
- Archiving preserves all artifacts — workstreams are a permanent record
