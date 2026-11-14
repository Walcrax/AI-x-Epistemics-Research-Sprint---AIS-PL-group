"""Build the 70-item MCQ set (+ reserve) for the v3 harness check (neutral empty pressure only;
see README_items.md). Selection logic is unchanged from v2.
Sources (clone next to this script's parent or edit paths):
  sycobench-600 (data/questions.json), MMLU-Pro (eval_results/*.zip unpacked to mp/),
  SuperGPQA (data/SuperGPQA-all.jsonl), gpqa (dataset.zip unpacked to gq/).
Output schema = SycoBench-600 questions.json schema + extra fields.
"""
import json, glob, csv, random, re, ast, collections, os, sys
SEED = 20261113
# Hand-vetted IDs (read for ambiguity, near-duplicate options, broken text, doubtful keys). Order = priority.
KEEP = {
 "FW":  [10944, 3384, 6384, 1634, 6643, 5264, 1342, 6307],
 "LW":  [11259, 11140, 307, 1121, 6866, 1336, 6757, 1782, 10926, 6213],
 "MIX": [871, 6020, 6604, 9421, 5230, 5080, 7101, 890, 1407, 870, 1280, 7034, 7639, 5896],
 "SG_HARD": ["58b56ec032d3", "10aa0c9ef787", "35d73d8a2757", "ab92e4198560", "f896af6b3325", "a05a20c9a2ab", "118d86cc46f8",
             "7020548474e7", "b5cf2e859d50", "68a3d4344faf", "b74bb84f970c", "15b8b25d04e6", "57e776dbdcaa", "0f384591a8c3",
             "52c4dea0f186", "215b8a18858f"],
}
N_PRIMARY = {"FW": 8, "LW": 10, "MIX": 12, "SG_HARD": 14, "GPQA": 20, "ANCHOR": 6}
def keep(pool, s, prefix):
    by = {i["id"]: i for i in pool}
    ordered = [by[f"{prefix}{k}"] for k in KEEP[s]]
    return ordered[:N_PRIMARY[s]], ordered[N_PRIMARY[s]:]
R = "/home/claude"
rng = random.Random(SEED)
BAD_OPT = re.compile(r"all of (the|these)|none of (the|these)|both .* and|neither|\b(options?|choices?|answers?) [A-J]\b|^\(?[A-J]\)? (and|or) \(?[A-J]\)?$|the above|n/a|^[ivx, and]+$|\b(i|ii|iii|iv)\b.*\b(only|and)\b", re.I)
NEG_Q = re.compile(r"\bnot\b|except|\bleast\b|\bfalse\b|incorrect|this page|\|.*\||L:1/|\$\$", re.I)
NUM = re.compile(r"^[\s$\\]*[-+]?[\d.,]+")
BAD_Q = re.compile(r"figure|diagram|shown (below|above)|the (graph|table|image|picture) |following (figure|table|graph)|which of the following is (not|false|incorrect)|EXCEPT|\bNOT\b|I\.|\(i\)", 0)

def letterize(key, distractors, r):
    opts = [key] + distractors
    r.shuffle(opts)
    L = "ABCD"
    return [f"{L[i]}) {o}" for i, o in enumerate(opts)], L[opts.index(key)], opts

def mk(id_, source, domain, tier, q, key, distractors, asserted, reasoning, extra):
    r = random.Random(f"{SEED}-{id_}")
    options, correct, order = letterize(key, distractors, r)
    return dict(id=id_, domain=domain, difficulty=tier, question=q.strip(), options=options, correct=correct,
                reasoning=reasoning, source=source, asserted_wrong="ABCD"[order.index(asserted)],
                option_seed=f"{SEED}-{id_}", **extra)

# ---------------- MMLU-Pro with per-item response priors ----------------
def load_model(path):
    out = {}
    files = [path] if path.endswith(".json") else [f for f in glob.glob(path + "/*_result.json")]
    for f in files:
        try: data = json.load(open(f))
        except Exception: continue
        if not isinstance(data, list): continue
        for x in data:
            if isinstance(x, dict) and "question_id" in x and "pred" in x: out[str(x["question_id"])] = x
    return out
mp = {}
for d in glob.glob(f"{R}/mp/model_outputs_*"):
    name = os.path.basename(d).replace("model_outputs_", "")
    js = [f for f in glob.glob(d + "/**/*.json", recursive=True) if "__MACOSX" not in f and "summary" not in f]
    got = load_model(js[0]) if len(js) == 1 else (load_model(os.path.dirname(js[0])) if js else {})
    if got: mp[name] = got
FRONT = "gemini-3.1-pro_5-shots"
PANEL = ["gpt-4o-2024-08-06_5shots", "claude-3-5-sonnet-20241022_5shots.json", "gemini-1.5-pro-002_5shots",
         "gpt-4o-mini_5shots", "claude-3-5-haiku-20241022_5shots.json", "Meta-Llama-3_1-70B-Instruct_5shots",
         "gemini-1.5-flash-002_5shots", "deepseek-chat-v2_5_5shots"]
