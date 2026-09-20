# V0 Specification

## Thesis
A lightweight AI-assisted workflow can reduce the work required to maintain a useful social presence and identify genuinely relevant Exousia testers without turning social activity into spam.

## Engines
### Content Engine
Research current AI/agentic-AI/developer topics, identify worthwhile discussion opportunities, draft original posts/reactions, explain evidence and uncertainty, and allow SKIP.

### Exousia Tester Recruitment Engine
Discover developers with observable evidence of coding-agent use or relevant agentic-development work, qualify them, maintain a candidate queue, and recommend human outreach.

No automatic contact in V0.

## Separation
Normal content serves useful participation and account activation. Recruitment serves finding qualified testers. Do not force an Exousia CTA into normal posts.

## Architecture
Research → Engine → Structured Output → Human Review → External Action.

V0 stays lightweight and file/CLI oriented.

## Candidate states
DISCOVERED → QUALIFIED → NEEDS_REVIEW → CONTACTED → RESPONDED → TEST_SCHEDULED → TESTED. Terminal: NOT_INTERESTED, IRRELEVANT.

AI interest alone is insufficient. Prefer observable signals such as OpenCode, Claude Code, Codex, Cursor, agentic development, developer tooling, agent permissions, sandboxing, tool access, security, or reliability work.
