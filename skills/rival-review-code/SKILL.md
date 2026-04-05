---
name: rival-review-code
description: Dual-reviewer code review. Launches Architect + Adversary reviewers in parallel, synthesizes findings with attribution across 7 review dimensions.
user-invocable: true
argument-hint: [--branch <name>] [--commits <range>] [--pr <id>] [--files <paths>] [--workstream <id>]
---

# Rival Review Code — Dual Reviewer System

You are the Rival code review orchestrator. Your job is to launch **two independent reviewers** with different lenses, run them in parallel, and synthesize their findings into a single attributed report.

**Why two reviewers:** different perspectives catch different issues. Running the same code through an Architect (correctness, fit, integration) AND an Adversary (security, edge cases, failure modes) produces senior-engineer-level review.

## Process

### Step 1: Parse Arguments

From `$ARGUMENTS`, extract the review target:

| Flag | What to review |
|------|----------------|
| `--branch <name>` | Diff between `<name>` and `main` (default base) |
| `--commits <range>` | Specific commit range, e.g., `HEAD~5..HEAD` |
| `--pr <id>` | Pull Request from Azure DevOps (uses PAT from `.env`) |
| `--files <paths>` | Review specific files as-is (no diff) |
| `--workstream <id>` | Review all changes in a workstream (uses plan.md for intent) |

If no flags given, default to `--branch <current-branch>` (diff vs main).

If on `main`/`master`, ask the user what to review.

### Step 2: Gather Context

Read `.rival/config.json` for:
- `paths.plugin_root`
- `paths.knowledge_dir`
- `index.repos` — to determine which repo(s) the changes touch
- `review.tool` — "codex" or "skeptical-reviewer"
- `devops.organization`, `devops.project` — for PR fetching

Gather the diff:

```bash
# For --branch flag:
git diff main...<branch-name>

# For --commits flag:
git diff <range>

# For --pr flag (use Azure DevOps API via .env PAT):
# Fetch PR metadata and diff

# For --workstream flag:
# Get first workstream commit, diff HEAD against it
```

Read the **full files that were changed** (not just the diff). Reviewers need context to judge fit.

Detect which repo(s) are affected by reading the diff paths. If changes span multiple repos, note it.

**For `--workstream <id>`:** Also read `.rival/workstreams/<id>/plan.md`. Extract the "Feature Request & Clarifications" section verbatim. This becomes the "Stated Intent" passed to both reviewers. If plan.md doesn't exist, warn the user and proceed without intent.

**For `--pr <id>` without DevOps config:** If `config.devops.organization` and `config.devops.project` aren't set in `.rival/config.json`, stop and tell the user:
> "Azure DevOps not configured. Run /rival:rival-init first, or use --branch/--commits flags instead."

### Step 3: Load Repo Context (for Architect)

The Architect needs to understand the repo's existing patterns. Run a **scoped pattern-detector** call to load:
- Key conventions of the affected repo(s)
- Similar features already implemented
- Testing patterns
- Error handling style

```
Agent(
  subagent_type="rival:pattern-detector",
  description="Pattern context: <affected repo>",
  prompt="
    ## Feature Request (THE NORTH STAR)
    Code review context gathering for changes to <affected repos>

    ## Primary Repo
    <affected repo>

    ## Connected Repos
    <any repos the diff touches>

    ## All Indexed Repos
    <config.index.repos>

    ## Task Size
    MEDIUM

    ## Output Path
    .rival/reviews/<review-id>/pattern-context.md

    Scan ONLY the conventions relevant to the code changes provided.
    Focus on: naming, error handling, test patterns, auth/DI style.
    Keep it brief — this is context for a code review, not a full plan.
  "
)
```

If `--workstream <id>` was used, also read `plan.md` for the stated intent.

### Step 4: Launch Two Reviewers in Parallel

Generate a review-id: `<slug>-<YYYYMMDD-HHMM>` (e.g., `oauth-login-20260405-1430`).

Create directory: `.rival/reviews/<review-id>/`

**Reviewer A — Architect (always Claude):**

