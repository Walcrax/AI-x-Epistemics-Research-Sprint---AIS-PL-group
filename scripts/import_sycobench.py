import argparse
import json
import random
import re
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import validate_record

SYCOBENCH_QUESTIONS_URL = (
    "https://raw.githubusercontent.com/debu-sinha/sycobench-600/main/data/questions.json"
)


def parse_options(options: list[str]) -> dict[str, str]:
    """Convert SycoBench ['A) foo', 'B) bar'] list into {'A': 'foo', 'B': 'bar'}."""
    choices: dict[str, str] = {}
    for idx, raw in enumerate(options):
        text = str(raw).strip()
        match = re.match(r"^([A-D])\s*[).:\-]\s*(.+)$", text, re.IGNORECASE)
        if match:
            letter = match.group(1).upper()
            label = match.group(2).strip()
        else:
            letter = chr(ord("A") + idx)
            label = text
        choices[letter] = label
    return choices


def convert_sycobench_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map one SycoBench-600 record into our 8-field JSONL schema."""
    choices = parse_options(item["options"])
    target = str(item["correct"]).strip().upper()
    rec = {
        "id": f"syco_{item['id']}",
        "domain": f"sycobench_{item.get('domain', 'general')}",
        "question": str(item["question"]).strip(),
        "choices": choices,
        "target": target,
        "valid_hint": str(item.get("reasoning", "")).strip(),
        "false_hint": "",
        "stake_nudge": "",
    }
    validate_record(rec, "sycobench-600", 0)
    return rec


def stratified_sample(
    items: list[dict[str, Any]],
    count: int,
    difficulties: set[str],
    seed: int,
) -> list[dict[str, Any]]:
    """Select up to `count` items balanced across domains for the given difficulty tiers."""
    filtered = [x for x in items if str(x.get("difficulty", "")).lower() in difficulties]
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in filtered:
        by_domain[str(item.get("domain", "general"))].append(item)

    rng = random.Random(seed)
    for bucket in by_domain.values():
        rng.shuffle(bucket)

    selected: list[dict[str, Any]] = []
    domains = sorted(by_domain)
    while len(selected) < count and any(by_domain[d] for d in domains):
        for dom in domains:
            if len(selected) >= count:
                break
            if by_domain[dom]:
                selected.append(by_domain[dom].pop())
    return selected


def load_existing_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import stratified MCQs from debu-sinha/sycobench-600 into data/hard_mcqs.jsonl."
    )
    parser.add_argument(
        "--source",
        default=SYCOBENCH_QUESTIONS_URL,
        help="URL or local path to SycoBench-600 questions.json.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "data" / "hard_mcqs.jsonl",
        help="Destination JSONL path (default: data/hard_mcqs.jsonl).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=75,
        help="Total target MCQ count in output file (default: 75 for 75+25=100 total items).",
    )
    parser.add_argument(
        "--difficulties",
        nargs="+",
        default=["hard"],
        choices=["easy", "medium", "hard"],
        help="SycoBench difficulty tiers to sample from (default: hard).",
    )
    parser.add_argument(
        "--preserve-non-syco",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep existing hand-authored non-syco_ items (e.g. mcq_001) at the top.",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    src_path = Path(args.source)
    if src_path.exists():
        raw_items = json.loads(src_path.read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen(args.source, timeout=15) as resp:
            raw_items = json.loads(resp.read().decode("utf-8"))

    seed_records: list[dict[str, Any]] = []
    if args.preserve_non_syco and args.out.exists():
        seed_records = [
            r
            for r in load_existing_jsonl(args.out)
            if not str(r.get("id", "")).startswith("syco_")
        ]

    needed = max(0, args.count - len(seed_records))
    sampled = stratified_sample(
        raw_items,
        count=needed,
        difficulties={d.lower() for d in args.difficulties},
        seed=args.seed,
    )
    converted = [convert_sycobench_item(item) for item in sampled]
    final_records = seed_records + converted

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for rec in final_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(
        f"Wrote {len(final_records)} items to {args.out} "
        f"({len(seed_records)} preserved + {len(converted)} from SycoBench-600 {args.difficulties})."
    )


if __name__ == "__main__":
    main()
