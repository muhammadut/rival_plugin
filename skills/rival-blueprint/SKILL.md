---
name: rival-blueprint
description: Create detailed task breakdown from reviewed plan with acceptance criteria.
user-invocable: true
argument-hint: [workstream-name]
---

# Rival Blueprint — Context-Engineered Task Card Generator

You are the Rival blueprint orchestrator. Your job is to take the reviewed plan and all gathered intelligence from prior phases, and produce **self-contained task cards** — one per implementation task. Each task card embeds exactly the context an implementing agent needs: relevant code, applicable risks, specific patterns, and precise acceptance criteria. Nothing more, nothing less.

This is the critical transformation point of the Rival workflow: wide intelligence gathered by 7+ agents gets distributed into narrow, laser-focused work orders.

You run inline in the current conversation.

## Phase 1: State Validation

### 1.1 Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured. Run `/rival:rival-init` first."

Store config values — you'll need `stack`, `frameworks`, `gemini_available`.

### 1.2 Resolve Workstream

Use the same resolution priority as rival-review:
1. Explicit `$ARGUMENTS` workstream name
2. Conversation context from prior commands
3. Auto-select if single active workstream
4. Ask user if multiple

### 1.3 Validate Phase

Read `state.json`. Phase must be `review-approved`.

- If earlier phase: Guide the user to the correct next step
- If `blueprint-approved` or later: "Blueprint already approved. Next step: `/rival:rival-build`"
- If `review-approved`: proceed

Update state to `blueprinting`.

## Phase 2: Load Intelligence

Read all workstream artifacts produced by prior phases:

| Artifact | Source Phase | What It Contains |
|----------|-------------|------------------|
| `context-briefing.md` | Plan | Code explorer findings, patterns, impact analysis, security risks, domain model, gaps |
| `plan.md` | Plan | Implementation phases, task list, approach, risk assessment |
| `review.md` | Review | Adversarial critique from Gemini/fallback |
| `review-decisions.md` | Review | ACCEPTED/REJECTED decisions with actions |

Parse and hold all of these in working memory. You will distribute their contents across task cards in Phase 5.

### 2.1 Extract Structured Sections from Context Briefing

Parse `context-briefing.md` into its component sections. You need to be able to reference each independently:

- **Relevant Code** — symbols found, files involved (from Code Explorer)
- **Architecture** — C4 levels affected (from C4 Mapper, if available)
- **Domain Model** — bounded contexts, aggregates, entities (from DDD Modeler, if available)
- **Event Flows** — event chains (from Event Storm Mapper, if available)
- **Patterns & Conventions** — patterns to follow, anti-patterns to avoid (from Pattern Detector)
- **Impact Analysis** — blast radius, files that will change, files that might break (from Impact Analyzer)
- **Security Considerations** — risks rated by severity (from Security Analyzer)
- **Gaps** — what doesn't exist yet (from Code Explorer)

### 2.2 Extract Accepted Review Items

Parse `review-decisions.md` and collect all items with decision `ACCEPT`. Each has:
- An issue title and severity
- A reason for acceptance
- An action to take

These MUST be assigned to specific tasks. Every accepted item must appear in at least one task card.

## Phase 3: Agent Spawning

Spawn specialized agents to produce test strategies and acceptance criteria.

### Agents for Blueprint Phase

| Agent | Condition | Purpose |
|-------|-----------|---------|
| `test-strategist` | Always | Design test scenarios per task |
| `bdd-writer` | `"bdd"` was selected by triage for this workstream | Write Given/When/Then scenarios |
| `adr-writer` | `"adr"` was selected by triage for this workstream | Draft ADRs for significant decisions |

Check the workstream's `state.json` → `triage.selected_frameworks` to see which frameworks
were selected. BDD and ADR agents only run if those frameworks were selected during triage
(or if the user overrode with "go full").

### Build Agent Prompts

Each agent receives:
- The implementation plan (`plan.md`)
- Accepted review items (from `review-decisions.md`)
- Context briefing (`context-briefing.md`)
- Framework reference file (if applicable — check `.rival/frameworks/<name>.md` first, then `${CLAUDE_PLUGIN_ROOT}/frameworks/<name>.md`)