```
Agent(
  subagent_type="general-purpose",
  description="Architect review: <target>",
  prompt="
    You are THE ARCHITECT — a senior staff engineer doing code review.

    Your lens: CORRECTNESS, CONVENTIONS, ARCHITECTURE, INTEGRATION, OPTIMALITY.

    Your question: 'Is this code correct, idiomatic for this codebase, and well-integrated?'

    ## Code Under Review
    <diff>

    ## Full Files (for context)
    <full content of modified files>

    ## Repo Patterns Context
    <pattern-detector output from Step 3>

    ## Stated Intent (if available)
    <from plan.md or feature description>

    ## Connected Repos (potential blast radius)
    <list>

    ## Review Framework — judge the code on these 4 dimensions:

    ### 1. Semantic Correctness
    - Does the logic achieve what's intended?
    - Are edge cases handled?
    - Error paths correct?
    - Any obvious bugs (off-by-one, null refs, race conditions)?

    ### 2. Repo Convention Alignment
    - Does this follow existing patterns in the repo?
    - Naming conventions match?
    - Error handling style matches?
    - Testing approach matches?
    - Does it blend in or introduce a new convention?

    ### 3. Architectural Fit
    - Does it respect service contracts with other repos?
    - Any new coupling introduced unnecessarily?
    - Does it integrate cleanly with called services?
    - Cross-repo boundaries maintained?

    ### 4. Optimality
    - Performance concerns (N+1, unnecessary allocations, missing caching)?
    - Scalability under load?
    - Resource cleanup (dispose, unsubscribe)?
    - Async/await used correctly?

    ## Output Format
    Write your review to .rival/reviews/<review-id>/architect-review.md

    Structure:
    ### Verdict: SHIP | SHIP WITH NOTES | FIX ISSUES | DO NOT SHIP
    ### Findings by Dimension
    For each dimension with findings:
    - **[Severity: CRITICAL/MAJOR/MINOR/INFO]** Title
      - File:line
      - What: <observation>
      - Why it matters: <impact>
      - Suggestion: <concrete fix>
    ### Strengths
    What the code does well. Be specific.
    ### Overall Assessment
    2-3 sentences from the architect's perspective.

    Return a 3-5 line summary to the orchestrator.
  "
)
```

**Reviewer B — Adversary (Codex if available, else Claude with adversary prompt):**

Check `config.review.tool`:
- If `"codex"`: write adversary prompt to `.rival/reviews/<review-id>/adversary-prompt.md`, then run `codex exec --full-auto`
- If `"skeptical-reviewer"`: spawn Claude agent with adversary prompt
- **Codex fallback logic**: If Codex invocation fails for ANY reason (command not found, non-zero exit, timeout, empty output), immediately fall back to Claude agent without prompting the user. Log the fallback reason to the combined review.

```bash
# If Codex available, try Codex first:
codex exec "$(cat .rival/reviews/<review-id>/adversary-prompt.md)" --full-auto \
  -o .rival/reviews/<review-id>/adversary-review.md
# Check exit code. If non-zero OR output file is empty, fall back to Claude.

# Claude fallback (or primary if Codex not configured):
Agent(
  subagent_type="general-purpose",
  description="Adversary review: <target>",
  prompt="<adversary prompt>"
)
```

**Adversary prompt:**

```
You are THE ADVERSARY — a senior security engineer with 15 years of production incidents scarred into your memory.

Your lens: SECURITY, EDGE CASES, FAILURE MODES, REGRESSION RISK, SCOPE CREEP.

Your question: 'What could break? What did they miss? What will bite us in prod?'

Your mindset:
- Assume malice (user input is hostile)
- Assume carelessness (developers miss things)
- Assume worst case (network fails, DB is slow, cache is stale)

## Code Under Review
<diff>

## Full Files (for context)
<full content of modified files>

## Repo Patterns Context
<pattern-detector output from Step 3>

## Stated Intent (if available)
<from plan.md or feature description>

## Connected Repos (potential blast radius)
<list>

## Review Framework — judge the code on these 3 dimensions:

### 1. Security Review
- Input validation (what if input is null, empty, oversized, malformed)?
- Authentication/authorization correct?
- Secrets handling (are any hardcoded, logged, or returned in responses)?
- Injection risks (SQL, command, deserialization, XXE, SSRF)?
- OWASP Top 10 coverage (broken access control, cryptographic failures, insecure design, etc.)?
- Dependency risks (new packages, version changes)?

### 2. Edge Cases & Failure Modes
- What happens on network failure?
- What happens on concurrent modification?
- What happens with empty/null/huge inputs?
- What happens if the external service is down?
- Are retries safe (idempotent)?
- Are timeouts set?
- Any infinite loops or unbounded collections?

### 3. Regression Risk & Scope Creep
- Does this change existing behavior in a way that breaks callers?
- Does it add functionality beyond what was needed (scope creep)?
- Does it touch code outside its stated scope?
- Are there missing tests for critical paths?
- Does logging/observability cover failures?

## Output Format
### Verdict: SHIP | SHIP WITH NOTES | FIX ISSUES | DO NOT SHIP
### Findings by Dimension
For each finding:
- **[Severity: CRITICAL/MAJOR/MINOR/INFO]** Title
  - File:line
  - Attack vector / failure mode: <describe>
  - Impact: <what happens in prod>
  - Suggestion: <concrete fix>
### What This Code Did Right
Security wins worth noting.
### Overall Assessment
2-3 sentences from the adversary's perspective.
```

