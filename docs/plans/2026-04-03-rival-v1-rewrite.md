# Rival v1.0 — Complete Plugin Rewrite

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the Rival plugin from a 9-command, 12-agent workflow into a streamlined 8-command, 6-agent system that leverages Claude's 1M context window, adds industry research, supports multi-repo projects (including Azure DevOps repos), replaces Gemini with Codex CLI, exposes a standalone `/rival:rival-research` command, and introduces persistent cross-workstream learning.

**Architecture:** Three core phases — Think (plan), Do (execute), Check (verify) — with auto-review built into planning and lessons-learned built into completion. The plan document is self-contained so a fresh-context Claude Code instance can read and execute it without any prior conversation. A standalone research command lets users explore ideas without committing to implementation.

**Tech Stack:** Claude Code plugin (markdown skills + agent definitions), Codex CLI for adversarial review, Context7/WebSearch for research.

**Meta Workflow for Building Agents:** Each agent in this plugin is built using a research-write-review cycle. Before writing any agent definition, we research the best techniques for that agent's domain (e.g., blast radius analysis, security review, pattern detection), write the agent incorporating those findings, then independently review it. This produces state-of-the-art agents, not basic vanilla prompts. See [Task 18](#task-18-meta-workflow-for-building-agents) for the process and [Task 19](#task-19-research-driven-agent-upgrades) for applying it to every agent.

**Working Directory:** `D:\github_projects\ai_ideas_exps\rival_plugin`

---

## Table of Contents

