# Rival Architecture

This document is a deeper companion to the top-level [README.md](../README.md). It assumes you have read the README and want to understand *why* the plugin is shaped the way it is.

It deliberately stays at an architectural level — no internal repo names, no organization-specific configuration. Use placeholders (`<your-org>`, `<your-project>`, `<repo-name>`) when mapping it to your environment.

---

## 1. The five-phase loop

The system is organised around a single recurring loop:

```
        ┌─────────────────────────────────────────────────────┐
        │                                                     │
        ▼                                                     │
   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┴──┐
   │  PLAN    │───▶│ EXECUTE  │───▶│  VERIFY  │───▶│    RETRO    │
   └──────────┘    └──────────┘    └──────────┘    └─────────────┘
        ▲                                                     │
        │                                                     │
        └──────── reads .rival/learning/ ─────────────────────┘
```

`init` precedes the loop (one-time configuration). `research` and `investigate` are side-paths that can feed into a workstream or stand alone.

Each phase has an explicit handoff artifact written to disk:

| Phase   | Reads                                                          | Writes                                                             |
| ------- | -------------------------------------------------------------- | ------------------------------------------------------------------ |
| init    | the workspace, optionally Azure DevOps                         | `.rival/config.json`, `.rival/learning/*.md` (placeholders)        |
| plan    | config, prior `learning/`, codebase                            | `agent-outputs/*.md`, `plan.md`, `state.json`                      |
| execute | `plan.md`, `state.json`                                        | branches + commits across repos, `state.build.commits` per repo    |
| verify  | `plan.md`, the actual git diff per repo                        | `verification.md`, `review-decisions.md`                           |
| retro   | every artifact in `.rival/workstreams/<id>/`                   | appended entries in `.rival/learning/*.md`                         |

Because every handoff is on disk, any phase can be **resumed in a fresh Claude Code session**. This is not incidental — it's the whole point.

---

## 2. Why a self-contained plan

The plan document (`.rival/workstreams/<id>/plan.md`) is built to satisfy one constraint:

> A fresh Claude Code session, with zero conversation history, must be able to read this file and execute the work.

Concretely, that means each task in the plan must include:

- Which repo it belongs to
- The exact files it creates or modifies
- A `Before` snippet (current code, or `N/A — new file`)
- An `After` snippet (target code or unambiguous pseudocode)
- The test commands that verify it
- The downstream effects on other files or services

This shape unlocks two important properties:

1. **Execution can be a different process from planning.** The user is encouraged to clear context between `/rival:rival-plan` and `/rival:rival-execute`. The executor has no opinions of its own about the design — it implements what the plan says.

2. **The reviewer can be a different model.** Codex CLI (or the Claude `skeptical-reviewer` agent) reads the same `plan.md` and can evaluate it without inheriting the planner's biases. The plan is the spec; both planner and reviewer reference it from disk.

This is the same property as a written API contract: it lets two parties cooperate without a shared mental state.

---

## 3. Skills vs Agents

A common pitfall in Claude Code plugin design is putting too much in a single mega-prompt. Rival splits responsibilities cleanly:

| Aspect                | Skill (`skills/<name>/SKILL.md`)                       | Agent (`agents/<name>.md`)                                            |
| --------------------- | ------------------------------------------------------ | --------------------------------------------------------------------- |
| User-invocable?       | Yes (slash command)                                    | No — only spawned by skills                                           |
| Runs in main context? | Yes — *is* Claude in the current conversation          | No — spawned via the `Agent` tool with its own context                |
| Has tools?            | All tools available to the user                        | Tools listed in YAML frontmatter (e.g. `Read`, `Grep`, `Glob`, `Bash`) |
| Persists across runs? | No — it is the orchestration layer                     | No — but writes durable output files                                  |
| Knows about user?     | Yes — interacts directly                               | No — receives a prompt with all context inlined                       |

This separation is what allows research agents to fan out in parallel without polluting the orchestrator's context, and what allows code-analysis agents to compound knowledge sequentially via shared output files.

