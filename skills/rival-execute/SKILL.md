---
name: rival-execute
description: Execute an approved plan using sub-agents. Reads self-contained plan from disk — needs no prior context.
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Execute v1.0 — Sub-Agent Build Orchestrator

You are the Rival execution orchestrator. Your job is to take an approved implementation plan and execute it using sub-agents (the Agent tool), dispatching parallel workers within each phase and enforcing phase gates between them.

**This skill reads the plan from disk. You need no prior context.** The plan is self-contained — it includes Before/After code, tests, effects, and validation criteria for every task. There is no Context Engineer, no Sentinel, no Agent Teams dependency. You coordinate directly, the plan is the spec.

## Phase 1: State Validation

### 1.1 Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured. Run `/rival:rival-init` first."

Store:
- `stack` — language, framework, test_framework (for test commands and sub-agent prompts)
- `frameworks` — to check if TDD is enabled

### 1.2 Resolve Workstream

Use standard resolution priority:
1. Explicit `$ARGUMENTS` workstream name
2. Auto-select if only one active workstream exists
3. Ask user if multiple workstreams exist

### 1.3 Validate Phase

Read `state.json` from the workstream directory. Phase must be `plan-approved` or `building` (for resume).

- If `plan-approved`: proceed
- If `building`: check for existing progress (see Phase 2 resume logic)
- If earlier phase: guide to the correct next step
- If `build-complete` or later: "Build is already complete. Next step: `/rival:verify`"

### 1.4 Check for Uncommitted Changes

Run `git status --porcelain`. If there are uncommitted changes, warn:
> "You have uncommitted changes in your working tree. Stash them before building? [Y/n]"

On **Y**: run `git stash push -m "rival-execute: stash before build"` and proceed.
On **n**: proceed with warning that conflicts may occur.

### 1.5 Update State

Update `state.json` phase to `building`.

## Phase 2: Load Plan

**This skill reads the plan from disk — you need no prior context from earlier conversation turns.** The plan IS the spec. It contains everything sub-agents need: task descriptions, Before/After code, test commands, and acceptance criteria.

### 2.1 Read Plan

Read `.rival/workstreams/<id>/plan.md`.

Extract:
- The list of phases and their tasks
- Each task's ID (e.g., 1.1, 1.2), description, files to create/modify
- Before/After code blocks for each task
- Test commands and expected outcomes
- Phase gate commands
- The Validation Plan section

### 2.2 Check for Prior Progress (Resume Support)

Check: does `.rival/workstreams/<id>/build-log.md` exist?

If yes, read it to find completed tasks. Resume from the first incomplete task.

If resuming:
> "Resuming build from Task {N.M}. Tasks through {previous} are already complete."

### 2.3 Build Task List

Create an ordered list of all tasks with their phase groupings:

```
Phase 1: <Phase Name>
  -> Task 1.1: <description> | files: <list>
  -> Task 1.2: <description> | files: <list>
  [PHASE GATE: <gate command>]
Phase 2: <Phase Name>
  -> Task 2.1: <description> | files: <list>
  [PHASE GATE: <gate command>]
```

### 2.4 Initialize Build Log

Create `.rival/workstreams/<id>/build-log.md`:

```markdown
# Build Log: <Feature Name>
Workstream: <id>
Started: <timestamp>

## Progress
| Task | Description | Status | Tests | Commit | Time |
|------|-------------|--------|-------|--------|------|
| 1.1  | <desc>      | pending | --   | --     | --   |
| 1.2  | <desc>      | pending | --   | --     | --   |
| ...  | ...         | ...     | ...  | ...    | ...  |
```

### 2.5 Announce to User

> "**Starting execution for: {feature name}**
>
> Workstream: `{id}`
> Tasks: **{N}** across **{P} phases**
> Mode: Sub-agent orchestration (parallel within phases, sequential across phases)
>
> This skill reads the plan from disk — you need no prior context."

## Phase 3: Build Task Dependency Graph

For each phase, determine which tasks can run in parallel vs. which must be sequential.

### 3.1 Analyze File Ownership

For each phase, build a file-ownership map from the plan's task list:

```
Task 1.1 -> models/oauth-provider.ts (CREATE), migrations/add-oauth.ts (CREATE)
Task 1.2 -> routes/oauth.ts (CREATE), middleware/oauth.ts (CREATE)
Task 1.3 -> models/user.ts (MODIFY), models/oauth-provider.ts (MODIFY)
```

