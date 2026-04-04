# Rival DevOps Integration

This document describes how the Rival plugin integrates with Azure DevOps (and optionally GitHub) to enable end-to-end planning, research, and ticket creation workflows.

---

## 1. `.paths.md` Format -- Full Specification

The `.paths.md` file is a per-project configuration file that lives in the project root. It stores personal access tokens, organization URLs, repo mappings, wiki endpoints, and board settings so that Rival agents can interact with DevOps services without prompting the user each time.

> **Security**: `.paths.md` contains secrets. Never commit it. Always add it to `.gitignore`.

### Template

```markdown
# .paths.md -- Rival DevOps Configuration
# DO NOT commit this file. Add to .gitignore.

## Azure DevOps
- PAT: <personal-access-token>
- Organization: https://dev.azure.com/myorg
- Project: RPM-Backend
- Repos:
  - quotation-api: https://dev.azure.com/myorg/RPM/_git/quotation-api
  - shared-models: https://dev.azure.com/myorg/RPM/_git/shared-models

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

### Field Reference

| Section | Field | Required | Description |
|---------|-------|----------|-------------|
| Azure DevOps | PAT | Yes | Personal access token with Code (Read/Write), Wiki (Read), and Work Items (Read/Write) scopes |
| Azure DevOps | Organization | Yes | Full URL to the Azure DevOps organization |
| Azure DevOps | Project | Yes | Project name within the organization |
| Azure DevOps | Repos | Yes | Key-value pairs mapping a short name to the full clone URL |
| Wiki | URL | No | Full URL to the project wiki; enables wiki context during planning |
| Boards | URL | No | Full URL to the boards hub |
| Boards | Default area | No | Default area path for new work items (backslash-separated) |
| Boards | Default iteration | No | Default iteration/sprint for new work items |
| GitHub | PAT | No | GitHub personal access token (only needed if repos are on GitHub) |
| GitHub | Repos | No | Key-value pairs for GitHub repos |

### How Rival Reads `.paths.md`

On `/rival:init`, the plugin scans the project root for `.paths.md`. If found, it parses each section and stores the values in the agent's in-memory context. The parser expects:

- Sections denoted by `## Heading`
- Key-value pairs as `- Key: Value`
- Nested lists (repos) as `  - name: url` (two-space indent)

---

## 2. Repo Cloning

The setup script (`scripts/setup-devops.sh`) automates cloning all repos listed in `.paths.md`.

### How It Works

1. The script reads the `Repos` entries from each provider section.
2. For Azure DevOps repos, it constructs the authenticated clone URL:
   ```
   https://<PAT>@dev.azure.com/myorg/RPM/_git/quotation-api
   ```
3. For GitHub repos, it uses:
   ```
   https://<PAT>@github.com/muhammadut/rival_plugin.git
   ```
4. Each repo is cloned into a `./repos/<short-name>/` directory relative to the project root.
5. If the directory already exists, the script performs a `git pull` instead.

### Directory Layout After Cloning

```
project-root/
  .paths.md
  repos/
    quotation-api/
    shared-models/
    rival-plugin/
```

### Security Considerations

- PATs are embedded in the clone URL only during the git operation. The script does **not** persist authenticated URLs in `.git/config`; it uses `git clone` with the token inline and then removes credentials from the remote config.
- All cloned repos are added to the project's `.gitignore` under `repos/`.

---

## 3. Wiki Access

Rival agents can read Azure DevOps wiki pages to gather organizational context during `/rival:plan` and `/rival:research` workflows.

### How It Works

1. The agent reads the Wiki URL from `.paths.md`.
2. It calls the Azure DevOps REST API:
   ```
   GET https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wikiId}/pages?path={pagePath}&api-version=7.1
   ```
   with the PAT as a Basic Auth header (`Authorization: Basic base64(:PAT)`).
3. The returned Markdown content is injected into the agent's context window as reference material.
4. Wiki pages are cached locally in `.rival/wiki-cache/` to avoid redundant API calls within the same session.

### Use Cases

- **Architecture decisions**: Agents read ADR (Architecture Decision Record) wiki pages before planning.
- **Team conventions**: Coding standards, naming conventions, and PR templates.
- **Domain glossary**: Business terms and definitions that inform variable naming and documentation.

