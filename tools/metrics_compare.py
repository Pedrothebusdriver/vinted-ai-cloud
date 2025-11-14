#!/usr/bin/env python3
import collections
import json
import os
import pathlib
import re

ROOT = pathlib.Path(".")
EVALS_DIR = ROOT / "data" / "evals"
AGENT_DIR = ROOT / ".agent" / "metrics"
RULES_OUT = ROOT / "rules" / "proposed"

AGENT_DIR.mkdir(parents=True, exist_ok=True)
RULES_OUT.mkdir(parents=True, exist_ok=True)

# Tunables (can later move to repo vars)
IMPROVE_MIN = float(os.environ.get("AGENT_IMPROVE_MIN", "1.0"))   # +1% overall to consider improved
REGRESS_MAX = float(os.environ.get("AGENT_REGRESS_MAX", "1.0"))   # allow <=1% drop per bucket

def pct(n, d):
    return (100.0 * n / d) if d else 0.0

def load_latest_eval_lines():
    if not EVALS_DIR.exists():
        return None, []
    dated = sorted([p for p in EVALS_DIR.glob("*") if p.is_dir()], reverse=True)
    if not dated:
        return None, []
    day = dated[0]
    lines = []
    for p in sorted(day.glob("*.jsonl")):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    return day.name, lines

def compute_metrics(lines):
    total = 0; correct = 0
    by_bucket = collections.Counter()
    ok_bucket = collections.Counter()
    fails = []  # keep some failing examples for proposals
    for j in lines:
        b = j.get("bucket","").strip()
        c = bool(j.get("correct", False))
        total += 1
        by_bucket[b] += 1
        if c:
            correct += 1
            ok_bucket[b] += 1
        else:
            fails.append(j)
    overall = pct(correct, total)
    per_bucket = {}
    for b, n in by_bucket.items():
        per_bucket[b] = {
            "n": n,
            "acc": pct(ok_bucket[b], n),
            "ok": ok_bucket[b],
            "fail": n - ok_bucket[b],
        }
    return {
        "overall": {"n": total, "acc": overall, "ok": correct, "fail": total - correct},
        "buckets": per_bucket,
        "fails": fails[:200],
    }

def load_baseline():
    p = AGENT_DIR / "baseline.json"
    if p.exists():
        return json.loads(p.read_text())
    return None

def save_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))

def tokens(s):
    return [t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if t]

def expected_leaf(bucket):
    # "electronics/phones" -> "phones"
    if not bucket: return ""
    return bucket.rsplit("/",1)[-1]

def propose_category_synonyms(metrics):
    """
    Very simple heuristic:
    If bucket is B (e.g., 'jackets') but prediction contains token 'coat',
    propose synonyms['coat'] = 'jackets' so text->category mapping can be improved.
    """
    syn = collections.Counter()
    for j in metrics["fails"]:
        b = expected_leaf(j.get("bucket",""))
        pred = (j.get("pred_category") or "").lower()
        for t in set(tokens(pred)):
            # ignore trivial tokens
            if len(t) < 3: continue
            # don't map the exact bucket name to itself
            if t == b: continue
            syn[(t, b)] += 1
    # keep only strong pairs (>=2 occurrences)
    out = {}
    for (tok, leaf), cnt in syn.items():
        if cnt >= 2:
            out[tok] = leaf
    return out

def render_table_row(cells):
    return "| " + " | ".join(cells) + " |"

def write_pr_markdown(day, current, baseline, deltas, syn_proposals):
    lines = []
    lines.append(f"# Agent rules tweak proposal — {day}")
    lines.append("")
    lines.append("## Accuracy")
    before = baseline["overall"]["acc"] if baseline else 0.0
    after = current["overall"]["acc"]
    delta = after - before
    lines.append(f"- Overall: **{after:.1f}%** (was {before:.1f}% — delta {delta:+.1f}%)")
    lines.append("")
    lines.append(render_table_row(["Bucket","Before","After","Δ","n"]))
    lines.append("|---|---:|---:|---:|---:|")
    # Join buckets to ensure consistent table
    buckets = set(current["buckets"].keys())
    if baseline: buckets |= set(baseline.get("buckets",{}).keys())
    for b in sorted(buckets):
        cb = current["buckets"].get(b, {"acc":0.0,"n":0})
        bb = (baseline.get("buckets",{}).get(b, {"acc":0.0,"n":0}) if baseline else {"acc":0.0,"n":0})
        lines.append(render_table_row([
            b or "(unknown)",
            f"{bb['acc']:.1f}%",
            f"{cb['acc']:.1f}%",
            f"{(cb['acc']-bb['acc']):+0.1f}%",
            str(cb["n"])
        ]))
    lines.append("")
    if syn_proposals:
        lines.append("## Proposed category synonyms")
        lines.append("These come from frequent mistakes (predicted token → expected bucket leaf).")
        lines.append("")
        lines.append("```yaml")
        lines.append("version: 1")
        lines.append("synonyms:")
        for k,v in sorted(syn_proposals.items()):
            lines.append(f"  {k}: {v}")
        lines.append("```")
        lines.append("")
    else:
        lines.append("## Proposed category synonyms")
        lines.append("_No safe proposals detected tonight (not enough consistent failures)._")
        lines.append("")

    # hardest examples (first 8)
    lines.append("## Hard examples")
    lines.append(render_table_row(["Bucket","Pred","Correct?","File"]))
    lines.append("|---|---|:--:|---|")
    count = 0
    for j in current["fails"]:
        if count >= 8: break
        b = j.get("bucket","")
        pred = j.get("pred_category","")
        ok = "❌"
        f = j.get("file","")
        lines.append(render_table_row([b, pred, ok, f]))
        count += 1

    body = "\n".join(lines)
    (AGENT_DIR / "pr.md").write_text(body)
    return body

def main():
    day, lines = load_latest_eval_lines()
    decision_path = AGENT_DIR / "decision.txt"
    if not lines:
        decision_path.write_text("IMPROVED: no\n(reason: no eval data)\n")
        print("IMPROVED: no")
        return

    current = compute_metrics(lines)
    baseline = load_baseline()

    before = baseline["overall"]["acc"] if baseline else 0.0
    after = current["overall"]["acc"]
    delta = after - before

    # Per-bucket regressions check
    regressed_bad = False
    if baseline:
        prev_b = baseline.get("buckets",{})
        for b, cur in current["buckets"].items():
            prev = prev_b.get(b, {"acc":0.0})
            if (cur["acc"] - prev["acc"]) < -REGRESS_MAX:
                regressed_bad = True
                break

    improved = (delta >= IMPROVE_MIN) and not regressed_bad
    # Always write current -> seed baseline if none
    save_json(AGENT_DIR / "current.json", current)
    if baseline is None:
        save_json(AGENT_DIR / "baseline.json", current)

    # Proposals (only if we have enough data)
    syn = propose_category_synonyms(current)
    if syn:
        RULES_OUT.mkdir(parents=True, exist_ok=True)
        rules_yaml = "version: 1\nsynonyms:\n" + "\n".join([f"  {k}: {v}" for k,v in sorted(syn.items())]) + "\n"
        (RULES_OUT / "categories.yaml").write_text(rules_yaml)

    # PR body
    write_pr_markdown(day or "(unknown)", current, baseline, delta, syn)

    # decision marker
    decision_path.write_text(f"IMPROVED: {'yes' if improved else 'no'}\n(overall delta {delta:+.1f} pp; "
                             f"baseline {'present' if baseline else 'created'})\n")
    print(f"IMPROVED: {'yes' if improved else 'no'}")

if __name__ == "__main__":
    main()
