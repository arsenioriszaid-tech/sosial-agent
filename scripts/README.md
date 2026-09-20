# Scripts

Keep V0 scripts local, small, reversible, and focused on research/dry-run workflows. Do not add platform automation without an explicit scope decision.

## V0 dry-run (stdlib only, no dependencies, no network)

```bash
python3 scripts/content_run.py --date 2026-09-20   # research items -> judged report + canonical drafts
python3 scripts/recruit_run.py --date 2026-09-20   # discovered profiles -> candidate queue + review report
python3 scripts/validate.py --date 2026-09-20      # verify outputs (exit 0 = pass)
```

Content contract V0.1: canonical drafts target 400–800 chars
(`config/canonical.yaml`), no hard limit, Facts/Analysis/Take labeled.
`--max-drafts` omitted drafts everything passing the gates. Platform
budgets (x: 280) appear only as FITS/NEEDS_REVIEW adaptation notes —
the engine never truncates canonical text.

Inputs default to `data/*/sample-inputs.json` (clearly-labeled fixtures, not
real research/people). For a real run, copy the sample file to a dated input
(e.g. `data/research/2026-09-21-inputs.json`), replace with operator-curated
items, and pass `--inputs <path>`. Same date + same inputs overwrite
deterministically (reruns are byte-identical).

V0 never performs external actions: both run scripts refuse `--publish`,
`--send`, `--reply`, `--follow`, `--like`, `--dm`, `--delete`, `--promote`.
