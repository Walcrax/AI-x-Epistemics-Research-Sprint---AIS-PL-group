import argparse
import csv
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai.log import EvalLog, read_eval_log

from scripts.export_results import ARM_ORDER, TONE_ORDER, collect_eval_files

CODING_CSV_COLUMNS = [
    "sample_id",
    "model",
    "arm",
    "tone",
    "turn0_ans",
    "flip_turn",
    "turn1_text",
    "turn2_text",
    "turn3_text",
    "coder1_label",
    "coder2_label",
]

VALID_CODING_LABELS = (
    "RATIONALISED",
    "EXPLICIT_DEFERENCE",
    "COMPLIED_UNDER_PROTEST",
)

CODING_TARGET_ARMS = {"stake_pushback", "incentive_pushback"}


def _message_text(msg: Any) -> str:
    content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            ctype = getattr(item, "type", None)
            if ctype == "text":
                txt = getattr(item, "text", "")
                if txt:
                    parts.append(str(txt))
            elif ctype != "reasoning":
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content).strip()


def _extract_turn_texts(sample: Any) -> tuple[str, str, str]:
    smeta = sample.metadata or {}
    assistant_msgs = [
        _message_text(msg)
        for msg in (sample.messages or [])
        if getattr(msg, "role", None) == "assistant"
    ]
    texts: list[str] = []
    for turn_idx in (1, 2, 3):
        raw = smeta.get(f"turn{turn_idx}_raw")
        if raw is not None and str(raw).strip():
            texts.append(str(raw).strip())
        elif turn_idx < len(assistant_msgs):
            texts.append(assistant_msgs[turn_idx])
        else:
            texts.append("")
    return texts[0], texts[1], texts[2]


def _compute_flip_turn(smeta: dict[str, Any], sc_meta: dict[str, Any]) -> int:
    if sc_meta.get("flip_turn") in {1, 2, 3}:
        return int(sc_meta["flip_turn"])
    t0 = smeta.get("turn0_ans")
    if t0 is None:
        return 0
    for turn_idx in (1, 2, 3):
        tk = smeta.get(f"turn{turn_idx}_ans")
        if tk is not None and tk != t0:
            return turn_idx
    return 0


def extract_coding_rows_from_log(log: EvalLog) -> list[dict[str, Any]]:
    """Extract flipped stake_pushback and incentive_pushback rows for human dual-coding."""
    rows: list[dict[str, Any]] = []
    task_args = log.eval.task_args or {}
    model = str(log.eval.model)

    for sample in log.samples or []:
        smeta = sample.metadata or {}
        scores = sample.scores or {}
        main_score = scores.get("selective_updating_scorer")
        sc_meta = main_score.metadata if main_score and main_score.metadata else {}

        arm = str(sc_meta.get("arm") or smeta.get("arm") or task_args.get("arm", ""))
        if arm not in CODING_TARGET_ARMS:
            continue

        applicable = bool(sc_meta.get("applicable", smeta.get("applicable", True)))
        if not applicable:
            continue

        flip_turn = _compute_flip_turn(smeta, sc_meta)
        ever_flipped = bool(sc_meta.get("ever_flipped", flip_turn > 0))
        if not ever_flipped or flip_turn <= 0:
            continue

        tone = str(sc_meta.get("tone") or smeta.get("tone") or task_args.get("tone", ""))
        t1_text, t2_text, t3_text = _extract_turn_texts(sample)
        rows.append(
            {
                "sample_id": str(sample.id),
                "model": model,
                "arm": arm,
                "tone": tone,
                "turn0_ans": smeta.get("turn0_ans") or "",
                "flip_turn": flip_turn,
                "turn1_text": t1_text,
                "turn2_text": t2_text,
                "turn3_text": t3_text,
                "coder1_label": "",
                "coder2_label": "",
            }
        )
    return rows


def export_coding_transcripts(inputs: list[Path], out_csv: Path) -> list[dict[str, Any]]:
    """Collect flipped stake/incentive trajectories into a UTF-8 CSV for dual coding."""
    eval_files = collect_eval_files(inputs)
    rows: list[dict[str, Any]] = []
    for path in eval_files:
        log = read_eval_log(str(path))
        if log.status != "success" and not log.samples:
            continue
        rows.extend(extract_coding_rows_from_log(log))

    rows.sort(
        key=lambda r: (
            str(r["sample_id"]),
            str(r["model"]),
            ARM_ORDER.get(str(r["arm"]), 99),
            TONE_ORDER.get(str(r["tone"]), 99),
        )
    )

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CODING_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export flipped stake_pushback and incentive_pushback trajectories into a UTF-8 CSV "
            f"for human dual-coding ({', '.join(VALID_CODING_LABELS)})."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[ROOT_DIR / "logs" / "pilot_v2"],
        help="One or more .eval files or directories (default: logs/pilot_v2).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "outputs" / "coding_transcripts.csv",
        help="Output UTF-8 CSV path (default: outputs/coding_transcripts.csv).",
    )
    args = parser.parse_args()

    rows = export_coding_transcripts(args.inputs, args.out)
    print(
        f"Exported {len(rows)} flipped stake/incentive trajectory row(s) to {args.out} "
        f"(labels: {', '.join(VALID_CODING_LABELS)})."
    )


if __name__ == "__main__":
    main()
