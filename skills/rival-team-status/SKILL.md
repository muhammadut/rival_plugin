---
name: rival-team-status
description: Pull team activity from Azure DevOps, then synthesize insightful per-person narrative reports connecting work to system context.
user-invocable: true
argument-hint: [--team <name>] [--names "..."] [--window <days>] [--refresh-roster]
---

# Rival Team Status — Insightful Team Activity Reports

Two-phase architecture:
1. **Gather** (Python script): pulls enriched data from Azure DevOps — PR descriptions, changed files, work item details, branches, cross-board work items
2. **Synthesize** (Claude): reads raw data and writes meaningful narrative reports that connect each person's work to the system

Output: `.team-status/YYYY-MM-DD/report.md` — a briefing, not a list.

## Process

### Step 1: Check Configuration

Read `.rival/config.json` for:
- `paths.plugin_root`
- `paths.python_cmd`
- `devops.organization` and `devops.project` (must be present)

If DevOps config missing: "Azure DevOps not configured. Run /rival:rival-init first."

Check for `.env` — must contain `ADO_PAT`, `ADO_ORG`, `ADO_PROJECT`.

### Step 2: Check / Create team.yaml

Look for `.rival/team.yaml`.

**If missing and `--names` not provided**, offer to set it up:

> "No team config found. You have two options:
> 1. Create team.yaml — tell me which repos to track, I'll discover who's working in them
> 2. Use --names to track specific people directly (e.g., `/rival:rival-team-status --names \"Bhoomika,Amy,Satish\"`)
>
> Which would you like?"

If option 1, walk through interactive setup:

> "Which repos should I track for this team?
> (From your indexed repos, list the ones this team owns or actively works in)
>
> Paste comma-separated names, or I can suggest based on naming patterns..."

Write `.rival/team.yaml`:

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

Run the team-status.py script:

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

# Force refresh of discovered roster:
{python_cmd} {plugin_root}/scripts/team-status.py \
  --config .rival/team.yaml --env .env --team skunk --refresh-roster
```

The script:
1. Discovers team members from branch activity (first run or --refresh-roster)
2. For each member: queries work items assigned to them (past 60d + active + backlog, across ALL boards)
3. Fetches PR details (description, changed files, commits)
4. Writes raw data to `.team-status/YYYY-MM-DD/raw-data.json`
5. Returns the path to raw-data.json on stdout

Capture the output path from stdout.

### Step 4: Synthesize the Report (Claude — this is YOU)

**This is the critical step. You (the orchestrator) now read the raw data and write a meaningful narrative.**

Read `.team-status/YYYY-MM-DD/raw-data.json`.

Also read `.rival/config.json` for the full `index.repos` array — you'll need repo names/frameworks to explain system context.

Write a report to `.team-status/YYYY-MM-DD/report.md` with this structure:

```markdown
# Team Status — <Scope> — <Date>

**Generated:** <ISO timestamp>
**Scope:** <team name or names list>
**Window:** last <N> days
**Members:** <count>

## Team Snapshot

<2-3 sentence high-level summary of what's happening. Examples:
"The team is focused on OAuth2 integration and webhook reliability improvements
this cycle. Three people are actively shipping to customer-facing APIs, while one
is on infrastructure modernization.">

## Themes & Initiatives

<Identify the 2-4 main themes you see across the team. Examples:
- **OAuth2 Integration** — Bhoomika and Amy are converging on external IdP support
- **Webhook Reliability** — Fabrizio and Satish are hardening carrier callbacks
- **EF Core 8 Upgrade** — scattered across repos, owned by Luke>

## Per-Member Reports

---

### <Member Name>
**Focus:** <1-sentence summary of what they're primarily working on this cycle>
**Active across <N> boards:** <board names>
**Activity:** <commits_60d> commits across <repos_active count> repos in last <window> days

#### 📋 Recently Completed (last <N> days) — <count> items

<For each completed item, write 1-2 sentences explaining what it actually did.
Use the description field, not just the title. Connect to system if possible.>

- **#<id> [Type] <Title>** — Closed <X days ago> · Board: <area path>
  <What this work accomplished, based on description. 1-2 sentences.>

#### ⏳ In Progress — <count> items

<For each active item, explain WHAT they're doing and WHY it matters.>

- **#<id> [Type] <Title>** — <state> · Board: <area path>
  <What this work is about. Reference the description. Note any linked items.>

#### 📅 Backlog (assigned) — <count> items

<For each backlog item, brief summary of what's queued up.>

- **#<id> [Type] <Title>** — <state> · Board: <area path>
  <1-sentence summary from description.>

#### 🔀 Active Pull Requests — <count>

