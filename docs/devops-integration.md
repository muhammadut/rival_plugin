# Rival DevOps Integration

This document describes how the Rival plugin integrates with Azure DevOps to enable end-to-end planning, research, and ticket creation workflows.

---

## 1. Architecture Overview

Rival uses a two-file configuration approach:

| File | Purpose | Contains Secrets? | Committed to Git? |
|------|---------|--------------------|--------------------|
| `.env` | Azure DevOps PAT, org, project | Yes | **Never** |
| `.rival/config.json` | All paths, repo index, experts, review tool | No (only `pat_configured: true/false`) | Optional |

The old `.paths.md` approach is deprecated. If a `.paths.md` file exists, Rival ignores it.

### Directory Layout After Setup

```
workspace-root/                  (Claude Code opens here)
  .env                           PAT + Azure DevOps config
  .gitignore                     Contains .env
  knowledge/                     Created by export script
    repos/                       All cloned repositories
      Rival.Apps.API/
      Rival.Customer.API/
      ...
    wikis/                       Exported wiki content (markdown + assets)
      Rival-Insurance-Technology.wiki/
    summary.json                 Index of everything downloaded
  .rival/
    config.json                  Rival configuration (includes paths)
    workstreams/                 Feature workstreams
    knowledge/
      codebase-patterns.md       Discovered patterns
      lessons-learned.md         Past lessons
```

---

## 2. Setup Flow (handled by `/rival:rival-init`)

Users do NOT run scripts manually. The init skill handles everything:

1. **Discovers** the plugin installation path and export script
2. **Prompts** for PAT (with step-by-step creation guide if needed)
3. **Asks** for organization name and project name
4. **Tests** the connection (validates both org access AND project access)
5. **Saves** `.env` with credentials (owner-only permissions, added to `.gitignore`)
6. **Runs** the export script to clone all repos and export all wikis
7. **Indexes** everything into `.rival/config.json`

### Manual Setup (alternative)

For users who prefer to set up manually or are on Windows without Claude Code:

```bash
# Mac/Linux:
export ADO_PAT="your-token-here"
export ADO_ORG="rivalitinc"
export ADO_PROJECT="Rival Insurance Technology"
python3 path/to/rival_plugin/scripts/export-ado-knowledge.py --output-dir ./knowledge

# Windows PowerShell:
$env:ADO_PAT="your-token-here"
$env:ADO_ORG="rivalitinc"
$env:ADO_PROJECT="Rival Insurance Technology"
python path\to\rival_plugin\scripts\export-ado-knowledge.py --output-dir .\knowledge
```

Or use the interactive shell wrapper (Mac/Linux only):

```bash
bash path/to/rival_plugin/scripts/setup-devops.sh
```

---

## 3. PAT Requirements

The Personal Access Token needs these scopes:

| Scope | Access | Required? | Used For |
|-------|--------|-----------|----------|
| Code | Read | **Yes** | Cloning all repositories |
| Wiki | Read | **Yes** | Exporting wiki content |
| Work Items | Read & Write | Optional | Board integration, ticket creation |
| Build | Read | Optional | Pipeline status checks |

### Creating a PAT

1. Navigate to: `https://dev.azure.com/{org}/_usersSettings/tokens`
2. Click **New Token**
3. Set Name: `Rival Plugin`, Expiration: maximum allowed
4. Select the scopes above
5. Click **Create** and copy immediately

### Security

- PAT is stored ONLY in `.env` (never in `config.json`)
- `.env` is created with `chmod 600` (owner-only read/write)
- `.env` is auto-added to `.gitignore`
- Git clone operations pass auth via `-c http.extraheader` (not persisted in `.git/config`)
- Error messages redact auth tokens automatically

---

## 4. Export Script (`scripts/export-ado-knowledge.py`)

Cross-platform Python 3 script that handles all Azure DevOps operations.

### Commands

```bash
# Test connection (validates org + project access)
python3 export-ado-knowledge.py --test-connection

# Full export (repos + wikis)
python3 export-ado-knowledge.py --output-dir ./knowledge

# Repos only
python3 export-ado-knowledge.py --output-dir ./knowledge --skip-wikis

# Wikis only
python3 export-ado-knowledge.py --output-dir ./knowledge --skip-repos
```