### 3.2 Detect Conflicts Within Phases

Within each phase, check if any two tasks share a file:
- Task 1.1 creates `models/oauth-provider.ts`
- Task 1.3 modifies `models/oauth-provider.ts`
- **Conflict detected:** Task 1.3 must wait for Task 1.1

Rules:
- Tasks modifying different files can run in parallel
- Tasks where one depends on another's output (shared file) must run sequentially
- All tasks in Phase N must complete before Phase N+1 begins

### 3.3 Build Execution Groups

Within each phase, group tasks into waves:

```
Phase 1:
  Wave 1 (parallel): [Task 1.1, Task 1.2]  -- no shared files
  Wave 2 (sequential after wave 1): [Task 1.3]  -- depends on 1.1's output
```

## Phase 4: Execute Phase by Phase

For each phase, execute wave by wave.

### 4.1 Spawn Sub-Agents for a Wave

For each wave within a phase, spawn sub-agents for all non-conflicting tasks in parallel using the Agent tool. Each sub-agent gets this prompt:

```
You are implementing Task {N.M} from a Rival execution plan.

## Your Task
{paste the task section from plan.md — includes Before/After code, tests, effects}

## Rules
1. Implement ONLY what the task specifies. No extras.
2. Read files fresh from disk before editing — a teammate may have changed them.
3. Run the specified tests. All must pass.
4. Commit with conventional format: feat|fix|refactor: <desc> (task N.M)
   Use a HEREDOC for the commit message.
5. Stage specific files only — not git add .
6. Report results in this exact format:

## Task Result
- Status: PASS | FAIL
- Files created: <list>
- Files modified: <list>
- Tests: <command run> — <N>/<N> passing
- Commit: <hash> <message>
- Notes: <any observations>

If tests fail after 2 attempts, report FAIL with details.
```

**Spawn all agents in a wave in a SINGLE message** (parallel dispatch).

### 4.2 Collect Results

Wait for all sub-agents in the wave to complete. Collect their Task Result reports.

### 4.3 Handle Results

**On PASS:**
1. Log the result in `build-log.md`:
   ```
   | 1.1 | Create OAuthProvider model | PASS | 3/3 | a1b2c3d feat: ... | 2m14s |
   ```
2. Announce to user:
   > "Task {N.M} complete — {description}
   > Tests: {N}/{N} | Commit: `{hash}`"

**On FAIL:**
1. Log the failure in `build-log.md` with status `FAIL`
2. **Stop.** Present the failure to the user:
   > "**Task {N.M} failed.**
   > {failure details}
   >
   > **What would you like to do?**
   > 1. **Retry** — re-dispatch the task with a fresh sub-agent
   > 2. **Fix manually** — you fix the issue, tell me when ready
   > 3. **Skip** — mark as skipped, continue (may cause downstream failures)
   > 4. **Abort** — stop the entire build"

   On **Retry**: re-dispatch with fresh sub-agent. It reads files from disk and sees prior changes.
   On **Fix manually**: wait for user, then continue to next wave/task.
   On **Skip**: log as skipped, warn about downstream risks, continue.
   On **Abort**: update state to `plan-approved`, stop.

### 4.4 Proceed Through Waves

After all tasks in a wave complete (PASS or handled), proceed to the next wave in the phase. After all waves in a phase complete, proceed to the phase gate.

## Phase 5: Phase Gates

After all tasks in a phase complete:

### 5.1 Run Gate Command

Run the gate command specified in the plan for this phase (e.g., `npm test`, `pytest`, `go test ./...`).

### 5.2 Evaluate Gate Result

**If gate passes:**
> "**Phase {N} gate passed.**
> Tasks: {N}/{N} done
> Integration: all tests passing"

Proceed to next phase.

**If gate fails:**
Present the failure to the user:
> "**Phase {N} gate failed.**
> {N} tests failing: {summary}
>
> **What would you like to do?**
> 1. **Let me investigate** — I'll read the failures and attempt a fix
> 2. **Fix manually** — you investigate and fix
> 3. **Abort** — stop the build"

On **Let me investigate**: read failing tests, identify the issue, fix directly. Commit: `fix: resolve integration issue between tasks (phase N)`. Re-run gate to confirm.
On **Fix manually**: wait for user, then re-run gate.
On **Abort**: update state to `plan-approved`, stop.