**Test Strategist prompt — IMPORTANT instruction:**
```
## Implementation Plan
<plan.md content>

## Accepted Review Items
<accepted items from review-decisions.md>

## Context Briefing
<context-briefing.md content>

Design a comprehensive test strategy for this implementation.

CRITICAL: Organize your test scenarios BY TASK NUMBER (matching the plan's task numbering).
For each task (e.g., Task 1.1, Task 1.2, Task 2.1), list the specific test scenarios
(unit, integration, e2e) that apply to THAT task. This mapping is essential — I need
to assign your scenarios to individual task cards.

For each test scenario include:
- Test type (unit/integration/e2e)
- What to test (specific behavior)
- Key assertions
- Edge cases specific to this task
```

**BDD Writer prompt — IMPORTANT instruction:**
```
## Framework Reference
<content of frameworks/bdd.md>

## Implementation Plan
<plan.md content>

## Accepted Review Items
<accepted items from review-decisions.md>

Write Given/When/Then acceptance scenarios for each planned feature.
Include happy paths, sad paths, and edge cases.

CRITICAL: Organize your scenarios BY TASK NUMBER (matching the plan's task numbering).
Group scenarios under the task they verify. A scenario may appear under multiple tasks
if it spans them, but each scenario should have a PRIMARY task assignment.
```

**ADR Writer prompt additions:**
```
## Framework Reference
<content of frameworks/adr.md>

## Implementation Plan
<plan.md content>

## Review Decisions
<review-decisions.md content>

## Context Briefing
<context-briefing.md content>

Identify significant architectural decisions from the plan and review.
Draft an ADR for each decision that has alternatives and meaningful consequences.
```

### Spawn Agents

Launch all selected agents in parallel:
```
Task(subagent_type="rival:test-strategist", description="Test Strategy: <feature>", prompt=...)
Task(subagent_type="rival:bdd-writer", description="BDD Scenarios: <feature>", prompt=...)
Task(subagent_type="rival:adr-writer", description="ADR Drafts: <feature>", prompt=...)
```

Collect all results.

### Save Raw Agent Outputs

Before using the results for context mapping, persist each agent's raw output to disk.
This creates an audit trail — you can trace any task card's content back to its source.

Write each agent's result to `.rival/workstreams/<id>/agent-outputs/`:

```
.rival/workstreams/<id>/agent-outputs/test-strategist.md
.rival/workstreams/<id>/agent-outputs/bdd-writer.md       (if BDD enabled)
.rival/workstreams/<id>/agent-outputs/adr-writer.md        (if ADR enabled)
```

Each file should contain the agent's complete, unmodified output. Do NOT summarize or
edit — save exactly what the agent returned.

This serves three purposes:
1. **Auditability** — if a task card has wrong test scenarios, trace it back to the source
2. **Resumability** — if blueprinting is interrupted, these outputs survive context clearing
3. **Education** — `rival-educate` can reference these to explain test strategy decisions

## Phase 4: Context Mapping

This is the intellectual core of blueprinting. You are distributing intelligence to tasks.

### 4.1 Parse Tasks from Plan

Extract the task list from `plan.md`. For each task, note:
- **Task ID** (e.g., 1.1, 1.2, 2.1)
- **Phase** it belongs to
- **Description**
- **Files to create or modify**
- **Risk level**

### 4.2 Build the Context Map

For each task, determine which intelligence applies to it. Work through each source:

#### A. Impact Analysis → Tasks

For each file listed in the Impact Analysis section of the context briefing:
- Which task modifies that file? → assign the blast radius information to that task
- What downstream files could break? → list them in that task's card

Example mapping:
```
Impact Analysis says: "Modifying user.ts affects auth.middleware.ts,
profile.controller.ts, user.serializer.ts"

Task 1.3 modifies user.ts → Task 1.3's card gets:
  "Blast Radius: auth.middleware.ts, profile.controller.ts, user.serializer.ts"
```

#### B. Security Risks → Tasks

For each security risk in the Security Considerations section:
- Which task introduces or touches the risky area? → assign the risk + mitigation to that task
- If a risk spans multiple tasks, assign it to the FIRST task that encounters it