<For each PR, read the title, description, and files_changed. Describe:
- What this PR does (not just "adds OAuth2" — explain the specifics)
- Which part of the system it touches (reference the repo's role)
- Current review state
- Any interesting details from the commits>

- **#<pr_id> [<repo>] <Title>** — <approval status> · Branch: <source>
  **What it does:** <2-3 sentences based on description + files_changed>
  **System impact:** <which service area, what downstream effects, 1-2 sentences>
  **Files touched:** <count> files in <top-level directories from files_changed>
  **Recent commits:** <summarize commit messages if interesting>

#### 🧩 System Context

<Based on the repos they're working in + work items + PRs, describe where
their work fits in the overall system. This is the "hard part" the user mentioned.
2-3 sentences. Examples:

"Bhoomika's work centers on the authentication boundary — she's owning the
new OAuth2 flow in Customer.API which interacts with the shared IdentityService
in Auth.API. Her webhook idempotency work in Apps.API affects the carrier
integration path, which has downstream impact on billing and notifications.">

---

<Repeat for each member>

---

## Cross-Team Observations

<If you notice patterns across members, surface them:
- "Three people are touching Customer.API this cycle — coordination needed"
- "No one is assigned to the Service Bus retry work, but it's in backlog"
- "Bhoomika and Amy are both working on auth — are they aligned?"
- "The APIM policy work in backlog has no owner assigned">

## Stale Items

<Call out anything that looks stuck:
- PRs older than 7 days with no updates
- Work items assigned but unchanged in >14 days
- Long-running branches
- Blocked items>

## Summary Stats

- Total active PRs: <N>
- PRs ready to merge (all approvals): <N>
- PRs in review: <N>
- Active work items: <N>
- Backlog items: <N>
- Completed in window: <N>
```

### Step 5: Display & Offer Next Actions

Show the user a brief summary + report location:

```
Team status report generated:
  .team-status/<date>/report.md

Snapshot:
  [2-3 sentence summary from the report]

Want to:
1. Open the full report
2. Dig into a specific person
3. Refresh the roster (re-discover members)
4. Save snapshot for tracking (git commit .team-status/)
5. Done
```

## Important Synthesis Guidelines

**When reading raw-data.json:**

1. **Read descriptions, not just titles.** A ticket titled "Fix bug" might have a description explaining it's a race condition in payment processing affecting $50K of transactions.

2. **Read PR descriptions AND files_changed.** The description says WHAT, files_changed say WHERE. Together they tell the full story.

3. **Group work items by theme per person.** Don't just list them — identify what each person is FOCUSED on.

4. **Connect to system context using config.index.repos:**
   - Know what each repo DOES (from language/framework in config)
   - Know how repos CONNECT (use dependency knowledge or pattern-detector if needed)
   - Reference the system impact: "This touches the carrier integration boundary"

5. **Be honest about gaps.** If a description is empty or unclear, say so. Don't fabricate meaning.

6. **Highlight cross-cutting concerns.** If two people are working on the same area, say so. If something is orphaned, say so.

7. **Write for a tech lead.** They want to know: "What's my team doing, is it aligned, what's stuck, what needs attention?"

**Tone:**
- Informative, not dry
- Specific, not vague
- Honest about uncertainty
- Focused on value: "why does this matter?"

## Directory Structure

```
.team-status/
  2026-04-05/
    raw-data.json        ← from Python script
    discovered-roster.json  ← from first-run or --refresh-roster
    report.md            ← synthesized by Claude (this skill)
  2026-04-06/
    raw-data.json
    report.md
  ...
```

Commit `.team-status/` to git if you want to track team progress over time.

## Edge Cases

| Situation | Handling |
|---|---|
| No team.yaml and no --names | Offer interactive setup or --names mode |
| Script fails | Show error, suggest checking .env and team.yaml |
| Member has no work items | Still show them in report with "No active work items tracked" |
| PR description is empty | Note it and fall back to title + files_changed for summary |
| Work item description is empty | Use title only, note the gap |
| First run (no cached roster) | Auto-discover members, save roster |
| Cached roster stale (>14 days old) | Suggest --refresh-roster in output |
| --names can't resolve a name | Warn, skip that name, continue with others |
| Too many members (>15) | Still generate full report; note it will be long |
| Python script unavailable / crashes | Fall back to simpler text report without enrichment |

## Flags

```bash
/rival:rival-team-status                           # default team from team.yaml
/rival:rival-team-status --team skunk              # specific team
/rival:rival-team-status --team skunk --refresh-roster  # re-discover members
/rival:rival-team-status --team skunk --window 90  # 90-day window
/rival:rival-team-status --names "Bhoomika,Amy,Satish"  # ad-hoc people
```

## Important Notes

- **Synthesis is the value.** Raw data dumps are cheap; insightful summaries are expensive. Take the time to write a good report.
- **Read every description.** The title is often meaningless; the description has the substance.
- **Connect work to system.** Don't just summarize tickets — explain what part of the system this work affects.
- **Roster is cached in team.yaml** after first discovery. Use --refresh-roster when team changes.
- **Reports are date-stamped.** Running twice the same day overwrites — that's fine for active use.
- **One report per run.** Don't split into multiple files. Tech lead wants ONE document to read.
