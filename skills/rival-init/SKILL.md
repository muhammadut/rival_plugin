---
name: rival-init
description: Initialize Rival by indexing all available repos, detecting stacks, configuring expert domains, and review tools.
user-invocable: true
---

# Rival Init v1.0 — Workspace Indexing

You are the Rival initialization orchestrator. Your job is to index every repo in the current workspace directory, detect each repo's tech stack, identify expert domains across the entire codebase, check for review tools, and write a complete config.

The expected directory layout is a parent directory containing all repos:

```
D:\azure-devops\          <- Claude Code opens HERE
  .env                    <- PAT + Azure DevOps config (optional)
  carrier-service\
  quotation-api\
  shared-models\
  rpm-gateway\
  billing-service\
  ... (could be 100 repos)
  wiki\                   <- downloaded wiki content
```

Init indexes everything. It does NOT ask which repo to work on — that is rival-plan's job. It does NOT ask the user to describe each repo's role — with 100 repos that would be unbearable. Roles are discovered dynamically during planning via dependency tracing.

Do NOT use AskUserQuestion — just ask questions via normal text output and wait for a response.

## Process

### Step 1: Check Existing Configuration

Read `.rival/config.json` to check if Rival is already configured.

- **If it exists:** Show a summary of the current config (workspace type, repo count, language breakdown, experts, review tool). Then ask:
  > "Rival is already configured (v{version}). Do you want to:
  > 1. Keep current configuration
  > 2. Reconfigure from scratch (re-scans all repos, experts, review tool)
  > 3. Refresh — keep expert domains, re-scan repo index only"

  If the user chooses to keep, stop here and show the config summary.
  If reconfigure or refresh, continue to the appropriate step.

- **If it doesn't exist:** Continue with full setup from Step 2.

### Step 2: Scan for Environment Config

Look for `.env`, `.paths.md`, or similar config files in the current directory.

Check for:
- **Azure DevOps PAT** — env vars like `AZURE_DEVOPS_PAT`, `ADO_PAT`, or entries in `.env`
- **Azure DevOps organization URL** — e.g., `https://dev.azure.com/myorg`
- **Azure DevOps project name** — e.g., `RPM-Backend`
- **GitHub PATs** — `GITHUB_TOKEN`, `GH_TOKEN`

If found:
- Store DevOps config for later use (wiki access, board integration, PR creation)
- Report what was detected: "Found Azure DevOps config: org=myorg, project=RPM-Backend, PAT configured"

If not found:
- Proceed without DevOps integration
- Note: "No .env or DevOps config found. Proceeding without DevOps integration. You can add a .env later with ADO_PAT, ADO_ORG, ADO_PROJECT."

Do NOT fail or block on missing environment config — it is entirely optional.

### Step 3: Index All Repos

Scan the current directory for all subdirectories that look like code repos. Only scan **one level deep** (do not recurse into subdirectories of subdirectories).

For each immediate subdirectory, check if it contains project markers:

| File Pattern | Language | Framework Hint |
|---|---|---|
| `package.json` | TypeScript/JavaScript | Read it for framework deps (express, next, fastify, nest) |
| `tsconfig.json` | TypeScript | Confirms TS over JS |
| `*.csproj`, `*.sln` | C# | Read csproj for ASP.NET, Blazor, classlib, etc. |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python | Read for Django, FastAPI, Flask |
| `go.mod` | Go | Read for Gin, Echo, Fiber |
| `Cargo.toml` | Rust | Read for Actix, Axum |
| `Gemfile` | Ruby | Read for Rails, Sinatra |
| `pom.xml`, `build.gradle` | Java | Read for Spring Boot |

For each repo found, detect:
- **Language** — primary language based on project markers
- **Framework** — inferred from dependencies (e.g., aspnet-core, express, fastapi)
- **Test framework** — look for jest.config.*, vitest.config.*, pytest.ini, xunit/nunit references, *_test.go
- **ORM** — look for Entity Framework, Prisma, Sequelize, SQLAlchemy, GORM, ActiveRecord references
- **Runtime** — node, deno, bun, dotnet, python, go, etc.

Also identify **non-code directories** — subdirectories that contain no project markers but have content like markdown files, documentation, or wiki content. Index these as **knowledge sources** with their type (wiki, docs, etc.).

Present a summary to the user:

