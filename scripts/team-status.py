#!/usr/bin/env python3
"""
Rival Plugin — Team Status Query

Queries Azure DevOps API for PRs, work items, and boards activity
scoped to a team, member, repo, or board.

Environment variables (from .env):
  ADO_PAT           Required. Azure DevOps personal access token.
  ADO_ORG           Required. Azure DevOps organization name.
  ADO_PROJECT       Required. Azure DevOps project name.

Usage:
  python3 team-status.py --team rpm-backend --config .rival/team.yaml
  python3 team-status.py --member "Alice Smith" --config .rival/team.yaml
  python3 team-status.py --repo Rival.Customer.API --config .rival/team.yaml
  python3 team-status.py --board RPM-Backend --config .rival/team.yaml
  python3 team-status.py --all --config .rival/team.yaml
  python3 team-status.py --me --config .rival/team.yaml  # uses git config user.email
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
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from urllib import error, parse, request


API_VERSION = "7.1"
API_VERSION_PREVIEW = "7.1-preview.1"


class AzureDevOpsError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[rival] {message}", flush=True)


def quote_path_component(value: str) -> str:
    return parse.quote(value, safe="")


def load_env(env_path: Path) -> Dict[str, str]:
    """Load ADO_* variables from a .env file."""
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
    """Load team.yaml config. Tries PyYAML first, falls back to custom parser."""
    if not config_path.exists():
        raise AzureDevOpsError(f"Team config not found: {config_path}")

    content = config_path.read_text(encoding="utf-8")

    # Prefer PyYAML if available (more robust)
    try:
        import yaml
        return yaml.safe_load(content) or {}
    except ImportError:
        pass

    return parse_simple_yaml(content)


def _strip_quotes(value: str) -> str:
    """Strip matching surrounding quotes (not inner ones)."""
    value = value.strip()
    if len(value) >= 2:
        if (value[0] == value[-1]) and value[0] in ('"', "'"):
            return value[1:-1]
    return value


def parse_simple_yaml(content: str) -> Dict:
    """
    Parse a simple YAML structure supporting:
    - Top-level dicts
    - Nested dicts (increasing indent)
    - Lists of scalars
    - Lists of dicts (list item with multiple key-value properties)

    Does NOT support: anchors, refs, multiline strings, flow style, block scalars.
    """
    lines = content.splitlines()
    root: Dict = {}
    # Stack tracks (indent, container, kind) where kind is "dict" or "list"
    # Container is the actual dict or list being filled at that indent level
    stack: List = [(-1, root, "dict")]

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.rstrip()
        i += 1

        # Skip empty and comments
        if not stripped or stripped.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        content_line = stripped.lstrip()

        # Pop stack until we find a parent with strictly lesser indent
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if not stack:
            raise AzureDevOpsError(f"Parse error: orphan line '{raw_line}'")

        parent_indent, parent, parent_kind = stack[-1]

        # ==== List item: starts with "- " ====
        if content_line.startswith("- "):
            if parent_kind != "list":
                raise AzureDevOpsError(
                    f"Parse error: list item '-' found but parent is not a list at line: '{raw_line}'"
                )

            item_content = content_line[2:].strip()

            # Case 1: "- value" (scalar list item)
            if ":" not in item_content or item_content.endswith(":"):
                if item_content.endswith(":"):
                    # "- key:" without value — this is a dict item in the list with subkeys
                    new_dict: Dict = {}
                    key = item_content[:-1].strip()
                    # Edge case: "- :" malformed
                    if key:
                        new_dict[key] = {}
                        parent.append(new_dict)
                        # The dict's subkey goes deeper, so we push the key's value as container
                        stack.append((indent, new_dict, "dict"))
                        # The nested empty dict needs to be filled — push it with a higher virtual indent
                        # Actually we need to determine if it's a dict or list from next line
                        next_child = _peek_next_content(lines, i)
                        if next_child and next_child[1].lstrip().startswith("- "):
                            new_dict[key] = []
                            stack.append((indent + 2, new_dict[key], "list"))
                        else:
                            stack.append((indent + 2, new_dict[key], "dict"))
                    continue

                # Pure scalar: "- value"
                parent.append(_strip_quotes(item_content))
                continue

            # Case 2: "- key: value" (dict item, possibly with siblings)
            # Parse the inline key-value pair
            key, _, value = item_content.partition(":")
            key = key.strip()
            value = value.strip()

            new_item: Dict = {}
            if value:
                new_item[key] = _strip_quotes(value)
            else:
                # "- key:" with multi-line value below
                next_child = _peek_next_content(lines, i)
                if next_child and next_child[1].lstrip().startswith("- "):
                    new_item[key] = []
                else:
                    new_item[key] = {}

            parent.append(new_item)

            # Push the new_item as dict context so subsequent same-indent keys
            # (like "  email: foo") get added to this dict item
            # The subsequent keys will be at indent + 2 relative to the "-" marker
            stack.append((indent, new_item, "dict"))

            # If the inline value had no scalar, we need to also push its container
            if not value:
                stack.append((indent + 2, new_item[key], "list" if isinstance(new_item[key], list) else "dict"))
            continue

        # ==== Regular key-value line ====
        if ":" not in content_line:
            # Skip lines that aren't key-value or list items
            continue

        key, _, value = content_line.partition(":")
        key = key.strip()
        value = value.strip()

        if parent_kind != "dict":
            raise AzureDevOpsError(
                f"Parse error: key '{key}' found but parent is not a dict at line: '{raw_line}'"
            )

        if value:
            parent[key] = _strip_quotes(value)
        else:
            # Determine if next child is a list or dict
            next_child = _peek_next_content(lines, i)
            if next_child and next_child[1].lstrip().startswith("- "):
                parent[key] = []
                stack.append((indent, parent[key], "list"))
            else:
                parent[key] = {}
                stack.append((indent, parent[key], "dict"))

    return root


def _peek_next_content(lines: List[str], start_idx: int) -> Optional[tuple]:
    """Return (indent, line) of next non-empty, non-comment line."""
    for j in range(start_idx, len(lines)):
        line = lines[j]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        return (indent, line)
    return None


@dataclass
class AzureDevOpsClient:
    organization: str
    project: str
    pat: str

    def __post_init__(self) -> None:
        token = base64.b64encode(f":{self.pat}".encode("utf-8")).decode("ascii")
        self.auth_header = f"Basic {token}"
        self.base_api = f"https://dev.azure.com/{quote_path_component(self.organization)}"

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
            detail = exc.read().decode("utf-8", errors="replace")
            raise AzureDevOpsError(f"{method} {url} failed: HTTP {exc.code}: {detail[:200]}") from exc
        except (error.URLError, socket.timeout, OSError) as exc:
            raise AzureDevOpsError(f"{method} {url} network error: {exc}") from exc

    def list_active_pull_requests(self, repo_names: Optional[List[str]] = None) -> List[Dict]:
        """List active (open) PRs across the project, optionally filtered by repo."""
        url = (
            f"{self.base_api}/{quote_path_component(self.project)}/_apis/git/pullrequests"
            f"?searchCriteria.status=active&api-version={API_VERSION}&$top=200"
        )
        data = self._request(url)
        prs = data.get("value", [])
        if repo_names:
            prs = [pr for pr in prs if pr.get("repository", {}).get("name") in repo_names]
        return prs

    def list_work_items(
        self,
        assigned_to: Optional[str] = None,
        area_paths: Optional[List[str]] = None,
        iteration: Optional[str] = None,
        state_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Query work items via WIQL. All user-provided strings are escaped."""
        # WIQL escapes single quotes by doubling them
        def wiql_escape(value: str) -> str:
            return str(value).replace("'", "''")

        wiql_parts = ["SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo], [System.WorkItemType], [System.AreaPath], [System.IterationPath], [System.Tags], [System.ChangedDate] FROM WorkItems WHERE [System.TeamProject] = @project"]

        if assigned_to:
            wiql_parts.append(f"AND [System.AssignedTo] CONTAINS '{wiql_escape(assigned_to)}'")

        if state_filter is None:
            state_filter = ["Active", "In Progress", "New", "To Do", "Doing"]
        if state_filter:
            states = ", ".join(f"'{wiql_escape(s)}'" for s in state_filter)
            wiql_parts.append(f"AND [System.State] IN ({states})")

        if area_paths:
            area_conditions = " OR ".join(
                f"[System.AreaPath] UNDER '{wiql_escape(ap)}'" for ap in area_paths
            )
            wiql_parts.append(f"AND ({area_conditions})")

        if iteration and iteration != "current":
            wiql_parts.append(f"AND [System.IterationPath] = '{wiql_escape(iteration)}'")
        elif iteration == "current":
            wiql_parts.append("AND [System.IterationPath] = @currentIteration")

        wiql = " ".join(wiql_parts) + " ORDER BY [System.ChangedDate] DESC"

        url = f"{self.base_api}/{quote_path_component(self.project)}/_apis/wit/wiql?api-version={API_VERSION}&$top=100"
        result = self._request(url, method="POST", body={"query": wiql})
        work_item_refs = result.get("workItems", [])

        if not work_item_refs:
            return []

        ids = ",".join(str(wi["id"]) for wi in work_item_refs[:100])
        detail_url = (
            f"{self.base_api}/{quote_path_component(self.project)}/_apis/wit/workitems"
            f"?ids={ids}&api-version={API_VERSION}"
        )
        details = self._request(detail_url)
        return details.get("value", [])

    def get_current_iteration(self, team: Optional[str] = None) -> Optional[Dict]:
        """Get the current iteration for the project (or specific team)."""
        team_segment = f"/{quote_path_component(team)}" if team else ""
        url = (
            f"{self.base_api}/{quote_path_component(self.project)}{team_segment}"
            f"/_apis/work/teamsettings/iterations?$timeframe=current&api-version={API_VERSION}"
        )
        try:
            data = self._request(url)
            iterations = data.get("value", [])
            return iterations[0] if iterations else None
        except AzureDevOpsError:
            return None


