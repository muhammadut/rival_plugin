# Rival Plugin — Improvements & Ideas from Agent Teams Test Run

Date: 2026-02-16
Context: First end-to-end test of rival-execute on Flagsmith repo (/healthz endpoint)

---

## 1. Validated: Agent Teams Execution Works

rival-execute successfully completed:
- Context Engineer wrote execution guide (field manual)
- 2 workers implemented 5 tasks across 2 TDD phases (red → green)
- Sentinel reviewed all 4 commits, 0 concerns
- Phase gates passed, team shut down cleanly
- State machine transitions correct: `review-approved` → `building` → `build-complete`
- ~11 minutes for a SMALL feature, first ever run

**Status: SHIPPED (v0.2.0)**

---

## 2. Critical: Agent Budget System (Triage-Aware Agents)

**Problem:** Code explorer used 152 tool uses for a SMALL /healthz endpoint. The triage classified it as SMALL (1-3 files) but the agents still ran their full deep-dive protocol.

**Fix:** Agents need triage-aware depth budgets:

```
SMALL:  tool budget ~15, surface scan, find 2-3 relevant files and stop
MEDIUM: tool budget ~50, moderate exploration, map affected area
LARGE:  tool budget ~100+, deep dive, full dependency tracing
```

**Where to implement:**
- rival-plan skill (pass triage size to agent prompts)
- Agent definition files in `agents/` (add budget awareness instructions)

**Impact:** Dramatically faster planning for small/medium tasks.

---

## 3. Feature: Project Atlas (`/rival:rival-scan`)

**Problem:** Every feature re-discovers project-level intelligence (patterns, architecture, dependencies, security baseline). This is wasteful — patterns don't change between features.

**Solution:** New two-tier architecture:

### Tier 1: Project Atlas (run once after init, cached)
New skill `/rival:rival-scan` that produces:
```
.rival/atlas/
  architecture.md    — file tree, modules, entry points
  patterns.md        — naming conventions with REAL code examples
  dependencies.md    — import graph, what breaks when X changes
  security.md        — auth patterns, middleware, known exposures
  tech-details.md    — deep stack info beyond init
```

This is a perfect Agent Teams use case — spawn 4 agents to scan different aspects in parallel. One-time cost, benefits all future features.

### Tier 2: Feature Scan (per feature, fast)
Planning agents receive the atlas and only do feature-specific work:
- Code Explorer: ~10 tool calls instead of 152 (atlas has the map)
- Pattern Detector: ~5 tool calls (patterns already cached)
- Impact Analyzer: ~5 tool calls (dependency graph cached)

**New workflow:** `init → scan → plan → review → execute → verify`

**Refresh strategy:** Manual (`/rival:rival-scan --refresh`) or auto-suggest when git shows major changes since last scan.

---

## 4. Fix: Lead Discipline at Phase Gates

**Problem:** At Phase 2 gate, the lead couldn't run tests (no Docker), so it read source files and did a code review itself. This bloats the lead's context and violates the "stay lean" principle.

**Fix:** Update rival-execute Phase Gate instructions:
```
If tests cannot be run (missing runtime/Docker/poetry):
1. Do NOT review code yourself
2. Ask the sentinel to do a thorough review
3. Present the user with: "Tests can't run locally. Options:
   a. Sentinel reviewed the code — proceed
   b. Run tests manually (provide the command)
   c. Abort"
```

**Where:** `rival-plugin/skills/rival-execute/SKILL.md` Phase 6.4

---

## 5. Fix: Gemini Model Version

**Problem:** rival-review invoked `gemini-2.5-pro` instead of `gemini-3-pro-preview` as specified in the skill.

**Possible causes:**
- Plugin cache serving old skill version (0.1.0)
- Claude ignoring the model specification in the skill prompt

**Fix:**
- Verify the installed skill file actually contains `gemini-3-pro-preview`
- Make the model instruction more prominent in the skill (bold, repeated)
- Consider reading model from `.rival/config.json` instead of hardcoding in skill

---

## 6. Fix: Plugin Cache / Version Issue

**Problem:** After pushing v0.2.0 to GitHub, the plugin installer still showed v0.1.0. The cache directory was `plugins/cache/rival-plugin/rival/0.1.0/`. The actual files were updated but the version label was stale.

**Investigation needed:**
- How does Claude Code plugin cache invalidation work?
- Does it key on the marketplace.json version?
- Is there a way to force cache refresh?

**Workaround:** The content was correct despite the label. Users can verify by checking if `skills/rival-execute/SKILL.md` exists.

---

## 7. UX: Init vs Triage Framework Selection Confusion

**Problem:** User was confused about why they select frameworks at init AND again at triage. The relationship between the two steps isn't clear.

**Current flow:**
- `rival-init`: "What frameworks does this PROJECT support?" (project-level config)
- `rival-plan` triage: "Which of those frameworks does THIS FEATURE need?" (per-feature)

**Fix options:**
1. Better explanatory text in both steps
2. Rename init step to "Available Frameworks" and triage to "Relevant for This Feature"
3. Add a brief explanation in the triage prompt: "These are the frameworks you configured in init. The triage agent recommends which ones are relevant for this specific feature:"

**Where:** `rival-plugin/skills/rival-init/SKILL.md` and `rival-plugin/skills/rival-plan/SKILL.md`

---

## 8. Architecture: Agent Teams vs Sub-Agents Decision Matrix

**Validated through testing:**

| Phase | Mechanism | Reason |
|-------|-----------|--------|
| rival-plan (research) | Sub-agents | Independent research, just report back |
| rival-review | Gemini CLI / sub-agent | Single reviewer, no coordination needed |
| rival-execute | Agent Teams | Coordinated implementation, shared task board, parallel workers |
| rival-verify | Gemini CLI / sub-agent | Single reviewer |

**Future consideration:** rival-plan COULD use Agent Teams if we want research agents to challenge each other's findings (competing hypotheses model from the docs). But for now, sub-agents are correct — simpler and cheaper.

---

## 9. Architecture: Two Execution Paths

**Implemented:**
- **Fast path:** `plan → review → execute → verify` (Agent Teams, parallel, skips blueprint)
- **Classic path:** `plan → review → blueprint → build → verify` (sequential, sub-agents)

**When to use which:**
- Fast path: default, recommended, when Agent Teams is available
- Classic path: fallback when Agent Teams isn't enabled, or for very small tasks where team overhead isn't worth it

---

## 10. Context Window Management (Core Design Principle)

**Key insight from this session:** The blueprint phase was the bottleneck because it loaded all intelligence into ONE context window and iterated over all tasks. By task 7+, context was degraded.

**The fix (rival-execute) distributes context:**
- Lead: stays lean (only task list + coordination messages)
- Context Engineer: reads all intelligence, writes ONE document (no iteration bloat)
- Workers: each gets fresh context, reads only what it needs
- Sentinel: grows slowly with each review (acceptable for typical builds)

**For very large builds (50+ tasks):** Consider phase-scoped sentinels (one per phase, fresh context each time).

---

## Priority Order

1. **Agent Budget System** — biggest bang for buck, fixes the painful 152-tool-use problem
2. **Project Atlas** — transforms the planning speed for all features
3. **Lead Discipline Fix** — quick fix to rival-execute skill
4. **UX: Init vs Triage clarity** — quick copy change
5. **Gemini Model Fix** — investigate cache issue
6. **Plugin Cache Investigation** — understand the version caching behavior
7. **Phase-scoped Sentinels** — only needed for very large builds, can wait
