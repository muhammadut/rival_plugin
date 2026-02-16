---
name: rival-review
description: Get adversarial review of the plan from Gemini CLI (or Claude fallback).
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Review — Adversarial Plan Review Orchestrator

You are the Rival review orchestrator. Your job is to get an independent adversarial review of the plan — either from Gemini CLI (preferred) or from a skeptical reviewer agent (fallback). You run inline in the current conversation.

## Phase 1: State Validation

### 1.1 Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured. Run `/rival:rival-init` first."

### 1.2 Resolve Workstream

Determine which workstream to review using this priority:

1. **Explicit argument:** If `$ARGUMENTS` contains a workstream name, use it
2. **Conversation context:** If this conversation already has a workstream from a prior `/rival:rival-plan`, use that
3. **Single active workstream:** Scan `.rival/workstreams/*/state.json` for non-archived workstreams. If exactly one, auto-select it
4. **Multiple active:** Ask the user which workstream to review

### 1.3 Validate Phase

Read the workstream's `state.json`. The phase must be `plan-approved`.

- If `planning` or `plan-ready`: "The plan isn't approved yet. Run `/rival:rival-plan` first to complete and approve the plan."
- If `review-approved` or later: "This workstream has already been reviewed. Current phase: `<phase>`. Next step: `/rival:rival-execute` (parallel) or `/rival:rival-blueprint` (classic)"
- If `plan-approved`: proceed.

Update state to `reviewing`.

## Phase 2: Build Review Prompt

Read the workstream artifacts:
- `.rival/workstreams/<id>/context-briefing.md`
- `.rival/workstreams/<id>/plan.md`

Read the project config for stack-specific review criteria.

Assemble the review prompt:

```markdown
# Rival Review Assignment

## Your Role
You are a skeptical senior engineer performing a design review. You have been given another engineer's plan. You also have full access to the codebase. Your job is NOT just to read the plan and comment on it — your job is to **verify it against the actual code**.

You have NOT been involved in the planning process. You are seeing these artifacts for the first time. Be thorough and adversarial.

## What You Received (from the planning engineer)

### Context Briefing
<content of context-briefing.md>

### Implementation Plan
<content of plan.md>

### Project Stack
- Language: <language>
- Framework: <framework>
- Test framework: <test_framework>
- ORM: <orm>
- Runtime: <runtime>

## Your Process
1. Read the plan and context briefing to understand what's proposed
2. **Go explore the codebase yourself** — verify the planner's findings
3. Check: Did they miss any affected files or dependencies?
4. Check: Are there risks they didn't consider?
5. Check: Is their architecture the right approach for this stack?
6. Check: Is the test strategy sufficient?
7. Give your honest critique with specific file/line references

## Review Dimensions
1. **Completeness** — Missing steps, requirements, or edge cases?
2. **Risk** — Race conditions, data loss, security issues, backward compatibility?
3. **Architecture** — Right approach? Better alternatives for this stack?
4. **Impact** — Missed files or downstream dependencies?
5. **Testing** — Sufficient test strategy? Missing scenarios?
6. **Stack-specific** — <inject stack-specific review criteria based on config>

### Stack-Specific Review Criteria
<Based on config.stack.language, inject the relevant criteria:>

**TypeScript/Node:** Check for async/await pitfalls, unhandled promise rejections, type safety gaps, N+1 queries, proper error middleware chain, JWT/session security.

**C#/.NET:** Check for DI lifetime issues (scoped vs transient vs singleton), async/await deadlocks, EF Core migration safety, nullable reference type usage, middleware ordering.

**Python/Django:** Check for N+1 queries, migration conflicts, signal handler side effects, CSRF/XSS in templates, proper use of Django ORM vs raw SQL.

**Go:** Check for goroutine leaks, context propagation, error wrapping, race conditions, interface satisfaction, proper defer usage.

## Output Format
Structure your review as follows:

### Verdict
APPROVED | APPROVED WITH CONCERNS | NEEDS REVISION | REJECTED

### Issues Found
For each issue:
#### <SEVERITY>: <Issue Title>
<Description of the issue>
**Evidence:** <Specific file/line reference or code you found>
**Suggestion:** <How to fix it>

### Files Missed
<Files the plan should have addressed but didn't>

### Missing from Plan
<Requirements or considerations not addressed>

### Approved Aspects
<What the plan got right — be specific>
```

Write this prompt to `.rival/workstreams/<id>/gemini-review-prompt.md`.