Example mapping:
```
Security says: "MEDIUM: OAuth tokens must be encrypted at rest"

Task 1.1 creates the OAuthProvider model with token fields
→ Task 1.1's card gets: "Security: encrypt accessToken and refreshToken fields at rest"
```

#### C. Patterns & Conventions → Tasks

For each pattern detected:
- What type of code is it about? (model pattern, route pattern, test pattern, etc.)
- Which tasks create that type of code? → assign the relevant pattern examples

Example mapping:
```
Patterns says: "Models use declare syntax, DataTypes import, init() pattern"

Task 1.1 creates a new model → Task 1.1's card gets the model pattern example
Task 2.1 creates a strategy → Task 2.1 gets the service/strategy pattern example
```

#### D. Domain Model → Tasks

If DDD analysis is available:
- Which aggregate does this task's code belong to?
- What invariants must be maintained?
- What are the boundaries (don't cross them)?

Example mapping:
```
DDD says: "User is an aggregate root. OAuthProvider belongs to User aggregate."

Task 1.1 creates OAuthProvider → Task 1.1's card gets:
  "Domain: OAuthProvider belongs to User aggregate. Access through User,
  never query OAuthProvider directly."
```

#### E. Review Items → Tasks

For each ACCEPTED review item:
- Which task should address it? (based on the action described in review-decisions.md)
- Assign the item's title, severity, and required action to that task

**Every accepted review item MUST be assigned to at least one task.** If an item doesn't
map to any existing task, create a new task for it.

#### F. Test Scenarios → Tasks

From the test strategist results (which are already organized by task number):
- Assign each test scenario to its corresponding task card

#### G. BDD Scenarios → Tasks

From the BDD writer results (organized by task number):
- Assign Given/When/Then scenarios to their corresponding task cards

### 4.3 Identify Task Boundaries

For each task, determine what is explicitly OUT OF SCOPE. This prevents implementing
agents from doing work that belongs to other tasks.

For each task, scan the other tasks' file lists:
- If another task also touches a file this task touches → note it as a boundary
- The task card must say: "Do NOT modify <file> — that's Task <X.Y>'s responsibility"

Example:
```
Task 1.3 modifies user.ts (adds association)
Task 3.2 modifies user.serializer.ts (adds avatarUrl to API response)

Task 1.3's card gets: "Do NOT modify user.serializer.ts — Task 3.2 handles that"
Task 3.2's card gets: "Task 1.3 has already added the avatarUrl field and association.
  You are adding it to the serializer output."
```

## Phase 5: Read Source Files for Embedding

For each task, read the actual source files that will be modified or serve as pattern
references. This step embeds real code into task cards so implementing agents don't
need to explore.

### 5.1 Files Being Modified

For each task that MODIFIES (not creates) an existing file:
- Read the full current content of that file
- Embed it in the task card under "Current File Content"

This gives the implementing agent the exact code it will be editing.

### 5.2 Pattern Reference Files

For each task, based on the patterns mapped in Phase 4:
- Read 1-2 existing files that demonstrate the pattern the task should follow
- Extract the relevant code section (not the whole file — just the pattern)
- Embed it in the task card under "Patterns to Follow"

Example: If Task 1.1 creates a new model, read an existing model file and extract
the model definition as a pattern example.

### 5.3 Practical Limits

- Embed at most **3 file contents** per task card to keep cards focused
- For large files (>100 lines), extract only the relevant section with line number references
- If a file is too large to embed, provide the file path and the specific lines to read

## Phase 6: Generate Task Cards

For each task, write a task card file to `.rival/workstreams/<id>/tasks/task-<N.M>.md`.

### Task Card Template

```markdown
# Task <N.M>: <Task Description>

Phase: <phase number and name>
Risk: <LOW | MEDIUM | HIGH>
TDD: <YES | NO — based on config.frameworks>

## What to Build

<Clear, specific specification of what this task accomplishes.
Not "add OAuth fields" but exactly which fields, what types, what constraints,
what relationships. The implementing agent should have zero ambiguity about
what to produce.>

## Files

<For each file, state whether to CREATE or MODIFY>

### <CREATE | MODIFY>: `<file path>`

<If MODIFY — embed the current file content:>
```<language>
// Current content of <file path>:
<full file content or relevant section with line numbers>
```

<If CREATE — describe what the file should contain and its role:>
Purpose: <what this file is for>

## Code Context

<Relevant code from other files that the agent needs to understand to do this task.
For example, if creating a service that uses a model, show the model's interface.
If adding a route, show the existing route registration pattern.>

```<language>
// From <file path> (lines <N-M>) — <why this is relevant>:
<code snippet>
```

## Patterns to Follow

<Actual code examples from this codebase showing the conventions to match.
NOT "follow existing patterns" — the actual pattern code.>

```<language>
// From <file path> — <pattern description>:
<code example showing the pattern>
```

<If multiple patterns are relevant, show each with a brief label.>

## Blast Radius

<From impact analysis. Only include if this task modifies existing files.>

These files depend on the files you're modifying. After your changes, they must
still work correctly:

| File | Dependency | Risk |
|------|-----------|------|
| <file path> | <how it depends — imports, calls, extends> | <will it break or is it safe?> |

<For each file, state whether it's SAFE (no action needed) or VERIFY (agent should
check it still compiles/works after changes).>

## Security Notes

<From security analysis. Only include risks that apply to THIS task.
Omit this section entirely if no security risks apply.>

- <SEVERITY>: <specific risk and what to do about it>

## Domain Context

<From DDD modeler. Only include if DDD framework is enabled and relevant.
Omit this section entirely if not applicable.>

- Aggregate: <which aggregate this code belongs to>
- Boundary: <what not to cross>
- Invariants: <what must remain true>

## Review Items Addressed

<From review-decisions.md. Only include if this task addresses a review critique.
Omit this section entirely if no review items apply.>

### Review Item #<N>: <title> (<SEVERITY>)
Action required: <what the review said to do>

## Acceptance Criteria

<If BDD enabled: Given/When/Then scenarios from BDD writer>
<If BDD not enabled: bullet-point acceptance criteria>

- [ ] <criterion 1 — specific, verifiable>
- [ ] <criterion 2>
- [ ] ...

## Tests to Write

<From test strategist, filtered to this task.>

### Unit Tests
- <test description>: <key assertion>
- <test description>: <key assertion>

### Integration Tests
<if applicable>
- <test description>: <key assertion>

### Edge Cases
- <edge case scenario>: <expected behavior>

## TDD Instructions

<Only include this section if TDD is enabled in config.frameworks>

Follow Red-Green-Refactor:
1. **RED**: Write the tests listed above first. Run them — they should fail.
2. **GREEN**: Write the minimum implementation to make tests pass.
3. **REFACTOR**: Clean up only if needed. Run tests again to confirm.

## Run When Done

```bash
<exact test command for this task's tests>
```

Full suite (run this too if you modified existing files):
```bash
<full test suite command from config.stack.test_framework>
```

## Scope Boundaries — Do NOT Do

<Explicit list of things this task should NOT touch, even if related.>

- Do NOT modify `<file>` — that is Task <X.Y>'s responsibility
- Do NOT implement <feature> — that is Task <X.Y>'s responsibility
- Do NOT add <thing> — it will be done in Phase <N>
```

### Task Card Quality Checklist

Before writing each task card, verify:

- [ ] **Self-contained**: An agent can implement this task by reading ONLY this card. No need to read blueprint.md, context-briefing.md, or any other artifact.
- [ ] **Code embedded**: Current file contents are included for all files being modified. Pattern examples show actual code, not just descriptions.
- [ ] **Risks assigned**: Every blast radius concern and security risk relevant to this task's files is included.
- [ ] **Review items mapped**: Every accepted review item appears in at least one task card.
- [ ] **Tests specified**: Concrete test scenarios (not "write appropriate tests").
- [ ] **Boundaries clear**: The "Do NOT Do" section prevents scope creep into other tasks.
- [ ] **Zero ambiguity**: The "What to Build" section is specific enough that two different agents would produce substantially similar implementations.

## Phase 7: Write Blueprint Index

Write `.rival/workstreams/<id>/blueprint.md` as an overview and index:

```markdown
# Blueprint: <Feature Name>
Generated: <timestamp>
Workstream: <id>
Based on: plan.md (reviewed and approved)

## Overview
<Brief summary of what will be built>

## Task Cards
Each task has a self-contained task card in `tasks/task-<N.M>.md` with embedded
code context, specific risks, patterns, and acceptance criteria.

### Phase 1: <Phase Name>

| Task | Description | Files | Risk | Review Items |
|------|-------------|-------|------|--------------|
| [1.1](tasks/task-1.1.md) | <description> | <file list> | LOW | — |
| [1.2](tasks/task-1.2.md) | <description> | <file list> | LOW | — |
| [1.3](tasks/task-1.3.md) | <description> | <file list> | MEDIUM | #4 |

### Phase 2: <Phase Name>

| Task | Description | Files | Risk | Review Items |
|------|-------------|-------|------|--------------|
| [2.1](tasks/task-2.1.md) | <description> | <file list> | MEDIUM | #1, #3 |
| [2.2](tasks/task-2.2.md) | <description> | <file list> | LOW | — |

### Phase 3: <Phase Name>
...

## Review Item Coverage

| Review Item | Severity | Assigned To |
|-------------|----------|-------------|
| #1: <title> | HIGH | Task 2.1 |
| #3: <title> | MEDIUM | Task 2.1 |
| #4: <title> | MEDIUM | Task 1.3 |

All <N> accepted review items are covered.

## Test Strategy Summary
<From test strategist: overall approach, coverage targets>

## Architecture Decisions
<If ADR enabled: summary table with links to ADR files>

## Definition of Done
- [ ] All task cards marked complete
- [ ] All tests passing (per-task and full suite)
- [ ] No regressions in existing tests
- [ ] All accepted review items addressed (see coverage table)
- [ ] <If TDD: tests written before implementation for each task>
- [ ] <If BDD: all Gherkin scenarios verified>
```

### ADR Files (if applicable)

If the ADR writer produced ADRs, write each to:
`.rival/workstreams/<id>/adrs/adr-NNN-<title-slug>.md`

## Phase 8: Human Gate

Update state to `blueprint-ready`.

Present the blueprint summary:

> "**Blueprint ready for review.**
>
> **<N> task cards** across **<N> phases**
>
> Each task card is self-contained with:
> - Embedded source code for files being modified
> - Specific patterns to follow (with code examples)
> - Blast radius warnings for risky modifications
> - Security notes where applicable
> - Concrete test scenarios and acceptance criteria
> - Explicit scope boundaries (what NOT to touch)
>
> Review items addressed: **<N> of <N>** accepted items mapped to tasks
> <If ADR: N Architecture Decision Records drafted>
>
> Full blueprint: `.rival/workstreams/<id>/blueprint.md`
> Task cards: `.rival/workstreams/<id>/tasks/`
>
> **What would you like to do?**
> 1. **Approve** — start building
> 2. **Review a task card** — tell me which task number to show
> 3. **Revise** — tell me what to change
> 4. **Reject** — go back to planning"

On **Approve**: Update state to `blueprint-approved`.
> "Blueprint approved. Next step: `/rival:rival-build` to start implementation."

On **Review a task card**: Read and display the requested task card. Let user
provide feedback, update the card, then re-present the gate options.

On **Revise**: Discuss and update affected task cards, re-present.

On **Reject**: Reset state, guide user.

## Important Notes

- **Self-containment is the goal.** An implementing agent should need ONLY its task card. If it needs to read blueprint.md or context-briefing.md, the task card is incomplete.
- **Embed real code, not references.** Don't say "follow the pattern in user.ts" — paste the actual code from user.ts. The implementing agent may not know to look there.
- **Every accepted review item MUST be assigned.** If an item doesn't fit any existing task, create a new task. Unassigned review items are a blueprint failure.
- **Task ordering within phases should minimize risk** — safe changes first, risky changes later.
- **Keep tasks atomic** — each one is independently implementable and testable. A task should be completable in a single agent session.
- **Be precise about file operations.** State CREATE vs MODIFY for every file. For MODIFY, embed the current content. For CREATE, describe the expected content.
- **Scope boundaries prevent cascading errors.** If two tasks touch the same file in different ways, be explicit about which task does what. The "Do NOT Do" section is as important as the "What to Build" section.
- **The context map is the hard part.** Resist the temptation to dump all intelligence into every card. Each card should have the MINIMUM context needed for its specific task — targeted, not comprehensive.
