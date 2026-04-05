---
name: rival-team-status
description: Show active PRs, work items, and board activity for a team, member, repo, or board. Queries Azure DevOps via your existing PAT.
user-invocable: true
argument-hint: [--team <name>] [--member <name>] [--repo <name>] [--board <name>] [--me] [--all] [--stale] [--sprint]
---

# Rival Team Status — Active Work Dashboard

Queries Azure DevOps for active PRs and work items, scoped by team, member, repo, or board. Uses your existing ADO PAT from `.env`.

## Process

### Step 1: Parse Arguments

From `$ARGUMENTS`:

| Flag | Scope |
|------|-------|
| `--me` | Your own PRs/work items (uses git config email) |
| `--team <name>` | Specific team from `.rival/team.yaml` |
| `--member <name>` | Specific person (name, devops_id, or email) |
| `--repo <name>` | Specific repo |
| `--board <name>` | Specific Azure DevOps board or area path |
| `--all` | Exhaustive — all teams, all repos, all boards |
| `--stale` | Only PRs >7 days old with no updates |
| `--sprint` | Focus on current iteration only |

Default (no flags): use `default_team` from `.rival/team.yaml`, or `--all` if no team config.

### Step 2: Check for team.yaml

Read `.rival/team.yaml`. If it doesn't exist, offer to create one:

> "No team config found. Let's create `.rival/team.yaml` so I can scope queries to your team.
>
> Would you like to:
> 1. Create team config interactively (recommended)
> 2. Run exhaustive query this time (all PRs, all work items)
> 3. Cancel"

**If they choose option 1**, walk them through:
- Team name (default: "main")
- Members: "List team members (name, devops_id, email). Format: 'Alice Smith, alices, alice@rival.com'. One per line. Empty line to finish."
- Repos: "Which repos does your team own? (comma-separated, from indexed repos)"
- Boards/area paths: "Azure DevOps area paths (e.g., 'Rival\\RPM\\Backend')"

Write `.rival/team.yaml` with this structure:

```yaml
default_team: main

teams:
  main:
    name: "<team name>"
    members:
      - name: "<name>"
        devops_id: "<devops_id>"
        email: "<email>"
    repos:
      - <repo1>
      - <repo2>
    area_paths:
      - "<area path>"
```

Add `.rival/team.yaml` to `.gitignore`.

### Step 3: Run the Status Script

Use the paths from `.rival/config.json` (from rival-init):
- `paths.python_cmd`
- `paths.plugin_root`

Construct script path: `{plugin_root}/scripts/team-status.py`

Run with the appropriate flags:

```bash
# Default (uses team.yaml default_team):
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env

# With flags:
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env --me
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env --member "Alice"
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env --repo Rival.Customer.API
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env --board RPM-Backend
{python_cmd} {plugin_root}/scripts/team-status.py --config .rival/team.yaml --env .env --all
```

On Windows, use `python` instead of `python3` (check `paths.python_cmd`).

### Step 4: Confirm Exhaustive Queries

If user passed `--all`, confirm before running:

> "Exhaustive mode will query ALL PRs, ALL work items, and ALL boards across the entire Azure DevOps project. This may take 30-60 seconds and returns a lot of data.
>
> Proceed? [Y/n]"

### Step 5: Display Results

The script outputs formatted text. Display it directly to the user.

If the user wants to drill down, offer follow-up actions:

> "Want to:
> 1. See details on a specific PR or work item
> 2. Filter further (e.g., by state, by assignee)
> 3. Export as JSON
> 4. Done"

## Edge Cases

| Situation | Handling |
|---|---|
| `.env` missing or no ADO_PAT | "Azure DevOps not configured. Run /rival:rival-init first." |
| `.rival/team.yaml` missing | Offer interactive setup or `--all` mode |
| Member not found in team.yaml | Fall through to raw query with the name as-is |
| No PRs or work items found | Display "All clear — no active work in this scope" |
| Azure DevOps API rate limit | Script handles timeouts gracefully; show error, suggest retry |
| `--me` but no git config email | Fall back to asking user for their DevOps identity |
| Exhaustive query takes too long | Script has 60s timeout per API call; partial results displayed |

## Important Notes

- This skill reads `.env` for ADO_PAT — never prompts for credentials directly
- Script is at `{paths.plugin_root}/scripts/team-status.py` — Python 3, cross-platform
- `.rival/team.yaml` is user-managed and gitignored (contains names/emails)
- PRs and work items are ALWAYS current state (no caching) — fresh from Azure DevOps API
- Use this for morning standup prep, sprint reviews, "what's my team up to" questions
- Paired naturally with `/rival:rival-plan` — team-status shows WHAT to work on, rival-plan plans HOW