1. [Task 1: Delete Obsolete Files](#task-1-delete-obsolete-files)
2. [Task 2: Update Package Metadata](#task-2-update-package-metadata)
3. [Task 3: Rewrite rival-init](#task-3-rewrite-rival-init) *(includes .paths.md, Azure DevOps, repo cloning)*
4. [Task 4: Create researcher Agent](#task-4-create-researcher-agent) *(built via meta workflow)*
5. [Task 5: Create expert-researcher Agent](#task-5-create-expert-researcher-agent) *(built via meta workflow)*
6. [Task 6: Update code-explorer Agent](#task-6-update-code-explorer-agent) *(research-upgraded)*
7. [Task 7: Merge impact-analyzer into security-analyzer](#task-7-merge-impact-analyzer-into-security-analyzer) *(research-upgraded)*
8. [Task 8: Update pattern-detector Agent](#task-8-update-pattern-detector-agent) *(research-upgraded, has live research capability)*
9. [Task 9: Update skeptical-reviewer Agent](#task-9-update-skeptical-reviewer-agent) *(research-upgraded)*
10. [Task 10: Rewrite rival-plan](#task-10-rewrite-rival-plan)
11. [Task 11: Rewrite rival-execute](#task-11-rewrite-rival-execute)
12. [Task 12: Rewrite rival-verify](#task-12-rewrite-rival-verify) *(no Codex timeout)*
13. [Task 13: Create rival-retro](#task-13-create-rival-retro)
14. [Task 14: Create rival-research](#task-14-create-rival-research) *(NEW — standalone research command)*
15. [Task 15: Update rival-status](#task-15-update-rival-status)
16. [Task 16: Update rival-educate](#task-16-update-rival-educate)
17. [Task 17: Delete Remaining Obsolete Agents](#task-17-delete-remaining-obsolete-agents)
18. [Task 18: Meta Workflow for Building Agents](#task-18-meta-workflow-for-building-agents) *(research-write-review cycle)*
19. [Task 19: Research-Driven Agent Upgrades](#task-19-research-driven-agent-upgrades) *(apply meta workflow to all agents)*
20. [Task 20: Azure DevOps Integration Placeholder](#task-20-azure-devops-integration-placeholder)
21. [Task 21: Final Commit — v1.0](#task-21-final-commit)

---

## Context: The Old vs New Architecture

### Old (v0.2) — 9 commands, 12 agents
```
init → plan → review → blueprint → build → verify
                          ↓ (alt)
                       execute
+ status, educate
```
Problems: separate review command, blueprint phase is context-engineering overhead that 1M context eliminates, no research phase, no multi-repo, Gemini dependency, no persistent learning, 12 agents (many redundant with 1M context).

### New (v1.0) — 8 commands, 6 agents
```
init → plan (includes research + auto-review) → execute → verify → retro
+ research (standalone), status, educate
```

### New Workflow — User Experience Examples

**Example 1: Large multi-repo C# task**
```
> /rival:init
  Rival detected:
  - Language: C# (.csproj found)
  - Framework: ASP.NET Core 8.0
  - Test framework: xUnit
  - ORM: Entity Framework Core
  - Runtime: .NET 8

  Found related repos nearby:
  1. ../carrier-service (C# / ASP.NET Core)
  2. ../quotation-api (C# / ASP.NET Core)
  3. ../rpm-gateway (C# / ASP.NET Core)
  Add these as related repos? [Y/n]

  Your stack uses Azure services. Enable Azure expertise? [Y/n]
  Any other expert domains? (e.g., apim, service-bus, rabbitmq): service-bus, apim

  Codex CLI: detected (gpt-5.4)

  Rival initialized. Start with: /rival:plan <describe your task>

> /rival:plan Add async carrier callbacks so carriers notify us when quotes are ready

  Triage: LARGE — cross-repo change, new endpoints, new queue patterns, 3 repos affected

  Researching...
    - Industry: webhook callback patterns for async APIs
    - Azure: Service Bus sessions for ordered processing
    - ASP.NET: minimal API callback endpoint patterns
    - Lessons: (none yet, first workstream)

  Analyzing codebase...
    - Code Explorer: scanning carrier-service, rpm-gateway, quotation-api
    - Security+Impact: tracing dependencies, checking auth patterns

  Writing plan...

  Auto-reviewing with Codex...
    Codex found 2 items:
    - ACCEPTED: Add idempotency key to callback endpoint
    - REJECTED: "Use Durable Functions" — out of scope, existing arch uses Service Bus

  Plan ready. Workstream: async-carrier-callbacks-20260403

  [Shows formatted plan with mermaid diagrams, before/after code,
   phase breakdown, review notes incorporated]

  What would you like to do?
  1. Approve — proceed to execution
  2. Revise — tell me what to change
  3. Reject — start over

> 1 (approve)

  Plan approved. Clear your context and run /rival:execute to start building.

  ⟨ user clears context ⟩

> /rival:execute

  Loading plan: async-carrier-callbacks-20260403

  Phase 1: Carrier Service — Callback Infrastructure (3 tasks)
    Task 1.1: Creating callback DTOs... [sub-agent working]
    Task 1.2: Adding callback endpoint... [sub-agent working]
    Task 1.3: HMAC verification service... [sub-agent working]
    Phase 1 gate: dotnet test carrier-service/ — 47/47 passing

  Phase 2: Service Bus — Status Events (2 tasks)
    Task 2.1: Status event publisher... [sub-agent working]
    Task 2.2: Gateway status consumer... [sub-agent working]
    Phase 2 gate: dotnet test — all repos — 89/89 passing

  Build complete.
  Tasks: 5/5 | Tests: 89/89 | Commits: 5
  Run /rival:verify for adversarial code review.

> /rival:verify

  Codex reviewing all changes...
  Verdict: PASS WITH NOTES
  - Note: Consider adding retry with exponential backoff on callback handler
  Ship it? [Y/n]

> y

  Workstream archived. Run /rival:retro to capture lessons learned.

> /rival:retro

  Analyzing workstream async-carrier-callbacks-20260403...

  Lessons extracted:
  + codebase-patterns.md: Added Service Bus session pattern, callback endpoint pattern
  + lessons-learned.md: "Codex flagged missing retry logic — add retry to all external
    integration points going forward"

  Commit to .rival/knowledge/? [Y/n]
```

**Example 2: Small single-repo fix**
```
> /rival:plan --light Fix null reference in QuotationValidator.cs line 47

  Mode: Light (single file, quick analysis)

  Reading QuotationValidator.cs...

  Issue: dto.CarrierResponse can be null when carrier times out.
  Line 47: var rate = dto.CarrierResponse.Rate; // NullReferenceException

  Plan:
  Before:
    var rate = dto.CarrierResponse.Rate;

  After:
    var rate = dto.CarrierResponse?.Rate
      ?? throw new ValidationException("Carrier response missing");

  Test to write:
    [Fact]
    public void Validate_WhenCarrierResponseNull_ThrowsValidationException()

  Approve? Or just go fix it directly — this is small enough for inline work.
```

**Example 3: Architecture discussion (no implementation)**
```
> /rival:plan Should we use Event Sourcing or CRUD for the new billing module?

  Triage: DISCUSSION — no implementation, architectural exploration

  Researching...
    - Event Sourcing in C# with EventStoreDB
    - CRUD patterns with EF Core for billing
    - Industry: when event sourcing adds value vs complexity

  Analyzing current codebase...
    - Current data access: EF Core CRUD everywhere, no event sourcing
    - Transaction patterns: Unit of Work via EF Core SaveChanges
    - Team expertise: all existing code is CRUD

  Analysis:

  | Dimension | Event Sourcing | CRUD (EF Core) |
  |-----------|---------------|----------------|
  | Audit trail | Built-in | Must add manually |
  | Complexity | High — new paradigm for team | Low — matches existing patterns |
  | Query perf | Needs read projections | Direct queries |
  | Team ramp-up | 2-3 weeks | Zero |

  Recommendation: CRUD with audit logging. Event sourcing adds significant
  complexity with no existing team expertise. The billing module needs reliable
  audit trails, but an audit log table achieves this without architectural risk.

  [No execution plan generated — this was a discussion]
```

### Edge Cases the System Must Handle

| Edge Case | What Happens |
|-----------|-------------|
| `/rival:execute` with no approved plan | "No approved plan found. Run `/rival:plan` first." |
| `/rival:plan` with no config | "Rival not configured. Run `/rival:init` first." |
| Codex CLI not installed | Fallback to `rival:skeptical-reviewer` agent, warn user |
| Configured repo path doesn't exist | Warn: "Repo '../carrier-service' not found at path. Skipping." Continue with available repos |
| Conflicting research results | Plan presents both sides with tradeoffs, doesn't silently pick one |
| Plan targets an unconfigured repo | "This repo isn't in your config. Want to add it?" |
| Multiple active workstreams | `execute`/`verify` ask which one; `status` shows all |
| User wants to re-plan after seeing auto-review | Revision loop: "Tell me what to change" |
| Execute hits test failure | Stop, present: retry / fix manually / skip / abort |
| Codex process fails (crash, not timeout) | Fallback to Claude skeptical-reviewer, warn user. Never timeout Codex — let it run. |
| --light on a task that's actually complex | Triage warns: "This looks like a MEDIUM task. Use full mode? [Y/n]" |
| Plan task modifies file in a repo the agent can't reach | Detect at plan time: "Task 2.1 modifies ../billing-api but it's not in your repos list" |
| Two workstreams modify the same files | `plan` warns: "Workstream X also modifies CarrierController.cs. Proceed?" |
| User runs retro before verify | Allow it — retro reads whatever artifacts exist |
| .rival/knowledge/ has stale info | retro overwrites with current codebase state, not append-only |

---

## Implementation Tasks

---

### Task 1: Delete Obsolete Files

**Why:** Remove the classic path (blueprint + build) and standalone review. These are being replaced by the simplified workflow.

**Files to delete:**
- `skills/rival-blueprint/SKILL.md` (entire directory)
- `skills/rival-build/SKILL.md` (entire directory)
- `skills/rival-review/SKILL.md` (entire directory)
- `agents/triage-agent.md` (inlined into plan skill)
- `agents/impact-analyzer.md` (merged into security-analyzer)
- `agents/c4-mapper.md` (absorbed — main agent reads C4 docs when needed)
- `agents/ddd-modeler.md` (absorbed — main agent reads DDD docs when needed)
- `agents/event-storm-mapper.md` (absorbed — main agent reads event storming docs when needed)
- `agents/bdd-writer.md` (absorbed — main agent writes BDD criteria inline)
- `agents/adr-writer.md` (absorbed — main agent writes ADRs inline)
- `agents/test-strategist.md` (absorbed — main agent defines test strategy inline)
- `IMPROVEMENTS.md` (replaced by this plan and eventual CHANGELOG)

**Keep unchanged:**
- `frameworks/` directory (all 6 files) — these are reference material the plan agent reads when relevant

**Step 1: Delete skill directories**

```bash
rm -rf skills/rival-blueprint
rm -rf skills/rival-build
rm -rf skills/rival-review
```

**Step 2: Delete absorbed agent files**

```bash
rm agents/triage-agent.md
rm agents/impact-analyzer.md
rm agents/c4-mapper.md
rm agents/ddd-modeler.md
rm agents/event-storm-mapper.md
rm agents/bdd-writer.md
rm agents/adr-writer.md
rm agents/test-strategist.md
```

**Step 3: Delete IMPROVEMENTS.md**

```bash
rm IMPROVEMENTS.md
```

**Step 4: Verify directory structure**

```bash
# Should now have:
# skills/ — 6 directories (init, plan, execute, verify, status, educate)
# agents/ — 4 files (code-explorer, pattern-detector, security-analyzer, skeptical-reviewer)
# frameworks/ — 6 files (unchanged)
find . -type f -not -path './.git/*' | sort
```

Expected output:
```
./.claude-plugin/marketplace.json
./.claude-plugin/plugin.json
./agents/code-explorer.md
./agents/pattern-detector.md
./agents/security-analyzer.md
./agents/skeptical-reviewer.md
./frameworks/adr.md
./frameworks/bdd.md
./frameworks/c4-model.md
./frameworks/ddd.md
./frameworks/event-storming.md
./frameworks/tdd.md
./package.json
./skills/rival-educate/SKILL.md
./skills/rival-execute/SKILL.md
./skills/rival-init/SKILL.md
./skills/rival-plan/SKILL.md
./skills/rival-status/SKILL.md
./skills/rival-verify/SKILL.md
```

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove obsolete skills and agents for v1.0 rewrite

Delete rival-blueprint, rival-build, rival-review skills.
Delete 8 agents absorbed into main orchestrator with 1M context.
Keep framework reference docs unchanged."
```

---

### Task 2: Update Package Metadata

**Why:** Reflect the new version, description, and remove Gemini references.

**Files:**
- Modify: `package.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Step 1: Update package.json**

Replace the full content of `package.json` with:

```json
{
  "name": "@anthropic/rival-plugin",
  "version": "1.0.0",
  "description": "Production-grade development workflow: research, plan, execute, verify, learn. Multi-repo support with Codex adversarial review.",
  "keywords": ["claude-code-plugin", "workflow", "codex", "review", "planning", "multi-repo", "research"],
  "license": "MIT",
  "files": [
    ".claude-plugin/",
    "skills/",
    "agents/",
    "frameworks/"
  ]
}
```

**Step 2: Update plugin.json**

Replace the full content of `.claude-plugin/plugin.json` with:

```json
{
  "name": "rival",
  "version": "1.0.0",
  "description": "Production-grade development workflow: research, plan, execute, verify, learn. Multi-repo support with adversarial review."
}
```

**Step 3: Update marketplace.json**

Replace the full content of `.claude-plugin/marketplace.json` with:

```json
{
  "name": "rival-plugin",
  "owner": {
    "name": "muhammadut"
  },
  "metadata": {
    "description": "Production-grade development workflow with research, adversarial review, and cross-workstream learning."
  },
  "plugins": [
    {
      "name": "rival",
      "source": {
        "source": "github",
        "repo": "muhammadut/rival_plugin"
      },
      "description": "Research-backed planning, parallel execution, adversarial review (Codex/Claude), persistent lessons learned. Multi-repo support.",
      "version": "1.0.0",
      "license": "MIT",
      "keywords": ["workflow", "codex", "review", "planning", "multi-repo", "research", "learning"]
    }
  ]
}
```

**Step 4: Commit**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore: update package metadata to v1.0.0

Remove Gemini references, add Codex and multi-repo keywords."
```

---

### Task 3: Rewrite rival-init

**Why:** Add multi-repo support, expert domain configuration, Codex CLI detection, and create the .rival/knowledge/ directory for persistent learning. Simplify framework selection — frameworks are now reference docs the plan agent pulls in when relevant, not a mandatory selection quiz.

**Files:**
- Rewrite: `skills/rival-init/SKILL.md`

**User Experience:**
```
> /rival:init

  Rival v1.0 — Project Setup

  Scanning project...
  Detected:
  - Language: C#
  - Framework: ASP.NET Core 8.0
  - Test framework: xUnit
  - ORM: Entity Framework Core
  - Runtime: .NET 8

  Is this correct? [Y/n/edit]

  Scanning for related repos nearby...
  Found:
  1. ../carrier-service — C# / ASP.NET Core (has .csproj)
  2. ../quotation-api — C# / ASP.NET Core (has .csproj)
  3. ../shared-models — C# class library (has .csproj)

  Which repos are part of this system? [all / select / none]
  > all

  Describe each repo's role (one line, helps agents understand the system):
  > carrier-service: Calls external carrier APIs, handles rate quotes and responses
  > quotation-api: Receives quotation requests from frontend, routes through APIM
  > shared-models: Shared DTOs and contracts used across services

  Expert domains — Rival can do deep research for your specific tech:
  Detected from your code: azure, ef-core
  Add more? (comma-separated, e.g., service-bus, apim, redis): service-bus, apim

  Checking for review tools...
  - Codex CLI: found (gpt-5.4)
  - Will use Codex for adversarial reviews. Fallback: Claude skeptical-reviewer.

  ╔══════════════════════════════════════════════════╗
  ║              Rival v1.0 Initialized              ║
  ╠══════════════════════════════════════════════════╣
  ║ Project: brownfield                              ║
  ║ Stack: C# / ASP.NET Core / xUnit / EF Core      ║
  ║ Repos: 4 (this + 3 related)                     ║
  ║ Experts: azure, ef-core, service-bus, apim       ║
  ║ Review: Codex CLI (gpt-5.4)                      ║
  ║ Knowledge: .rival/knowledge/ (empty, will grow)  ║
  ╚══════════════════════════════════════════════════╝

  Start planning: /rival:plan <describe your task>
```

**Config format (.rival/config.json):**

```json
{
  "version": "1.0.0",
  "project_type": "brownfield",
  "stack": {
    "language": "csharp",
    "framework": "aspnet-core",
    "test_framework": "xunit",
    "orm": "ef-core",
    "runtime": "dotnet8"
  },
  "repos": [
    {
      "name": "rpm-backend",
      "path": ".",
      "role": "Main RPM backend API",
      "source": "local"
    },
    {
      "name": "carrier-service",
      "path": "../carrier-service",
      "role": "Calls external carrier APIs, handles rate quotes and responses",
      "source": "local"
    },
    {
      "name": "quotation-api",
      "path": "../quotation-api",
      "role": "Receives quotation requests from frontend, routes through APIM",
      "source": "azure-devops"
    },
    {
      "name": "shared-models",
      "path": "../shared-models",
      "role": "Shared DTOs and contracts used across services",
      "source": "azure-devops"
    }
  ],
  "experts": ["azure", "ef-core", "service-bus", "apim"],
  "review": {
    "tool": "codex",
    "codex_model": "gpt-5.4",
    "fallback": "skeptical-reviewer"
  },
  "devops": {
    "provider": "azure-devops",
    "paths_file": ".paths.md",
    "features_available": ["repos", "wikis", "boards"]
  },
  "initialized_at": "2026-04-03T14:30:00Z"
}
```

**The `.paths.md` file (checked during init, user-managed):**

This file lives in the project root (or home directory) and contains credentials and paths for remote repo access and DevOps integration. Rival does NOT create this file — the user creates it (or a setup script does). Init just looks for it and reads configuration from it.

```markdown
# .paths.md — Rival DevOps Configuration
# DO NOT commit this file. Add to .gitignore.

## Azure DevOps
- PAT: <personal-access-token>
- Organization: https://dev.azure.com/myorg
- Project: RPM-Backend
- Repos:
  - quotation-api: https://dev.azure.com/myorg/RPM/_git/quotation-api
  - shared-models: https://dev.azure.com/myorg/RPM/_git/shared-models
  - carrier-service: https://dev.azure.com/myorg/RPM/_git/carrier-service

## Wiki
- URL: https://dev.azure.com/myorg/RPM/_wiki/wikis/RPM.wiki

## Boards
- URL: https://dev.azure.com/myorg/RPM/_boards
- Default area: RPM\Backend
- Default iteration: Sprint 42

## GitHub (if applicable)
- PAT: <github-personal-access-token>
- Repos:
  - rival-plugin: https://github.com/muhammadut/rival_plugin
```

**What init does with `.paths.md`:**
1. Checks if `.paths.md` exists in project root or home directory
2. If found: reads repo URLs, offers to clone missing repos, stores DevOps config
3. If not found: proceeds with local-only repo discovery (existing behavior)
4. Warns user to add `.paths.md` to `.gitignore` if not already there
5. Later (Task 20): a setup script will help generate this file interactively
```

**Directory structure created:**
```
.rival/
  config.json
  workstreams/
  knowledge/
    codebase-patterns.md    (empty placeholder with header)
    lessons-learned.md      (empty placeholder with header)
```

**Step 1: Write the new skill file**

Write the complete new `skills/rival-init/SKILL.md`. The skill must cover:

1. **Check existing config** — if exists, show summary and offer reconfigure
2. **Detect project type** — brownfield vs greenfield via source file glob
3. **Detect tech stack** — scan for package manifests, read them for framework details
4. **Multi-repo discovery** — scan parent directory for sibling repos with same language markers. Also accept user-provided paths.
5. **Repo role descriptions** — ask user to describe each repo's role (one line). This is critical context for agents exploring across repos.
6. **Expert domain detection** — infer from code (Azure SDK imports → azure, Service Bus NuGet → service-bus) plus ask user for additions
7. **Review tool detection** — check `codex --version`, store model. If not found, note fallback to skeptical-reviewer.
8. **Create directory structure** — .rival/, .rival/workstreams/, .rival/knowledge/ with placeholder files
9. **Write config.json**
10. **Display summary**

**Edge cases to handle in the skill:**
- Parent directory not accessible → only use current repo
- Sibling repo has different language → still offer to include (some systems are polyglot)
- User provides relative paths with `../` → resolve and validate they exist
- Codex CLI installed but no API key configured → `codex --version` succeeds but `codex exec` would fail. Detect this if possible.
- Re-running init on existing project → offer to keep repos and just refresh stack detection
- Empty project (greenfield) → skip repo discovery, skip pattern detection expert suggestions

**Step 2: Commit**

```bash
git add skills/rival-init/SKILL.md
git commit -m "feat(init): rewrite for v1.0 with multi-repo, experts, codex detection

- Multi-repo discovery: scans sibling dirs, user provides roles
- Expert domain detection: inferred from imports + user additions
- Codex CLI detection with fallback to skeptical-reviewer
- Creates .rival/knowledge/ for persistent lessons
- Simplified: no mandatory framework quiz (plan agent pulls docs as needed)"
```

---

### Task 4: Create researcher Agent

**Why:** New agent that does industry research via WebSearch and Context7 docs before the codebase is analyzed. This ensures the plan is informed by current best practices, not just what's in the codebase today.

**Files:**
- Create: `agents/researcher.md`

**What this agent does:**
- Receives: feature description + stack info + expert domains
- Uses: WebSearch to find industry best practices, common patterns, known pitfalls
- Uses: Context7 (if available) to look up library/framework documentation
- Returns: structured research brief with findings organized by relevance

**The agent prompt must instruct it to:**
1. Search for the specific pattern/feature being built (e.g., "webhook callback patterns ASP.NET Core")
2. Search for known pitfalls and anti-patterns for this type of work
3. Search for the specific stack's recommended approach (e.g., "Azure Service Bus ordered messaging best practices")
4. Return ONLY findings relevant to the task — not a generic tutorial
5. Include source URLs for each finding so the plan can reference them
6. Flag conflicting advice with both sides presented

**Tools:** WebSearch, WebFetch, Read (for reading local docs if referenced)

**Output format:**
```markdown
### Industry Best Practices
- Finding 1 (source: URL)
- Finding 2 (source: URL)

### Stack-Specific Patterns
- Pattern 1: description + code example from docs
- Pattern 2: description

### Known Pitfalls
- Pitfall 1: what goes wrong and how to avoid it
- Pitfall 2: ...

### Conflicting Advice
- Topic: Option A (source) vs Option B (source) — tradeoffs
```

**Step 1: Research phase** (meta workflow)
- WebSearch: "best practices for AI-assisted software research agents"
- WebSearch: "how to evaluate source quality in automated research"
- WebSearch: "prompt engineering for research synthesis tasks"
- Incorporate findings into the agent definition

**Step 2: Write agents/researcher.md**

**Step 3: Review phase** (meta workflow) — Codex or skeptical-reviewer reviews the agent

**Step 4: Commit**

```bash
git add agents/researcher.md
git commit -m "feat(agents): add researcher agent for industry best practices

Uses WebSearch and Context7 to find patterns, pitfalls, and
documentation before codebase analysis begins.
Built with research-write-review meta workflow."
```

---

### Task 5: Create expert-researcher Agent

**Why:** Deeper research for specific expert domains configured in init (Azure, APIM, Service Bus, etc.). While the researcher does broad pattern search, this agent dives into specific API documentation and configuration guides.

**Files:**
- Create: `agents/expert-researcher.md`

**What this agent does:**
- Receives: feature description + specific expert domain(s) to research + stack info
- Uses: WebSearch + Context7 for official documentation
- Returns: API references, configuration patterns, service limits, gotchas specific to the expert domain

**Example:** If expert domain is "service-bus" and the feature involves async messaging:
- Searches Azure Service Bus documentation for message sessions, dead-letter queues, retry policies
- Finds specific C# SDK patterns for `ServiceBusClient`, `ServiceBusProcessor`
- Reports message size limits, partition considerations, session handling
- Includes actual code snippets from official docs

**Tools:** WebSearch, WebFetch, Read

**Output format:**
```markdown
### Domain: <expert-domain>

#### Official Documentation
- Key doc: <title> (<URL>)
- API reference: <relevant section>

#### Recommended Patterns
- Pattern: <name>
  ```<language>
  // Code from official docs
  ```

#### Configuration & Limits
- Limit: <description>
- Config: <key setting and recommended value>

#### Common Mistakes
- Mistake: <what people get wrong>
- Fix: <correct approach>
```

**Step 1: Write agents/expert-researcher.md**

**Step 2: Commit**

```bash
git add agents/expert-researcher.md
git commit -m "feat(agents): add expert-researcher for deep domain docs

Dives into specific tech documentation (Azure, APIM, Service Bus, etc.)
configured via init experts list."
```

---

### Task 6: Update code-explorer Agent

**Why:** Add multi-repo support (explore across repos from config), add budget awareness based on task size (LIGHT/MEDIUM/LARGE), and simplify output since we no longer feed results into 5 downstream agents.

**Files:**
- Modify: `agents/code-explorer.md`

**Key changes:**

1. **Multi-repo support:** Agent receives a list of repos (name, path, role) and explores across all of them. File paths in output use `<repo-name>:<relative-path>` format for clarity.

2. **Budget awareness:** Agent receives a `budget` field:
   - `LIGHT`: ~15 tool calls, surface scan, find 2-5 relevant files and stop
   - `MEDIUM`: ~50 tool calls, moderate exploration, map affected area across repos
   - `LARGE`: ~100+ tool calls, deep dive, full dependency tracing across all repos

3. **Simplified consumers:** Output is consumed by the main plan agent and the security-analyzer (which now includes impact analysis). No need for C4/DDD/Event Storm-specific sections.

4. **Role descriptions:** The repo roles from config help the agent understand which repo to look in for what. e.g., "quotation-api receives frontend requests" → look there for request DTOs.

**Edge cases:**
- Repo path doesn't exist → warn, skip that repo, continue with others
- Very large monorepo → budget limits prevent runaway exploration
- Polyglot system (C# backend + React frontend) → agent adapts search patterns per repo's language

**Step 1: Rewrite agents/code-explorer.md**

**Step 2: Commit**

```bash
git add agents/code-explorer.md
git commit -m "feat(agents): update code-explorer with multi-repo and budget awareness

- Explores across all configured repos with role context
- Budget system: LIGHT (~15 calls), MEDIUM (~50), LARGE (~100+)
- Simplified output format for 1M context consumption"
```

---

### Task 7: Merge impact-analyzer into security-analyzer

**Why:** With 1M context, one agent can do both impact/blast radius analysis and security analysis in a single pass. This eliminates a serial dependency (impact-analyzer had to wait for code-explorer, then security-analyzer waited for both). Now security-analyzer gets code-explorer results and does everything.

**Files:**
- Modify: `agents/security-analyzer.md`

**Key changes:**

1. **Add blast radius analysis:** Before the OWASP section, add a "Dependency Tracing" step that does what impact-analyzer used to do — trace references, classify files into WILL CHANGE / MIGHT BREAK / SAFE.

2. **Add multi-repo support:** Trace dependencies across repo boundaries (e.g., shared-models changes affect all consumers).

3. **Combined output format:** Single structured output with both impact and security sections.

**New output format:**
```markdown
### Blast Radius
| File | Repo | Impact Level | Reason |
...

### Dependency Graph
SymbolA (WILL CHANGE)
  <- imported by FileB (WILL CHANGE)
  <- imported by FileC (MIGHT BREAK)

### Security Risks
(existing OWASP format, unchanged)

### Critical Items (Action Required)
(merged list: both impact risks and security risks, ordered by severity)
```

**Step 1: Rewrite agents/security-analyzer.md**

**Step 2: Commit**

```bash
git add agents/security-analyzer.md
git commit -m "feat(agents): merge impact analysis into security-analyzer

Single agent now does both blast radius tracing and OWASP security
analysis. Reduces serial dependency chain in planning phase."
```

---

### Task 8: Update pattern-detector Agent

**Why:** Add multi-repo awareness. When detecting patterns, the agent should identify conventions that are consistent across repos (shared patterns) vs repo-specific conventions. This matters for multi-repo projects where each service might have slightly different patterns.

**Files:**
- Modify: `agents/pattern-detector.md`

**Key changes:**

1. **Multi-repo:** Receive repo list, explore patterns in each. Note which patterns are universal vs repo-specific.
2. **Budget awareness:** Same LIGHT/MEDIUM/LARGE budgets as code-explorer.
3. **Simplified output:** Pattern examples must include repo name for multi-repo clarity.
4. **Live research capability (NEW):** Add WebSearch to this agent's tool list. When the agent encounters a framework or library it doesn't have built-in knowledge for, it can search the web for best practices. Example: if it's analyzing a NestJS codebase but has no NestJS-specific patterns, it searches "NestJS project structure conventions" and incorporates the findings. This makes the pattern-detector adaptive to ANY stack, not just ones we've pre-programmed.

**Step 1: Research phase** (meta workflow)
- WebSearch: "code pattern detection techniques for AI agents"
- WebSearch: "how linters detect naming conventions and project structure"
- WebSearch: "AST-based pattern matching for code analysis"
- Incorporate findings into the agent upgrade

**Step 2: Rewrite agents/pattern-detector.md with multi-repo, budget, and live research**

**Step 2: Commit**

```bash
git add agents/pattern-detector.md
git commit -m "feat(agents): update pattern-detector with multi-repo support

Detects shared vs repo-specific conventions in multi-repo projects.
Adds budget awareness for tool call limits."
```

---

### Task 9: Update skeptical-reviewer Agent

**Why:** Minor update — change references from "Gemini review output format" to "Codex review output format". Also clarify that this agent is the fallback when Codex CLI is unavailable, and can review both plans and code.

**Files:**
- Modify: `agents/skeptical-reviewer.md`

**Key changes:**
1. Update the output format reference (remove Gemini mention)
2. Add note that this is Codex fallback
3. Keep the entire adversarial review process unchanged — it's already excellent

**Step 1: Update the references in agents/skeptical-reviewer.md**

**Step 2: Commit**

```bash
git add agents/skeptical-reviewer.md
git commit -m "fix(agents): update skeptical-reviewer to reference Codex fallback

Remove Gemini references, clarify role as Codex CLI fallback reviewer."
```

---

### Task 10: Rewrite rival-plan — THE BIG ONE

**Why:** This is the centerpiece of v1.0. Combines research + codebase analysis + plan synthesis + auto-review into one command. Produces a self-contained execution document that a fresh-context orchestrator can read and execute.

**Files:**
- Rewrite: `skills/rival-plan/SKILL.md`

**This is the largest task. The skill must handle:**

#### 10.1: Initialization
- Read config, validate it exists
- Parse arguments: feature description + flags (--light, --discussion)
- Generate workstream ID
- Check for existing workstreams on same topic
- Create workstream directory + state.json

#### 10.2: Inline Triage (no separate agent)
Classify the task inline. Three categories:

| Category | Criteria | What Happens |
|----------|---------|-------------|
| **LIGHT** | Single file fix, simple bug, small refactor. `--light` flag used. | Minimal scan (one code-explorer call with LIGHT budget), quick plan, no research, no auto-review |
| **MEDIUM** | Single-repo feature, moderate scope, 3-10 files | Full research, focused analysis (MEDIUM budget), full plan, auto-review |
| **LARGE** | Cross-repo, new subsystems, >10 files, architectural changes | Deep research + expert research, comprehensive analysis (LARGE budget), detailed plan with diagrams, auto-review |
| **DISCUSSION** | Questions about architecture, pros/cons, no implementation | Research only, comparison document output, no execution plan, no auto-review |

The triage also decides which framework reference docs to load. With 1M context, the main agent can read 2-3 framework docs directly. Decision logic:
- New entities/domain concepts → read `frameworks/ddd.md`
- Architectural changes → read `frameworks/c4-model.md`
- Event flows or async patterns → read `frameworks/event-storming.md`
- User-facing feature → read `frameworks/bdd.md`
- Framework docs available in `.rival/frameworks/` (custom) take priority over bundled

Show triage result to user with option to override:
```
Triage: MEDIUM — single-repo feature, ~6 files affected
Research: industry patterns + azure (from experts)
Analysis: code-explorer (MEDIUM) + security-analyzer + pattern-detector
Framework docs: DDD (new domain entities detected)

[Accept] [Upgrade to LARGE] [Downgrade to LIGHT]
```

#### 10.3: Research Phase (MEDIUM + LARGE only)
Spawn research agents in parallel:

```
Agent("rival:researcher")     → industry best practices for this type of feature
Agent("rival:expert-researcher") → deep docs for each relevant expert domain
```

Also: read `.rival/knowledge/*.md` for lessons from past workstreams.

For LIGHT: skip research entirely.
For DISCUSSION: research only, skip codebase analysis.

#### 10.4: Codebase Analysis Phase
Spawn analysis agents. What gets spawned depends on triage:

| Agent | LIGHT | MEDIUM | LARGE |
|-------|-------|--------|-------|
| code-explorer | LIGHT budget | MEDIUM budget | LARGE budget |
| pattern-detector | skip | MEDIUM budget | LARGE budget |
| security-analyzer | skip | after code-explorer | after code-explorer |

For LIGHT: just code-explorer with LIGHT budget (15 tool calls max).
For MEDIUM: code-explorer + pattern-detector in parallel (Batch 1), then security-analyzer (Batch 2, needs code-explorer results).
For LARGE: all three, same batching.

#### 10.5: Plan Synthesis
The main agent (with 1M context) synthesizes everything into the plan document.

**CRITICAL: The plan document format must be self-contained.** A fresh Claude Code instance with zero context must be able to read this file and execute the implementation without any other artifacts.

The plan document format:

```markdown
# Execution Plan: <Feature Name>

## Metadata
- Workstream: <id>
- Created: <timestamp>
- Size: LIGHT | MEDIUM | LARGE
- Repos: <list of repos involved, with roles>
- Review: <Codex reviewed / Claude reviewed / not reviewed (LIGHT)>
- Lessons applied: <list of lessons from .rival/knowledge/ that were relevant>

## System Map
<For MEDIUM/LARGE: Mermaid diagram showing how the repos/services connect
and which parts are affected. For LIGHT: skip this section.>

## Research Findings
<For MEDIUM/LARGE: Key findings from researcher + expert-researcher.
Include source URLs. For LIGHT: skip.>

## Lessons from Past Workstreams
<Any relevant entries from .rival/knowledge/*.md. "None" if first workstream.>

## Current State
<For each affected file: repo, path, relevant code snippet showing BEFORE state.
Use code blocks with language tags. For files being created, note "does not exist yet.">

## Target State
<For each affected file: what the code should look like AFTER implementation.
Include actual code or clear pseudocode. For architectural changes, include
Mermaid diagram showing the target architecture.>

## Review Notes
<Auto-review findings that were ACCEPTED, incorporated into the plan.
Rejected items listed with reasoning. For LIGHT: "Not reviewed (light mode).">

## Implementation Phases

### Phase 1: <name>
**Repos:** <which repos this phase touches>
**Gate:** <test command to run after this phase, e.g., "dotnet test carrier-service/">

#### Task 1.1: <description>
- **Repo:** <repo-name>
- **Action:** CREATE | MODIFY
- **Files:** <list with full relative paths within repo>
- **What to do:** <specific, unambiguous instructions>
- **Before:** <current code, if MODIFY> (or "N/A — new file")
- **After:** <target code or clear pseudocode>
- **Tests:** <specific tests to write or run>
- **Effects:** <what other files/services this change impacts>

#### Task 1.2: <description>
...

### Phase 2: <name>
...

## Validation Plan
<End-to-end verification steps. What commands to run across all repos.
Integration test scenarios if applicable.>

## Risks & Mitigations
<Specific risks with severity and concrete mitigations.
Not generic — tied to actual files and code.>
```

**Why this format works for fresh-context execution:**
- System Map tells the orchestrator how repos connect
- Current State shows exactly what exists now (no need to re-explore)
- Target State shows exactly what to build
- Each task has Before/After code — sub-agents don't need to explore
- Phase gates tell the orchestrator what to run between phases
- Validation plan covers end-to-end verification

#### 10.6: Auto-Review (MEDIUM + LARGE only)
After writing the plan, automatically review it:

**Path A — Codex available:**
```bash
codex exec "You are reviewing an implementation plan. Verify it against the actual codebase.

## Plan to Review
$(cat .rival/workstreams/<id>/plan.md)

## Your Task
1. Read the actual files referenced in the plan — verify they exist and match the 'Before' code
2. Check for missed files or dependencies
3. Check for security issues in the approach
4. Check that the phase ordering makes sense
5. Flag any incorrect assumptions

Return:
### Verdict: APPROVED | NEEDS REVISION
### Issues (for each):
  - Severity: HIGH | MEDIUM | LOW
  - Issue: <description>
  - Evidence: <file:line reference>
  - Suggestion: <fix>" \
  --full-auto \
  -o .rival/workstreams/<id>/review-raw.md
```

**Path B — Codex unavailable:**
```
Agent(
  subagent_type="rival:skeptical-reviewer",
  prompt=<same review prompt as above, but embedded in agent prompt>
)
```

**Path C — Codex fails (process error, not timeout):**
Fall back to Path B, warn user. **Do NOT set a timeout on Codex** — let it run as long as it needs. Codex can take several minutes for thorough reviews; this is expected and acceptable.

After review completes, the main agent reads the review, evaluates each item (ACCEPT/REJECT with evidence), and **updates the plan.md** with accepted changes. The review notes section of the plan records what was found and how it was addressed.

For LIGHT: skip auto-review entirely. The task is small enough that the risk is low.

#### 10.7: Human Gate
Present the plan to the user with:
1. Summary of findings (research highlights, key risks)
2. Plan overview (phases, task count, repos affected)
3. Review results (if applicable)
4. Three options: Approve / Revise / Reject

On Approve: update state to `plan-approved`
On Revise: discussion loop, update plan, re-present
On Reject: reset state, ask for new direction

For DISCUSSION mode: present the analysis document. No approve/execute flow.

#### 10.8: Context Clearing Guidance
After approval, tell the user:
```
Plan approved. To execute:
1. Clear your context (Ctrl+L or start a new session)
2. Run /rival:execute
   OR run /rival:execute <workstream-name> if you have multiple workstreams

The plan is fully self-contained — the executor needs no prior context.
```

**Step 1: Write the complete new skills/rival-plan/SKILL.md**

This will be the longest file in the plugin (~400-500 lines). It replaces the current plan skill (505 lines) but adds research, auto-review, and the new plan format.

**Step 2: Commit**

```bash
git add skills/rival-plan/SKILL.md
git commit -m "feat(plan): complete rewrite with research, auto-review, self-contained plans

- Inline triage (LIGHT/MEDIUM/LARGE/DISCUSSION)
- Research phase: industry best practices + expert domain docs
- Loads lessons from .rival/knowledge/
- Auto-review with Codex CLI (fallback: skeptical-reviewer)
- Self-contained plan format for fresh-context execution
- --light flag for simple tasks, --discussion for architecture exploration
- Framework docs loaded by main agent when relevant (not separate agents)"
```

---

### Task 11: Rewrite rival-execute

**Why:** Simplified orchestration. No Agent Teams dependency. Main Claude Code instance reads the self-contained plan and spawns sub-agents for each task. With 1M context, the orchestrator holds the entire plan and coordinates everything.

**Files:**
- Rewrite: `skills/rival-execute/SKILL.md`

**User Experience:**
```
> /rival:execute

  Loading plan: async-carrier-callbacks-20260403
  Size: LARGE | Phases: 3 | Tasks: 8 | Repos: 3

  Phase 1: Carrier Service — Callback Infrastructure (3 tasks)

    Task 1.1: Creating CarrierCallbackDto... [spawning agent]
    Task 1.2: Adding callback endpoint... [spawning agent]
      (1.1 and 1.2 run in parallel — no file conflicts)
    Task 1.1: PASS — 2 files created, 3/3 tests passing, commit a1b2c3d
    Task 1.2: PASS — 2 files modified, 5/5 tests passing, commit d4e5f6g
    Task 1.3: HMAC verification... [spawning agent]
      (1.3 depends on 1.1 output — runs after 1.1 completes)
    Task 1.3: PASS — 1 file created, 4/4 tests passing, commit h7i8j9k

    Phase 1 Gate: dotnet test carrier-service/
    Result: 47/47 passing

  Phase 2: Service Bus — Status Events (2 tasks)
    ...

  Build complete.
  Tasks: 8/8 | Tests: 89/89 | Commits: 8
  Build log: .rival/workstreams/async-carrier-callbacks-20260403/build-log.md

  Next: /rival:verify for adversarial code review
```

**The skill must cover:**

#### 11.1: State Validation
- Read config
- Resolve workstream (argument / auto-select / ask)
- Validate phase is `plan-approved` (or `building` for resume)

#### 11.2: Load Plan
- Read `plan.md` from workstream directory
- Parse phases, tasks, dependencies, gates
- Check for prior progress (resume support via build-log.md)

#### 11.3: Build Task Dependency Graph
For each phase, determine which tasks can run in parallel:
- Tasks modifying different files → parallel
- Tasks where one depends on another's output → sequential
- All tasks in Phase N must complete before Phase N+1 starts

#### 11.4: Execute Phase by Phase
For each phase:
1. Spawn sub-agents for all non-conflicting tasks in parallel
2. Each sub-agent gets this prompt:

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

3. Collect results
4. On PASS: log to build-log.md, announce to user
5. On FAIL: stop, present options (retry / fix manually / skip / abort)

#### 11.5: Phase Gates
After all tasks in a phase complete:
1. Run the gate command from the plan (e.g., `dotnet test carrier-service/`)
2. On pass: announce, proceed to next phase
3. On fail: present failure to user with options

#### 11.6: Build Complete
After all phases pass:
1. Run full validation from plan's Validation Plan section
2. Write build summary to build-log.md
3. Update state to `build-complete`
4. Present summary with commit list
5. Suggest `/rival:verify`

#### Edge cases:
- Sub-agent modifies wrong file → phase gate tests catch it
- Two parallel agents edit same file (shouldn't happen if dependency analysis is correct, but if it does) → git merge conflict at commit time, agent reports FAIL
- Test command doesn't exist → warn, ask user for correct command
- Repo at configured path is dirty (uncommitted changes) → warn at start: "carrier-service has uncommitted changes. Stash them? [Y/n]"
- User's context is polluted from prior work → skill explicitly says "this skill reads the plan from disk, you need no prior context"
- Resume after crash → build-log.md tracks completed tasks, resumes from first incomplete

**Step 1: Write the complete new skills/rival-execute/SKILL.md**

**Step 2: Commit**

```bash
git add skills/rival-execute/SKILL.md
git commit -m "feat(execute): simplified orchestration with sub-agents

- No Agent Teams dependency — uses regular sub-agents
- Reads self-contained plan from disk (fresh context)
- Parallel task dispatch within phases (file conflict detection)
- Phase gates with integration tests
- Resume support via build-log.md
- Clean user progress reporting"
```

---

### Task 12: Rewrite rival-verify

**Why:** Replace Gemini CLI with Codex CLI. Simplify — same concept, different tool.

**Files:**
- Rewrite: `skills/rival-verify/SKILL.md`

**Key changes:**

1. **Codex instead of Gemini:** Use `codex exec` with `--full-auto` for headless review
2. **Fallback:** If Codex unavailable, spawn `rival:skeptical-reviewer` agent
3. **No timeout on Codex:** Let it run as long as it needs — thorough code review takes time. Only fall back if Codex crashes or returns an error.
4. **Auto-suggestion:** For LARGE workstreams, suggest running verify automatically after execute completes. For LIGHT, skip or make optional.
5. **Reads plan.md** (not blueprint.md) — the plan IS the spec

**Codex invocation:**
```bash
codex exec "You are performing adversarial code verification.

## Implementation Plan (what was supposed to be built):
$(cat .rival/workstreams/<id>/plan.md)

## Actual Code Changes:
$(git diff <first-workstream-commit>~1..HEAD)

## Test Results:
$(<test command from plan>)

## Your Task:
1. Read the actual source files, not just the diff
2. Verify each task was implemented correctly
3. Check for security issues not in the plan
4. Check test quality — are tests meaningful?
5. Check for regressions in existing functionality

## Output:
### Verdict: PASS | PASS WITH NOTES | NEEDS FIXES | FAIL
### Task Verification: (for each task: verified or issue)
### Issues Found: (severity, description, file:line, suggestion)
### Security Check: PASS or CONCERNS with details" \
  --full-auto \
  -o .rival/workstreams/<id>/verification.md
```

**Step 1: Write the complete new skills/rival-verify/SKILL.md**

**Step 2: Commit**

```bash
git add skills/rival-verify/SKILL.md
git commit -m "feat(verify): replace Gemini with Codex CLI for adversarial review

- codex exec with --full-auto for headless verification
- Fallback to rival:skeptical-reviewer if Codex unavailable
- Auto-suggest for LARGE workstreams
- Reads plan.md as the spec (not blueprint.md)"
```

---

### Task 13: Create rival-retro — NEW SKILL

**Why:** Persistent learning. After each workstream, extract lessons that benefit future workstreams and other developers.

**Files:**
- Create: `skills/rival-retro/SKILL.md` (new directory + file)

**User Experience:**
```
> /rival:retro

  Analyzing workstream: async-carrier-callbacks-20260403

  Reading artifacts...
  - plan.md: 3 phases, 8 tasks
  - build-log.md: 8/8 tasks PASS
  - verification.md: PASS WITH NOTES

  Comparing against .rival/knowledge/...
  - codebase-patterns.md: last updated 2026-03-15

  Lessons extracted:

  New codebase patterns:
  + Service Bus: use message sessions with correlation ID for ordered processing
  + Callback endpoints: always add HMAC signature verification
  + Cross-repo DTOs: update shared-models first, then consumers

  New lessons learned:
  + 2026-04-03 (async-carrier-callbacks): Codex flagged missing retry logic on
    callback handler — always add retry with exponential backoff on external
    integration points
  + 2026-04-03 (async-carrier-callbacks): Phase 2 gate initially failed because
    rpm-gateway consumer wasn't reading from the correct Service Bus topic.
    Lesson: verify queue/topic names match across services before implementation.

  Agent performance:
  - Code Explorer: 67 tool calls (within LARGE budget of 100)
  - Researcher: found Service Bus sessions pattern — directly used in implementation
  - Auto-review (Codex): caught idempotency gap — good catch, included in plan

  Updated files:
  - .rival/knowledge/codebase-patterns.md (+3 entries)
  - .rival/knowledge/lessons-learned.md (+2 entries)

  Commit these to git? [Y/n]
```

**The skill must cover:**

1. **Resolve workstream** (standard priority)
2. **Read all artifacts** — plan.md, build-log.md, verification.md, git diff
3. **Read current knowledge** — .rival/knowledge/*.md
4. **Extract lessons** — three categories:
   - **Codebase patterns:** conventions discovered during this workstream that agents should know
   - **Lessons learned:** mistakes, surprises, review catches, things to do differently
   - **Agent performance:** how well the agents performed, what to improve (informational)
5. **Update knowledge files** — append new entries (don't replace existing)
6. **Present to user** — show what was extracted, let them edit before committing
7. **Update state** to `archived`

**Knowledge file format:**

`.rival/knowledge/codebase-patterns.md`:
```markdown
# Codebase Patterns
Last updated: 2026-04-03
Updated by workstream: async-carrier-callbacks-20260403

## Service Communication
- Service Bus: use message sessions with correlation ID for ordered processing
- Callback endpoints: always add HMAC signature verification

## Data Access
- EF Core: always include both Up() and Down() in migrations
- Shared DTOs: update shared-models repo first, then rebuild consumers

## Testing
- Integration tests: use TestServer with in-memory Service Bus emulator
```

`.rival/knowledge/lessons-learned.md`:
```markdown
# Lessons Learned

## 2026-04-03: async-carrier-callbacks
- Codex flagged missing retry logic on callback handler. Rule: always add retry
  with exponential backoff on external integration points.
- Phase 2 gate failed: queue/topic name mismatch across services. Rule: verify
  message contract (queue names, topic names) matches across all services before
  starting implementation.
- Researcher found Service Bus sessions pattern that was directly useful.
  Expert domains in config (service-bus) working as intended.
```

**Edge cases:**
- User runs retro before verify → allowed, reads whatever artifacts exist
- Knowledge files don't exist yet → create them with headers
- Knowledge files are getting too large (>200 lines) → agent should consolidate/summarize older entries rather than endlessly appending
- Duplicate lesson from previous workstream → detect and skip
- User rejects the commit → changes stay on disk but not committed

**Step 1: Create directory and write skills/rival-retro/SKILL.md**

```bash
mkdir -p skills/rival-retro
```

**Step 2: Write the skill file**

**Step 3: Commit**

```bash
git add skills/rival-retro/SKILL.md
git commit -m "feat(retro): add lessons-learned skill for persistent knowledge

New /rival:retro command extracts codebase patterns and lessons from
completed workstreams, writes to .rival/knowledge/ for future agents.
Committed to git so all team members benefit."
```

---

### Task 14: Create rival-research — NEW STANDALONE RESEARCH COMMAND

**Why:** Users often want to explore an idea, find best practices, or understand tradeoffs WITHOUT committing to an implementation plan. Currently they'd have to use `/rival:plan --discussion` which is overloaded. A dedicated `/rival:rival-research` command gives users a clean, focused research workflow that can optionally convert findings into a workstream.

**Files:**
- Create: `skills/rival-research/SKILL.md` (new directory + file)

**User Experience:**

```
> /rival:research How do I send back the results from the queue responses up to the frontend?

  Researching for your stack: C# / ASP.NET Core / Azure Service Bus

  Industry research...
    - SignalR for real-time push to frontend
    - Long polling from frontend with status endpoint
    - Server-Sent Events (SSE) for one-way streaming
    - WebSocket for bidirectional communication

  Expert domain research (azure, service-bus)...
    - Azure SignalR Service (managed, scales to millions)
    - Azure Web PubSub (lower level, more control)
    - Service Bus → Azure Function → SignalR hub pattern

  Codebase analysis...
    - Current frontend: React SPA, no real-time currently
    - Backend: ASP.NET Core controllers, no SignalR hubs exist
    - Service Bus consumers exist in carrier-service (pull model)

  ┌─────────────────────────────────────────────────────────────────┐
  │ Option 1: SignalR (Recommended)                                │
  ├─────────────────────────────────────────────────────────────────┤
  │ How: Service Bus consumer → SignalR hub → frontend JS client   │
  │ Pros: Real-time, native ASP.NET Core support, Azure managed    │
  │ Cons: New dependency, requires WebSocket support in infra       │
  │ Effort: MEDIUM (new hub + frontend client + consumer update)   │
  │ Azure cost: ~$50/mo for Standard tier                          │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │ Option 2: Polling Endpoint                                     │
  ├─────────────────────────────────────────────────────────────────┤
  │ How: Frontend polls GET /quotations/{id}/status every 5s       │
  │ Pros: Simple, no new infra, works behind any proxy             │
  │ Cons: Not real-time, wasted requests, 5s delay                 │
  │ Effort: LOW (new endpoint + frontend setInterval)              │
  │ Azure cost: None additional                                    │
  └─────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────┐
  │ Option 3: Server-Sent Events (SSE)                             │
  ├─────────────────────────────────────────────────────────────────┤
  │ How: Frontend opens SSE connection, backend pushes status       │
  │ Pros: Real-time, simpler than SignalR, HTTP-based              │
  │ Cons: One-way only, limited browser connection pool             │
  │ Effort: LOW-MEDIUM (new endpoint + EventSource on frontend)    │
  │ Azure cost: None additional                                    │
  └─────────────────────────────────────────────────────────────────┘

  Sources:
  - Microsoft Docs: Real-time ASP.NET Core with SignalR (URL)
  - Azure Architecture Center: Async messaging patterns (URL)
  - Martin Fowler: Event-Driven Architecture (URL)

  What would you like to do?
  1. Explore an option deeper (ask follow-up questions)
  2. Convert to a workstream → creates a /rival:plan with this research pre-loaded
  3. Create a ticket (requires .paths.md with DevOps config)
  4. Done — just wanted to learn
```

**The skill must cover:**

1. **Read config** — get stack, repos, experts
2. **Parse the question** — understand what they're asking about
3. **Spawn research agents** (parallel):
   - `rival:researcher` → industry patterns and best practices
   - `rival:expert-researcher` → deep docs for relevant expert domains
4. **Scan codebase** — quick code-explorer (LIGHT budget) to understand what exists relevant to the question
5. **Synthesize into options** — present 2-4 options with pros/cons/effort/cost
6. **Present with sources** — always include source URLs
7. **Offer next steps:**
   - Deep dive into one option
   - Convert to workstream (pre-loads research into `/rival:plan`)
   - Create a DevOps ticket (if `.paths.md` configured)
   - Done

**Converting research to a workstream:**
When the user picks an option and says "convert to workstream," the research findings get written to `.rival/workstreams/<id>/research-preload.md`. When `/rival:plan` detects this file exists for a workstream, it skips its own research phase and uses the pre-loaded findings instead. This avoids duplicate research.

**Edge cases:**
- Question is too vague → ask for clarification before researching
- No expert domains configured → just do industry research
- User asks about tech not in their stack → still research it, note it's not currently in use
- Multiple follow-up questions → maintain context within the conversation
- Research finds the codebase already has what the user is asking about → point it out

**Step 1: Create directory and write skills/rival-research/SKILL.md**

```bash
mkdir -p skills/rival-research
```

**Step 2: Write the skill file**

**Step 3: Commit**

```bash
git add skills/rival-research/SKILL.md
git commit -m "feat(research): add standalone research command

/rival:research for exploring ideas, finding best practices, comparing
options with pros/cons. Can convert findings to a workstream or DevOps ticket."
```

---

### Task 15: Update rival-status

**Why:** Update phase names and progress mapping for the new workflow. Remove references to blueprint/review phases.

**Files:**
- Modify: `skills/rival-status/SKILL.md`

**Key changes:**

1. **New phase mapping:**
   ```
   planning       → 2/8
   plan-ready     → 3/8
   plan-approved  → 4/8
   building       → 6/8
   build-complete → 7/8
   verifying      → 7/8
   archived       → 8/8
   ```

2. **Remove references to:** blueprinting, blueprint-ready, blueprint-approved, reviewing, review-ready, review-approved

3. **Update next-step suggestions:**
   - `plan-approved` → `/rival:execute`
   - `build-complete` → `/rival:verify`
   - `archived` → `/rival:retro` (if knowledge not updated yet)

4. **Show knowledge status:** "Last retro: 2026-04-03 (2 lessons)"

**Step 1: Update skills/rival-status/SKILL.md**

**Step 2: Commit**

```bash
git add skills/rival-status/SKILL.md
git commit -m "fix(status): update phase names and progress for v1.0 workflow

Remove blueprint/review phases, add retro step, update progress mapping."
```

---

### Task 16: Update rival-educate

**Why:** Update artifact references for the new workflow. The plan document now includes research findings and review notes (previously separate artifacts). Remove references to blueprint.md and review.md as separate files.

**Files:**
- Modify: `skills/rival-educate/SKILL.md`

**Key changes:**

1. **Update artifact list:** The key artifact is now `plan.md` which contains:
   - Research findings (previously not captured)
   - Review notes (previously in review.md, review-decisions.md)
   - Full implementation phases (previously split between plan.md and blueprint.md)

2. **Update topic list:**
   - Add `research` topic → explains what industry best practices were found and how they influenced the plan
   - Add `lessons` topic → explains what was learned from past workstreams

3. **Remove references to:** blueprint.md, review.md, review-decisions.md, tasks/*.md

4. **Update Section 4 (Review) to read from plan.md:** Review notes are now embedded in the plan under "## Review Notes" section, not in separate files.

**Step 1: Update skills/rival-educate/SKILL.md**

**Step 2: Commit**

```bash
git add skills/rival-educate/SKILL.md
git commit -m "fix(educate): update artifact references for v1.0 single-plan format

Plan.md now contains research, review notes, and full task breakdown.
Add research and lessons topics."
```

---

### Task 17: Delete Remaining Obsolete Agents

**Why:** Verify no stale agent files remain. After Tasks 4-9, the agents directory should contain exactly 6 files.

**Files to verify exist:**
- `agents/code-explorer.md` (updated in Task 6)
- `agents/pattern-detector.md` (updated in Task 8)
- `agents/security-analyzer.md` (updated in Task 7)
- `agents/skeptical-reviewer.md` (updated in Task 9)
- `agents/researcher.md` (created in Task 4)
- `agents/expert-researcher.md` (created in Task 5)

**Step 1: Verify directory contents**

```bash
ls agents/
# Should show exactly 6 files
```

**Step 2: If any stale files remain, delete them**

**Step 3: Commit (only if changes needed)**

```bash
git add agents/
git commit -m "chore: clean up agents directory — 6 agents for v1.0"
```

---

### Task 18: Meta Workflow for Building Agents — research-write-review Cycle

**Why:** Every agent in this plugin should be state-of-the-art, not a basic vanilla prompt. The meta workflow ensures that before writing any agent definition, we research the best techniques for that agent's domain, write the agent incorporating cutting-edge practices, then independently review it. This produces agents that are genuinely better than what any single pass would produce.

**Files:**
- Create: `docs/meta-workflow/research-phase.md`
- Create: `docs/meta-workflow/write-phase.md`
- Create: `docs/meta-workflow/review-phase.md`

**The three-file meta workflow:**

These are instruction documents that the builder (Claude Code) reads when constructing or upgrading an agent. They are NOT skills — they are reference docs for the implementation process.

#### `docs/meta-workflow/research-phase.md` — What to research before writing an agent

```markdown
# Meta Workflow: Research Phase

Before writing or upgrading an agent definition, research these areas:

## 1. Domain Best Practices
- What are the current industry best practices for this agent's domain?
- Example: For a "security-analyzer" agent, research:
  - Latest OWASP guidelines (are we on 2021 or has 2025 been released?)
  - SAST/DAST tool approaches and what they check
  - Real-world security review checklists from FAANG companies
  - Common false positives and how to avoid them

## 2. Academic/Expert Techniques
- Are there published techniques for this type of analysis?
- Example: For a "code-explorer" agent, research:
  - Program slicing techniques for dependency analysis
  - Call graph construction approaches
  - How LSP servers analyze code (similar to what we're doing manually)

## 3. Existing AI Agent Implementations
- How do other AI agent systems implement this capability?
- Search: "<domain> AI agent prompt" or "<domain> LLM agent technique"
- What prompt engineering techniques work best for this type of task?

## 4. Stack-Specific Considerations
- What are the specific challenges for different tech stacks?
- C# has different patterns than Python for the same type of analysis
- What tools/commands are available per stack?

## 5. Failure Modes
- What commonly goes wrong with this type of agent?
- What edge cases trip up automated analysis?
- How can the agent detect when it's in over its head?

## Output
Write research findings to: `.rival/workstreams/<id>/agent-research/<agent-name>.md`
This file feeds into the Write Phase.
```

#### `docs/meta-workflow/write-phase.md` — How to write the agent using research

```markdown
# Meta Workflow: Write Phase

Using the research findings, write the agent definition:

## 1. Incorporate Research Findings
- Every technique discovered in research should be considered for inclusion
- If a technique is too complex, note it as an "advanced mode" the agent CAN use
- Include specific commands, patterns, and approaches from research

## 2. Give the Agent Research Capability
- Where appropriate, give agents WebSearch or Context7 tools
- The agent should be able to do live research during execution
- Example: pattern-detector can search for "<framework> naming conventions"
  if it encounters a framework it doesn't have built-in knowledge about

## 3. Stack-Adaptive Instructions
- Agent should adapt its approach based on the stack it's analyzing
- Don't just have one process — have stack-specific branches
- Example: security-analyzer should check for C# deserialization risks
  in C# codebases but prototype pollution in Node.js codebases

## 4. Failure Recovery
- Include explicit instructions for when the agent gets stuck
- "If you can't find X after Y attempts, try Z instead"
- Budget-aware fallback strategies

## 5. Output Quality
- Include example output in the agent definition
- Show what a GOOD output looks like vs a BAD one
- Be specific about what "thorough" means for this agent
```

#### `docs/meta-workflow/review-phase.md` — Independent review of the agent

```markdown
# Meta Workflow: Review Phase

After writing the agent, get an independent review:

## Review Criteria

1. **Completeness:** Does the agent cover all the techniques found in research?
2. **Practicality:** Can the agent actually execute these techniques with its available tools?
3. **Edge cases:** Does the agent handle unusual codebases, languages, or project structures?
4. **Budget awareness:** Will the agent stay within tool call limits?
5. **Output quality:** Is the output format useful for downstream consumers?
6. **Stack coverage:** Does the agent work for C#, TypeScript, Python, Go, etc.?

## Review Process

Option A (Codex available):
  codex exec "Review this AI agent definition for quality and completeness.
  [paste agent definition]
  [paste research findings that informed it]
  Does this agent incorporate the research findings effectively?
  What techniques are missing? What could be improved?"
  --full-auto

Option B (Claude fallback):
  Spawn a skeptical-reviewer sub-agent with the agent definition + research findings.

## Iteration
If review finds gaps, update the agent and re-review.
Target: reviewer says "APPROVED" or "APPROVED WITH MINOR NOTES."
```

**Step 1: Create directory and write the three files**

```bash
mkdir -p docs/meta-workflow
```

**Step 2: Commit**

```bash
git add docs/meta-workflow/
git commit -m "feat: add meta workflow for research-write-review agent building

Three-phase process ensures every agent definition is built from
current best practices, not vanilla prompts. Research → Write → Review."
```

---

### Task 19: Research-Driven Agent Upgrades

**Why:** Apply the meta workflow (Task 18) to upgrade every agent in the plugin. Each agent should incorporate the latest techniques for its domain, have the ability to do live research when encountering unfamiliar stacks, and be reviewed independently.

**This task is executed in sub-steps, one per agent. For each agent:**

1. Run research phase (WebSearch for best techniques in that domain)
2. Rewrite the agent incorporating findings
3. Review the agent with Codex or skeptical-reviewer
4. Iterate if needed

**Agents to upgrade (in order):**

#### 19.1: Upgrade code-explorer
- Research: program analysis techniques, dependency tracing, call graph construction, best practices for multi-repo code navigation
- Key upgrade: add ability to search the web for unfamiliar framework conventions when encountered
- Review checkpoint

#### 19.2: Upgrade security-analyzer (now includes blast radius)
- Research: latest OWASP 2025 guidelines (if released), SAST tool approaches, real-world security checklists from security firms, blast radius analysis techniques, dependency graph analysis
- Key upgrade: add stack-specific vulnerability databases, reference current CVE patterns
- Review checkpoint

#### 19.3: Upgrade pattern-detector
- Research: code convention detection techniques, AST-based pattern matching approaches, how linters detect patterns
- Key upgrade: **add live research capability** — when the agent encounters a framework it doesn't have built-in knowledge for, it can WebSearch for "<framework> naming conventions" or "<framework> project structure best practices" and incorporate findings
- Tools: add WebSearch to this agent's tool list
- Review checkpoint

#### 19.4: Upgrade skeptical-reviewer
- Research: code review best practices from Google's engineering practices, adversarial testing techniques, common review blindspots
- Key upgrade: incorporate specific review checklists from industry (Google's "What to Look For in a Code Review")
- Review checkpoint

#### 19.5: Upgrade researcher
- Research: best practices for AI-assisted research, how to evaluate source quality, techniques for synthesizing conflicting information
- Key upgrade: source quality scoring, conflict detection, structured comparison output
- Review checkpoint

#### 19.6: Upgrade expert-researcher
- Research: best practices for technical documentation navigation, how to extract actionable patterns from API docs
- Key upgrade: framework-specific search strategies (Azure docs have a different structure than AWS docs)
- Review checkpoint

**Step 1-6: For each agent, run the meta workflow cycle**

Each sub-step produces a commit:

```bash
git commit -m "feat(agents): research-upgrade code-explorer with program analysis techniques"
git commit -m "feat(agents): research-upgrade security-analyzer with OWASP 2025 + blast radius"
git commit -m "feat(agents): research-upgrade pattern-detector with live research capability"
git commit -m "feat(agents): research-upgrade skeptical-reviewer with Google review practices"
git commit -m "feat(agents): research-upgrade researcher with source quality scoring"
git commit -m "feat(agents): research-upgrade expert-researcher with framework-specific strategies"
```

---

### Task 20: Azure DevOps Integration Placeholder

**Why:** The user has a script on their work laptop that pulls repos, downloads wikis, and accesses Azure DevOps boards. This task creates the placeholder structure and documentation so that script can be integrated later.

**Files:**
- Create: `docs/devops-integration.md` — documentation for the integration
- Create: `scripts/setup-devops.sh` — placeholder setup script (will be replaced with real one)

**The documentation must cover:**

1. **`.paths.md` format** — full specification of the file format (already defined in Task 3)
2. **Repo cloning** — how the setup script will clone repos from Azure DevOps or GitHub using PATs
3. **Wiki access** — how agents can read wiki pages for additional context during planning
4. **Board integration** — how `/rival:research` can create tickets from research findings
5. **Ticket creation format** — what fields to populate (title, description, area, iteration, acceptance criteria)

**Placeholder setup script (`scripts/setup-devops.sh`):**

```bash
#!/bin/bash
# Rival DevOps Setup Script
# This script will be replaced with the full version from the user's work laptop.
#
# What it will do:
# 1. Prompt for Azure DevOps PAT
# 2. Prompt for organization URL and project
# 3. Clone all configured repos
# 4. Download wiki content
# 5. Write .paths.md with all configuration
# 6. Add .paths.md to .gitignore
#
# For now, this is a placeholder. See docs/devops-integration.md for the full spec.

echo "Rival DevOps Setup — Placeholder"
echo "Replace this script with the full version from your work environment."
echo ""
echo "Manual setup:"
echo "1. Create .paths.md in your project root (see docs/devops-integration.md)"
echo "2. Add .paths.md to .gitignore"
echo "3. Run /rival:init to detect the configuration"
```

**Step 1: Create docs and script**

```bash
mkdir -p scripts
```

**Step 2: Write docs/devops-integration.md and scripts/setup-devops.sh**

**Step 3: Commit**

```bash
git add docs/devops-integration.md scripts/setup-devops.sh
git commit -m "feat: add Azure DevOps integration placeholder and documentation

Placeholder for repo cloning, wiki access, and board integration.
Full script will be added from work laptop. See docs/devops-integration.md."
```

---

### Task 21: Auto-Versioning with GitHub Actions

**Why:** The plugin version should update automatically when changes are pushed, so users always see the current version when they install it. No manual version bumping.

**Files:**
- Create: `.github/workflows/version-bump.yml`

**How it works:**

A GitHub Action runs on every push to `main`. It:
1. Reads commit messages since last tag
2. Determines version bump type (major/minor/patch) from conventional commit prefixes:
   - `feat:` → minor bump (1.0.0 → 1.1.0)
   - `fix:` → patch bump (1.0.0 → 1.0.1)
   - `feat!:` or `BREAKING CHANGE:` → major bump (1.0.0 → 2.0.0)
   - `chore:`, `docs:` → no bump
3. Updates version in: `package.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
4. Commits the version bump
5. Creates a git tag

**The workflow file:**

```yaml
name: Auto Version Bump

on:
  push:
    branches: [main]
    paths:
      - 'skills/**'
      - 'agents/**'
      - 'frameworks/**'

jobs:
  version-bump:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Determine version bump
        id: bump
        run: |
          LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
          COMMITS=$(git log ${LAST_TAG}..HEAD --pretty=format:"%s")

          if echo "$COMMITS" | grep -qE "^feat!:|BREAKING CHANGE:"; then
            echo "bump=major" >> $GITHUB_OUTPUT
          elif echo "$COMMITS" | grep -qE "^feat(\(.*\))?:"; then
            echo "bump=minor" >> $GITHUB_OUTPUT
          elif echo "$COMMITS" | grep -qE "^fix(\(.*\))?:"; then
            echo "bump=patch" >> $GITHUB_OUTPUT
          else
            echo "bump=none" >> $GITHUB_OUTPUT
          fi

      - name: Bump version
        if: steps.bump.outputs.bump != 'none'
        run: |
          BUMP=${{ steps.bump.outputs.bump }}
          CURRENT=$(jq -r .version package.json)
          IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

          case $BUMP in
            major) MAJOR=$((MAJOR+1)); MINOR=0; PATCH=0 ;;
            minor) MINOR=$((MINOR+1)); PATCH=0 ;;
            patch) PATCH=$((PATCH+1)) ;;
          esac

          NEW="${MAJOR}.${MINOR}.${PATCH}"
          echo "Bumping $CURRENT → $NEW ($BUMP)"

          # Update all three files
          jq --arg v "$NEW" '.version = $v' package.json > tmp.json && mv tmp.json package.json
          jq --arg v "$NEW" '.version = $v' .claude-plugin/plugin.json > tmp.json && mv tmp.json .claude-plugin/plugin.json
          jq --arg v "$NEW" '.plugins[0].version = $v' .claude-plugin/marketplace.json > tmp.json && mv tmp.json .claude-plugin/marketplace.json

          echo "new_version=$NEW" >> $GITHUB_OUTPUT

      - name: Commit and tag
        if: steps.bump.outputs.bump != 'none'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
          git commit -m "chore: bump version to ${{ steps.bump.outputs.new_version }}"
          git tag "v${{ steps.bump.outputs.new_version }}"
          git push && git push --tags
```

**Step 1: Create the workflow directory and file**

```bash
mkdir -p .github/workflows
```

**Step 2: Write the workflow file**

**Step 3: Commit**

```bash
git add .github/workflows/version-bump.yml
git commit -m "ci: add auto-versioning GitHub Action

Automatically bumps version on push to main based on conventional commits.
Updates package.json, plugin.json, and marketplace.json."
```

---

### Task 22: Final Verification — v1.0

**Why:** Final verification and version tag.

**Step 1: Verify complete file structure**

```bash
find . -type f -not -path './.git/*' | sort
```

Expected:
```
./.claude-plugin/marketplace.json
./.claude-plugin/plugin.json
./.github/workflows/version-bump.yml
./agents/code-explorer.md
./agents/expert-researcher.md
./agents/pattern-detector.md
./agents/researcher.md
./agents/security-analyzer.md
./agents/skeptical-reviewer.md
./docs/devops-integration.md
./docs/meta-workflow/research-phase.md
./docs/meta-workflow/review-phase.md
./docs/meta-workflow/write-phase.md
./docs/plans/2026-04-03-rival-v1-rewrite.md
./frameworks/adr.md
./frameworks/bdd.md
./frameworks/c4-model.md
./frameworks/ddd.md
./frameworks/event-storming.md
./frameworks/tdd.md
./package.json
./scripts/setup-devops.sh
./skills/rival-educate/SKILL.md
./skills/rival-execute/SKILL.md
./skills/rival-init/SKILL.md
./skills/rival-plan/SKILL.md
./skills/rival-research/SKILL.md
./skills/rival-retro/SKILL.md
./skills/rival-status/SKILL.md
./skills/rival-verify/SKILL.md
```

**Step 2: Verify all skill frontmatter is correct**

Each skill file must have proper frontmatter:
```yaml
---
name: rival-<name>
description: <one-line description>
user-invocable: true
argument-hint: <if applicable>
---
```

**Step 3: Grep for stale references**

```bash
grep -r "gemini" skills/ agents/ --include="*.md" -i
# Should return 0 results

grep -r "blueprint" skills/ agents/ --include="*.md" -i
# Should return 0 results (except this plan doc)

grep -r "rival-build" skills/ agents/ --include="*.md" -i
# Should return 0 results

grep -r "rival-review" skills/ agents/ --include="*.md" -i
# Should return 0 results (except mentions of auto-review within plan)
```

**Step 4: Create git tag**

```bash
git tag -a v1.0.0 -m "Rival v1.0.0 — Research-backed planning, multi-repo, persistent learning"
```

---

## Dependency Order

```
Task 1  (delete old files)           — no dependencies
Task 2  (package metadata)           — no dependencies
Task 3  (rival-init)                 — after Task 1 (clean slate)
Task 4  (researcher agent)           — no dependencies
Task 5  (expert-researcher agent)    — no dependencies
Task 6  (code-explorer agent)        — no dependencies
Task 7  (security-analyzer agent)    — no dependencies
Task 8  (pattern-detector agent)     — no dependencies
Task 9  (skeptical-reviewer)         — no dependencies
Task 10 (rival-plan)                 — after Tasks 3-9 (references all agents)
Task 11 (rival-execute)              — after Task 10 (references plan format)
Task 12 (rival-verify)               — after Task 9 (references skeptical-reviewer)
Task 13 (rival-retro)                — after Task 3 (references knowledge dir)
Task 14 (rival-research)             — after Tasks 4-5 (uses research agents)
Task 15 (rival-status)               — after Task 10 (references new phases)
Task 16 (rival-educate)              — after Task 10 (references new plan format)
Task 17 (verify agents)              — after Tasks 4-9
Task 18 (meta workflow docs)         — no dependencies
Task 19 (research-upgrade agents)    — after Tasks 4-9 AND Task 18 (needs agents + meta workflow)
Task 20 (devops placeholder)         — after Task 3 (references .paths.md from init)
Task 21 (auto-versioning)            — no dependencies
Task 22 (final verification)         — after all tasks
```

**Parallelizable groups:**
- Group A (independent): Tasks 1, 2, 4, 5, 6, 7, 8, 9, 18, 21
- Group B (after Group A): Tasks 3, 10, 17, 19
- Group C (after Task 10): Tasks 11, 12, 13, 14, 15, 16, 20
- Group D (final): Task 22

---

## Success Criteria

1. All 8 slash commands work: init, plan, execute, verify, retro, research, status, educate
2. `--light` mode produces a quick plan without research or auto-review
3. `--discussion` mode produces analysis without execution plan
4. `/rival:research` produces structured options with pros/cons and can convert to workstream
5. Multi-repo: init configures multiple repos (local + Azure DevOps), plan explores across them
6. `.paths.md` integration: init detects and reads DevOps configuration
7. Codex review: plan auto-reviews with Codex, verify uses Codex — **no timeouts**, let Codex run
8. Fallback: skeptical-reviewer works when Codex is unavailable
9. Knowledge: retro writes to .rival/knowledge/, plan reads from it
10. Fresh context: execute reads plan from disk with no prior conversation
11. No references to Gemini, blueprint, or build (classic path) anywhere in the codebase
12. Framework docs (frameworks/) still present and loadable by plan agent
13. Meta workflow docs exist for research-write-review agent building cycle
14. All 6 agents have been research-upgraded using the meta workflow
15. Auto-versioning GitHub Action bumps version on push to main
16. DevOps integration placeholder exists with full specification for future script