### Features

- **Incremental updates**: If repos already exist, does `git fetch + pull` instead of re-cloning
- **Collision prevention**: If two repo names sanitize to the same directory name, appends `_2`, `_3` etc.
- **Wiki depth limit**: Protects against circular references (max 50 levels deep)
- **Graceful failures**: If one repo fails to clone, continues with the rest
- **PAT safety**: Auth tokens are masked in all error messages and logs

### Output: `summary.json`

The export script creates a `summary.json` that lists everything downloaded:

```json
{
  "generatedAt": "2026-04-03T14:30:00Z",
  "repos": [
    {"name": "Rival.Apps.API", "id": "...", "path": "repos/Rival.Apps.API", "remoteUrl": "...", "defaultBranch": "refs/heads/main"}
  ],
  "wikis": [
    {"name": "Rival-Insurance-Technology.wiki", "id": "...", "type": "projectWiki", "path": "wikis/Rival-Insurance-Technology.wiki"}
  ]
}
```

Rival init reads this to validate that all expected repos were cloned.

---

## 5. Paths in Config

After init, `.rival/config.json` stores all discovered paths so other skills don't need to re-discover them:

```json
{
  "paths": {
    "plugin_root": "/Users/user/rival_plugin",
    "export_script": "/Users/user/rival_plugin/scripts/export-ado-knowledge.py",
    "knowledge_dir": "./knowledge",
    "python_cmd": "python3",
    "platform": "macos"
  }
}
```

All Rival skills read `config.paths` to find:
- The export script (for re-pulling, refreshing)
- The knowledge directory (for repo/wiki access)
- The Python command (for running the export script)
- The platform (for constructing platform-appropriate commands)

---

## 6. Wiki Access

After export, wiki content is available locally as markdown files:

```
knowledge/wikis/Rival-Insurance-Technology.wiki/
  manifest.json           Wiki metadata + page tree
  pages/                  Markdown content, organized by wiki path
    index.md
    Architecture/
      index.md
    Onboarding/
      index.md
  assets/                 Downloaded images and attachments
  git/                    Git clone of wiki repo (if available)
```

Rival agents reference wiki content during:
- **Planning** — architecture decisions, team conventions, domain glossary
- **Research** — existing documentation, standards

---

## 7. Board Integration (Work Items)

When the PAT has Work Items (Read & Write) scope, Rival can create tickets on Azure DevOps Boards.

### How It Works

1. During `/rival:rival-research`, the agent identifies actionable findings
2. Each finding is formatted as a work item proposal and presented to the user
3. On approval, the agent calls the Azure DevOps REST API to create the work item

### API Details

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Task?api-version=7.1
Content-Type: application/json-patch+json
Authorization: Basic base64(:PAT)
```

### Work Item Fields

| Field | API Path | Description |
|-------|----------|-------------|
| Title | `/fields/System.Title` | Short summary |
| Description | `/fields/System.Description` | HTML-formatted body with context and proposed fix |
| Area Path | `/fields/System.AreaPath` | Team area |
| Iteration Path | `/fields/System.IterationPath` | Sprint/iteration |
| Tags | `/fields/System.Tags` | `rival-generated; {category}` |

---

## 8. Windows Support

The Python export script works on all platforms. The shell wrapper (`setup-devops.sh`) is Mac/Linux only.

| Platform | How to Run |
|----------|-----------|
| macOS | `/rival:rival-init` (recommended) or `bash setup-devops.sh` |
| Linux | `/rival:rival-init` (recommended) or `bash setup-devops.sh` |
| Windows | `/rival:rival-init` (recommended) or run the Python script directly via PowerShell |

Windows users running Claude Code will use `/rival:rival-init` which calls the Python script directly — no shell wrapper needed.

---

## 9. Refreshing / Re-pulling

To update repos and wikis after initial setup:

- **Via Rival**: Run `/rival:rival-init` and choose option 4 ("Re-pull from Azure DevOps")
- **Via shell**: `bash setup-devops.sh --refresh`
- **Via Python**: Re-run the export script (it does `git fetch + pull` on existing repos)
- **Via config**: Rival reads `config.paths.export_script` and `config.paths.python_cmd` to run the script