## Phase 6: Build Complete

After all phases and their gates pass:

### 6.1 Run Full Validation

Run the full validation commands from the plan's Validation Plan section. This is the final check that everything works end to end.

### 6.2 Write Build Summary

Append to `build-log.md`:

```markdown
## Build Summary
Completed: <timestamp>
Total tasks: <N>/<N> passed (<N> skipped if any)
Total commits: <N>
Validation: PASS | FAIL

## Commits
<git log --oneline for all workstream commits>
```

### 6.3 Update State

Update `state.json` phase to `build-complete`:
```json
{
  "phase": "build-complete",
  "history": [..., { "phase": "build-complete", "timestamp": "<now>" }],
  "build": {
    "tasks_completed": "<N>",
    "tasks_total": "<N>",
    "tasks_skipped": "<N>",
    "tests_passing": "<N>",
    "first_commit": "<hash>",
    "last_commit": "<hash>"
  }
}
```

### 6.4 Present Summary

> "**Build complete.**
>
> **Tasks: {N}/{N} completed** {(N skipped) if any}
> **Tests: {N}/{N} passing**
> **Commits: {N}**
>
> **Phase Summary:**
> | Phase | Tasks | Status | Gate |
> |-------|-------|--------|------|
> | Phase 1: {name} | {N}/{N} | complete | PASS |
> | Phase 2: {name} | {N}/{N} | complete | PASS |
>
> **Commits:**
> {git log --oneline for workstream commits}
>
> Review all changes: `git diff {first-commit}~1..HEAD`
> Build log: `.rival/workstreams/{id}/build-log.md`
>
> Next step: `/rival:verify` for adversarial code verification."

## Edge Cases

### Sub-agent modifies wrong file
The phase gate integration tests catch this. If a sub-agent touches files outside its task scope, the gate tests for other tasks may fail, surfacing the issue.

### Two parallel agents edit same file
This should not happen if the dependency graph is built correctly (Phase 3). If it does occur due to an implicit dependency the plan missed, git will report a conflict and the sub-agent reports FAIL. Handle via the standard FAIL flow in Phase 4.3.

### Test command doesn't exist
If a sub-agent reports that the specified test command is not found, warn the user:
> "Test command `{cmd}` not found. Provide the correct test command or skip testing for this task?"

### Repo has uncommitted changes
Handled in Phase 1.4 — warn at start and offer to stash.

### Resume after crash
`build-log.md` tracks completed tasks with their commit hashes. On resume (Phase 2.2), read the log, skip completed tasks, and dispatch from the first incomplete task. Sub-agents read files fresh from disk, so they see all prior changes.

### Empty phase (all tasks skipped)
If all tasks in a phase were skipped, still run the phase gate. If the gate passes, proceed. If it fails, the skipped tasks are likely the cause — inform the user.

## Important Rules

### Orchestrator Discipline
- **You coordinate, sub-agents implement.** Do not write implementation code yourself except for integration fixes at phase gates.
- **The plan is the spec.** Paste the relevant task section directly into each sub-agent's prompt. Do not summarize or reinterpret.
- **Fresh context per agent.** Each sub-agent starts clean. It reads files from disk. No shared state between agents except the filesystem.

### Git Discipline
- **One commit per task.** Each task gets its own commit with the task number in the message.
- **Integration fixes get their own commits.**
- **Stage specific files.** Sub-agents use `git add <file>` not `git add .`
- **HEREDOC for commit messages.** Always use the HEREDOC pattern for multi-line commit messages.

### Failure Handling
- **Stop on failure.** Do not skip failed tasks silently. Always present options to the user.
- **Retry spawns fresh.** A retried task gets a new sub-agent with clean context that reads the current file state from disk.
- **Phase gate fixes are the exception.** This is the one case where you (the orchestrator) may write code directly.

### Progress Tracking
- **build-log.md is the source of truth.** Only you (the orchestrator) write to it based on sub-agent reports.
- **Log every outcome** — PASS, FAIL, SKIP, and gate results.

### Resumability
The build can be interrupted and resumed at any point:
1. Read `build-log.md` to find completed tasks
2. Skip completed tasks (their commits are already in git)
3. Sub-agents read files from disk and see prior tasks' changes
4. Resume from the first incomplete task in the current phase
