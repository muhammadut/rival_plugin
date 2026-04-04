# Meta Workflow: Review Phase

After writing the agent, get an independent review:

## Review Criteria

1. **Completeness:** Does the agent cover all the techniques found in research?
2. **Practicality:** Can the agent actually execute these techniques with its available tools?
3. **Edge cases:** Does the agent handle unusual codebases, languages, or project structures?
4. **Budget awareness:** Will the agent stay within tool call limits?
5. **Output quality:** Is the output format useful for downstream consumers?
6. **Stack coverage:** Does the agent work for C#, TypeScript, Python, Go, etc.?

## Review Process

Option A (Codex available):
  codex exec "Review this AI agent definition for quality and completeness.
  [paste agent definition]
  [paste research findings that informed it]
  Does this agent incorporate the research findings effectively?
  What techniques are missing? What could be improved?"
  --full-auto

Option B (Claude fallback):
  Spawn a skeptical-reviewer sub-agent with the agent definition + research findings.

## Iteration
If review finds gaps, update the agent and re-review.
Target: reviewer says "APPROVED" or "APPROVED WITH MINOR NOTES."