for m in [FRONT] + PANEL: assert m in mp, (m, sorted(mp))
print("MMLU-Pro models:", len(mp), "| frontier proxy acc",
      round(sum(x["pred"] == x["answer"] for x in mp[FRONT].values()) / len(mp[FRONT]), 3),
      "| panel acc", [round(sum(x["pred"] == x["answer"] for x in mp[m].values()) / len(mp[m]), 2) for m in PANEL])

MP_CATS = ["law", "health", "psychology", "biology", "history", "philosophy", "business", "economics", "other", "chemistry", "physics", "engineering", "computer science"]
cands = collections.defaultdict(list)
for qid, x in mp[FRONT].items():
    if x["category"] not in MP_CATS: continue
    opts = x["options"] if isinstance(x["options"], list) else ast.literal_eval(x["options"])
    opts = [str(o).strip() for o in opts]
    q = x["question"]
    if len(opts) < 4 or len(q) > 1400 or BAD_Q.search(q) or any(BAD_OPT.search(o) or not o for o in opts): continue
    if len(set(o.lower() for o in opts)) < len(opts) or NEG_Q.search(q): continue
    if NUM.match(opts[int(x["answer_index"])]) or sum(c.isdigit() for c in opts[int(x["answer_index"])]) > 3 or len(q) < 50: continue
    ki = int(x["answer_index"]); key = opts[ki]
    panel = [mp[m][qid]["pred"] for m in PANEL if qid in mp[m]]
    if len(panel) < 6: continue
    p_panel = sum(p == x["answer"] for p in panel) / len(panel)
    votes = collections.Counter()
    for m, d in mp.items():
        p = d.get(qid, {}).get("pred")
        if p and p != x["answer"] and len(p) == 1 and ord(p) - 65 < len(opts) and ord(p) >= 65: votes[p] += 1
    wrong_modal = collections.Counter(p for p in panel + [x["pred"]] if p != x["answer"] and p)
    modal_share = (wrong_modal.most_common(1)[0][1] / (len(panel) + 1)) if wrong_modal else 0
    ranked = [l for l, _ in votes.most_common()] + [chr(65 + i) for i in range(len(opts)) if i != ki]
    dl = []
    for l in ranked:
        if l not in dl and l != x["answer"]: dl.append(l)
    dist = [opts[ord(l) - 65] for l in dl[:3]]
    f_right = x["pred"] == x["answer"]
    if not f_right and p_panel >= 0.38 and modal_share <= 0.5: s = "FW"       # frontier proxy wrong, key supported by part of panel
    elif f_right and 0.12 <= p_panel <= 0.3: s = "LW"                                 # frontier proxy right, 2024 panel mostly wrong
    elif f_right and 0.38 <= p_panel <= 0.62: s = "MIX"
    else: continue
    cands[s].append(mk(f"mmlupro_{qid}", "MMLU-Pro", x["category"], s, q, key, dist, dist[0], "",
                       dict(src_detail=x["src"], needs_key_check=(s == "FW"), prior_frontier_proxy_correct=f_right, prior_panel_acc=round(p_panel, 2), stratum=s)))
print({k: len(v) for k, v in cands.items()})

def take(pool, n, key, cap, r):
    pool.sort(key=lambda i: i["id"]); r.shuffle(pool); out = []; cnt = collections.Counter()
    for it in pool:
        if len(out) == n: break
        if cnt[key(it)] < cap: out.append(it); cnt[key(it)] += 1
    return out, [it for it in pool if it not in out]

primary, reserve = [], []
for s in ("FW", "LW", "MIX"):
    a, b = keep(cands[s], s, "mmlupro_"); primary += a; reserve += b

# ---------------- SuperGPQA: hard, non-calculation ----------------
sg = [json.loads(l) for l in open(f"{R}/SuperGPQA/data/SuperGPQA-all.jsonl")]
pool = []
for x in sg:
    if x["difficulty"] != "hard" or x["is_calculation"]: continue
    opts = [str(o).strip() for o in x["options"]]
    q = x["question"]
    if len(opts) < 4 or len(q) > 900 or len(q) < 60 or BAD_Q.search(q) or any(BAD_OPT.search(o) or not o or len(o) > 220 for o in opts): continue
    if NEG_Q.search(q) or NUM.match(x["answer"].strip()) or any("$$" in o for o in opts): continue
    if x["answer"].strip() not in opts or re.search(r"[\u4e00-\u9fff]|\\begin|_{2,}|\(\s*\)", q + " ".join(opts)): continue
    r = random.Random(f"{SEED}-{x['uuid']}")
    dist = r.sample([o for o in opts if o != x["answer"].strip()], 3)
    pool.append(mk(f"supergpqa_{x['uuid'][:12]}", "SuperGPQA", x["discipline"], "hard", q, x["answer"].strip(), dist, dist[0], "",
                   dict(src_detail=f"{x['field']} / {x['subfield']}", uuid=x["uuid"], stratum="SG_HARD")))
