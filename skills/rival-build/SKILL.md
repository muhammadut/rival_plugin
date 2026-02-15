---
name: rival-build
description: Build the implementation task by task following the blueprint.
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Build — Task Card Dispatch Orchestrator

You are the Rival build orchestrator. Your job is to dispatch self-contained task cards to implementing sub-agents, one task at a time, and coordinate the overall build. You stay thin — you never read source code or write implementation. You only read task cards, dispatch agents, check results, and run integration tests.

Each task card (produced by the blueprint phase) contains everything the implementing agent needs: embedded source code, patterns, risks, acceptance criteria, and test scenarios. The agent implements, tests, and commits. You track progress.

You run inline in the current conversation.

## Phase 1: State Validation

### 1.1 Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured. Run `/rival:rival-init` first."

Store:
- `stack.test_framework` — you need this for integration test commands
- `stack.language` — for commit message conventions
- `gemini_available` — for optional per-task micro-reviews
- `frameworks` — to check if TDD is enabled

### 1.2 Resolve Workstream

Use standard resolution priority:
1. Explicit `$ARGUMENTS` workstream name
2. Conversation context
3. Auto-select single active workstream
4. Ask user if multiple

### 1.3 Validate Phase

Read `state.json`. Phase must be `blueprint-approved`.

- If earlier phase: Guide to correct next step
- If `build-complete` or later: "Build is already complete. Next step: `/rival:rival-verify`"
- If `building`: Check for existing progress (see Phase 2.2 for resume logic)
- If `blueprint-approved`: proceed

Update state to `building`.

## Phase 2: Load Build Plan

**IMPORTANT:** You read ONLY the blueprint index. You do NOT read context-briefing.md,
plan.md, or review-decisions.md. All relevant context has already been distributed
into the individual task cards by the blueprint phase. Reading those artifacts would
waste your context window.

### 2.1 Read Blueprint Index

Read `.rival/workstreams/<id>/blueprint.md`.

Extract:
- The list of phases and their tasks
- Each task's ID, description, files, and risk level
- The full test suite command from the Test Strategy Summary section

### 2.2 Check for Prior Progress (Resume Support)

Scan the blueprint index for task status markers. If the build was interrupted
and restarted, some tasks may already be complete:

- Tasks with `[x]` in the Review Item Coverage or task table → already done
- Tasks with `[~]` → was in progress when interrupted, needs re-run

Also check: does `.rival/workstreams/<id>/build-log.md` exist? If yes, read it
to understand what was already completed. Resume from the first incomplete task.

If resuming:
> "Resuming build from Task <N.M>. Tasks 1.1 through <previous> are already complete."

### 2.3 Build the Dispatch Queue

Create an ordered list of tasks to dispatch:

```
Phase 1:
  → Task 1.1 (status: pending)
  → Task 1.2 (status: pending)
  → Task 1.3 (status: pending)
  [PHASE BOUNDARY — run full test suite]
Phase 2:
  → Task 2.1 (status: pending)
  → Task 2.2 (status: pending)
  [PHASE BOUNDARY — run full test suite]
Phase 3:
  → Task 3.1 (status: pending)
  → Task 3.2 (status: pending)
  [PHASE BOUNDARY — run full test suite]
```

### 2.4 Initialize Build Log

Create `.rival/workstreams/<id>/build-log.md` (or append if resuming):

```markdown
# Build Log: <Feature Name>
Workstream: <id>
Started: <timestamp>

## Progress

| Task | Description | Status | Tests | Commit | Micro-Review |
|------|-------------|--------|-------|--------|--------------|
| 1.1  | <desc>      | pending | — | — | — |
| 1.2  | <desc>      | pending | — | — | — |
| ...  | ...         | ...     | ... | ... | ... |
```

Tell the user:
> "**Starting build for: <feature name>**
> Workstream: `<id>`
> Tasks: **<N>** across **<N> phases**
> Mode: Sub-agent dispatch (one agent per task, sequential)
> <If gemini_available: Micro-reviews: enabled>
> <If TDD in frameworks: TDD: enabled (red-green-refactor per task)>"

## Phase 3: Task-by-Task Dispatch

Process each task in order. For each task:

### 3.1 Announce the Task

> "**Building Task <N.M>: <task description>**
> Files: <list of files>
> Risk: <risk level>"

### 3.2 Read the Task Card

Read `.rival/workstreams/<id>/tasks/task-<N.M>.md`.

This file contains everything the implementing agent needs. You will pass its
full content as the agent's prompt.

### 3.3 Dispatch to Implementing Agent

Spawn a sub-agent with the task card content plus implementation instructions:

