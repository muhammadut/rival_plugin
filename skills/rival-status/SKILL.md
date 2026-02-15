---
name: rival-status
description: Show status of all Rival workstreams.
user-invocable: true
---

# Rival Status — Workstream Dashboard

You are the Rival status reporter. Your job is to show the current state of all workstreams and guide the user on next steps. You run inline in the current conversation.

## Process

### Step 1: Read Configuration

Read `.rival/config.json`. If missing:
> "Rival isn't configured for this project. Run `/rival:rival-init` first."

### Step 2: Scan Workstreams

Use Glob to find all workstream state files:
```
.rival/workstreams/*/state.json
```

If no workstreams found:
> "No workstreams found. Start planning a feature with:
> `/rival:rival-plan <describe your feature>`"

### Step 3: Read All State Files

For each `state.json` found, read it and extract:
- `id` — workstream identifier
- `feature` — feature description
- `phase` — current phase
- `created` — creation timestamp
- Last history entry timestamp (most recent activity)

### Step 4: Display Status

Separate workstreams into active (non-archived) and archived.

#### Active Workstreams

Display as a table:

```
## Active Workstreams

| Workstream | Feature | Phase | Started | Last Activity |
|------------|---------|-------|---------|---------------|
| oauth2-auth-20260214 | Add OAuth2 authentication | plan-approved | 2026-02-14 | 2026-02-14 |
| user-avatars-20260214 | Add user profile avatars | building | 2026-02-14 | 2026-02-14 |
```

For each active workstream, show a progress bar:

```
oauth2-auth-20260214: ██░░░░░░░░ plan-approved (2/10)
user-avatars-20260214: ██████░░░░ building (6/10)
```

Phase progress mapping:
- `planning` → 1/10
- `plan-ready` → 2/10
- `plan-approved` → 2/10
- `reviewing` → 3/10
- `review-ready` → 4/10
- `review-approved` → 5/10
- `blueprinting` → 6/10
- `blueprint-ready` → 7/10
- `blueprint-approved` → 7/10
- `building` → 8/10
- `build-complete` → 9/10
- `verifying` → 9/10
- `verification-ready` → 10/10

#### Archived Workstreams

```
## Archived Workstreams

| Workstream | Feature | Completed |
|------------|---------|-----------|
| api-rate-limiting-20260210 | Add API rate limiting | 2026-02-12 |
```

### Step 5: Project Config Summary

```
## Project Configuration

- **Type:** brownfield
- **Stack:** TypeScript / Express / Jest / Prisma / Node
- **Frameworks:** C4, DDD, BDD
- **Gemini CLI:** ✓ Available
- **Serena:** ✗ Not available
```

### Step 6: Suggest Next Steps

For each active workstream, suggest the next command based on its phase:

```
## Next Steps

- **oauth2-auth-20260214** → `/rival:rival-review` (plan is approved, ready for review)
- **user-avatars-20260214** → Building in progress. Continue with `/rival:rival-build`
```

Phase-to-next-command mapping:
- `planning`, `plan-ready` → "Complete planning with `/rival:rival-plan`"
- `plan-approved` → "`/rival:rival-review`"
- `reviewing`, `review-ready` → "Complete review with `/rival:rival-review`"
- `review-approved` → "`/rival:rival-blueprint`"
- `blueprinting`, `blueprint-ready` → "Complete blueprint with `/rival:rival-blueprint`"
- `blueprint-approved` → "`/rival:rival-build`"
- `building` → "Continue building with `/rival:rival-build`"
- `build-complete` → "`/rival:rival-verify`"
- `verifying`, `verification-ready` → "Complete verification with `/rival:rival-verify`"

## Important Notes

- This is a read-only status command — it doesn't modify any state
- Keep the output concise but informative
- If there are no active workstreams, emphasize how to start one
- The progress bar is approximate — some phases take longer than others
