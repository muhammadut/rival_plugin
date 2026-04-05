---
name: rival-team-status
description: Pull team activity from Azure DevOps, then synthesize a code-grounded engineering brief via the team-narrative-writer agent.
user-invocable: true
argument-hint: [--team <name>] [--names "..."] [--window <days>] [--refresh-roster]
---

# Rival Team Status — Code-Grounded Engineering Brief

Two-phase architecture:
1. **Gather** (Python script): pulls enriched data from Azure DevOps — PR descriptions, changed files, work item details, branches, cross-board work items
2. **Write** (team-narrative-writer agent): reads raw data AND the actual code in `knowledge/repos/` to produce an engineering brief that links every ticket/PR to real architectural context

Output: `.team-status/YYYY-MM-DD/report.md` — a briefing grounded in real code, not a ticket list.

## Process

### Step 1: Check Configuration

Read `.rival/config.json` for:
- `paths.plugin_root`
- `paths.python_cmd`
- `paths.knowledge_dir` (where knowledge/repos/ lives)
- `index.repos` (full repo list)
- `devops.organization` and `devops.project`

If DevOps config missing: "Azure DevOps not configured. Run /rival:rival-init first."

Check for `.env` — must contain `ADO_PAT`, `ADO_ORG`, `ADO_PROJECT`.

### Step 2: Check / Create team.yaml

Look for `.rival/team.yaml`.

**If missing and `--names` not provided**, offer to set it up:

> "No team config found. Two options:
> 1. Create team.yaml — tell me which repos to track, I'll discover who's working in them
> 2. Use --names to track specific people directly (e.g., `/rival:rival-team-status --names \"Bhoomika,Amy,Satish\"`)
>
> Which would you like?"

If option 1, walk through interactive setup and write:

```yaml
default_team: main

teams:
  main:
    name: "<team name>"
    repos:
      - <repo1>
      - <repo2>
    activity_window_days: 60
```

Add `.rival/team.yaml` to `.gitignore`.

### Step 3: Gather Enriched Data (Python)

Run the team-status.py script using paths from config:

```bash
# Mac/Linux:
{python_cmd} {plugin_root}/scripts/team-status.py \
  --config .rival/team.yaml \
  --env .env \
  --team <team-name>

# With --names:
{python_cmd} {plugin_root}/scripts/team-status.py \
  --env .env \
  --names "Bhoomika,Amy,Satish"

# Force refresh roster:
{python_cmd} {plugin_root}/scripts/team-status.py \
  --config .rival/team.yaml --env .env --team skunk --refresh-roster
```

The script:
1. Discovers team members from branch activity (first run or --refresh-roster)
2. For each member: queries work items assigned to them across ALL boards
3. Fetches PR details (description, changed files, commits)
4. Writes raw data to `.team-status/YYYY-MM-DD/raw-data.json`
5. Prints the path to raw-data.json on stdout

Capture the output path. If the script fails, show the error and stop.

### Step 4: Invoke team-narrative-writer Agent

This is where the engineering brief is written. Spawn the agent:

```
Agent(
  subagent_type="rival:team-narrative-writer",
  description="Team Brief: <scope>",
  prompt="
    ## Raw Data Path
    {absolute path to .team-status/<date>/raw-data.json}

    ## Knowledge Dir
    {absolute path from config.paths.knowledge_dir}/repos

    ## Output Path
    {absolute path to .team-status/<date>/report.md}

    ## Team Repos
    <JSON array of repos from team.yaml or the repos that appeared in raw-data>

    ## All Indexed Repos
    <JSON array from config.index.repos>

    ## Task
    Read the raw-data.json. For EVERY work item and PR across ALL members
    (no cherry-picking), link the ticket to actual code in knowledge/repos/.
    Produce a code-grounded engineering brief at the Output Path.

    Be specific with file paths. Be complete. Be insightful.
  "
)
```

The agent will read both the raw data AND the actual code, then write the report.

Wait for the agent to complete. It may take several minutes for large teams (many repos × many tickets × code reading).

### Step 5: Display Summary & Offer Next Actions

Read the final report briefly and show the user:

```
Engineering brief complete:
  .team-status/<date>/report.md

Executive summary:
  [first 3-5 lines from the "Executive Summary" section]

Members covered: <N>
Active items analyzed: <N>
Repos touched: <N>

Want to:
1. Open the full report
2. Dig into a specific person (I can read the section)
3. Refresh roster (re-discover members from branches)
4. Commit snapshot for tracking (git add .team-status/)
5. Done
```

## Directory Structure

```
.team-status/
  2026-04-05/
    raw-data.json           ← from Python script (ADO API data)
    discovered-roster.json  ← from first-run or --refresh-roster
    report.md               ← from team-narrative-writer agent
  2026-04-06/
    ...
```

Commit `.team-status/` to git if you want to track team progress over time.

## Edge Cases

| Situation | Handling |
|---|---|
| No team.yaml and no --names | Offer interactive setup or --names mode |
| Script fails | Show error, suggest checking .env and team.yaml |
| knowledge/repos/ doesn't exist | Agent will note which tickets reference unavailable repos |
| First run (no cached roster) | Script auto-discovers members, saves roster |
| Cached roster stale (>14 days old) | Suggest --refresh-roster |
| --names can't resolve a name | Warn, skip that name, continue with others |
| Very large teams (>15 members) | Report will be long; agent handles it |
| Python script unavailable / crashes | Report cannot be generated — fix script first |

## Flags

```bash
/rival:rival-team-status                           # default team from team.yaml
/rival:rival-team-status --team skunk              # specific team
/rival:rival-team-status --team skunk --refresh-roster  # re-discover members
/rival:rival-team-status --team skunk --window 90  # 90-day window
/rival:rival-team-status --names "Bhoomika,Amy,Satish"  # ad-hoc people
```

## Important Notes

- **The writer agent does the heavy lifting.** Don't try to synthesize inline — spawn the agent.
- **Code grounding is the value.** The agent reads knowledge/repos/ to understand what's real vs what tickets claim. That's what makes the report useful.
- **Every item gets coverage.** No cherry-picking of "interesting" items. The agent covers everything.
- **Roster is cached** in team.yaml's `discovered_members` after first run. Use --refresh-roster when team changes.
- **Reports are date-stamped.** One per day. Running twice same day overwrites.
- **Honor the user's scope.** If they asked --names "Bhoomika", report covers ONLY Bhoomika — don't expand unnecessarily.