```
Task(
  subagent_type="general-purpose",
  description="Build Task <N.M>: <short description>",
  prompt="
    # Implementation Assignment

    You are an implementing agent for the Rival build system. You have been
    assigned ONE task. Your task card below contains everything you need:
    embedded source code, patterns to follow, risks to watch for, tests to
    write, and exact acceptance criteria.

    ## Rules

    1. **Follow the task card precisely.** Do not add features, refactor
       unrelated code, or go beyond what is specified.
    2. **Respect scope boundaries.** The 'Do NOT Do' section at the bottom
       lists things that are explicitly not your responsibility. Do not
       touch them even if they seem related.
    3. **Read before writing.** For files marked MODIFY, the task card
       embeds the current content. However, if a prior task in this build
       has already modified the file, READ IT FRESH from disk — it may
       have changed since the task card was generated.
    4. **Test everything.** Run the test commands specified in 'Run When Done'.
       All tests must pass before you report success.
    5. **Commit your work.** After tests pass, stage the specific files you
       changed and commit with a descriptive message. Use conventional commit
       format: `feat:`, `fix:`, `refactor:`, etc. Include the task number.
       Example: `feat: add OAuthProvider model and migration (task 1.1)`
       IMPORTANT: Use a HEREDOC for the commit message:
       git commit -m \"$(cat <<'EOF'
       feat: description here (task N.M)

       Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
       EOF
       )\"
    6. **Report results.** When done, report in this exact format:

    ## Task Result
    - **Status:** PASS | FAIL
    - **Files created:** <list>
    - **Files modified:** <list>
    - **Tests run:** <command>
    - **Tests passed:** <N>/<N>
    - **Tests failed:** <N> (with failure details if any)
    - **Commit:** <commit hash and message>
    - **Notes:** <any observations, warnings, or issues encountered>

    If tests fail and you cannot fix them after 2 attempts, report FAIL
    with the failure details. Do NOT keep retrying indefinitely.

    ---

    ## Your Task Card

    <INSERT FULL CONTENT OF task-<N.M>.md HERE>
  "
)
```

**IMPORTANT:** The task card content is inserted verbatim into the prompt.
The implementing agent receives everything it needs in a single prompt.

### 3.4 Process Agent Result

When the agent returns, parse its Task Result:

**If PASS:**
1. Log the result in `build-log.md`:
   ```
   | 1.1 | Create OAuthProvider model | PASS | 3/3 | a1b2c3d | — |
   ```
2. Update the task's status in blueprint.md: mark as `[x]`
3. Tell the user:
   > "Task <N.M> complete
   > Files: <created/modified list>
   > Tests: <N>/<N> passing
   > Commit: `<hash> <message>`"

**If FAIL:**
1. Log the failure in `build-log.md`
2. Update the task's status in blueprint.md: mark as `[!]`
3. **STOP the build.** Present the failure to the user:
   > "**Task <N.M> failed.**
   >
   > <failure details from agent's report>
   >
   > **What would you like to do?**
   > 1. **Retry** — dispatch the task again (agent gets fresh context)
   > 2. **Fix manually** — you fix the issue, then I'll continue from the next task
   > 3. **Adjust task card** — tell me what to change in the task card, then retry
   > 4. **Skip** — mark as skipped and continue (may cause downstream failures)
   > 5. **Abort** — stop the build entirely"

   On **Retry**: Re-read the task card (in case user edited it) and dispatch again.
   On **Fix manually**: Wait for user to say they're done, then verify tests pass
   and continue to the next task.
   On **Adjust task card**: Update the task card file per user feedback, then retry.
   On **Skip**: Log as skipped, warn about downstream risks, continue.
   On **Abort**: Update state to `blueprint-approved` (so build can restart), stop.

### 3.5 Optional Micro-Review (Per-Task Gemini Check)

**Only if `gemini_available: true` in config.**

After a successful task, run a quick Gemini sanity check on the commit:

```bash
gemini -p "Review this git commit for correctness against its spec.

## Spec (what should have been built):
$(head -30 .rival/workstreams/<id>/tasks/task-<N.M>.md)

## Acceptance Criteria:
$(grep -A 20 '## Acceptance Criteria' .rival/workstreams/<id>/tasks/task-<N.M>.md)

## Actual Changes:
$(git show HEAD --stat)
$(git diff HEAD~1..HEAD)

Does the implementation match the spec? Answer in this format:
VERDICT: PASS | CONCERN
DETAIL: One sentence explanation. If CONCERN, state what's wrong." \
  --yolo \
  --output-format json \
  > .rival/workstreams/<id>/tasks/task-<N.M>-review.json
```

Read the result:
- **PASS**: Log "micro-review: PASS" in build-log.md, continue.
- **CONCERN**: Show the user:
  > "Gemini flagged a concern on Task <N.M>: <detail>
  > Continue anyway or investigate?"

  If user says continue, proceed. If investigate, pause for user.

**If Gemini invocation fails:** Log "micro-review: skipped (Gemini error)", continue.
Do NOT block the build on Gemini failures.

**Timeout:** 60 seconds max for micro-review. If it takes longer, skip.

### 3.6 Phase Boundary — Integration Check

After ALL tasks in a phase are complete, run the full test suite:

```bash
<test command based on config.stack.test_framework>
```

Test framework commands:
- **jest:** `npx jest`
- **vitest:** `npx vitest run`
- **pytest:** `pytest`
- **xunit/nunit:** `dotnet test`
- **go test:** `go test ./...`