print("SuperGPQA candidates", len(pool))
a, b = keep(pool, "SG_HARD", "supergpqa_")
primary += a; reserve += b

# ---------------- GPQA Diamond (gated: keep out of public repo) ----------------
csv.field_size_limit(10**9)
gp = list(csv.DictReader(open(f"{R}/gq/dataset/gpqa_diamond.csv")))
pool = []
for x in gp:
    q = x["Question"].strip()
    opts = [x["Correct Answer"].strip()] + [x[f"Incorrect Answer {i}"].strip() for i in (1, 2, 3)]
    if len(q) > 1200 or any(len(o) > 300 for o in opts) or BAD_Q.search(q): continue
    r = random.Random(f"{SEED}-{x['Record ID']}")
    pool.append(mk(f"gpqa_{x['Record ID']}", "GPQA-Diamond", x["High-level domain"], "diamond", q, opts[0], opts[1:], r.choice(opts[1:]),
                   x["Explanation"].strip(), dict(src_detail=x["Subdomain"], stratum="GPQA", gated=True, canary=x["Canary String"])))
print("GPQA candidates", len(pool))
a, rest = take(pool, 20, lambda i: i["domain"], 8, rng); b, _ = take(rest, 16, lambda i: i["domain"], 7, rng)
primary += a; reserve += b

# ---------------- SycoBench-600 hard anchors ----------------
sy = json.load(open(f"{R}/sycobench-600/data/questions.json"))
pool, seen = [], set()
for x in sy:
    stem = re.sub(r"\W+", " ", x["question"].lower()).strip()
    if x["difficulty"] != "hard" or stem in seen: continue
    seen.add(stem)
    opts = [re.sub(r"^[A-D]\)\s*", "", o) for o in x["options"]]
    key = opts["ABCD".index(x["correct"])]
    r = random.Random(f"{SEED}-{x['id']}")
    dist = [o for o in opts if o != key]
    pool.append(mk(f"sycobench_{x['id']}", "SycoBench-600", x["domain"], "hard", x["question"], key, dist, r.choice(dist), x["reasoning"],
                   dict(src_detail="", stratum="ANCHOR")))
a, rest = take(pool, 6, lambda i: i["domain"], 1, rng); b, _ = take(rest, 6, lambda i: i["domain"], 1, rng)
primary += a; reserve += b

# pilot: 20 of the 70, proportional by stratum
pil = {"FW": 2, "LW": 3, "MIX": 3, "SG_HARD": 4, "GPQA": 6, "ANCHOR": 2}
for s, n in pil.items():
    for it in rng.sample([i for i in primary if i["stratum"] == s], n): it["pilot"] = True
for it in primary: it.setdefault("pilot", False); it["set"] = "primary"
for it in reserve: it["pilot"] = False; it["set"] = "reserve"
assert len(primary) == 70 and len({i["id"] for i in primary + reserve}) == len(primary + reserve)
json.dump(primary, open("mcq_70.json", "w"), indent=1, ensure_ascii=False)
json.dump(reserve, open("mcq_reserve.json", "w"), indent=1, ensure_ascii=False)
for nm, S in [("primary", primary), ("reserve", reserve)]:
    print(nm, len(S), dict(collections.Counter(i["stratum"] for i in S)), dict(collections.Counter(i["correct"] for i in S)))
print("domains", dict(collections.Counter(i["domain"] for i in primary)))

# Public-safe copy: GPQA asks that items never appear in plain text online, so strip them to IDs.
pub = [dict(it, question="[GPQA item: load by Record ID from the gated dataset]", options=[], reasoning="") if it.get("gated") else it for it in primary]
json.dump(pub, open("mcq_70_public.json", "w"), indent=1, ensure_ascii=False)
for it in primary + reserve:
    assert it["asserted_wrong"] != it["correct"] and len(it["options"]) == 4 and len(set(it["options"])) == 4, it["id"]
with open("mcq_70_overview.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "source", "domain", "stratum", "pilot", "correct", "asserted_wrong", "has_reason", "needs_key_check", "prior_panel_acc", "question_start"])
    for it in primary:
        w.writerow([it["id"], it["source"], it["domain"], it["stratum"], it["pilot"], it["correct"], it["asserted_wrong"], bool(it["reasoning"]),
                    it.get("needs_key_check", False), it.get("prior_panel_acc", ""),
                    "[gated]" if it.get("gated") else it["question"][:80].replace("\n", " ")])
