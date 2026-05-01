# Rival

**A Claude Code plugin for production-grade development workflows.**

Rival turns the loose, ad-hoc loop of "ask Claude to build a feature" into a disciplined sequence: **research → plan → execute → verify → learn**. Each step writes durable artifacts to disk, each step can be replayed in a fresh session, and a second model (Codex CLI, with a Claude fallback) is used as an adversarial reviewer so the planner is never marking its own homework.

It is built for **multi-repo workspaces** (typical of teams with many service repos and a wiki) but works on a single repo too.

---

## What problem does it solve?

The default Claude Code experience excels at small, in-context tasks. It struggles when:

- The work spans **many repos** that depend on each other.
- The user wants the model to **research best practices** before committing to an approach.
- Plans need to **survive a context reset** so execution can start in a clean session.
- A **second opinion** is required before code is merged.
- Lessons from past work should **carry forward** instead of being re-learned every time.

Rival addresses each of these explicitly.

---

## Mental model

The plugin centers on a **workstream** — a named unit of work with a slugified ID (e.g. `add-async-callbacks-20260501`). Each workstream moves through phases:

```
init  →  plan  →  execute  →  verify  →  retro
                    ↑                       │
                    └───── learning ────────┘
```

| Phase    | Skill (slash command)                | What it produces                                                       |
| -------- | ------------------------------------ | ---------------------------------------------------------------------- |
| init     | `/rival:rival-init`                  | `.rival/config.json` — workspace index, expert domains, review tool    |
| research | `/rival:rival-research`              | (optional) standalone research, can convert into a workstream preload  |
| plan     | `/rival:rival-plan <feature>`        | `plan.md` — a self-contained execution plan with Before/After code     |
| execute  | `/rival:rival-execute [workstream]`  | feature branches + commits across affected repos                       |
| verify   | `/rival:rival-verify [workstream]`   | adversarial review (Codex or Claude) of the actual diff vs the plan    |
| retro    | `/rival:rival-retro [workstream]`    | extracted patterns + lessons appended to `.rival/learning/`            |

Side commands cover ad-hoc needs: `/rival:rival-investigate` (senior-engineer Q&A), `/rival:rival-review-code` (dual-reviewer code review), `/rival:rival-status` (workstream dashboard), `/rival:rival-educate` (plain-English walkthrough), `/rival:rival-team-status` (team activity brief).

---

## High-level architecture

```
┌──────────────────────────── User ────────────────────────────┐
│                                                              │
│      /rival:rival-plan "Add async carrier callbacks"         │
│                            │                                 │
└────────────────────────────┼─────────────────────────────────┘
                             ▼
┌──────────── Skills (orchestrators, user-invocable) ──────────┐
│  rival-init │ rival-research │ rival-plan │ rival-execute    │
│  rival-verify │ rival-retro │ rival-investigate │ ...        │
└──────────────────────────┬───────────────────────────────────┘
                           │ dispatch via Agent tool
                           ▼
┌────────── Agents (specialists, NOT user-invocable) ──────────┐
│  researcher           — industry / web research              │
│  expert-researcher    — domain-specific deep dives           │
│  pattern-detector     — codebase conventions + divergences   │
│  code-explorer        — cross-repo symbol & file discovery   │
│  security-analyzer    — blast-radius & security risk         │
│  skeptical-reviewer   — Claude-side adversarial reviewer     │
│  team-narrative-writer — engineering brief author            │
└──────────────────────────┬───────────────────────────────────┘
                           │ each agent writes its output to
                           ▼
              .rival/workstreams/<id>/agent-outputs/
              ├── 01-researcher.md
              ├── 02-expert-researcher-<domain>.md
              ├── 03-pattern-detector.md
              ├── 04-code-explorer.md
              └── 05-security-analyzer.md
                           │
                           ▼
                .rival/workstreams/<id>/plan.md
                  (synthesized self-contained plan)
                           │
                           ▼
                  approval → execute → verify
                           │
                           ▼
                .rival/learning/  (persistent patterns + lessons)
```

### The three component types

| Component   | Lives in           | Role                                                                                                  |
| ----------- | ------------------ | ----------------------------------------------------------------------------------------------------- |
| **Skills**  | `skills/<name>/SKILL.md` | User-facing slash commands. They orchestrate — they read state, dispatch agents, write artifacts. |
| **Agents**  | `agents/<name>.md` | Specialists invoked by skills via the `Agent` tool. They do not run independently.                    |
| **Scripts** | `scripts/`         | Out-of-process helpers (Python/Bash) for things skills shouldn't do directly — e.g. cloning many repos, exporting wikis, generating PDFs. |