def format_pr(pr: Dict) -> str:
    pr_id = pr.get("pullRequestId")
    title = pr.get("title", "")[:80]
    repo = pr.get("repository", {}).get("name", "?")
    source = pr.get("sourceRefName", "").replace("refs/heads/", "")
    creator = pr.get("createdBy", {}).get("displayName", "?")
    status = pr.get("status", "")
    reviewers = pr.get("reviewers", [])
    approved = sum(1 for r in reviewers if r.get("vote", 0) > 0)
    total = len(reviewers)
    return f"  #{pr_id} [{repo}] {title} — {creator} ({source}) — {approved}/{total} approved"


def format_work_item(wi: Dict) -> str:
    fields = wi.get("fields", {})
    wi_id = wi.get("id")
    title = fields.get("System.Title", "")[:70]
    wi_type = fields.get("System.WorkItemType", "")
    state = fields.get("System.State", "")
    assignee = fields.get("System.AssignedTo", {})
    assignee_name = assignee.get("displayName", "Unassigned") if isinstance(assignee, dict) else str(assignee)
    return f"  #{wi_id} [{wi_type}] {title} — {assignee_name} ({state})"


def render_report(
    scope: str,
    prs: List[Dict],
    work_items: List[Dict],
    team_config: Optional[Dict] = None,
) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"Team Status — {scope}")
    lines.append("=" * 70)
    lines.append("")

    if team_config:
        lines.append(f"Team: {team_config.get('name', 'Unknown')}")
        members = team_config.get("members", [])
        if members:
            names = [m.get("name", m.get("devops_id", "?")) if isinstance(m, dict) else m for m in members]
            lines.append(f"Members: {', '.join(names)}")
        lines.append("")

    lines.append(f"## Active Pull Requests ({len(prs)})")
    if prs:
        for pr in prs[:30]:
            lines.append(format_pr(pr))
        if len(prs) > 30:
            lines.append(f"  ... and {len(prs) - 30} more")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append(f"## Active Work Items ({len(work_items)})")
    if work_items:
        # Group by state
        by_state: Dict[str, List[Dict]] = {}
        for wi in work_items:
            state = wi.get("fields", {}).get("System.State", "Unknown")
            by_state.setdefault(state, []).append(wi)

        for state, items in sorted(by_state.items()):
            lines.append(f"\n### {state} ({len(items)})")
            for item in items[:20]:
                lines.append(format_work_item(item))
            if len(items) > 20:
                lines.append(f"  ... and {len(items) - 20} more")
    else:
        lines.append("  (none)")
    lines.append("")

    # Stats
    lines.append("## Summary")
    lines.append(f"  Active PRs: {len(prs)}")
    lines.append(f"  Work items: {len(work_items)}")
    lines.append("")

    return "\n".join(lines)