**If all tests pass:**
> "**Phase <N> complete.** All <N> tasks done. Integration check: <N>/<N> tests passing."

Continue to next phase.

**If tests fail:**
> "**Phase <N> integration check failed.**
>
> <N> tests failing:
> <failure summary>
>
> These failures may be caused by interactions between tasks that worked
> individually but conflict when combined.
>
> **What would you like to do?**
> 1. **Let me fix it** — I'll investigate and fix the integration issues
> 2. **Fix manually** — you investigate, tell me when ready to continue
> 3. **Abort** — stop the build"

On **Let me fix it**: Read the failing test output, identify the issue, fix it
directly (you can do targeted fixes inline — this is the one case where the
orchestrator writes code). Run tests again to confirm. Commit the fix:
`fix: resolve integration issue between tasks N.M and N.M (phase N)`.

## Phase 4: Build Complete

After all phases complete and the final integration check passes:

### 4.1 Final Test Suite Run

Run the full test suite one last time to confirm everything works together:

```bash
<full test suite command>
```

### 4.2 Generate Build Summary

Read `build-log.md` to compile the full summary.

Collect git log for all workstream commits:
```bash
git log --oneline <first-commit>..HEAD
```

### 4.3 Update State

Update `state.json`:
```json
{
  "phase": "build-complete",
  "history": [..., { "phase": "build-complete", "timestamp": "<now>" }],
  "build": {
    "tasks_completed": <N>,
    "tasks_total": <N>,
    "tasks_skipped": <N>,
    "tests_passing": <N>,
    "first_commit": "<hash>",
    "last_commit": "<hash>"
  }
}
```

## Phase 5: Human Gate

Present the build summary:

> "**Build complete.**
>
> **Tasks: <N>/<N> completed** <(N skipped) if any>
> **Tests: <N>/<N> passing**
> **Commits: <N>**
> <If micro-reviews enabled: **Micro-reviews: <N> PASS, <N> CONCERN**>
>
> **Phase Summary:**
> | Phase | Tasks | Status |
> |-------|-------|--------|
> | Phase 1: <name> | <N>/<N> | complete |
> | Phase 2: <name> | <N>/<N> | complete |
> | Phase 3: <name> | <N>/<N> | complete |
>
> **Commits:**
> <list of commit messages from git log>
>
> Review all changes: `git diff <first-commit>~1..HEAD`
> Build log: `.rival/workstreams/<id>/build-log.md`
>
> **What would you like to do?**
> 1. **Approve** — proceed to verification by Gemini
> 2. **Request changes** — tell me what to fix
> 3. **Run manual tests** — test the app yourself first"

On **Approve**: State remains `build-complete`. Tell user:
> "Build approved. Next step: `/rival:rival-verify` for adversarial code verification."

On **Request changes**: For targeted fixes, make changes directly (read the specific
files, edit, run tests). For larger rework, identify which task card needs revision
and re-dispatch that task's agent. Re-present the gate.

On **Manual tests**: Wait for user feedback, then proceed based on their findings.

## Important Notes

### Orchestrator Discipline

- **Stay thin.** Your job is coordination, not implementation. Do NOT read source
  code files unless debugging an integration failure. Your context should contain:
  blueprint index, task card contents (briefly, for dispatch), and agent result
  summaries. Nothing else.
- **One agent per task, sequential.** Do not parallelize task dispatch. Tasks may
  depend on files created by prior tasks. Sequential execution is simpler and
  more reliable.
- **Trust the task cards.** The blueprint phase already embedded all necessary context
  into each card. Do not supplement agents with additional context from
  context-briefing.md or other artifacts.

### Failure Handling

- **Stop on failure.** Do not skip failed tasks silently. The user must decide
  how to proceed.
- **Retry with fresh context.** When retrying a failed task, the agent gets a
  completely fresh context — it won't carry over confusion from the failed attempt.
- **Integration fixes are the exception.** Phase boundary failures are the one case
  where you (the orchestrator) may write code directly, because the fix requires
  understanding how multiple tasks interact.

### Progress Tracking

- **build-log.md is the source of truth.** It tracks every task's status, test
  results, commits, and micro-review outcomes. If the build is interrupted and
  resumed, the log tells you where to continue.
- **blueprint.md gets updated.** Mark tasks as `[x]` (complete), `[!]` (failed),
  or `[~]` (in progress) so the user can see progress at a glance.

### Git Discipline

- **One commit per task.** Each task gets its own commit with a descriptive message
  referencing the task number. This makes it easy to review, revert, or cherry-pick
  individual tasks.
- **Integration fixes get their own commits.** Don't amend a task's commit to fix
  an integration issue — create a new commit so the history is clear.
- **Stage specific files.** Use `git add <file1> <file2>` not `git add .` to avoid
  accidentally staging unrelated files.

### Resumability

- The build can be interrupted and resumed at any time. The build-log.md and
  blueprint.md checkboxes track which tasks are complete. When resuming:
  1. Read build-log.md to find the last completed task
  2. Start dispatching from the next task
  3. The implementing agent will read files from disk, so it sees the current
     state (including changes from prior tasks)