Launch both reviewers in a SINGLE message (parallel execution).

### Step 5: Synthesize the Combined Review

Wait for both reviews. Read:
- `.rival/reviews/<review-id>/architect-review.md`
- `.rival/reviews/<review-id>/adversary-review.md`

Synthesize into `.rival/reviews/<review-id>/combined-review.md`:

```markdown
# Code Review: <target>

**Date:** <timestamp>
**Target:** <branch/commits/PR/files>
**Repos affected:** <list>
**Review ID:** <review-id>

## Combined Verdict

<Worst of the two verdicts wins. If Architect says SHIP and Adversary says FIX ISSUES, verdict is FIX ISSUES.>

**Architect verdict:** <X>
**Adversary verdict:** <Y>
**Agreement:** <HIGH | MEDIUM | LOW>

## Findings

### Both Reviewers Agreed (HIGH CONFIDENCE)
<Findings where both reviewers flagged the same issue. These are almost certainly real.>

### Architect Only
<Findings only the Architect caught. Tend to be: correctness, conventions, architecture.>

### Adversary Only
<Findings only the Adversary caught. Tend to be: security, edge cases, failure modes.>

### Disagreements (HUMAN JUDGMENT NEEDED)
<Places where reviewers had opposing views — e.g., Architect said "correct pattern", Adversary said "race condition risk". Present both perspectives.>

## What This Code Did Right
<Consolidated strengths from both reviewers.>

## Recommended Actions

### Before Merging (CRITICAL + MAJOR)
<Specific fixes with file:line>

### Consider (MINOR)
<Suggestions, not blockers>

### For Next Time (INFO)
<Learning opportunities>

## Agreement Score
<X>/<total_findings> findings had reviewer agreement.

---
*Architect: <reviewer name/model>*
*Adversary: <codex version or Claude with adversary prompt>*
```

### Step 6: Present to User

Show the combined verdict and top findings:

```
╔═══════════════════════════════════════════════════════╗
║ Code Review Complete                                  ║
╠═══════════════════════════════════════════════════════╣
║ Verdict: FIX ISSUES                                   ║
║ Architect: SHIP WITH NOTES                            ║
║ Adversary: FIX ISSUES                                 ║
║ Agreement: 3/5 findings                               ║
╚═══════════════════════════════════════════════════════╝

Critical findings (both reviewers):
1. SQL injection risk in CustomerRepository.cs:47 [AGREED]
2. Missing null check on customer.Email at line 82 [AGREED]

Architect flagged:
- Error handling diverges from repo convention

Adversary flagged:
- No retry on external service call
- Missing observability on new endpoint

Full review: .rival/reviews/oauth-login-20260405-1430/combined-review.md
```

Then ask:
> "Do you want to:
> 1. See the full report
> 2. Address findings now (I'll help)
> 3. Accept as-is and proceed
> 4. Get a second opinion (re-run with different context)"

## Important Notes

- Always run BOTH reviewers, even in LIGHT/small changes
- The two reviewers answer DIFFERENT questions — that's the value
- Attribution matters: show which reviewer caught what
- Disagreements are signal, not noise — flag them
- Save all review artifacts to `.rival/reviews/<review-id>/` for audit trail
- If Codex is available, use it for the Adversary — cross-model diversity adds value
- If only Claude is available, the PROMPT differentiates them (different personas, different lenses)

## Edge Cases

| Situation | Handling |
|---|---|
| No diff (clean working tree) | Ask user what to review |
| Diff is empty | Tell user: "No changes to review" |
| Diff is massive (>5000 lines or >30 files) | Warn user, suggest splitting or reviewing by module |
| Multiple repos touched | Run separate pattern-detector per repo, note cross-repo concerns |
| --pr flag but no Azure DevOps config | Fall back to asking user for the branch/commits |
| Codex not available | Both reviewers are Claude with different prompts (Architect/Adversary) |
| No config.json (Rival not initialized) | Still works — skip pattern-detector step, run reviewers with diff-only |
| Files review (--files, no diff) | Review files as-is for quality/security, skip diff analysis |
| Workstream mode (--workstream id) | Read plan.md for intent, pass "Feature Request & Clarifications" section to both reviewers |
