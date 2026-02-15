---
name: rival-init
description: Initialize Rival for this project. Configures stack, frameworks, and detects tools.
user-invocable: true
---

# Rival Init — Project Configuration

You are the Rival initialization orchestrator. Your job is to configure Rival for this project by detecting the tech stack, asking about development frameworks, and checking tool availability.

## Process

### Step 1: Check for Existing Configuration

Read `.rival/config.json` to check if Rival is already configured.

- **If it exists:** Show the current config summary and ask:
  > "Rival is already configured for this project. Do you want to:
  > 1. Keep current configuration
  > 2. Reconfigure from scratch"

  If the user chooses to keep, stop here and show the config summary.

- **If it doesn't exist:** Continue with setup.

### Step 2: Determine Project Type

Check for existing source code to auto-detect brownfield vs greenfield:

Use Glob to look for source files:
- `**/*.ts`, `**/*.js`, `**/*.py`, `**/*.cs`, `**/*.go`, `**/*.java`, `**/*.rb`

If source files exist, suggest **brownfield**. If the project is empty or only has config files, suggest **greenfield**.

Ask the user to confirm:
> "This looks like a **brownfield** project (existing codebase detected). Is that correct?"

Present options:
1. Brownfield (existing codebase) — recommended if files detected
2. Greenfield (new project)

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
> - Language: TypeScript
> - Framework: Express
> - Test framework: Jest
> - ORM: Prisma
> - Runtime: Node
>
> Is this correct? Adjust any values?"

Use the AskUserQuestion tool to let them confirm or provide corrections for each field.

### Step 4: Select Development Frameworks

Before presenting the selection, explain what frameworks do and how Rival uses them:

> "Rival uses development frameworks to shape how it plans, reviews, and builds your code. You're not committing to using all of them on every task — Rival's triage system automatically selects the relevant ones per task based on what you're building.
>
> Think of these as **tools in the toolbox** — enable the ones your team values, and Rival will pull them out when they're needed."

Present each framework with an educational description. Use AskUserQuestion with multiSelect: true:

1. **C4 Model** — Understands your architecture at 4 zoom levels (System → Containers → Components → Code). Helps Rival assess blast radius — does your change affect one file or the whole system?
   *Example: "This change adds a new external API integration — that's a Level 1 system context change with high blast radius."*

2. **DDD (Domain-Driven Design)** — Models your business domain: entities, aggregates, boundaries. Helps Rival understand where business logic lives and how concepts relate.
   *Example: "Order and OrderLineItem are one aggregate — changes to line items must go through the Order."*

3. **BDD (Behavior-Driven Development)** — Writes acceptance criteria as Given/When/Then scenarios. Helps define what "done" looks like from the user's perspective before building.
   *Example: "Given a user with an expired coupon, When they apply it at checkout, Then they see 'Coupon expired' and the total is unchanged."*

4. **TDD (Test-Driven Development)** — Writes tests before implementation (Red-Green-Refactor). Helps Rival build code with confidence — every line exists because a test demanded it.
   *Example: Rival writes a failing test for calculateDiscount(), then writes the minimum code to pass it.*

5. **ADR (Architecture Decision Records)** — Documents significant design decisions with context, alternatives considered, and consequences. Creates a decision log future developers can reference.
   *Example: "ADR-003: Use RabbitMQ over Kafka for order notifications — lower operational complexity for our team size."*

6. **Event Storming** — Maps domain events, commands, and workflows. Helps Rival understand what happens, in what order, triggered by what. Essential for event-driven or workflow-heavy systems.
   *Example: "PlaceOrder command → OrderPlaced event → trigger InventoryReserved policy → emit PaymentRequested event."*

After the user selects, confirm and explain the dynamic selection:
> "You've enabled: **<selected frameworks>**
>
> Rival won't run all of these on every task. When you start planning a feature, Rival's triage system analyzes your request and selects only the frameworks relevant to that specific task. A small bug fix might use none of them. A new feature might use three."

### Step 4b: Custom Frameworks

After framework selection, mention custom framework support:

> "Your team can also add custom frameworks. Create markdown files in `.rival/frameworks/` describing your team's conventions (e.g., API design standards, observability requirements, coding style guides). Rival will treat them like built-in frameworks — agents read them and apply them during planning.
>
> Example: Create `.rival/frameworks/api-design.md` with your REST conventions, then add `'api-design'` to your frameworks list."

### Step 5: Detect Gemini CLI

Check if Gemini CLI is installed by running:

```bash
gemini --version 2>/dev/null
```

- If the command succeeds (exit code 0): `gemini_available: true`
- If it fails: `gemini_available: false`

If Gemini is not found, inform the user:
> "Gemini CLI not detected. Rival will use single-model mode (Claude reviews its own work via a separate agent). For best results, install Gemini CLI: `npm install -g @google/gemini-cli`"

### Step 6: Check Serena Availability

Check if Serena MCP server is available by looking for it in the MCP configuration. Use Grep to search for "serena" in:
- `.claude/settings.json`
- `.mcp.json`
- `~/.claude/settings.json`

- If found: `serena_available: true`
- If not found: `serena_available: false`

This is informational only — Rival works without Serena but agents can use it for more precise code analysis when available.

### Step 7: Write Configuration

Create the `.rival/` directory structure and write `.rival/config.json`:

```bash
# Create directories
.rival/
.rival/workstreams/
.rival/frameworks/     # For custom team frameworks
```

```json
{
  "project_type": "brownfield|greenfield",
  "stack": {
    "language": "typescript",
    "framework": "express",
    "test_framework": "jest",
    "orm": "prisma",
    "runtime": "node"
  },
  "frameworks": ["c4", "ddd", "bdd"],
  "gemini_available": true,
  "serena_available": false,
  "initialized_at": "2026-02-14T10:30:00Z"
}
```

Note: `frameworks` lists all **available** frameworks for this project. The triage agent
selects which ones are relevant per workstream — not all of them run on every task.

### Step 8: Display Summary

Show the configuration summary:

```
╔══════════════════════════════════════════╗
║           Rival Initialized              ║
╠══════════════════════════════════════════╣
║ Project Type:  brownfield                ║
║ Language:      TypeScript                ║
║ Framework:     Express                   ║
║ Test Framework: Jest                     ║
║ ORM:           Prisma                    ║
║ Runtime:       Node                      ║
║                                          ║
║ Frameworks:    C4, DDD, BDD              ║
║ Gemini CLI:    ✓ Available               ║
║ Serena:        ✗ Not available           ║
╚══════════════════════════════════════════╝
```

Then suggest next steps:
> "Rival is ready. Start planning a feature with:
> `/rival:rival-plan <describe your feature>`"

## Important Notes

- All user interactions should use AskUserQuestion for structured choices
- Auto-detect as much as possible to minimize user input
- Always confirm detected values — don't silently assume
- The config file is the single source of truth for all other Rival skills
- If detection fails for any field, ask the user to provide it manually
