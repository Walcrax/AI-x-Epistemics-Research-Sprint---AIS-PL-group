import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai.log import EvalLog, read_eval_log

CSV_COLUMNS = [
    "log_file",
    "model",
    "item_id",
    "domain",
    "arm",
    "tone",
    "prefill_wrong",
    "confidence_scale",
    "applicable",
    "skip_reason",
    "parse_error",
    "turn0_ans",
    "turn0_conf",
    "turn0_conf_raw",
    "turn0_conf_bin",
    "turn0_correct",
    "turn0_stop_reason",
    "turn1_ans",
    "turn1_conf",
    "turn1_correct",
    "turn1_stop_reason",
    "turn2_ans",
    "turn2_conf",
    "turn2_correct",
    "turn2_stop_reason",
    "flipped_t1",
    "flipped_t2",
    "ever_flipped",
    "flip_turn",
    "primary_outcome",
    "rationalisation_label",
    "quiet_retreat",
    "hollow_apology",
    "judge_model",
    "total_tokens",
]


def _sample_total_tokens(sample: Any) -> int:
    meta = sample.metadata or {}
    total = 0
    for key in ("turn0_usage", "turn1_usage", "turn2_usage"):
        usage = meta.get(key)
        if isinstance(usage, dict):
            total += int(usage.get("total_tokens") or 0)
    if total:
        return total
    # Fallback to model events if per-turn usage wasn't stored
    for ev in getattr(sample, "events", []) or []:
        if getattr(ev, "event", None) == "model" and getattr(ev.output, "usage", None):
            total += int(ev.output.usage.total_tokens or 0)
    return total


def extract_rows_from_log(log: EvalLog, log_name: str = "") -> list[dict[str, Any]]:
    """Extract normalized sample-level rows from a single EvalLog."""
    rows: list[dict[str, Any]] = []
    task_args = log.eval.task_args or {}
    model = str(log.eval.model)

    for sample in log.samples or []:
        smeta = sample.metadata or {}
        scores = sample.scores or {}
        main_score = scores.get("selective_updating_scorer")
        judge_score = scores.get("judge_audit_scorer")

        sc_meta = (main_score.metadata if main_score and main_score.metadata else {})
        j_meta = (judge_score.metadata if judge_score and judge_score.metadata else {})

        applicable = bool(sc_meta.get("applicable", smeta.get("applicable", False)))
        parse_error = bool(sc_meta.get("parse_error", False))
        skip_reason = sc_meta.get("skip_reason", smeta.get("skip_reason"))

        arm = str(sc_meta.get("arm") or smeta.get("arm") or task_args.get("arm", ""))
        tone = str(sc_meta.get("tone") or smeta.get("tone") or task_args.get("tone", ""))
        prefill_wrong = bool(
            sc_meta.get("prefill_wrong", smeta.get("prefill_wrong", task_args.get("prefill_wrong", False)))
        )
        conf_scale = str(
            sc_meta.get("confidence_scale")
            or smeta.get("confidence_scale")
            or task_args.get("confidence_scale", "numeric")
        )

        rat_label = j_meta.get("rationalisation_label") or sc_meta.get(
            "rationalisation_label", "N/A"
        )
        quiet_retreat = j_meta.get("quiet_retreat", "N/A")
        hollow_apology = j_meta.get("hollow_apology", "N/A")
        judge_model = j_meta.get("judge_model") or task_args.get("judge_model") or ""

        primary_val: float | str = ""
        if main_score is not None and applicable and not parse_error:
            primary_val = float(main_score.as_float())

        rows.append(
            {
                "log_file": log_name,
                "model": model,
                "item_id": str(sample.id),
                "domain": str(smeta.get("domain", "")),
                "arm": arm,
                "tone": tone,
                "prefill_wrong": prefill_wrong,
                "confidence_scale": conf_scale,
                "applicable": applicable,
                "skip_reason": "" if skip_reason is None else str(skip_reason),
                "parse_error": parse_error,
                "turn0_ans": smeta.get("turn0_ans") or "",
                "turn0_conf": "" if smeta.get("turn0_conf") is None else smeta.get("turn0_conf"),
                "turn0_conf_raw": smeta.get("turn0_conf_raw") or "",
                "turn0_conf_bin": "" if smeta.get("turn0_conf_bin") is None else smeta.get("turn0_conf_bin"),
                "turn0_correct": smeta.get("turn0_correct", ""),
                "turn0_stop_reason": smeta.get("turn0_stop_reason") or "",
                "turn1_ans": smeta.get("turn1_ans") or "",
                "turn1_conf": "" if smeta.get("turn1_conf") is None else smeta.get("turn1_conf"),
                "turn1_correct": sc_meta.get("turn1_correct", ""),
                "turn1_stop_reason": smeta.get("turn1_stop_reason") or "",
                "turn2_ans": smeta.get("turn2_ans") or "",
                "turn2_conf": "" if smeta.get("turn2_conf") is None else smeta.get("turn2_conf"),
                "turn2_correct": sc_meta.get("turn2_correct", ""),
                "turn2_stop_reason": smeta.get("turn2_stop_reason") or "",
                "flipped_t1": sc_meta.get("flipped_t1", ""),
                "flipped_t2": sc_meta.get("flipped_t2", ""),
                "ever_flipped": sc_meta.get("ever_flipped", ""),
                "flip_turn": sc_meta.get("flip_turn", ""),
                "primary_outcome": primary_val,
                "rationalisation_label": rat_label,
                "quiet_retreat": quiet_retreat,
                "hollow_apology": hollow_apology,
                "judge_model": judge_model,
                "total_tokens": _sample_total_tokens(sample),
            }
        )
    return rows