---

## 4. Board Integration

The `/rival:research` skill can create work items (tickets) directly on Azure DevOps Boards from research findings.

### How It Works

1. During `/rival:research`, the agent identifies actionable findings -- bugs, tech debt, missing features, or improvements.
2. Each finding is formatted as a work item proposal and presented to the user for approval.
3. On approval, the agent calls the Azure DevOps REST API:
   ```
   POST https://dev.azure.com/{org}/{project}/_apis/wit/workitems/$Task?api-version=7.1
   Content-Type: application/json-patch+json
   Authorization: Basic base64(:PAT)
   ```
4. The work item is created with the fields described in section 5 below.
5. The agent returns the work item URL to the user for confirmation.

### Permissions Required

The PAT must have the **Work Items (Read, Write)** scope. If the scope is missing, the agent will warn the user and skip ticket creation.

---

## 5. Ticket Creation Format

When Rival creates a work item on Azure DevOps Boards, it uses the following fields:

### Required Fields

| Field | API Path | Description | Example |
|-------|----------|-------------|---------|
| Title | `/fields/System.Title` | Short summary of the work item | `Fix null reference in QuotationService.Calculate()` |
| Description | `/fields/System.Description` | HTML-formatted body with context, root cause, and proposed fix | See template below |
| Area Path | `/fields/System.AreaPath` | Team area (from `.paths.md` default or overridden) | `RPM\Backend` |
| Iteration Path | `/fields/System.IterationPath` | Sprint/iteration (from `.paths.md` default or overridden) | `RPM\Sprint 42` |

### Optional Fields

| Field | API Path | Description |
|-------|----------|-------------|
| Acceptance Criteria | `/fields/Microsoft.VSTS.Common.AcceptanceCriteria` | HTML-formatted list of conditions for completion |
| Tags | `/fields/System.Tags` | Semicolon-separated tags, e.g. `rival-generated; tech-debt` |
| Priority | `/fields/Microsoft.VSTS.Common.Priority` | 1 (Critical) through 4 (Low) |
| Work Item Type | URL parameter `$Type` | `Task`, `Bug`, `User Story`, or `Feature` |

### Description Template

```html
<h3>Context</h3>
<p>Found during <code>/rival:research</code> analysis of <code>{repo-name}</code>.</p>

<h3>Finding</h3>
<p>{detailed description of the issue or improvement}</p>

<h3>Proposed Fix</h3>
<p>{suggested approach to resolve the issue}</p>

<h3>References</h3>
<ul>
  <li>File: <code>{file-path}</code>, Line {line-number}</li>
  <li>Related wiki: <a href="{wiki-url}">{page-title}</a></li>
</ul>

<p><em>Auto-generated by Rival Plugin</em></p>
```

### Acceptance Criteria Template

```html
<ul>
  <li>[ ] {criterion 1}</li>
  <li>[ ] {criterion 2}</li>
  <li>[ ] Unit tests pass with no regressions</li>
  <li>[ ] Code reviewed and approved</li>
</ul>
```

### Example API Payload

```json
[
  {
    "op": "add",
    "path": "/fields/System.Title",
    "value": "Fix null reference in QuotationService.Calculate()"
  },
  {
    "op": "add",
    "path": "/fields/System.Description",
    "value": "<h3>Context</h3><p>Found during <code>/rival:research</code> analysis of <code>quotation-api</code>.</p>..."
  },
  {
    "op": "add",
    "path": "/fields/System.AreaPath",
    "value": "RPM\\Backend"
  },
  {
    "op": "add",
    "path": "/fields/System.IterationPath",
    "value": "RPM\\Sprint 42"
  },
  {
    "op": "add",
    "path": "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
    "value": "<ul><li>[ ] Null check added before Calculate() call</li><li>[ ] Unit test covers null input scenario</li></ul>"
  },
  {
    "op": "add",
    "path": "/fields/System.Tags",
    "value": "rival-generated; bug"
  }
]
```

---

## Next Steps

- [ ] Implement the full `scripts/setup-devops.sh` (replace placeholder)
- [ ] Add `.paths.md` parser to `/rival:init`
- [ ] Build wiki fetcher with caching
- [ ] Build work item creation module
- [ ] Add board integration to `/rival:research` output
