# Meta Workflow: Research Phase

Before writing or upgrading an agent definition, research these areas:

## 1. Domain Best Practices
- What are the current industry best practices for this agent's domain?
- Example: For a "security-analyzer" agent, research:
  - Latest OWASP guidelines (are we on 2021 or has 2025 been released?)
  - SAST/DAST tool approaches and what they check
  - Real-world security review checklists from FAANG companies
  - Common false positives and how to avoid them

## 2. Academic/Expert Techniques
- Are there published techniques for this type of analysis?
- Example: For a "code-explorer" agent, research:
  - Program slicing techniques for dependency analysis
  - Call graph construction approaches
  - How LSP servers analyze code (similar to what we're doing manually)

## 3. Existing AI Agent Implementations
- How do other AI agent systems implement this capability?
- Search: "<domain> AI agent prompt" or "<domain> LLM agent technique"
- What prompt engineering techniques work best for this type of task?

## 4. Stack-Specific Considerations
- What are the specific challenges for different tech stacks?
- C# has different patterns than Python for the same type of analysis
- What tools/commands are available per stack?

## 5. Failure Modes
- What commonly goes wrong with this type of agent?
- What edge cases trip up automated analysis?
- How can the agent detect when it's in over its head?

## Output
Write research findings to: `.rival/workstreams/<id>/agent-research/<agent-name>.md`
This file feeds into the Write Phase.
