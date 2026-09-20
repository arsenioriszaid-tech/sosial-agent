#!/usr/bin/env python3
"""Content Engine V0.1 dry-run: research -> verified facts -> context ->
analysis -> core observation -> canonical draft -> human review.

Platform adaptation is a separate, non-destructive NOTE (FITS/NEEDS_REVIEW);
platform budgets never constrain the canonical draft and the engine never
truncates it.

Reads operator-curated research items (JSON), enforces CONTENT-RULES.md, and
emits:
  data/research/<date>-research.md   judged items + SKIP reasons
  data/drafts/<date>-drafts.md        canonical drafts for HUMAN review

V0 never publishes. Outputs are marked PENDING_HUMAN_REVIEW.
Rerunnable: same --date + same inputs overwrite deterministically.

Usage:
  python3 scripts/content_run.py [--date YYYY-MM-DD] [--max-drafts N]
                                 [--inputs path] [--allow-exousia-cta]
  (--max-drafts omitted = no cap; every item passing the gates is drafted.)
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
(HYPE_PATTERNS, BAIT_PATTERNS, REPO_ROOT, load_json, load_yaml,
 refuse_forbidden_flags, sha_short, utc_today,
 write_text) = (common.HYPE_PATTERNS, common.BAIT_PATTERNS, common.REPO_ROOT,
                common.load_json, common.load_yaml,
                common.refuse_forbidden_flags, common.sha_short,
                common.utc_today, common.write_text)

CONTRACT = "v0.1"
MIN_CONTEXT_CHARS = 40


def load_canon_config():
    try:
        cfg = load_yaml(REPO_ROOT / "config/canonical.yaml")
        canon = cfg.get("canonical", {})
        budgets = cfg.get("platform_budgets", {})
    except (OSError, ValueError):
        canon, budgets = {}, {}
    return (
        int(canon.get("target_min_chars", 400)),
        int(canon.get("target_max_chars", 800)),
        {k: int(v) for k, v in budgets.items()} or {"x": 280},
    )


def contains(patterns, *texts):
    blob = " ".join(t for t in texts if t).lower()
    return [p for p in patterns if p in blob]


def normalize(item):
    """Map new V0.1 schema with backward-compatible fallback to V0 fields."""
    facts = item.get("verified_facts")
    if not facts:
        facts = [item.get("factual_summary", "").strip()] \
            if item.get("factual_summary", "").strip() else []
    context = item.get("context", "").strip() or item.get("why_it_matters", "").strip()
    obs = item.get("core_observation", "").strip() or item.get("possible_angle", "").strip()
    take = item.get("take", "").strip()
    trust = item.get("claim_trust", "single-source").strip() or "single-source"
    depth = item.get("depth", "").strip()
    if not depth:
        depth = "analysis" if (item.get("possible_angle", "").strip()
                               or item.get("core_observation", "").strip()) else "headline-only"
    return {"facts": facts, "context": context, "obs": obs, "take": take,
            "trust": trust, "depth": depth}


def rank(item, n):
    score = 0
    score += 2 if n["obs"] else 0
    score += 1 if len(n["context"]) >= MIN_CONTEXT_CHARS else 0
    score += {"solid": 2, "single-source": 1, "unverified": 0}.get(n["trust"], 0)
    score += 2 if n["depth"] == "analysis" else 1 if n["depth"] == "contextualized" else 0
    score += 1 if n["take"] else 0
    return score


def decide(item, n, allowed_topics):
    """Return (decision, reason). Decision is DRAFT or SKIP."""
    if item.get("topic") not in allowed_topics:
        return "SKIP", f"off-topic ({item.get('topic')!r} not in config/topics.yaml)"
    if not item.get("source", "").strip() or not n["facts"]:
        return "SKIP", "no evidence basis (missing source or verified facts)"
    if not n["obs"]:
        return "SKIP", "no meaningful observation (no core observation)"
    if len(n["context"]) < MIN_CONTEXT_CHARS:
        return "SKIP", f"context too thin ({len(n['context'])} < {MIN_CONTEXT_CHARS} chars)"
    if n["trust"] == "unverified":
        return "SKIP", "main claim not trustworthy enough (claim_trust=unverified)"
    if n["depth"] == "headline-only":
        return "SKIP", "headline repetition only (depth=headline-only)"
    hype = contains(HYPE_PATTERNS, *n["facts"], n["obs"], n["take"])
    if hype:
        return "SKIP", f"generic hype per CONTENT-RULES.md ({', '.join(hype)})"
    bait = contains(BAIT_PATTERNS, n["obs"], n["take"])
    if bait and n["depth"] != "analysis":
        return "SKIP", f"controversy/engagement bait without substance ({', '.join(bait)})"
    return "DRAFT", f"depth={n['depth']} trust={n['trust']} score={rank(item, n)}"


def build_canonical(item, n, budgets):
    """Compose the canonical draft. Facts/Analysis/Take labeled apart; the
    template injects no hook, question, CTA, or truncation — a '?' appears
    only if the operator's own text contains one."""
    paras = [
        "Facts: " + " ".join(n["facts"]),
        "Analysis: " + (n["obs"] + (" " + n["context"] if n["context"] not in n["obs"] else "")).strip(),
    ]
    take_text = n["take"] if n["take"] else "— (no take; the observation stands on its own.)"
    paras.append("Take: " + take_text)
    body = "\n\n".join(paras)
    conf = item.get("confidence", "low")
    unc = (f"Confidence: {conf}; claim_trust={n['trust']}. "
           + ("Low confidence — vendor claim/rough estimate, treat as unverified. "
              if conf == "low" else
              "Single-source report; may not generalize. ")
           + "No firsthand verification claimed; no user experience invented.")
    notes = []
    for plat, budget in budgets.items():
        if len(body) <= budget:
            notes.append(f"{plat}: FITS ({len(body)}<={budget}, postable as-is)")
        else:
            notes.append(f"{plat}: NEEDS_REVIEW ({len(body)} chars > {budget}; "
                         f"human adapts — do not auto-truncate)")
    fields = {
        "premise": n["context"],
        "evidence_basis": f"{item['source']} — " + " ".join(n["facts"]),
        "core_observation": n["obs"],
        "interpretation": take_text,
        "why_worth_posting": ("Specific observation with builder/operator relevance; "
                              "complete thought, not engagement bait."),
        "uncertainty_risks": unc,
        "platform_notes": "; ".join(notes),
        "pillar": "technical_observations",
    }
    return body, fields