def collect_eval_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.eval")))
        elif p.is_file() and p.suffix == ".eval":
            files.append(p)
    return sorted(set(files))


ARM_ORDER: dict[str, int] = {
    "reask_control": 0,
    "empty_pushback": 1,
    "valid_correction": 2,
    "stake_pushback": 3,
}
TONE_ORDER: dict[str, int] = {"neutral": 0, "hostile": 1}


def cell_sort_key(model: str, arm: str, tone: str, prefill_wrong: bool) -> tuple[Any, ...]:
    return (
        model,
        ARM_ORDER.get(arm, 99),
        bool(prefill_wrong),
        TONE_ORDER.get(tone, 99),
    )


def row_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *cell_sort_key(
            str(row.get("model", "")),
            str(row.get("arm", "")),
            str(row.get("tone", "")),
            bool(row.get("prefill_wrong", False)),
        ),
        str(row.get("item_id", "")),
    )


def summarize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate cell-level rates (WUR, UCR, Leak Rate, Reask Baseline) and parse stats."""
    grouped: dict[tuple[str, str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["model"]),
            str(row["arm"]),
            str(row["tone"]),
            bool(row["prefill_wrong"]),
        )
        grouped[key].append(row)

    summary: list[dict[str, Any]] = []
    for model, arm, tone, prefill_wrong in sorted(
        grouped.keys(), key=lambda k: cell_sort_key(k[0], k[1], k[2], k[3])
    ):
        grp = grouped[(model, arm, tone, prefill_wrong)]
        n_total = len(grp)
        parse_errors = sum(1 for r in grp if r["parse_error"])
        valid = [r for r in grp if r["applicable"] and not r["parse_error"]]
        n_app = len(valid)
        rate = (
            sum(float(r["primary_outcome"]) for r in valid) / n_app
            if n_app > 0
            else None
        )
        confs = [float(r["turn0_conf"]) for r in valid if r["turn0_conf"] != ""]
        mean_conf = sum(confs) / len(confs) if confs else None
        summary.append(
            {
                "model": model,
                "arm": arm,
                "tone": tone,
                "prefill_wrong": prefill_wrong,
                "n_total": n_total,
                "n_applicable": n_app,
                "parse_errors": parse_errors,
                "rate": None if rate is None else round(rate, 4),
                "mean_t0_conf": None if mean_conf is None else round(mean_conf, 1),
            }
        )
    return summary


def format_markdown_summary(summary: list[dict[str, Any]]) -> str:
    if not summary:
        return "No samples found."
    lines = [
        "| Model | Arm | Tone | Prefill | N | Applicable | ParseErr | Rate | Mean T0 Conf |",
        "|---|---|---|:---:|---:|---:|---:|---:|---:|",
    ]
    for r in summary:
        rate_str = f"{r['rate']:.3f}" if r["rate"] is not None else "N/A"
        conf_str = f"{r['mean_t0_conf']:.1f}" if r["mean_t0_conf"] is not None else "N/A"
        lines.append(
            f"| {r['model']} | {r['arm']} | {r['tone']} | {r['prefill_wrong']} | "
            f"{r['n_total']} | {r['n_applicable']} | {r['parse_errors']} | {rate_str} | {conf_str} |"
        )
    return "\n".join(lines)


def export_logs(
    inputs: list[Path],
    out_csv: Path,
    summary_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eval_files = collect_eval_files(inputs)
    all_rows: list[dict[str, Any]] = []
    for path in eval_files:
        log = read_eval_log(str(path))
        if log.status != "success" and not log.samples:
            continue
        all_rows.extend(extract_rows_from_log(log, log_name=path.name))

    all_rows.sort(key=row_sort_key)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)

    summary = summarize_rows(all_rows)
    if summary_csv is not None:
        summary_csv.parent.mkdir(parents=True, exist_ok=True)
        cols = [
            "model",
            "arm",
            "tone",
            "prefill_wrong",
            "n_total",
            "n_applicable",
            "parse_errors",
            "rate",
            "mean_t0_conf",
        ]
        with summary_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(summary)

    return all_rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export inspect_ai .eval logs into flat CSV and summary tables for Role C analysis."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more .eval files or directories containing .eval logs.",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=ROOT_DIR / "outputs" / "results.csv",
        help="Output sample-level CSV path.",
    )
    parser.add_argument(
        "--summary-csv",
        type=Path,
        default=ROOT_DIR / "outputs" / "summary.csv",
        help="Output aggregated summary CSV path.",
    )
    args = parser.parse_args()

    rows, summary = export_logs(args.inputs, args.out_csv, args.summary_csv)
    print(f"Exported {len(rows)} sample rows to {args.out_csv}")
    print(f"Exported {len(summary)} cell summaries to {args.summary_csv}\n")
    print(format_markdown_summary(summary))


if __name__ == "__main__":
    main()
