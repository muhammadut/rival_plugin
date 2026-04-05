#!/usr/bin/env python3
"""
Rival Plugin — Team Status Enriched Data Gatherer

Gathers enriched data from Azure DevOps for team analysis:
- Active branches and their authors (last N days)
- Full PR details (description, changed files, commits)
- Full work item details (description, parent/child links, acceptance criteria)
- Cross-board visibility (no area path filtering)

Outputs structured JSON that Claude synthesizes into narrative reports.

Environment variables (from .env):
  ADO_PAT           Required. Azure DevOps personal access token.
  ADO_ORG           Required. Azure DevOps organization name.
  ADO_PROJECT       Required. Azure DevOps project name.

Usage:
  python3 team-status.py --config .rival/team.yaml --env .env --team skunk
  python3 team-status.py --names "Bhoomika,Amy,Satish" --env .env
  python3 team-status.py --team skunk --refresh-roster
  python3 team-status.py --team skunk --window 90
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple
from urllib import error, parse, request


API_VERSION = "7.1"
API_VERSION_PREVIEW = "7.1-preview.1"
DEFAULT_WINDOW_DAYS = 60

# Work item state buckets
COMPLETED_STATES = {"Closed", "Done", "Resolved", "Completed", "Removed"}
ACTIVE_STATES = {"Active", "In Progress", "Committed", "Doing"}
BACKLOG_STATES = {"New", "Proposed", "To Do", "Approved", "Open"}


class AzureDevOpsError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[rival] {message}", flush=True)


def quote_path_component(value: str) -> str:
    return parse.quote(value, safe="")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now_utc() - timedelta(days=n)


def iso_utc(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# Env + Config loading
# ============================================================

def load_env(env_path: Path) -> Dict[str, str]:
    env = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key.startswith("ADO_"):
            env[key] = value
    return env


def load_team_config(config_path: Path) -> Dict:
    if not config_path.exists():
        raise AzureDevOpsError(f"Team config not found: {config_path}")
    content = config_path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        pass
    return parse_simple_yaml(content)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2:
        if (value[0] == value[-1]) and value[0] in ('"', "'"):
            return value[1:-1]
    return value


def parse_simple_yaml(content: str) -> Dict:
    """Simple YAML parser for team.yaml structure."""
    lines = content.splitlines()
    root: Dict = {}
    stack: List = [(-1, root, "dict")]

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.rstrip()
        i += 1
        if not stripped or stripped.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        content_line = stripped.lstrip()

        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            raise AzureDevOpsError(f"Parse error at: '{raw_line}'")

        _, parent, parent_kind = stack[-1]

        if content_line.startswith("- "):
            if parent_kind != "list":
                raise AzureDevOpsError(f"List item outside list: '{raw_line}'")
            item_content = content_line[2:].strip()

            if ":" not in item_content or item_content.endswith(":"):
                parent.append(_strip_quotes(item_content.rstrip(":")))
                continue

            key, _, value = item_content.partition(":")
            new_item: Dict = {}
            if value.strip():
                new_item[key.strip()] = _strip_quotes(value.strip())
            parent.append(new_item)
            stack.append((indent, new_item, "dict"))
            continue

        if ":" not in content_line:
            continue

        key, _, value = content_line.partition(":")
        key = key.strip()
        value = value.strip()

        if parent_kind != "dict":
            raise AzureDevOpsError(f"Key outside dict: '{raw_line}'")

        if value:
            parent[key] = _strip_quotes(value)
        else:
            next_child = _peek_next_content(lines, i)
            if next_child and next_child.lstrip().startswith("- "):
                parent[key] = []
                stack.append((indent, parent[key], "list"))
            else:
                parent[key] = {}
                stack.append((indent, parent[key], "dict"))

    return root


def _peek_next_content(lines: List[str], start_idx: int) -> Optional[str]:
    for j in range(start_idx, len(lines)):
        line = lines[j]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        return line
    return None


# ============================================================
# Azure DevOps Client
# ============================================================

@dataclass
class AzureDevOpsClient:
    organization: str
    project: str
    pat: str

    def __post_init__(self) -> None:
        token = base64.b64encode(f":{self.pat}".encode("utf-8")).decode("ascii")
        self.auth_header = f"Basic {token}"
        self.base_api = f"https://dev.azure.com/{quote_path_component(self.organization)}"
        self.project_api = f"{self.base_api}/{quote_path_component(self.project)}"

    def _request(self, url: str, method: str = "GET", body: Optional[dict] = None) -> dict:
        headers = {
            "Authorization": self.auth_header,
            "Accept": "application/json",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")

        req = request.Request(url, headers=headers, method=method, data=data)
        try:
            with request.urlopen(req, timeout=60) as resp:
                payload = resp.read()
                if not payload:
                    return {}
                return json.loads(payload.decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise AzureDevOpsError(f"HTTP {exc.code} {method} {url[:80]}...: {detail}") from exc
        except (error.URLError, socket.timeout, OSError) as exc:
            raise AzureDevOpsError(f"Network error {method}: {exc}") from exc

    # ---- Repos & Branches ----

    def get_repo(self, repo_name: str) -> Optional[Dict]:
        url = f"{self.project_api}/_apis/git/repositories/{quote_path_component(repo_name)}?api-version={API_VERSION}"
        try:
            return self._request(url)
        except AzureDevOpsError:
            return None

    def list_branches(self, repo_id: str) -> List[Dict]:
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/refs"
            f"?filter=heads/&api-version={API_VERSION}&$top=500"
        )
        data = self._request(url)
        return data.get("value", [])

    def list_commits(self, repo_id: str, from_date: datetime, top: int = 200) -> List[Dict]:
        """List commits across all branches since from_date."""
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/commits"
            f"?searchCriteria.fromDate={iso_utc(from_date)}"
            f"&searchCriteria.$top={top}"
            f"&api-version={API_VERSION}"
        )
        data = self._request(url)
        return data.get("value", [])

    # ---- Pull Requests ----

    def list_active_prs(self, repo_names: Optional[List[str]] = None) -> List[Dict]:
        url = (
            f"{self.project_api}/_apis/git/pullrequests"
            f"?searchCriteria.status=active&api-version={API_VERSION}&$top=200"
        )
        data = self._request(url)
        prs = data.get("value", [])
        if repo_names:
            prs = [pr for pr in prs if pr.get("repository", {}).get("name") in repo_names]
        return prs

    def get_pr_details(self, repo_id: str, pr_id: int) -> Dict:
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}"
            f"?api-version={API_VERSION}"
        )
        return self._request(url)

    def get_pr_commits(self, repo_id: str, pr_id: int) -> List[Dict]:
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/commits"
            f"?api-version={API_VERSION}&$top=50"
        )
        data = self._request(url)
        return data.get("value", [])

    def get_pr_iterations(self, repo_id: str, pr_id: int) -> List[Dict]:
        """Get PR iterations (shows files changed per iteration)."""
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}/iterations"
            f"?api-version={API_VERSION}"
        )
        data = self._request(url)
        return data.get("value", [])

    def get_pr_changes(self, repo_id: str, pr_id: int, iteration_id: int) -> Dict:
        url = (
            f"{self.base_api}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}"
            f"/iterations/{iteration_id}/changes?api-version={API_VERSION}&$top=200"
        )
        return self._request(url)

    # ---- Work Items ----

    def query_work_items_by_person(self, assigned_to_email: str, window_days: int) -> List[int]:
        """Get work item IDs assigned to a person, active or recently changed."""
        def esc(v: str) -> str:
            return str(v).replace("'", "''")

        from_date = iso_utc(days_ago(window_days))

        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.AssignedTo] CONTAINS '{esc(assigned_to_email)}' "
            f"AND ([System.State] IN ('Active', 'In Progress', 'Committed', 'Doing', "
            f"'New', 'Proposed', 'To Do', 'Approved', 'Open') "
            f"OR ([System.State] IN ('Closed', 'Done', 'Resolved', 'Completed') "
            f"AND [System.ChangedDate] >= '{from_date}')) "
            "ORDER BY [System.ChangedDate] DESC"
        )

        url = f"{self.project_api}/_apis/wit/wiql?api-version={API_VERSION}&$top=200"
        result = self._request(url, method="POST", body={"query": wiql})
        refs = result.get("workItems", [])
        return [wi["id"] for wi in refs]

    def get_work_items(self, ids: List[int]) -> List[Dict]:
        """Get full work item details including description."""
        if not ids:
            return []
        items = []
        # API limit: 200 ids per request
        for chunk_start in range(0, len(ids), 200):
            chunk = ids[chunk_start:chunk_start + 200]
            ids_str = ",".join(str(i) for i in chunk)
            url = (
                f"{self.project_api}/_apis/wit/workitems"
                f"?ids={ids_str}"
                f"&$expand=relations"
                f"&api-version={API_VERSION}"
            )
            data = self._request(url)
            items.extend(data.get("value", []))
        return items

    # ---- Identity Resolution ----

    def resolve_identity(self, name_query: str) -> List[Dict]:
        """Resolve a name to ADO identities. Returns list of matches."""
        url = (
            f"{self.base_api}/_apis/identities"
            f"?searchFilter=General&filterValue={quote_path_component(name_query)}"
            f"&api-version={API_VERSION_PREVIEW}"
        )
        try:
            data = self._request(url)
            return data.get("value", [])
        except AzureDevOpsError:
            return []


# ============================================================
# Branch Discovery & Author Extraction
# ============================================================

def discover_members_from_repos(
    client: AzureDevOpsClient,
    repo_names: List[str],
    window_days: int,
) -> List[Dict]:
    """Scan repos for recent commit activity, extract unique authors."""
    from_date = days_ago(window_days)
    authors: Dict[str, Dict] = {}  # email -> author info

    for repo_name in repo_names:
        log(f"Scanning {repo_name} for activity (last {window_days}d)...")
        repo = client.get_repo(repo_name)
        if not repo:
            log(f"  WARNING: repo '{repo_name}' not found, skipping")
            continue
        repo_id = repo["id"]

        try:
            commits = client.list_commits(repo_id, from_date)
        except AzureDevOpsError as exc:
            log(f"  WARNING: failed to list commits for {repo_name}: {exc}")
            continue

        # Also list branches to count branches per author
        try:
            branches = client.list_branches(repo_id)
        except AzureDevOpsError:
            branches = []

        for commit in commits:
            author = commit.get("author", {})
            email = (author.get("email") or "").lower().strip()
            name = author.get("name", "").strip()
            if not email or not name:
                continue
            # Skip bot/service accounts
            if any(pattern in email.lower() for pattern in ["noreply", "[bot]", "azuredevops", "github-actions"]):
                continue
            if any(pattern in name.lower() for pattern in ["[bot]", "azure devops", "github actions"]):
                continue

            if email not in authors:
                authors[email] = {
                    "name": name,
                    "email": email,
                    "commits": 0,
                    "repos": set(),
                    "last_active": None,
                }
            authors[email]["commits"] += 1
            authors[email]["repos"].add(repo_name)
            commit_date = commit.get("author", {}).get("date", "")
            if commit_date:
                if not authors[email]["last_active"] or commit_date > authors[email]["last_active"]:
                    authors[email]["last_active"] = commit_date

    # Convert to list, serialize sets
    result = []
    for email, info in authors.items():
        result.append({
            "name": info["name"],
            "email": email,
            "commits": info["commits"],
            "repos_active": sorted(info["repos"]),
            "last_active": info["last_active"],
        })
    result.sort(key=lambda x: x["commits"], reverse=True)
    return result


# ============================================================
# Data Enrichment
# ============================================================

def enrich_pr(client: AzureDevOpsClient, pr: Dict) -> Dict:
    """Fetch PR description, changed files, commits."""
    repo_id = pr.get("repository", {}).get("id")
    pr_id = pr.get("pullRequestId")
    enriched = dict(pr)

    if not repo_id or not pr_id:
        return enriched

    try:
        commits = client.get_pr_commits(repo_id, pr_id)
        enriched["commits_list"] = [
            {
                "id": c.get("commitId", "")[:8],
                "comment": c.get("comment", "").split("\n")[0][:200],
                "author": c.get("author", {}).get("name", ""),
                "date": c.get("author", {}).get("date", ""),
            }
            for c in commits[:10]
        ]
    except AzureDevOpsError:
        enriched["commits_list"] = []

    try:
        iterations = client.get_pr_iterations(repo_id, pr_id)
        if iterations:
            latest_iter_id = iterations[-1].get("id")
            changes_data = client.get_pr_changes(repo_id, pr_id, latest_iter_id)
            changes = changes_data.get("changeEntries", [])
            files_changed = []
            for change in changes[:100]:
                item = change.get("item", {})
                files_changed.append({
                    "path": item.get("path", ""),
                    "change_type": change.get("changeType", ""),
                })
            enriched["files_changed"] = files_changed
            enriched["files_count"] = len(changes)
    except AzureDevOpsError:
        enriched["files_changed"] = []
        enriched["files_count"] = 0

    return enriched


def categorize_work_items(items: List[Dict], window_days: int) -> Dict:
    """Split work items into completed/active/backlog buckets."""
    completed = []
    active = []
    backlog = []
    cutoff = days_ago(window_days)

    for item in items:
        fields = item.get("fields", {})
        state = fields.get("System.State", "")

        if state in COMPLETED_STATES:
            changed_date = fields.get("System.ChangedDate", "")
            if changed_date:
                try:
                    dt = datetime.fromisoformat(changed_date.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        completed.append(item)
                except ValueError:
                    pass
        elif state in ACTIVE_STATES:
            active.append(item)
        elif state in BACKLOG_STATES:
            backlog.append(item)

    return {"completed": completed, "active": active, "backlog": backlog}


# ============================================================
# Main orchestration
# ============================================================

def gather_for_member(
    client: AzureDevOpsClient,
    member: Dict,
    window_days: int,
    team_repos: Optional[List[str]] = None,
    all_active_prs: Optional[List[Dict]] = None,
) -> Dict:
    """Gather all enriched data for one person."""
    email = member.get("email", "")
    name = member.get("name", "")

    # Get work items
    log(f"  Fetching work items for {name}...")
    try:
        wi_ids = client.query_work_items_by_person(email, window_days)
        work_items = client.get_work_items(wi_ids)
    except AzureDevOpsError as exc:
        log(f"    WARNING: {exc}")
        work_items = []

    categorized = categorize_work_items(work_items, window_days)

    # Find this person's PRs
    member_prs = []
    if all_active_prs:
        for pr in all_active_prs:
            creator = pr.get("createdBy", {})
            creator_email = (creator.get("uniqueName") or creator.get("mailAddress") or "").lower()
            if creator_email == email.lower():
                member_prs.append(pr)

    # Enrich each PR
    log(f"  Enriching {len(member_prs)} PRs for {name}...")
    enriched_prs = [enrich_pr(client, pr) for pr in member_prs]

    # Boards they're active on
    boards = set()
    for item in work_items:
        area = item.get("fields", {}).get("System.AreaPath", "")
        if area:
            boards.add(area)

    return {
        "member": {
            "name": name,
            "email": email,
            "commits_60d": member.get("commits", 0),
            "repos_active": member.get("repos_active", []),
            "last_active": member.get("last_active"),
        },
        "boards": sorted(boards),
        "work_items": {
            "completed": categorized["completed"],
            "active": categorized["active"],
            "backlog": categorized["backlog"],
        },
        "pull_requests": enriched_prs,
    }


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Rival — Enriched Team Status Data Gathering")
    parser.add_argument("--config", default=".rival/team.yaml")
    parser.add_argument("--env", default=".env")
    parser.add_argument("--team", help="Team name from team.yaml")
    parser.add_argument("--names", help="Comma-separated list of names to track (ad-hoc)")
    parser.add_argument("--window", type=int, help="Activity window in days")
    parser.add_argument("--refresh-roster", action="store_true", help="Re-discover members from branches")
    parser.add_argument("--output-dir", default=".team-status", help="Output directory (date-stamped subdir will be created)")
    args = parser.parse_args(argv)

    # Load env
    env = load_env(Path(args.env))
    ado_pat = env.get("ADO_PAT") or os.environ.get("ADO_PAT", "")
    ado_org = env.get("ADO_ORG") or os.environ.get("ADO_ORG", "")
    ado_project = env.get("ADO_PROJECT") or os.environ.get("ADO_PROJECT", "")

    if not all([ado_pat, ado_org, ado_project]):
        log(f"ERROR: Missing ADO_PAT, ADO_ORG, or ADO_PROJECT. Check {args.env}")
        return 1

    client = AzureDevOpsClient(organization=ado_org, project=ado_project, pat=ado_pat)

    # Load team config
    config_path = Path(args.config)
    config = {}
    if config_path.exists():
        try:
            config = load_team_config(config_path)
        except AzureDevOpsError as exc:
            log(f"WARNING: Could not parse config: {exc}")

    # Create output directory
    date_str = now_utc().strftime("%Y-%m-%d")
    output_dir = Path(args.output_dir) / date_str
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine members to track
    members: List[Dict] = []
    team_repos: List[str] = []
    scope_desc = ""
    window_days = args.window or DEFAULT_WINDOW_DAYS

    if args.names:
        # Name-driven mode
        scope_desc = f"Names: {args.names}"
        log("Resolving names to Azure DevOps identities...")
        for raw_name in args.names.split(","):
            name_query = raw_name.strip()
            if not name_query:
                continue
            identities = client.resolve_identity(name_query)
            if identities:
                # Take the first match
                ident = identities[0]
                members.append({
                    "name": ident.get("providerDisplayName", name_query),
                    "email": ident.get("properties", {}).get("Mail", {}).get("$value", "")
                             or ident.get("descriptor", ""),
                    "commits": 0,
                    "repos_active": [],
                    "last_active": None,
                })
                log(f"  Resolved: {name_query} → {ident.get('providerDisplayName', '?')}")
            else:
                log(f"  WARNING: could not resolve '{name_query}'")
    else:
        # Team-driven mode
        teams_dict = config.get("teams", {})
        team_name = args.team or config.get("default_team")
        if not team_name or team_name not in teams_dict:
            log(f"ERROR: team '{team_name}' not found in {config_path}")
            log("Either specify --team <name>, --names, or create team.yaml")
            return 1

        team_config = teams_dict[team_name]
        team_repos = team_config.get("repos", [])
        if team_config.get("activity_window_days"):
            window_days = int(team_config["activity_window_days"])
        scope_desc = f"Team: {team_config.get('name', team_name)}"

        # Discover or load cached members
        needs_refresh = args.refresh_roster or not team_config.get("discovered_members")
        if needs_refresh:
            log(f"Discovering active members from {len(team_repos)} repos (window: {window_days}d)...")
            members = discover_members_from_repos(client, team_repos, window_days)
            log(f"Discovered {len(members)} active members.")
            # Persist to team.yaml (simple append — user can regenerate)
            team_config["discovered_members"] = members
            team_config["discovery_refreshed"] = iso_utc(now_utc())
            # Note: we don't auto-save team.yaml (YAML writing is lossy for comments).
            # Instead, output a separate roster file that user can merge.
            roster_path = output_dir / "discovered-roster.json"
            roster_path.write_text(json.dumps({
                "team": team_name,
                "refreshed_at": iso_utc(now_utc()),
                "window_days": window_days,
                "members": members,
            }, indent=2), encoding="utf-8")
            log(f"Roster saved: {roster_path}")
        else:
            members = team_config.get("discovered_members", [])
            log(f"Using cached roster: {len(members)} members (use --refresh-roster to update)")

    if not members:
        log("No members to track. Exiting.")
        return 1

    # Fetch all active PRs once (for cross-reference)
    log("Fetching all active PRs in project...")
    try:
        all_prs = client.list_active_prs(repo_names=team_repos if team_repos else None)
    except AzureDevOpsError as exc:
        log(f"WARNING: failed to list PRs: {exc}")
        all_prs = []

    # Gather per-member data
    per_member_data = []
    for member in members:
        log(f"Processing: {member.get('name')}")
        member_data = gather_for_member(
            client=client,
            member=member,
            window_days=window_days,
            team_repos=team_repos,
            all_active_prs=all_prs,
        )
        per_member_data.append(member_data)

    # Write raw data
    raw_data = {
        "generated_at": iso_utc(now_utc()),
        "scope": scope_desc,
        "window_days": window_days,
        "team_repos": team_repos,
        "organization": ado_org,
        "project": ado_project,
        "members": per_member_data,
    }

    raw_data_path = output_dir / "raw-data.json"
    raw_data_path.write_text(json.dumps(raw_data, indent=2, default=str), encoding="utf-8")

    log("=" * 60)
    log(f"Data gathered successfully.")
    log(f"  Scope: {scope_desc}")
    log(f"  Members: {len(per_member_data)}")
    log(f"  Total PRs: {sum(len(m['pull_requests']) for m in per_member_data)}")
    log(f"  Total work items: {sum(len(m['work_items']['active']) + len(m['work_items']['completed']) + len(m['work_items']['backlog']) for m in per_member_data)}")
    log(f"  Output: {raw_data_path}")
    log("=" * 60)

    # Print path for the skill to read
    print(str(raw_data_path.resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except AzureDevOpsError as exc:
        print(f"[rival] ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\n[rival] Interrupted.", file=sys.stderr)
        raise SystemExit(130)