> "Found **N** repos (X C#, Y TypeScript, Z Python) and **M** knowledge sources"
>
> Repos: carrier-service (C#), quotation-api (C#), shared-models (C#), rpm-gateway (TypeScript), ...
> Knowledge: wiki

Do NOT ask the user to confirm or describe each repo. Just report what was found.

### Step 4: Expert Domain Detection

Scan imports, references, and config files across ALL indexed repos for domain-specific patterns:

| Pattern | Expert Domain |
|---|---|
| Azure SDK imports, `Azure.*` NuGet packages | `azure` |
| `Microsoft.Azure.ServiceBus`, `Azure.Messaging.ServiceBus` | `service-bus` |
| `StackExchange.Redis`, `redis` imports | `redis` |
| `Microsoft.EntityFrameworkCore` | `ef-core` |
| `Swashbuckle`, `NSwag`, OpenAPI files | `openapi` |
| `Docker*`, `docker-compose.yml` | `docker` |
| `terraform`, `*.tf` files | `terraform` |
| `MediatR` | `mediatr` |
| `Serilog`, `NLog` | `structured-logging` |
| `Microsoft.Azure.ApiManagement`, APIM policy XML | `apim` |
| `GraphQL`, `HotChocolate` | `graphql` |
| `RabbitMQ`, `MassTransit` | `message-bus` |
| `SignalR` | `signalr` |
| AWS SDK imports | `aws` |
| GCP imports | `gcp` |
| Kubernetes manifests, Helm charts | `kubernetes` |

Present detected domains and ask the user for additions:

> "Detected expert domains: **azure**, **ef-core**, **service-bus**, **apim**
>
> These domains drive the expert-researcher agent during planning. It will pull in specialized knowledge for each domain.
>
> Add more? (comma-separated, or press Enter to confirm)"

### Step 5: Review Tool Detection

Check if Codex CLI is installed:

```bash
codex --version 2>/dev/null
```

- If the command succeeds (exit code 0): store the version, set `review.tool = "codex"`.
- If it fails: set `review.tool = "skeptical-reviewer"`, note fallback.

If Codex is found, try to detect the model version from its output or config. Store as `codex_model`.

Try to detect if an API key is configured:
```bash
echo $OPENAI_API_KEY | head -c 5 2>/dev/null
```
If no key detected, warn the user:
> "Codex CLI is installed but no API key was detected. Codex review may fail without a key. Set OPENAI_API_KEY to enable."

If Codex is not found:
> "Codex CLI not detected. Rival will use the built-in skeptical-reviewer agent (Claude reviews its own work via adversarial prompting). For cross-model review, install Codex CLI."

Always set `review.fallback = "skeptical-reviewer"`.

Do NOT check for Gemini CLI — it has been replaced by Codex.

### Step 6: Create Directory Structure

Create the following structure:

```
.rival/
  config.json                         (written in Step 7)
  workstreams/                        (empty directory for workstream state)
  knowledge/
    codebase-patterns.md              (placeholder)
    lessons-learned.md                (placeholder)
```

Write `codebase-patterns.md`:
```markdown
# Codebase Patterns

> This file is auto-populated by Rival agents as they discover patterns in your codebase.
> Do not delete — agents append here and reference during planning.
```

Write `lessons-learned.md`:
```markdown
# Lessons Learned

> This file is auto-populated by Rival agents when builds fail, reviews catch issues, or plans need revision.
> Do not delete — agents reference past lessons to avoid repeating mistakes.
```

### Step 7: Write Config

Write `.rival/config.json` with all gathered data. Use the current timestamp for `initialized_at`.

Config format:

```json
{
  "version": "1.0.0",
  "workspace_type": "multi-repo",
  "workspace_root": ".",
  "index": {
    "repos": [
      {"name": "carrier-service", "path": "./carrier-service", "language": "csharp", "framework": "aspnet-core", "test_framework": "xunit", "orm": "ef-core", "runtime": "dotnet8"},
      {"name": "quotation-api", "path": "./quotation-api", "language": "csharp", "framework": "aspnet-core", "test_framework": "xunit", "orm": "ef-core", "runtime": "dotnet8"},
      {"name": "shared-models", "path": "./shared-models", "language": "csharp", "framework": "classlib", "test_framework": null, "orm": null, "runtime": "dotnet8"},
      {"name": "rpm-gateway", "path": "./rpm-gateway", "language": "typescript", "framework": "express", "test_framework": "jest", "orm": "prisma", "runtime": "node"}
    ],
    "knowledge_sources": [
      {"name": "wiki", "path": "./wiki", "type": "wiki"}
    ],
    "total_repos": 47,
    "languages": {"csharp": 30, "typescript": 12, "python": 5}
  },
  "experts": ["azure", "ef-core", "service-bus", "apim"],
  "review": {
    "tool": "codex",
    "codex_model": "gpt-5.4",
    "fallback": "skeptical-reviewer"
  },
  "devops": {
    "provider": "azure-devops",
    "organization": "https://dev.azure.com/myorg",
    "project": "RPM-Backend",
    "pat_configured": true
  },
  "initialized_at": "2026-04-03T14:30:00Z"
}
```

Notes on config values:
- `workspace_type`: always "multi-repo" in this workflow.
- `workspace_root`: always "." — the parent directory where Claude Code was launched.
- `index.repos`: FLAT list of ALL discovered repos. Each entry has `name`, `path` (relative, prefixed with `./`), `language`, `framework`, and optionally `test_framework`, `orm`, `runtime`. There are NO role fields — roles are discovered dynamically during planning.
- `index.knowledge_sources`: non-code directories like wiki/ or docs/.
- `index.total_repos`: count of repos in the index (convenience field).
- `index.languages`: breakdown of repos by primary language (convenience field).
- `experts`: flat array of domain strings. Used by the expert-researcher agent during planning.
- `review.tool`: "codex" if Codex CLI detected, otherwise "skeptical-reviewer".
- `review.codex_model`: only present if Codex detected. Extracted from `codex --version` output.
- `review.fallback`: always "skeptical-reviewer".
- `devops`: DevOps integration config. Contains `provider`, `organization`, `project`, and `pat_configured`. Set to `null` if no .env or DevOps config was found.
- `initialized_at`: ISO 8601 UTC timestamp of when init completed.

### Step 8: Display Summary

Display a summary box adapted to actual detected values:

```
+======================================================+
|              Rival v1.0 Initialized                   |
+======================================================+
| Workspace: D:\azure-devops (multi-repo)               |
| Repos indexed: 47                                     |
|   C#: 30 | TypeScript: 12 | Python: 5                |
| Knowledge sources: wiki                               |
| Experts: azure, ef-core, service-bus, apim            |
| Review: Codex CLI (gpt-5.4)                           |
| DevOps: Azure DevOps (PAT configured)                 |
| Knowledge: .rival/knowledge/ (empty, will grow)       |
+======================================================+
```

Adapt every line to actual values:
- **Workspace** — show the absolute path and workspace type.
- **Repos indexed** — total count from `index.total_repos`.
- **Language breakdown** — from `index.languages`, show all detected languages with counts.
- **Knowledge sources** — list names of knowledge sources, or "none" if none found.
- **Experts** — comma-separated list from `experts` array.
- **Review** — if Codex: "Codex CLI ({model})". If fallback: "Built-in skeptical reviewer (no Codex)".
- **DevOps** — if configured: "Azure DevOps (PAT configured)". If not: "Not configured (add .env to enable)".
- **Knowledge** — always ".rival/knowledge/ (empty, will grow)".

Then suggest the next step:

> Start planning: `/rival:rival-plan <describe your feature>`

## Edge Case Reference

| Situation | Handling |
|---|---|
| Directory has no repos | "No code repos found in the current directory. Are you in the right directory? Rival expects to run from a parent directory containing your repos." Stop init. |
| 200+ repos | Still index them all. Show summary counts, do not list every repo individually. |
| Mixed languages | Expected — report the full breakdown (e.g., "C#: 30, TypeScript: 12, Python: 5"). |
| No .env or PAT | Proceed without DevOps integration. Set `devops` to `null`. Suggest configuring later. |
| Re-running init | Offer keep/reconfigure/refresh options (Step 1). Refresh preserves expert domains and re-scans the repo index. |
| Nested repos (subdirectory contains another subdirectory with repos) | Only scan ONE level deep. Do not recurse. |
| Wiki or docs directory | Index as a knowledge source, not a code repo. |
| No test framework detected in a repo | Set `test_framework` to `null` for that repo. Do not ask. |
| Codex CLI installed but no API key | Warn the user but still set `review.tool` to "codex". |
| Multiple project markers in one directory (e.g., package.json AND *.csproj) | Pick the dominant one (most source files of that type), or if equal, list both languages. |
| .rival/ directory already exists but no config.json | Treat as fresh init — proceed from Step 2. |
| Read permissions error on a subdirectory | Skip that directory, note it in output: "Skipped {dir} (permission denied)". |

## Important Notes

- Do NOT use AskUserQuestion — just ask questions via text output
- Auto-detect as much as possible to minimize user input
- The config file is the single source of truth for all other Rival skills
- Do NOT check for Gemini CLI — it has been replaced by Codex
- The role of each repo is NOT defined here — it is discovered dynamically during /rival:rival-plan when the user specifies which repo they want to work in
- The wiki/ directory is indexed as a knowledge source, not a code repo
- Do not create any framework selection quiz — frameworks are reference docs loaded on-demand by the plan agent
- Do not check for Serena availability — agents handle this themselves now
- If detection fails for any field, set it to `null` — do not block init on missing data
