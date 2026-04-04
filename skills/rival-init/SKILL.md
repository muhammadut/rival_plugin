---
name: rival-init
description: Initialize Rival for this project. Detects stack, configures multi-repo, expert domains, and review tools.
user-invocable: true
---

# Rival Init v1.0 — Project Configuration

You are the Rival initialization orchestrator. Your job is to configure Rival for this project by detecting the tech stack, discovering related repos, identifying expert domains, checking review tools, and writing a complete config.

Use AskUserQuestion for all user interactions. Auto-detect as much as possible, always confirm detected values.

## Process

### Step 1: Check for Existing Configuration

Read `.rival/config.json` to check if Rival is already configured.

- **If it exists:** Show a summary of the current config (project type, stack, repos, experts, review tool). Then ask:
  > "Rival is already configured (v{version}). Do you want to:
  > 1. Keep current configuration
  > 2. Reconfigure from scratch (re-detects stack, repos, experts)
  > 3. Refresh — keep repos and experts, re-detect stack only"

  If the user chooses to keep, stop here and show the config summary.
  If reconfigure or refresh, continue to the appropriate step.

- **If it doesn't exist:** Continue with full setup from Step 2.

### Step 2: Determine Project Type

Check for existing source code to auto-detect brownfield vs greenfield.

Use Glob to look for source files:
- `**/*.ts`, `**/*.js`, `**/*.py`, `**/*.cs`, `**/*.go`, `**/*.java`, `**/*.rb`, `**/*.rs`

If source files exist, suggest **brownfield**. If the project is empty or only has config files, suggest **greenfield**.

Ask the user to confirm:
> "This looks like a **brownfield** project (existing codebase detected). Is that correct?"

Present options:
1. Brownfield (existing codebase)
2. Greenfield (new project)

If **greenfield**: skip Step 4 (multi-repo discovery) and Step 6 (expert domain suggestions). Proceed directly to Step 3 for stack detection (user declares intended stack), then jump to Step 7.

### Step 3: Detect Tech Stack

Auto-detect the stack by checking for known files. Use Glob to search for:

| File Pattern | Language | Framework Hint |
|---|---|---|
| `package.json` | TypeScript/JavaScript | Read it for framework deps (express, next, fastify, nest) |
| `tsconfig.json` | TypeScript | Confirms TS over JS |
| `*.csproj`, `*.sln` | C# | Read csproj for ASP.NET, Blazor, etc. |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python | Read for Django, FastAPI, Flask |
| `go.mod` | Go | Read for Gin, Echo, Fiber |
| `Cargo.toml` | Rust | Read for Actix, Axum |
| `Gemfile` | Ruby | Read for Rails, Sinatra |
| `pom.xml`, `build.gradle` | Java | Read for Spring Boot |

For the detected language, also detect:
- **Test framework:** Look for `jest.config.*`, `vitest.config.*`, `pytest.ini`, `*.test.*`, `*_test.go`, `xunit`, `nunit`
- **ORM:** Look for Sequelize, Prisma, Entity Framework, SQLAlchemy, GORM, ActiveRecord references
- **Runtime:** node, deno, bun, dotnet, python, go

Present the detected stack and ask the user to confirm or correct:

> "Detected stack:
> - Language: C#
> - Framework: ASP.NET Core
> - Test framework: xUnit
> - ORM: EF Core
> - Runtime: .NET 8
>
> Is this correct? Adjust any values?"

Use AskUserQuestion to let them confirm or provide corrections for each field.

### Step 4: Multi-repo Discovery

**Skip this step if the project is greenfield.**

Scan the parent directory (`../`) for sibling repositories that might be part of the same system.

