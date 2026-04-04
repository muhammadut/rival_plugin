# Meta Workflow: Write Phase

Using the research findings, write the agent definition:

## 1. Incorporate Research Findings
- Every technique discovered in research should be considered for inclusion
- If a technique is too complex, note it as an "advanced mode" the agent CAN use
- Include specific commands, patterns, and approaches from research

## 2. Give the Agent Research Capability
- Where appropriate, give agents WebSearch or Context7 tools
- The agent should be able to do live research during execution
- Example: pattern-detector can search for "<framework> naming conventions"
  if it encounters a framework it doesn't have built-in knowledge about

## 3. Stack-Adaptive Instructions
- Agent should adapt its approach based on the stack it's analyzing
- Don't just have one process — have stack-specific branches
- Example: security-analyzer should check for C# deserialization risks
  in C# codebases but prototype pollution in Node.js codebases

## 4. Failure Recovery
- Include explicit instructions for when the agent gets stuck
- "If you can't find X after Y attempts, try Z instead"
- Budget-aware fallback strategies

## 5. Output Quality
- Include example output in the agent definition
- Show what a GOOD output looks like vs a BAD one
- Be specific about what "thorough" means for this agent