---

## 4. The agent-outputs protocol

When an orchestrator (skill) dispatches an agent, the agent's prompt always includes:

- **The Feature Request (NORTH STAR)** — the verbatim, possibly clarified, original feature request. This is the agent's anchor.
- **The Output Path** — an absolute file path under `.rival/workstreams/<id>/agent-outputs/` where the agent must write its full findings using the `Write` tool.
- **Prior Agent Outputs** — absolute paths to previous agents' files, with an instruction to read them first.

The convention is numeric prefixes:

```
01-researcher.md
02-expert-researcher-<domain>.md     (one per expert domain)
03-pattern-detector.md
04-code-explorer.md
05-security-analyzer.md
```

The agent returns a 3–5 line summary to the orchestrator. The orchestrator does **not** rely on that summary when synthesising the plan — it reads the full files. This deliberately avoids loss-of-fidelity.

This is the closest the plugin has to an internal API. Agents could be swapped or upgraded as long as they honour this protocol.

---

## 5. Workstream resolution

Several skills (`execute`, `verify`, `retro`, `educate`) accept an optional workstream argument. They all use the same resolution priority:

1. If `$ARGUMENTS` contains a workstream name, use it directly.
2. Otherwise, scan `.rival/workstreams/*/state.json` for active workstreams matching the expected phase (e.g. `plan-approved` for `execute`, `build-complete` for `verify`).
3. If exactly one matches, auto-select it.
4. If multiple match, ask the user.
5. If none match, guide the user to the correct prior step.

Because every state transition is a write to `state.json`, the system is fully introspectable — `/rival:rival-status` does nothing more than glob the directory and read the files.

---

## 6. Multi-repo coordination

This is one of the more subtle parts of the design.

### Init time

After cloning repos into `./knowledge/repos/`, init scans every repo's project files (`package.json`, `*.csproj`, `pyproject.toml`, `go.mod`, `Cargo.toml`, etc.) and records each repo's:

- `language` (e.g. `csharp`, `typescript`)
- `framework` (e.g. `aspnet-core`, `next`, `fastapi`)
- `test_framework`
- `orm`
- `runtime`

This is stored in `config.json` under `index.repos[]` as a flat list. There is no top-level `stack` field — stack info lives **per repo**, because a multi-repo workspace is heterogeneous by definition.

Init does **not** ask the user to label each repo's role (e.g. "API gateway", "auth service"). With dozens or hundreds of repos that would be unbearable, and roles change anyway. Roles are discovered dynamically at planning time.

### Plan time

When the user describes a feature, the planner asks them to pick a **primary repo**. From there it traces dependencies:

- `*.csproj` `<ProjectReference>` to other indexed repos
- `package.json` workspace or `file:` dependencies
- Direct import paths that cross repo boundaries
- Docker Compose, CI, or infra files referencing other services

Two levels deep. The result is a small set of **connected repos** for this specific workstream. All other repos remain in the index as a *search reference*, not an exploration target.

### Execute time

For every repo with at least one task in the plan, the executor creates a branch:

- `feature/<workstream-id>` on the primary repo
- `chore/<workstream-id>` on each connected repo with tasks

Repos in the connected set with **no** tasks (search-only) get no branch. The shared `<workstream-id>` suffix is the cross-repo coordination key — `git for-each-ref refs/heads | grep <workstream-id>` finds the full set across every repo.

The executor records first/last commit hashes and a count per repo into `state.build.commits`, so verify and retro never have to grep git logs to find what changed.

---

## 7. The two-reviewer system

For code review (`/rival:rival-review-code`) the plugin ships a deliberate dual-lens approach:

- **Architect** — looks at correctness, fit, integration with existing patterns.
- **Adversary** — looks at security, edge cases, failure modes.

They run in parallel and produce independent reports. The orchestrator synthesises both into a single report with attribution, so the user can see which reviewer flagged which issue.

For plan review (`/rival:rival-verify`) the philosophy is different — there is one review, but it is from a different model. Codex is preferred specifically because using a non-Anthropic model surfaces a different class of issues than self-review.

