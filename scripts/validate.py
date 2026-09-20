#!/usr/bin/env python3
"""Validate V0 dry-run outputs: schema, safety, traceability.

Checks for --date (default: today UTC):
  1. Required files exist (research md, drafts md, queue json, recruitment md).
  2. Drafts: every draft has premise/evidence/uncertainty; every skip has a
     reason; no Exousia CTA in normal drafts (SPEC separation); drafts within
     char limit (WARN).
  3. Candidates: required schema fields; QUALIFIED/NEEDS_REVIEW carry
     evidence; statuses are V0-legal (no post-human states); profile URLs
     are http(s); nothing marked contacted.
  4. Safety: no forbidden-action or credential patterns in any output.
  5. Traceability: recorded input hashes match current inputs.

Exit 0 = all PASS (WARNs allowed), 1 = any FAIL.

Usage:
  python3 scripts/validate.py [--date YYYY-MM-DD]
"""
import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path


def _load_common():
    spec = importlib.util.spec_from_file_location(
        "v0common", Path(__file__).resolve().parent / "common.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


common = _load_common()
(REPO_ROOT, CREDENTIAL_PATTERNS, FORBIDDEN_ACTION_PATTERNS,
 CANDIDATE_STATES_V0, POST_HUMAN_STATES, load_json, load_yaml) = (
    common.REPO_ROOT, common.CREDENTIAL_PATTERNS,
    common.FORBIDDEN_ACTION_PATTERNS, common.CANDIDATE_STATES_V0,
    common.POST_HUMAN_STATES, common.load_json, common.load_yaml)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def warn(name, detail=""):
    RESULTS.append((name, True, f"WARN: {detail}"))
    print(f"[WARN] {name} — {detail}")


REQUIRED_DRAFT_FIELDS = ("premise:", "evidence_basis:", "uncertainty_risks:",
                           "core_observation:", "interpretation:", "platform_notes:")
REQUIRED_CANDIDATE_FIELDS = ("handle", "platform", "profile_url", "relevance",
                             "evidence", "matched_signals", "likely_agent_user",
                             "reason", "confidence", "status", "reviewed_by_human")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=common.utc_today())
    args = ap.parse_args()
    d = args.date

    research = REPO_ROOT / f"data/research/{d}-research.md"
    drafts_p = REPO_ROOT / f"data/drafts/{d}-drafts.md"
    queue_p = REPO_ROOT / f"data/candidates/{d}-queue.json"
    recruit = REPO_ROOT / f"data/reports/{d}-recruitment.md"

    for label, p in (("research report", research), ("drafts file", drafts_p),
                     ("candidate queue", queue_p), ("recruitment report", recruit)):
        check(f"{label} exists", p.exists(), str(p))

    texts = {}
    for label, p in (("research", research), ("drafts", drafts_p), ("recruitment", recruit)):
        texts[label] = p.read_text(encoding="utf-8") if p.exists() else ""
    queue = load_json(queue_p) if queue_p.exists() else {"candidates": []}
    queue_text = queue_p.read_text(encoding="utf-8") if queue_p.exists() else ""

    # --- Draft structure (V0.1 canonical contract: no hard length limit,
    # facts/interpretation labeled, platform adaptation as notes only) ---
    bodies = []
    if texts["drafts"]:
        for field in REQUIRED_DRAFT_FIELDS:
            check(f"drafts contain {field}", field in texts["drafts"])
        check("skips carry reasons",
              "## Skipped" in texts["drafts"] and ": " in texts["drafts"].split("## Skipped", 1)[1])
        check("human-review boundary marked",
              "PENDING_HUMAN_REVIEW" in texts["drafts"])
        bodies = re.findall(r"```\n(.*?)```", texts["drafts"], re.S)
        check("facts/analysis/take labeled",
              "Facts:" in texts["drafts"] and "Analysis:" in texts["drafts"]
              and "Take:" in texts["drafts"])
        try:
            _canon = load_yaml(REPO_ROOT / "config/canonical.yaml")
            cmin = int(_canon.get("canonical", {}).get("target_min_chars", 400))
            cmax = int(_canon.get("canonical", {}).get("target_max_chars", 800))
            x_budget = int(_canon.get("platform_budgets", {}).get("x", 280))
        except (OSError, ValueError):
            cmin, cmax, x_budget = 400, 800, 280
        off = [b for b in bodies if not (cmin <= len(b.strip()) <= cmax)]
        if off:
            warn("canonical length",
                 f"{len(off)} draft(s) outside {cmin}-{cmax} target (valid; human judges)")
        else:
            check("canonical drafts in target range", True,
                  f"{len(bodies)} draft(s), no hard limit")
        sections = re.split(r"(?m)^## Draft \d+", texts["drafts"])
        adapt_ok = bool(bodies) and len(sections) > 1
        for sec, body in zip(sections[1:], bodies):
            if len(body.strip()) > x_budget and "NEEDS_REVIEW" not in sec:
                adapt_ok = False
            if "platform_notes:" not in sec:
                adapt_ok = False
        check("platform adaptation noted, never truncated", adapt_ok,
              f"{len(bodies)} draft(s)")
        check("no brutal mid-sentence cut in canonical bodies",
              not any(b.strip().endswith("…") for b in bodies),
              "canonical has no hard limit")
        exousia = [b for b in bodies if "exousia" in b.lower()]
        check("no forced Exousia CTA in drafts", not exousia,
              f"{len(exousia)} violation(s)" if exousia else "separation holds")

    # --- Candidate schema ---
    cands = queue.get("candidates", [])
    check("queue non-empty", bool(cands))
    need_evidence_ok = True
    for c in cands:
        missing = [f for f in REQUIRED_CANDIDATE_FIELDS if f not in c]
        check(f"candidate {c.get('handle')}: schema", not missing,
              f"missing {missing}" if missing else f"status={c.get('status')}")
        if c.get("status") in ("QUALIFIED", "NEEDS_REVIEW") and not c.get("evidence"):
            need_evidence_ok = False
        if c.get("status") not in CANDIDATE_STATES_V0:
            check(f"candidate {c.get('handle')}: V0-legal status", False,
                  f"{c.get('status')} is post-human or unknown")
        if c.get("status") in POST_HUMAN_STATES or c.get("reviewed_by_human") is True:
            check(f"candidate {c.get('handle')}: no contact in V0", False,
                  "dry-run must not mark contact")
        url = str(c.get("profile_url", ""))
        if not url.startswith(("http://", "https://")):
            check(f"candidate {c.get('handle')}: profile_url", False, url)
    if cands:
        check("QUALIFIED/NEEDS_REVIEW carry evidence", need_evidence_ok)
        check("recruitment report marks review boundary",
              "PENDING_HUMAN_REVIEW" in texts["recruitment"])
        check("openers not sent", "DO NOT SEND" in texts["recruitment"])

    # --- Safety scan ---
    blob = "\n".join(texts.values()) + "\n" + queue_text
    low = blob.lower()
    hits = [p for p in FORBIDDEN_ACTION_PATTERNS if p in low]
    check("no forbidden-action patterns", not hits,
          f"{hits}" if hits else "clean")
    creds = [p for p in CREDENTIAL_PATTERNS if p in low]
    check("no credential/secret patterns", not creds,
          f"{creds}" if creds else "clean")

    # --- Traceability: the inputs file named in each report must exist and
    # its sha256 must match the hash recorded in that report (works for
    # sample fixtures and dated operator-curated inputs alike).
    research_inputs_text = ""
    for label, carrier in (("research", texts["research"]),
                           ("recruitment", texts["recruitment"] + queue.get("inputs_sha256", ""))):
        m = re.search(r"inputs:\s*(\S+)\s*\(sha256:\s*([0-9a-f]+)\)", carrier)
        if not m:
            check(f"{label} inputs traceable", False, "no inputs+hash header found")
            continue
        inp = REPO_ROOT / m.group(1) if not Path(m.group(1)).is_absolute() \
            else Path(m.group(1))
        # stored paths may be absolute (same machine) or repo-relative
        try:
            rel = inp.relative_to(REPO_ROOT) if inp.is_absolute() else inp
            inp = REPO_ROOT / rel
        except ValueError:
            pass
        if not inp.exists():
            check(f"{label} inputs traceable", False, f"missing {m.group(1)}")
            continue
        h = hashlib.sha256(inp.read_bytes()).hexdigest()
        check(f"{label} inputs traceable",
              h == m.group(2) or h[:12] in carrier, h[:12])
        if label == "research":
            research_inputs_text = inp.read_text(encoding="utf-8")

    # --- No injected questions: the template adds no hook/'?'. Every '?'
    # in a canonical body must already exist in the operator inputs.
    if bodies and research_inputs_text:
        q_body = sum(b.count("?") for b in bodies)
        q_in = research_inputs_text.count("?")
        check("no injected questions", q_body <= q_in,
              f"{q_body} '?' in drafts vs {q_in} in inputs (template adds none)")

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed.")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