The plugin manifest at `.claude-plugin/plugin.json` is intentionally tiny — Claude Code auto-discovers `skills/`, `agents/`, and `scripts/` from the directory layout.

---

## How a single workstream flows

This is the canonical happy path through `/rival:rival-plan`:

1. **Read config** (`.rival/config.json`) — identifies the indexed repos, configured expert domains, and review tool.
2. **Pick a primary repo** — interactively, based on the feature description.
3. **Trace dependencies** — read project files (`*.csproj`, `package.json`, etc.) to discover which connected repos may need to change.
4. **Ask 3–5 clarifying questions** — scope boundary, success criteria, integration points, edge cases. Answers become the *enriched feature description* passed to every downstream agent.
5. **Triage** — classify as `LIGHT`, `MEDIUM`, or `LARGE` (or `DISCUSSION`).
6. **Research in parallel** — `researcher` + per-domain `expert-researcher` agents fan out, each writing a numbered file under `agent-outputs/`.
7. **Analyse the codebase sequentially** — `pattern-detector` → `code-explorer` → `security-analyzer`. Each agent reads the prior agents' outputs from disk, so context compounds without bloating any single agent's prompt.
8. **Synthesize** — the orchestrator reads every file in `agent-outputs/` and writes `plan.md`. The plan includes a system map, current/target code, per-task Before/After snippets, phase gates, and a validation plan.
9. **Auto-review** — `codex exec` is invoked headlessly to read the plan and verify it against the actual codebase. If Codex isn't installed, the `skeptical-reviewer` agent runs instead.
10. **Human gate** — the user approves, revises, or rejects.

Once approved, `/rival:rival-execute` reads `plan.md` from disk in a fresh context. It creates a coordinated branch set across affected repos (`feature/<workstream-id>` on the primary, `chore/<workstream-id>` on connected repos), dispatches sub-agents to implement each task, runs the phase gates between phases, and records commit ranges back into `state.json`.

`/rival:rival-verify` then re-reads the plan and the actual diff per repo, hands both to Codex (or the fallback reviewer), and asks: *did the build match the plan?*

`/rival:rival-retro` mines the artifacts of a finished workstream and appends new patterns / lessons to `.rival/learning/`, where they are read by future planning runs.

---

## Filesystem layout (post-init)

```
<workspace-root>/                  ← Claude Code is opened here
├─ .env                             ADO PAT + org/project (gitignored)
├─ .gitignore
├─ knowledge/                       Created by export-ado-knowledge.py
│  ├─ repos/                        Every cloned repo — flat, one level deep
│  ├─ wikis/                        Exported markdown + assets
│  └─ summary.json                  Index of everything that was downloaded
└─ .rival/
   ├─ config.json                   Single source of truth for all skills
   ├─ workstreams/
   │  └─ <id>/
   │     ├─ state.json              Phase, primary/connected repos, build commits
   │     ├─ agent-outputs/          One numbered file per agent
   │     ├─ plan.md                 Self-contained execution plan
   │     ├─ build-log.md
   │     ├─ verification.md
   │     └─ review-decisions.md
   ├─ learning/
   │  ├─ codebase-patterns.md       Conventions discovered across workstreams
   │  └─ lessons-learned.md         Mistakes / surprises / things to avoid
   ├─ investigations/               Reports from /rival:rival-investigate
   └─ reviews/                      Reports from /rival:rival-review-code
```

`config.json` deliberately holds **paths only, never secrets**. The Azure DevOps PAT lives in `.env` and is read on demand by the export script.

---

## Design choices worth noting

A few decisions are load-bearing — understanding them explains the rest of the system:

1. **The plan is self-contained.** Anything in `plan.md` must be readable by a fresh Claude session with zero conversation history. That is why each task carries its own Before/After code, file paths, and test commands. This decoupling is what makes adversarial review by a *different model* possible.

2. **Agents communicate through files, not return values.** Each agent writes its full findings to a numbered Markdown file under `agent-outputs/`. The orchestrator reads them verbatim during synthesis. Summaries are returned as a courtesy but are never load-bearing.

3. **Sequential analysis, parallel research.** Researchers run in parallel because their outputs are independent. Code analysers run sequentially (`pattern-detector → code-explorer → security-analyzer`) because each one reads and reasons about the previous one's output.

4. **Two reviewer paths, never a single point of failure.** If Codex CLI is installed, it is the primary reviewer (cross-model adversarial). If it is missing or fails, the in-plugin `skeptical-reviewer` agent takes over. The user always gets a review.

