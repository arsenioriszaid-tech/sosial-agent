#!/usr/bin/env python3
"""Recruitment Engine V0 dry-run: discovered profiles -> qualified queue.

Reads operator-discovered public profiles (JSON), applies the evidence rules
from config/recruitment.yaml (observable coding-agent/agentic-development
evidence required; generic AI interest is insufficient), and emits:
  data/candidates/<date>-queue.json  structured candidate records
  data/reports/<date>-recruitment.md  human-review report + draft openers

V0 never contacts anyone. Outreach openers are drafts for HUMAN review.
Rerunnable: same --date + same inputs overwrite deterministically.

Usage:
  python3 scripts/recruit_run.py [--date YYYY-MM-DD] [--inputs path]
"""
import argparse
import importlib.util
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
(REPO_ROOT, load_json, load_yaml, refuse_forbidden_flags, sha_short,
 utc_today, write_json, write_text) = (
    common.REPO_ROOT, common.load_json, common.load_yaml,
    common.refuse_forbidden_flags, common.sha_short, common.utc_today,
    common.write_json, common.write_text)

CODING_AGENT_SIGNALS = {"opencode", "claude code", "codex", "cursor",
                        "coding-agent", "coding agent", "agentic development"}
EXOUSIA_RELEVANT_SIGNALS = {"permission", "sandbox", "tool access",
                            "security", "reliab"}


def qualify(profile, preferred_signals):
    """Return (status, matched, reason, confidence, missing)."""
    evidence = profile.get("evidence", [])
    blob = " ".join(evidence).lower()
    matched = sorted({s for s in preferred_signals if s.lower() in blob})
    has_agent = any(s in blob for s in CODING_AGENT_SIGNALS)
    has_exousia = any(s in blob for s in EXOUSIA_RELEVANT_SIGNALS)
    if not evidence:
        return ("IRRELEVANT", matched, "no observable evidence supplied",
                "high", "any public evidence of coding-agent or agentic work")
    if not matched:
        return ("IRRELEVANT", matched,
                "generic AI interest only; no preferred signal matched",
                "medium", "observable coding-agent use or agent-security work")
    if has_agent and has_exousia:
        return ("QUALIFIED", matched,
                "observable coding-agent use plus Exousia-relevant signal",
                "high", "direct confirmation of testing availability (human step)")
    return ("NEEDS_REVIEW", matched,
            "partial signal match; human must judge relevance", "low",
            "stronger evidence of agent use or permissions/sandboxing work")


def opener(profile, status):
    handle = profile.get("handle", "there")
    return (f"Hi {handle} — saw your notes on "
            f"{(profile.get('evidence', ['your agent workflow']))[0].lower()} "
            f"and wondered how you currently scope what your agent may touch. "
            f"We're exploring that problem space; would you be open to a short "
            f"chat about what has/hasn't worked for you?")


def main():
    refuse_forbidden_flags(sys.argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=utc_today())
    ap.add_argument("--inputs",
                    default=str(REPO_ROOT / "data/candidates/sample-inputs.json"))
    args = ap.parse_args()

    cfg = load_yaml(REPO_ROOT / "config/recruitment.yaml")
    preferred = cfg["preferred_signals"]
    assert cfg.get("evidence_required") is True, "recruitment.yaml: evidence_required must stay true"
    assert cfg.get("automatic_contact") is False, "recruitment.yaml: automatic_contact must stay false"

    data = load_json(args.inputs)
    _, input_hash = sha_short(args.inputs)
    run_id = f"recruit-{args.date}-{input_hash[:8]}"
    fixture_note = ("SAMPLE FIXTURE inputs — not real people. "
                    "Replace with operator-discovered profiles for real runs." if "sample" in args.inputs
                    else "Operator-discovered inputs.")

    records = []
    for p in data["profiles"]:
        status, matched, reason, conf, missing = qualify(p, preferred)
        records.append({
            "handle": p.get("handle"),
            "platform": p.get("platform"),
            "profile_url": p.get("profile_url"),
            "relevance": ("exousia-tester-candidate" if status == "QUALIFIED"
                          else "possible-candidate" if status == "NEEDS_REVIEW"
                          else "not-relevant"),
            "evidence": p.get("evidence", []),
            "matched_signals": matched,
            "likely_agent_user": any(s in " ".join(p.get("evidence", [])).lower()
                                     for s in CODING_AGENT_SIGNALS),
            "reason": reason,
            "confidence": conf,
            "missing_info": missing,
            "status": status,
            "reviewed_by_human": False,
        })
    write_json(REPO_ROOT / f"data/candidates/{args.date}-queue.json",
               {"run_id": run_id, "inputs_sha256": input_hash, "candidates": records})

    counts = {}
    for r in records:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    report = (
        f"# Recruitment report {args.date}\n\n"
        f"run_id: {run_id}\ninputs: {args.inputs} (sha256: {input_hash})\n"
        f"inputs_note: {fixture_note}\n"
        f"signals: {preferred}\n\n"
        f"> STATUS: PENDING_HUMAN_REVIEW — V0 never contacts candidates. "
        f"A human reviews, converses, and schedules tests.\n\n"
        f"## Queue summary\n\n"
        f"discovered={len(records)} " +
        " ".join(f"{k.lower()}={v}" for k, v in sorted(counts.items())) + "\n\n"
        f"## Candidates\n\n"
        f"| handle | platform | profile | status | confidence | matched signals | reason |\n"
        f"|---|---|---|---|---|---|---|\n")
    for r in records:
        report += (f"| {r['handle']} | {r['platform']} | {r['profile_url']} | "
                   f"{r['status']} | {r['confidence']} | "
                   f"{'; '.join(r['matched_signals']) or '—'} | {r['reason']} |\n")
    report += "\n## Draft openers (DO NOT SEND — human review required)\n\n"
    for r in records:
        if r["status"] in ("QUALIFIED", "NEEDS_REVIEW"):
            report += f"### {r['handle']} ({r['status']})\n\n```\n{opener(r, r['status'])}\n```\n\n"
    report += ("---\nHuman review: verify evidence on the public profile, "
               "then decide CONTACTED / IRRELEVANT per WORKFLOW.md. "
               "Record outcome in the candidate queue.\n")
    write_text(REPO_ROOT / f"data/reports/{args.date}-recruitment.md", report)

    print(f"run {run_id}: {len(records)} discovered -> " +
          " ".join(f"{k.lower()}={v}" for k, v in sorted(counts.items())))


if __name__ == "__main__":
    main()
