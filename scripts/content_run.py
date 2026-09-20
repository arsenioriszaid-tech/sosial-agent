#!/usr/bin/env python3
"""Content Engine V0 dry-run: research items -> ranked opportunities -> drafts.

Reads operator-curated research items (JSON), enforces CONTENT-RULES.md
(no hype, no fake experience, SKIP when no contribution), and emits:
  data/research/<date>-research.md   ranked opportunities + SKIP reasons
  data/drafts/<date>-drafts.md        draft candidates for HUMAN review

V0 never publishes. Outputs are marked PENDING_HUMAN_REVIEW.
Rerunnable: same --date + same inputs overwrite deterministically.

Usage:
  python3 scripts/content_run.py [--date YYYY-MM-DD] [--max-drafts N]
                                 [--inputs path] [--allow-exousia-cta]
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
(HYPE_PATTERNS, REPO_ROOT, load_json, load_yaml,
 refuse_forbidden_flags, sha_short, utc_today,
 write_text) = (common.HYPE_PATTERNS, common.REPO_ROOT, common.load_json,
                common.load_yaml, common.refuse_forbidden_flags,
                common.sha_short, common.utc_today, common.write_text)

CONF_SCORE = {"high": 2, "medium": 1, "low": 0}
DRAFT_CHAR_LIMIT = 280  # X post length; keeps drafts reviewable as-is


def contains_hype(*texts):
    blob = " ".join(texts).lower()
    return [p for p in HYPE_PATTERNS if p in blob]


def rank(item):
    score = 0
    score += 2 if item.get("possible_angle", "").strip() else 0
    score += 1 if item.get("why_it_matters", "").strip() else 0
    score += CONF_SCORE.get(item.get("confidence", "low"), 0)
    score += 1 if len(item.get("factual_summary", "")) > 60 else 0
    return score


def decide(item, allowed_topics):
    """Return (decision, reason). Decision is DRAFT or SKIP."""
    if item.get("topic") not in allowed_topics:
        return "SKIP", f"off-topic ({item.get('topic')!r} not in config/topics.yaml)"
    if not item.get("source", "").strip() or not item.get("factual_summary", "").strip():
        return "SKIP", "missing source or factual summary (no evidence basis)"
    if not item.get("possible_angle", "").strip():
        return "SKIP", "no meaningful contribution (no concrete angle)"
    hype = contains_hype(item.get("factual_summary", ""), item.get("possible_angle", ""))
    if hype:
        return "SKIP", f"generic hype per CONTENT-RULES.md ({', '.join(hype)})"
    return "DRAFT", f"substance score {rank(item)}"


def build_draft(item):
    """Template draft in builder/learner voice. Reports others' experience,
    never invents firsthand experience. The angle (the hook/question) is
    kept intact; only the context summary is trimmed to fit.
    Returns (draft_text, fields)."""
    angle = item["possible_angle"].strip()
    summary = item["factual_summary"].strip()
    sep = " -- Konteks: "
    if len(angle) > 200:
        angle = angle[:199] + "…"
    head = DRAFT_CHAR_LIMIT - len(angle) - len(sep)
    if len(summary) > head:
        summary = summary[:head - 1] + "…" if head > 1 else ""
    core = f"{angle}{sep}{summary}" if summary else angle
    conf = item.get("confidence", "low")
    unc = (f"Confidence: {conf}. "
           + ("Low confidence — vendor claim/rough estimate, treat as unverified. "
              if conf == "low" else
              "Single-source report; may not generalize. ")
           + "No firsthand verification claimed.")
    fields = {
        "premise": item["why_it_matters"].strip(),
        "evidence_basis": f"{item['source']} — {item['factual_summary'].strip()}",
        "why_worth_posting": ("Concrete, specific development with an open question; "
                              "invites practitioner replies, not hype."),
        "uncertainty_risks": unc,
        "pillar": "technical_observations",
    }
    return core, fields


def main():
    refuse_forbidden_flags(sys.argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=utc_today())
    ap.add_argument("--max-drafts", type=int, default=3)
    ap.add_argument("--inputs", default=str(REPO_ROOT / "data/research/sample-inputs.json"))
    ap.add_argument("--allow-exousia-cta", action="store_true",
                    help="Only for the direct_recruitment pillar (<=5%%). "
                         "Without it, any Exousia mention is rejected.")
    args = ap.parse_args()

    topics = load_yaml(REPO_ROOT / "config/topics.yaml")["topics"]
    pillars = load_yaml(REPO_ROOT / "config/content-pillars.yaml")
    data = load_json(args.inputs)
    items = data["items"]
    _, input_hash = sha_short(args.inputs)
    prompt_shas = {p: sha_short(REPO_ROOT / "prompts" / p)[0]
                   for p in ("content-research.md", "content-drafting.md")}

    judged = []
    for it in items:
        decision, reason = decide(it, topics)
        judged.append((rank(it) if decision == "DRAFT" else -1, it, decision, reason))
    judged.sort(key=lambda r: r[0], reverse=True)

    drafts, skips = [], []
    for _, it, decision, reason in judged:
        if decision == "DRAFT" and len(drafts) < args.max_drafts:
            core, fields = build_draft(it)
            if "exousia" in core.lower() and not args.allow_exousia_cta:
                skips.append((it, "forced Exousia CTA rejected (SPEC separation rule)"))
                continue
            drafts.append((it, core, fields))
        else:
            skips.append((it, reason if decision == "SKIP" else
                          f"ranked below top-{args.max_drafts} cutoff"))

    run_id = f"content-{args.date}-{input_hash[:8]}"
    fixture_note = ("SAMPLE FIXTURE inputs — not real research. "
                    "Replace with operator-curated items for real runs." if "sample" in args.inputs
                    else "Operator-curated inputs.")
    header = (f"run_id: {run_id}\ninputs: {args.inputs} (sha256: {input_hash})\n"
              f"inputs_note: {fixture_note}\n"
              f"prompts: {prompt_shas}\nconfig_topics_sha: "
              f"{sha_short(REPO_ROOT/'config/topics.yaml')[0]}\n"
              f"pillars: {pillars['pillars']}\n")

    research_md = (
        f"# Research report {args.date}\n\n{header}\n"
        f"## Ranked opportunities\n\n"
        f"| id | topic | confidence | score | decision | reason |\n"
        f"|---|---|---|---|---|---|\n" +
        "".join(f"| {it['id']} | {it['topic']} | {it.get('confidence','low')} | "
                f"{s if s>=0 else '—'} | "
                f"{'DRAFT' if any(d[0]['id']==it['id'] for d in drafts) else 'SKIP'} | "
                f"{next(r for _,x,_,r in judged if x['id']==it['id'])} |\n"
                for s, it, _, _ in judged) +
        f"\n## Notes\n- Facts above come only from operator-supplied items; "
        f"no novelty was manufactured.\n"
        f"- V0 does not publish. All drafts are PENDING_HUMAN_REVIEW.\n")
    write_text(REPO_ROOT / f"data/research/{args.date}-research.md", research_md)

    drafts_md = (
        f"# Draft candidates {args.date}\n\n{header}\n"
        f"> STATUS: PENDING_HUMAN_REVIEW — V0 never publishes. "
        f"A human approves, edits, and posts.\n\n")
    for i, (it, core, f) in enumerate(drafts, 1):
        drafts_md += (
            f"## Draft {i} (from {it['id']}: {it['topic']})\n\n"
            f"```\n{core}\n```\n({len(core)}/{DRAFT_CHAR_LIMIT} chars)\n\n"
            f"- premise: {f['premise']}\n"
            f"- evidence_basis: {f['evidence_basis']}\n"
            f"- why_worth_posting: {f['why_worth_posting']}\n"
            f"- uncertainty_risks: {f['uncertainty_risks']}\n"
            f"- pillar: {f['pillar']}\n\n")
    drafts_md += ("## Skipped\n\n" + "".join(
        f"- {it['id']} ({it['topic']}): {reason}\n" for it, reason in skips)
        + "\n---\nHuman review: approve / edit / reject each draft. "
          "Record outcome per WORKFLOW.md.\n")
    write_text(REPO_ROOT / f"data/drafts/{args.date}-drafts.md", drafts_md)

    print(f"run {run_id}: {len(items)} items -> "
          f"{len(drafts)} drafts, {len(skips)} skips "
          f"(research + drafts written for {args.date})")


if __name__ == "__main__":
    main()