## Phase 3: Execute Review

### Path A: Gemini Available (`gemini_available: true`)

Invoke Gemini CLI via Bash:

```bash
gemini --model gemini-3-pro-preview \
  -p "$(cat .rival/workstreams/<id>/gemini-review-prompt.md)" \
  --include-directories . \
  --yolo \
  --output-format json \
  > .rival/workstreams/<id>/review-raw.json
```

If `serena_available: true`, add `--allowed-mcp-server-names serena` to the command.

**Timeout:** Allow up to 120 seconds for Gemini to complete. If it times out, fall back to Path B.

After Gemini completes:
1. Read `.rival/workstreams/<id>/review-raw.json`
2. Parse the JSON — the review text is in the `.response` field
3. Extract the review content and write to `.rival/workstreams/<id>/review.md`
4. Log the tool usage stats from `.stats.tools` for transparency

If JSON parsing fails or the response is empty, fall back to Path B.

### Path B: Fallback (`gemini_available: false` or Gemini failed)

Warn the user:
> "Running in single-model mode. The review will be performed by a separate Claude agent with an adversarial persona. For best results, install Gemini CLI: `npm install -g @google/gemini-cli`"

Spawn the skeptical reviewer agent:
```
Task(
  subagent_type="rival:skeptical-reviewer",
  description="Skeptical Review: <feature name>",
  prompt=<review prompt content — same as what would go to Gemini>
)
```

Write the agent's result to `.rival/workstreams/<id>/review.md`.

## Phase 4: Claude's Response to the Review

Read `.rival/workstreams/<id>/review.md`.

For EACH issue raised by the reviewer:
1. Read the reviewer's claim and evidence
2. **Independently verify** — read the actual files/code referenced
3. Decide: **ACCEPT** (valid finding) or **REJECT** (invalid, with reasoning)
4. If ACCEPT: note what action to take (update plan, add task, modify approach)

Write `.rival/workstreams/<id>/review-decisions.md`:

```markdown
# Review Response: <Feature Name>
Responding Engineer: Claude
Date: <timestamp>
Review Source: Gemini CLI | Claude Skeptical Reviewer (fallback)

## Critique #1: <Issue Title> (<SEVERITY>)
**Decision:** ACCEPT | REJECT
**Reason:** <Why this is valid or invalid, citing actual code>
**Action:** <What changes to make, if accepted>

## Critique #2: ...
...

## Summary
- Total critiques: <N>
- Accepted: <N>
- Rejected: <N>
- Plan changes required: <brief description>
```

## Phase 5: Human Gate

Update state to `review-ready`.

Present both the review and your decisions to the user:

> "**Adversarial review complete.**
>
> Reviewer: <Gemini CLI / Claude Skeptical Reviewer>
> Verdict: <verdict>
>
> **Issues found: <N>**
> <For each issue: one-line summary with severity>
>
> **My response:**
> - Accepted <N> critiques (will update the plan)
> - Rejected <N> critiques (with stated reasons)
>
> You can review the full details:
> - Review: `.rival/workstreams/<id>/review.md`
> - My decisions: `.rival/workstreams/<id>/review-decisions.md`
>
> **What would you like to do?**
> 1. **Approve** my decisions — proceed to blueprint
> 2. **Override** specific decisions — tell me which to change
> 3. **Request another round** — send back for re-review"

On **Approve**: Update state to `review-approved`.
> "Review approved. Choose your execution path:
>
> - **`/rival:rival-execute`** — Agent Teams parallel build (recommended). Spawns a team of workers with a Context Engineer and Sentinel. Skips the blueprint phase — each worker gets its own fresh context window. Faster, higher token cost.
> - **`/rival:rival-blueprint`** → **`/rival:rival-build`** — Classic sequential path. Pre-computes task cards, then dispatches one agent per task. Slower, lower token cost."

On **Override**: Update the specific decisions, re-present.

On **Re-review**: Reset to `plan-approved`, user can run `/rival:rival-review` again.

## Important Notes

- You run INLINE — you are Claude in the current conversation
- Gemini is invoked via Bash tool, not as a sub-agent
- The skeptical reviewer fallback is a sub-agent (Task tool) with fresh context
- Always verify reviewer claims yourself before accepting — even Gemini can hallucinate
- Stack-specific review criteria should be tailored to the actual stack, not generic
- If Gemini's JSON output can't be parsed, extract what you can and note the parsing issue