Look for directories containing:
- Same language markers as the current project (e.g., `*.csproj` if current is C#)
- Common project files: `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `.git/`
- Different language markers too (polyglot systems are common)

**Edge cases:**
- If the parent directory is not accessible (permissions, network drive): skip sibling scan, only use current repo. Inform the user: "Could not scan parent directory. You can manually add repos below."
- If user provides relative paths with `../`: resolve them, verify the path exists and contains source code.
- If sibling repos have a different language: still offer them (polyglot systems). Note the language difference.

Present discovered repos and ask user to confirm which are related:

> "Found these repositories alongside this project:
> 1. ../carrier-service (C#, .csproj detected)
> 2. ../notification-hub (TypeScript, package.json detected)
> 3. ../infra-scripts (no source files — config/scripts only)
>
> Which of these are part of your system? Select all that apply.
> You can also add paths manually (e.g., `../other-repo`)."

Use AskUserQuestion with multiSelect to let the user pick repos. Also accept manual path input.

### Step 5: Repo Role Descriptions

**Skip this step if no additional repos were selected in Step 4.**

For each selected repo (including the current one), ask the user to describe its role in one line. This context is critical for agents that explore across repos.

> "Describe each repo's role (one line each):
> - **rpm-backend** (this repo): "
> - **carrier-service**: "
> - **notification-hub**: "

Example roles:
- "Main RPM backend API — handles orders, users, pricing"
- "Calls external carrier APIs, handles rate quotes and label generation"
- "Sends emails, SMS, push notifications via Azure Service Bus triggers"

Store each repo entry with: `name`, `path` (relative), `role` (user-provided), `source` ("local").

### Step 6: Expert Domain Detection

**Skip this step if the project is greenfield (no code to scan).**

Infer expert domains from code patterns. Scan for:

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

Present detected domains and ask user for additions:

> "Detected expert domains: **azure**, **ef-core**, **service-bus**
>
> These domains drive the expert-researcher agent during planning. It will pull in specialized knowledge for each domain.
>
> Add more? (comma-separated, or press Enter to confirm)"

Use AskUserQuestion to accept additions.

### Step 7: Review Tool Detection

Check if Codex CLI is installed:

```bash
codex --version 2>/dev/null
```

- If the command succeeds (exit code 0): store the version, set `review.tool = "codex"`.
- If it fails: set `review.tool = "skeptical-reviewer"`, note fallback.

If Codex is found, try to detect the model version from its output or config. Store as `codex_model`.

Try to detect if an API key is configured:
```bash
# Check for common env vars
echo $OPENAI_API_KEY | head -c 5 2>/dev/null
```
If no key detected, warn the user:
> "Codex CLI is installed but no API key was detected. Codex review may fail without a key. Set OPENAI_API_KEY to enable."

If Codex is not found:
> "Codex CLI not detected. Rival will use the built-in skeptical-reviewer agent (Claude reviews its own work via adversarial prompting). For cross-model review, install Codex CLI."

Always set `review.fallback = "skeptical-reviewer"`.

### Step 8: Check .paths.md

Look for `.paths.md` in:
1. Project root (current directory)
2. User home directory (`~/`)

If found:
- Read the file for repo URLs, DevOps configuration (Azure DevOps org, project, wiki URLs, board URLs).
- Extract `provider` (e.g., "azure-devops", "github", "gitlab").
- Extract available features: repos, wikis, boards, pipelines.
- Store the path in config as `devops.paths_file`.
- **Warn the user:** "Found .paths.md — make sure it's in your .gitignore (it may contain org-specific URLs)."

If not found:
- Set `devops` to `null` in config.
- Inform the user: "No .paths.md found. DevOps integration is optional. You can add one later with repo URLs and board links."
- Proceed with local-only discovery.

### Step 9: Create Directory Structure

Create the following structure:

```
.rival/
  config.json                         (written in Step 10)
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

### Step 10: Write Config and Display Summary

Write `.rival/config.json` with all gathered data. Use the current timestamp for `initialized_at`.

Config format:
```json
{
  "version": "1.0.0",
  "project_type": "brownfield|greenfield",
  "stack": {
    "language": "csharp",
    "framework": "aspnet-core",
    "test_framework": "xunit",
    "orm": "ef-core",
    "runtime": "dotnet8"
  },
  "repos": [
    {"name": "rpm-backend", "path": ".", "role": "Main RPM backend API", "source": "local"},
    {"name": "carrier-service", "path": "../carrier-service", "role": "Calls external carrier APIs", "source": "local"}
  ],
  "experts": ["azure", "ef-core", "service-bus"],
  "review": {
    "tool": "codex|skeptical-reviewer",
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

Notes on config values:
- `repos`: always includes current repo as first entry with `"path": "."`. Additional repos use relative paths.
- `experts`: flat array of domain strings. Used by the expert-researcher agent during planning.
- `review.tool`: "codex" if Codex CLI detected, otherwise "skeptical-reviewer".
- `review.codex_model`: only present if Codex detected. Extracted from `codex --version` output.
- `review.fallback`: always "skeptical-reviewer".
- `devops`: `null` if no .paths.md found.
- `initialized_at`: ISO 8601 UTC timestamp of when init completed.

Display the summary box:

```
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
```

Adapt the summary to actual detected values. For the Stack line, use friendly display names (e.g., "C#" not "csharp", "ASP.NET Core" not "aspnet-core"). For Repos, show count as "this + N related". If review tool is skeptical-reviewer, show "Built-in skeptical reviewer (no Codex)".

Then suggest the next step:
> "Rival is ready. Start planning a feature with:
> `/rival:plan <describe your task>`"

## Edge Case Reference

| Situation | Handling |
|---|---|
| Parent directory not accessible | Skip sibling scan, only use current repo. Allow manual path input. |
| Sibling repo has different language | Still offer to include it. Note the language difference in the prompt. Polyglot systems are normal. |
| User provides relative paths with `../` | Resolve the path, verify it exists and contains source code or a `.git/` directory. Reject if path doesn't exist. |
| Codex CLI installed but no API key | Detect via env var check. Warn user but still set tool to "codex". |
| Re-running init on existing project | Offer keep/reconfigure/refresh options (Step 1). Refresh preserves repos and experts, re-detects stack. |
| Empty project (greenfield) | Skip multi-repo discovery (Step 4), skip repo roles (Step 5), skip expert domain suggestions (Step 6). User declares intended stack in Step 3. |
| No test framework detected | Set `test_framework` to `null`, ask user to specify or confirm none. |
| Multiple languages detected | Pick the dominant one (most source files), note others. Ask user to confirm primary language. |
| .paths.md in .gitignore check | Warn user to add it if not already ignored. Do not modify .gitignore automatically. |

## Important Notes

- All user interactions must use AskUserQuestion for structured choices
- Auto-detect as much as possible to minimize user input
- Always confirm detected values — never silently assume
- The config file is the single source of truth for all other Rival skills
- If detection fails for any field, ask the user to provide it manually
- Do not create any framework selection quiz — frameworks are now reference docs loaded on-demand by the plan agent
- Do not check for Gemini CLI — it has been replaced by Codex
- Do not check for Serena availability — agents handle this themselves now