def get_git_email() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def find_team(config: Dict, team_name: Optional[str]) -> Optional[Dict]:
    teams = config.get("teams", {})
    if not team_name:
        team_name = config.get("default_team")
    if not team_name:
        return None
    return teams.get(team_name)


def find_member(config: Dict, query: str) -> Optional[Dict]:
    """Find a member by name, devops_id, or email (fuzzy)."""
    query_lower = query.lower()
    for team in config.get("teams", {}).values():
        for member in team.get("members", []):
            if not isinstance(member, dict):
                continue
            name = member.get("name", "").lower()
            devops_id = member.get("devops_id", "").lower()
            email = member.get("email", "").lower()
            if query_lower in name or query_lower == devops_id or query_lower in email:
                return member
    return None


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Rival Plugin — Team Status from Azure DevOps")
    parser.add_argument("--config", default=".rival/team.yaml", help="Path to team.yaml config")
    parser.add_argument("--env", default=".env", help="Path to .env with ADO_PAT")
    parser.add_argument("--team", help="Team name (from team.yaml)")
    parser.add_argument("--member", help="Member name, devops_id, or email")
    parser.add_argument("--repo", help="Filter by specific repo name")
    parser.add_argument("--board", help="Filter by board/area path")
    parser.add_argument("--me", action="store_true", help="Show my work (uses git config user.email)")
    parser.add_argument("--all", action="store_true", help="Exhaustive: all teams, all repos, all boards")
    parser.add_argument("--stale", action="store_true", help="Only show stale PRs (>7 days no activity)")
    parser.add_argument("--sprint", action="store_true", help="Focus on current iteration")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of formatted text")
    args = parser.parse_args(argv)

    # Load env
    env_path = Path(args.env)
    env = load_env(env_path)
    ado_pat = env.get("ADO_PAT") or os.environ.get("ADO_PAT", "")
    ado_org = env.get("ADO_ORG") or os.environ.get("ADO_ORG", "")
    ado_project = env.get("ADO_PROJECT") or os.environ.get("ADO_PROJECT", "")

    if not all([ado_pat, ado_org, ado_project]):
        log(f"ERROR: Missing ADO_PAT, ADO_ORG, or ADO_PROJECT. Check {env_path}")
        return 1

    client = AzureDevOpsClient(organization=ado_org, project=ado_project, pat=ado_pat)

    # Load team config
    config_path = Path(args.config)
    config = {}
    if config_path.exists():
        try:
            config = load_team_config(config_path)
        except AzureDevOpsError as exc:
            log(f"WARNING: Could not parse team config: {exc}")

    scope_desc = ""
    filter_repos: Optional[List[str]] = None
    filter_assignee: Optional[str] = None
    filter_area_paths: Optional[List[str]] = None
    filter_iteration = "current" if args.sprint else None
    team_config: Optional[Dict] = None

    # Determine scope
    if args.all:
        scope_desc = "ALL TEAMS (exhaustive)"
        log("Exhaustive mode: querying all PRs and work items. This may take a moment.")
    elif args.me:
        email = get_git_email()
        if not email:
            log("ERROR: --me requires git config user.email to be set")
            return 1
        filter_assignee = email
        scope_desc = f"My Work ({email})"
    elif args.member:
        member = find_member(config, args.member)
        if member:
            filter_assignee = member.get("email") or member.get("name")
            scope_desc = f"Member: {member.get('name', args.member)}"
        else:
            log(f"WARNING: Member '{args.member}' not found in team.yaml. Using as raw query.")
            filter_assignee = args.member
            scope_desc = f"Member: {args.member}"
    elif args.repo:
        filter_repos = [args.repo]
        scope_desc = f"Repo: {args.repo}"
    elif args.board:
        filter_area_paths = [args.board]
        scope_desc = f"Board/Area: {args.board}"
    else:
        # Default: use team from config
        team_config = find_team(config, args.team)
        if not team_config:
            log(f"No team config found and no scope flags. Showing exhaustive view.")
            scope_desc = "ALL (no team configured)"
        else:
            filter_repos = team_config.get("repos", [])
            filter_area_paths = team_config.get("area_paths", [])
            scope_desc = f"Team: {team_config.get('name', 'Unknown')}"

    # Query PRs
    log("Fetching active pull requests...")
    try:
        prs = client.list_active_pull_requests(repo_names=filter_repos)
    except AzureDevOpsError as exc:
        log(f"ERROR fetching PRs: {exc}")
        prs = []

    # Query work items
    log("Fetching work items...")
    try:
        work_items = client.list_work_items(
            assigned_to=filter_assignee,
            area_paths=filter_area_paths,
            iteration=filter_iteration,
        )
    except AzureDevOpsError as exc:
        log(f"ERROR fetching work items: {exc}")
        work_items = []

    # Filter stale PRs
    if args.stale:
        from datetime import datetime, timedelta, timezone
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        prs = [
            pr for pr in prs
            if pr.get("creationDate")
            and datetime.fromisoformat(pr["creationDate"].replace("Z", "+00:00")) < seven_days_ago
        ]

    # Output
    if args.json:
        output = {
            "scope": scope_desc,
            "pull_requests": prs,
            "work_items": work_items,
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        print(render_report(scope_desc, prs, work_items, team_config))

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