5. **No `OPENAI_API_KEY` plumbing.** Codex CLI uses its own auth (`codex auth login`). The plugin never reads or stores OpenAI credentials.

6. **Multi-repo branching is coordinated.** Every branch across every affected repo carries the same workstream ID suffix (`feature/<id>`, `chore/<id>`), so a future engineer can find the full set with one grep across all repos.

7. **Roles are not declared, they are discovered.** Init does not ask the user to label each repo's purpose. Roles emerge during planning via dependency tracing — `connector-api` references `shared-models` via a `ProjectReference`, so `shared-models` becomes a connected repo for that workstream only.

8. **Learning is opt-in but durable.** `.rival/learning/` starts empty. `/rival:rival-retro` is the only writer. Each future planning run reads it before the research phase, so insights compound without re-running expensive scans.

---

## Quick start

```bash
# 1. Install the plugin into Claude Code (from a marketplace or the github source).
# 2. Open Claude Code in your intended workspace root (can be empty).
# 3. Initialize:
/rival:rival-init

# Init walks you through:
#   - Connecting to Azure DevOps (PAT, org, project)
#   - Pulling all repos + wikis into ./knowledge/
#   - Indexing languages, frameworks, expert domains
#   - Detecting Codex CLI for adversarial review
#   - Writing .rival/config.json

# 4. Plan a feature:
/rival:rival-plan "Add idempotent webhook callbacks for carrier integrations"

# 5. Approve, then in a fresh session:
/rival:rival-execute

# 6. Verify the build:
/rival:rival-verify

# 7. Capture lessons for future workstreams:
/rival:rival-retro
```

You can also use the standalone exploratory commands at any time:

- `/rival:rival-research <topic>` — explore without committing to a plan.
- `/rival:rival-investigate <question>` — senior-engineer Q&A across the codebase.
- `/rival:rival-review-code [--branch | --commits | --pr | --files]` — dual-reviewer code review.
- `/rival:rival-status` — list every workstream and its phase.
- `/rival:rival-educate` — plain-English walkthrough of the current workstream.

---

## Requirements

- **Claude Code** (CLI, IDE extension, or desktop app).
- **Python 3** — required for the Azure DevOps export script.
- **git** — required for cloning repos.
- **Codex CLI** *(optional but recommended)* — second model for adversarial review. If not present, the in-plugin `skeptical-reviewer` agent is used.
- An **Azure DevOps Personal Access Token** with Code (Read), Wiki (Read), Work Items (Read & Write) scopes — only needed if you use the ADO integration.

---

## Repository layout

```
rival_plugin/
├─ .claude-plugin/
│  ├─ plugin.json          Plugin manifest (name, version, description)
│  └─ marketplace.json     Marketplace listing
├─ skills/                  User-invocable orchestrators
│  ├─ rival-init/SKILL.md
│  ├─ rival-plan/SKILL.md
│  ├─ rival-research/SKILL.md
│  ├─ rival-execute/SKILL.md
│  ├─ rival-verify/SKILL.md
│  ├─ rival-retro/SKILL.md
│  ├─ rival-investigate/SKILL.md
│  ├─ rival-review-code/SKILL.md
│  ├─ rival-status/SKILL.md
│  ├─ rival-educate/SKILL.md
│  └─ rival-team-status/SKILL.md
├─ agents/                  Specialists (not user-invocable)
│  ├─ researcher.md
│  ├─ expert-researcher.md
│  ├─ pattern-detector.md
│  ├─ code-explorer.md
│  ├─ security-analyzer.md
│  ├─ skeptical-reviewer.md
│  └─ team-narrative-writer.md
├─ scripts/                 Out-of-process helpers
│  ├─ export-ado-knowledge.py    Clones all ADO repos + exports wikis
│  ├─ ado-fetch.py               Light ADO fetch helpers
│  ├─ team-status.py             Pulls team activity for /rival-team-status
│  ├─ team-status-pdf.py         Renders the team brief as a PDF
│  └─ setup-devops.sh            One-shot DevOps bootstrapping
├─ docs/
│  ├─ ARCHITECTURE.md            Deeper architectural notes
│  ├─ devops-integration.md      How ADO integration is wired
│  ├─ meta-workflow/             Internal notes on research/review/write loop
│  └─ plans/                     Historical design plans for the plugin itself
└─ .github/workflows/
   └─ version-bump.yml           CI for releases
```

---

## License

MIT.
