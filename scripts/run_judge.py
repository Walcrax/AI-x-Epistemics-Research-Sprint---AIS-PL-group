import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai import score
from inspect_ai.log import EvalLog, read_eval_log, write_eval_log

from src.scorers import assert_cross_family_judge, judge_audit_scorer


def collect_eval_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in inputs:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.eval")))
        elif p.is_file() and p.suffix == ".eval":
            files.append(p)
    return sorted(set(files))


def log_needs_judge(log: EvalLog, include_style_labels: bool, force: bool) -> bool:
    """Skip logs with zero judge-eligible samples unless forced."""
    if not log.samples:
        return False
    if not force and all(
        "judge_audit_scorer" in (s.scores or {}) for s in log.samples
    ):
        return False

    for sample in log.samples:
        meta = sample.metadata or {}
        if not meta.get("applicable", True) or meta.get("turn2_ans") is None:
            continue
        if include_style_labels:
            return True
        arm = meta.get("arm", "")
        flipped_t2 = meta.get("turn2_ans") != meta.get("turn0_ans")
        t2_correct = meta.get("turn2_ans") == str(sample.target).strip().upper()
        if arm == "stake_pushback" and flipped_t2 and not t2_correct:
            return True
    return False


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    parser = argparse.ArgumentParser(
        description="Post-hoc cross-family judge pass over saved inspect_ai .eval logs."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more .eval files or directories containing .eval logs.",
    )
    parser.add_argument(
        "--judge-model",
        required=True,
        help="Judge model identifier (e.g. openai/gpt-5-mini or anthropic/claude-sonnet-4-5).",
    )
    parser.add_argument(
        "--include-style-labels",
        action="store_true",
        help="Also label QUIET_RETREAT and HOLLOW_APOLOGY across applicable samples.",
    )
    parser.add_argument(
        "--allow-same-family",
        action="store_true",
        help="Allow judging a model from the same family (disabled by default).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Optional directory for judged .eval logs (defaults to updating in-place).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run judge even if judge_audit_scorer is already present.",
    )
    args = parser.parse_args()

    files = collect_eval_files(args.inputs)
    if not files:
        print("No .eval files found.")
        return

    judged_count = 0
    for path in files:
        log = read_eval_log(str(path))
        if log.status != "success":
            print(f"SKIP (status={log.status}): {path.name}")
            continue

        assert_cross_family_judge(
            str(log.eval.model), args.judge_model, allow_same_family=args.allow_same_family
        )

        if not log_needs_judge(log, args.include_style_labels, args.force):
            print(f"SKIP (no judge-eligible samples or already judged): {path.name}")
            continue

        scorer_fn = judge_audit_scorer(
            judge_model=args.judge_model,
            include_style_labels=args.include_style_labels,
            allow_same_family=args.allow_same_family,
        )
        updated = score(log, scorer_fn, action="overwrite" if args.force else "append", copy=True)

        dest = (args.out_dir / path.name) if args.out_dir else path
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
        write_eval_log(updated, str(dest))
        judged_count += 1
        print(f"JUDGED -> {dest}")

    print(f"Done. Judged {judged_count} log(s).")


if __name__ == "__main__":
    main()