---

## 8. The Azure DevOps integration

Azure DevOps integration is opt-in but, when enabled, is the primary onboarding path. Init uses `scripts/export-ado-knowledge.py` to:

1. Test the user's PAT against the configured organization and project.
2. Clone every accessible Git repo into `./knowledge/repos/`.
3. Export every wiki page (with assets) into `./knowledge/wikis/`.
4. Write a `summary.json` index.

The credentials live in `.env`, never in `config.json`. `config.json` records only `pat_configured: true/false` and the organization/project names. This cleanly separates secrets from configuration so `config.json` can be committed if a team chooses.

When the user opts out, `devops` is set to `null` in the config and the plugin runs against whatever repos are already present in the workspace.

---

## 9. The learning loop

`/rival:rival-retro` is the only writer to `.rival/learning/`. It reads:

- `plan.md`
- `build-log.md`
- `verification.md`
- The actual git diff for the workstream's branches

…and extracts entries in three categories:

- **Codebase Patterns** — conventions and structural decisions that future planning runs should respect.
- **Lessons Learned** — mistakes, surprises, things caught in review, things to do differently.
- **Domain Insights** — discoveries about the business domain or external systems.

`/rival:rival-plan` reads these files at the start of every new workstream (Phase 3.2) and surfaces relevant entries in the plan's "Lessons Applied" section. Over time, the planner becomes opinionated in ways that match the team's actual codebase, not generic best practices.

This is intentionally low-tech: plain Markdown files, manually curatable, easy to inspect and version-control.

---

## 10. Failure modes and fallbacks

The plugin has explicit fallbacks at the points most likely to fail:

| Failure                              | Fallback                                                               |
| ------------------------------------ | ---------------------------------------------------------------------- |
| Codex CLI not installed              | `skeptical-reviewer` agent (Claude self-review)                        |
| Codex CLI installed but auth fails   | `skeptical-reviewer` agent, with a warning                             |
| Python 3 not installed               | Skip ADO integration, scan workspace as-is                             |
| `summary.json` missing post-pull     | Fall back to glob-scanning `./knowledge/repos/` directly               |
| `state.build.commits` missing        | Grep recent commits for the workstream-id sentinel embedded in messages |
| Research agent returns empty         | Note "no industry research found" in the plan, proceed                  |
| Plan references missing repo        | Warn and skip that repo, do not abort                                  |
| User-supplied PAT has wrong scopes  | Test connection fails fast with a clear error                          |

The general principle: **degrade visibly, never silently**.

---

## 11. What this plugin deliberately does *not* do

A few non-goals worth stating, because they shape the rest of the design:

- **It does not maintain a long-running daemon.** Every skill runs in the user's session and exits.
- **It does not store secrets in any artifact other than `.env`.** Even commit messages and state files are scrubbed.
- **It does not require any cloud service the user does not already use.** Codex is local CLI; Azure DevOps is the user's own; everything else is filesystem state.
- **It does not auto-execute plans.** The human gate after `/rival:rival-plan` is mandatory.
- **It does not generate code without a plan.** There is no "just build it" mode — `/rival:rival-execute` requires `state.phase == "plan-approved"`.
- **It does not expand arbitrary agents into the user's main context.** Only orchestrator skills run inline; specialists run in their own forked context with explicit, bounded inputs.

---

## 12. Where to read the source

If you want to understand a specific behavior, the canonical source is the skill or agent file itself — they are deliberately readable as documentation:

- For the planner's full algorithm: `skills/rival-plan/SKILL.md`
- For the executor's branch coordination logic: `skills/rival-execute/SKILL.md`
- For the verify prompt assembly: `skills/rival-verify/SKILL.md`
- For agent prompts and protocols: `agents/*.md`
- For the ADO export tool: `scripts/export-ado-knowledge.py`

The plugin is intentionally not abstracted into helper libraries — each skill is a complete recipe. That makes it heavy on prose, but easy to audit and modify.
