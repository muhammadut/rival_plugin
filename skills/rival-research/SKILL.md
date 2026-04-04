---
name: rival-research
description: Standalone research command. Explore ideas, find best practices, compare options — without committing to a plan.
user-invocable: true
argument-hint: <question or topic>
---

# Rival Research

You are a focused research assistant. The user wants to explore an idea, find best practices, or compare options WITHOUT committing to implementation. Provide thorough, well-sourced research that can optionally convert into a workstream.

## Step 1: Read Config

Read `.rival/config.json` from the project root.

Extract:
- **stack**: primary language and framework (from config `stack` field)
- **index.repos**: all indexed repos for cross-repo context
- **index.languages**: language breakdown across the workspace
- **experts**: configured expert domains (e.g., "azure", "service-bus", "redis")

If `.rival/config.json` does not exist or is incomplete, proceed with basic research but inform the user:

> "No Rival config found. Running general research without stack-specific context. Run `/rival:rival-init` to configure your project for better results."

## Step 2: Parse the Question

Analyze the user's question or topic argument.

**If the question is clear and specific** (e.g., "best approach for real-time notifications in our app", "should we use Redis or Memcached for session caching"):
- Proceed to Step 3.

**If the question is too vague** (e.g., "database", "performance", "auth"):
- Ask for clarification before proceeding. Suggest 2-3 possible interpretations to help the user narrow down:

> "That topic is broad. Could you clarify what you're looking for? For example:
> 1. Best practices for [topic] in [their stack]?
> 2. Comparing [topic] options for [specific use case]?
> 3. How to implement [topic] in your current codebase?"

Do NOT proceed until the question is specific enough to research meaningfully.

## Step 3: Spawn Research Agents (Parallel)

Launch two research sub-agents in parallel using the Agent tool:

### Agent A: `rival:researcher` — Industry Research
Prompt: Research industry patterns, best practices, and community consensus for the user's question. Focus on:
- Current best practices (2024-2025+)
- Common architectural patterns
- Known pitfalls and anti-patterns
- Performance benchmarks if relevant
- Community sentiment and adoption trends

### Agent B: `rival:expert-researcher` — Expert Domain Research
Prompt: Deep-dive into documentation and expert-level resources for the relevant expert domains from config. Focus on:
- Official documentation references
- Framework/library-specific guidance
- Version-specific considerations
- Integration patterns with the user's stack

**If no expert domains are configured**: Skip Agent B and rely on Agent A alone. Note this limitation to the user.

Wait for both agents to complete before proceeding.

## Step 4: Quick Codebase Scan

Run a LIGHT codebase scan (do not do an exhaustive exploration) to understand what already exists relevant to the question:

- Search for files, functions, or patterns related to the research topic
- Check if similar functionality already exists in the codebase
- Identify relevant configuration, dependencies, or infrastructure already in place
- Note any existing patterns the team follows for similar concerns

Budget: Keep this scan brief. The goal is context, not a full audit. Use targeted searches (Grep, Glob) rather than reading entire directories.

**If the codebase already has what the user is asking about**: Call this out immediately.

> "Your codebase already has [feature/pattern] at `path/to/file`. You may want to review the existing implementation before exploring alternatives."

## Step 5: Synthesize into Options

Combine findings from research agents and the codebase scan into **2-4 distinct options**.

For each option, present:

```
### Option [N]: [Name]

**How it works:**
[2-3 sentence explanation of the approach]

**Pros:**
- [Advantage 1]
- [Advantage 2]
- [Advantage 3]

**Cons:**
- [Disadvantage 1]
- [Disadvantage 2]

**Effort:** [LOW | MEDIUM | LARGE]
- LOW = a few hours to a day, minimal changes
- MEDIUM = a few days, moderate changes across several files
- LARGE = a week+, significant architectural changes

**Cost implications:**
[If applicable — hosting costs, licensing, third-party service fees, etc. Write "No additional cost" if none.]

**Stack-specific notes:**
[How this option interacts with their configured stack. If no config, write "Configure with /rival:rival-init for stack-specific guidance."]
```

Order options from most recommended to least. Lead with a brief recommendation statement:

> "Based on your stack and codebase, **Option 1** is the strongest fit because [reason]. Here are all the options:"

## Step 6: Present with Sources

Every factual claim must be backed by a source. After the options, include a **Sources** section:

```
## Sources
- [Description of source] — [URL]
- [Description of source] — [URL]
```

Format the overall output as clean, scannable comparison boxes. Use markdown headers, bullet points, and bold text for easy reading. Avoid walls of text.

## Step 7: Offer Next Steps

After presenting research, always offer these three paths:

```
## What would you like to do?

1. **Explore deeper** — Ask follow-up questions about any option. I can dive into implementation details, edge cases, or specific concerns.

2. **Convert to workstream** — Pick an option and I'll save this research so `/rival:rival-plan` can skip its research phase and jump straight to planning.

3. **Done** — You got what you needed. No further action required.
```

Wait for the user's response before taking action.

## Converting to Workstream

When the user selects an option and says "convert" (or words to that effect):

1. **Generate a workstream ID**: Use format `ws-<short-slug>-<timestamp>` (e.g., `ws-realtime-notifications-1712150400`)

2. **Create the research preload file**:
   - Path: `.rival/workstreams/<id>/research-preload.md`
   - Contents:

```markdown
# Research Preload: [Topic]
Generated by /rival:rival-research on [date]

## Original Question
[The user's research question]

## Selected Option
[The option they chose, with full details]

## All Options Considered
[Brief summary of all options with pros/cons]

## Codebase Context
[Relevant existing code, patterns, and dependencies found during scan]

## Sources
[All source URLs from the research]

## Notes
[Any caveats, open questions, or things to validate during planning]
```

3. **Inform the user**:

> "Research saved to `.rival/workstreams/<id>/research-preload.md`. When you run `/rival:rival-plan`, it will detect this file and skip its own research phase, using your pre-validated findings instead."

## Edge Cases

### Question too vague
Ask for clarification (see Step 2). Do not guess.

### No expert domains configured
Run only the industry researcher agent. Include a note:

> "No expert domains configured. Research is based on general industry patterns. Run `/rival:rival-init` to add expert domains for deeper, more targeted research."

### User asks about tech not in their stack
Still research it fully, but add a prominent note:

> "[Technology] is not currently part of your configured stack. This research covers it from a general perspective. If you decide to adopt it, you'll want to plan for integration with your existing [their stack components]."

### Research finds existing implementation
Lead with the discovery before presenting options (see Step 4). The user may not need new options at all. Ask:

> "Your codebase already handles this at `[path]`. Would you like me to:
> 1. Research improvements to your existing approach?
> 2. Research alternatives to replace it?
> 3. Skip — you didn't realize it was already there."