def main():
    refuse_forbidden_flags(sys.argv)
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=utc_today())
    ap.add_argument("--max-drafts", type=int, default=None,
                    help="Optional operator budget; default drafts everything passing the gates.")
    ap.add_argument("--inputs", default=str(REPO_ROOT / "data/research/sample-inputs.json"))
    ap.add_argument("--allow-exousia-cta", action="store_true",
                    help="Only for the direct_recruitment pillar (<=5%%). "
                         "Without it, any Exousia mention is rejected.")
    args = ap.parse_args()
    canon_min, canon_max, budgets = load_canon_config()

    topics = load_yaml(REPO_ROOT / "config/topics.yaml")["topics"]
    pillars = load_yaml(REPO_ROOT / "config/content-pillars.yaml")
    data = load_json(args.inputs)
    items = data["items"]
    _, input_hash = sha_short(args.inputs)
    prompt_shas = {p: sha_short(REPO_ROOT / "prompts" / p)[0]
                   for p in ("content-research.md", "content-drafting.md")}

    judged = []
    for it in items:
        n = normalize(it)
        decision, reason = decide(it, n, topics)
        judged.append((rank(it, n) if decision == "DRAFT" else -1, it, n, decision, reason))
    judged.sort(key=lambda r: r[0], reverse=True)

    drafts, skips = [], []
    for _, it, n, decision, reason in judged:
        if decision == "DRAFT" and (args.max_drafts is None or len(drafts) < args.max_drafts):
            body, fields = build_canonical(it, n, budgets)
            if "exousia" in body.lower() and not args.allow_exousia_cta:
                skips.append((it, "forced Exousia CTA rejected (SPEC separation rule)"))
                continue
            drafts.append((it, body, fields))
        else:
            skips.append((it, reason if decision == "SKIP" else
                          f"ranked below top-{args.max_drafts} operator budget"))

    run_id = f"content-{args.date}-{input_hash[:8]}"
    fixture_note = ("SAMPLE FIXTURE inputs — not real research. "
                    "Replace with operator-curated items for real runs." if "sample" in args.inputs
                    else "Operator-curated inputs.")
    header = (f"run_id: {run_id}\ncontract: {CONTRACT}\n"
              f"inputs: {args.inputs} (sha256: {input_hash})\n"
              f"inputs_note: {fixture_note}\n"
              f"prompts: {prompt_shas}\nconfig_topics_sha: "
              f"{sha_short(REPO_ROOT/'config/topics.yaml')[0]}\n"
              f"canonical_target: {canon_min}-{canon_max} chars, no hard limit\n"
              f"pillars: {pillars['pillars']}\n")

    research_md = (
        f"# Research report {args.date}\n\n{header}\n"
        f"## Judged items\n\n"
        f"| id | topic | confidence | depth | claim_trust | score | decision | reason |\n"
        f"|---|---|---|---|---|---|---|---|\n" +
        "".join(f"| {it['id']} | {it['topic']} | {it.get('confidence','low')} | {n['depth']} | "
                f"{n['trust']} | {s if s>=0 else '—'} | "
                f"{'DRAFT' if any(d[0]['id']==it['id'] for d in drafts) else 'SKIP'} | "
                f"{next(r for _,x,_,_,r in judged if x['id']==it['id'])} |\n"
                for s, it, n, _, _ in judged) +
        f"\n## Notes\n- Facts above come only from operator-supplied items; "
        f"no novelty, experience, or opinions were manufactured.\n"
        f"- V0 does not publish. All drafts are PENDING_HUMAN_REVIEW.\n")
    write_text(REPO_ROOT / f"data/research/{args.date}-research.md", research_md)

    drafts_md = (
        f"# Draft candidates {args.date} (contract {CONTRACT})\n\n{header}\n"
        f"> STATUS: PENDING_HUMAN_REVIEW — V0 never publishes. "
        f"A human approves, edits, adapts per platform, and posts.\n"
        f"> Canonical drafts have no hard length limit; platform budgets apply "
        f"only to the adaptation notes below.\n\n")
    for i, (it, body, f) in enumerate(drafts, 1):
        in_range = "in-target" if canon_min <= len(body) <= canon_max else "off-target (WARN, still valid)"
        drafts_md += (
            f"## Draft {i} (from {it['id']}: {it['topic']}) — CANONICAL\n\n"
            f"```\n{body}\n```\n({len(body)} chars, target {canon_min}-{canon_max}: {in_range})\n\n"
            f"- premise: {f['premise']}\n"
            f"- evidence_basis: {f['evidence_basis']}\n"
            f"- core_observation: {f['core_observation']}\n"
            f"- interpretation: {f['interpretation']}\n"
            f"- why_worth_posting: {f['why_worth_posting']}\n"
            f"- uncertainty_risks: {f['uncertainty_risks']}\n"
            f"- platform_notes: {f['platform_notes']}\n"
            f"- pillar: {f['pillar']}\n\n")
    drafts_md += ("## Skipped\n\n" + "".join(
        f"- {it['id']} ({it['topic']}): {reason}\n" for it, reason in skips)
        + "\n---\nHuman review: approve / edit / adapt / reject each draft. "
          "Record outcome per WORKFLOW.md.\n")
    write_text(REPO_ROOT / f"data/drafts/{args.date}-drafts.md", drafts_md)

    print(f"run {run_id} [{CONTRACT}]: {len(items)} items -> "
          f"{len(drafts)} canonical drafts, {len(skips)} skips "
          f"(research + drafts written for {args.date})")


if __name__ == "__main__":
    main()
