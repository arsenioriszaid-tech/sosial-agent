# Recruitment report 2026-09-20

run_id: recruit-2026-09-20-6688acc8
inputs: /root/sosial-agent/data/candidates/sample-inputs.json (sha256: 6688acc8d0502ff3ee0265bca569a5eb5fdcd1a8aa24923211dfd2a8a5a7f3d4)
inputs_note: SAMPLE FIXTURE inputs — not real people. Replace with operator-discovered profiles for real runs.
signals: ['OpenCode', 'Claude Code', 'Codex', 'Cursor', 'coding-agent usage', 'agent permissions', 'sandboxing', 'tool access', 'agent security', 'agent reliability']

> STATUS: PENDING_HUMAN_REVIEW — V0 never contacts candidates. A human reviews, converses, and schedules tests.

## Queue summary

discovered=4 irrelevant=2 needs_review=1 qualified=1

## Candidates

| handle | platform | profile | status | confidence | matched signals | reason |
|---|---|---|---|---|---|---|
| devA | x | https://example.com/devA | QUALIFIED | high | Claude Code; sandboxing; tool access | observable coding-agent use plus Exousia-relevant signal |
| devB | x | https://example.com/devB | NEEDS_REVIEW | low | Cursor | partial signal match; human must judge relevance |
| devC | x | https://example.com/devC | IRRELEVANT | medium | — | generic AI interest only; no preferred signal matched |
| devD | x | https://example.com/devD | IRRELEVANT | high | — | no observable evidence supplied |

## Draft openers (DO NOT SEND — human review required)

### devA (QUALIFIED)

```
Hi devA — saw your notes on uses claude code daily on a monorepo and wondered how you currently scope what your agent may touch. We're exploring that problem space; would you be open to a short chat about what has/hasn't worked for you?
```

### devB (NEEDS_REVIEW)

```
Hi devB — saw your notes on uses cursor for refactoring work and wondered how you currently scope what your agent may touch. We're exploring that problem space; would you be open to a short chat about what has/hasn't worked for you?
```

---
Human review: verify evidence on the public profile, then decide CONTACTED / IRRELEVANT per WORKFLOW.md. Record outcome in the candidate queue.
