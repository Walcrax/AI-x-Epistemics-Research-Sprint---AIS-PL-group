import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai.log import read_eval_log

from scripts.export_results import ARM_ORDER, TONE_ORDER, collect_eval_files


def _sample_cell_fields(log: Any, sample: Any) -> tuple[str, str, bool]:
    smeta = sample.metadata or {}
    task_args = log.eval.task_args or {}
    arm = str(smeta.get("arm") or task_args.get("arm", ""))
    tone = str(smeta.get("tone") or task_args.get("tone", ""))
    prefill = bool(smeta.get("prefill_wrong", task_args.get("prefill_wrong", False)))
    return arm, tone, prefill


def entry_sort_key(log: Any, sample: Any, sort_by: str = "item") -> tuple[Any, ...]:
    arm, tone, prefill = _sample_cell_fields(log, sample)
    base_cell = (ARM_ORDER.get(arm, 99), prefill, TONE_ORDER.get(tone, 99))
    if sort_by == "model":
        return (str(log.eval.model), *base_cell, str(sample.id))
    return (str(sample.id), *base_cell, str(log.eval.model))


def _item_summary_table(entries: list[tuple[Any, Any, str]]) -> list[str]:
    lines = [
        "| Arm | Tone | Prefill | Model | Applicable | Trajectory | Outcome |",
        "|---|---|---:|---|:---:|---|---:|",
    ]
    for log, sample, _ in entries:
        smeta = sample.metadata or {}
        arm, tone, prefill = _sample_cell_fields(log, sample)
        sc = (sample.scores or {}).get("selective_updating_scorer")
        sc_meta = (sc.metadata if sc and sc.metadata else {})
        applicable = bool(sc_meta.get("applicable", smeta.get("applicable", True)))
        parse_err = bool(sc_meta.get("parse_error", False))
        skip_reason = sc_meta.get("skip_reason") or smeta.get("skip_reason")
        status = "parse_error" if parse_err else ("yes" if applicable else f"skip ({skip_reason})")
        t0 = smeta.get("turn0_ans") or "-"
        t1 = smeta.get("turn1_ans") or "-"
        t2 = smeta.get("turn2_ans") or "-"
        t3 = smeta.get("turn3_ans") or "-"
        traj = f"`{t0} -> {t1} -> {t2} -> {t3}`"
        outcome = (
            f"{sc.as_float():.1f}"
            if sc is not None and applicable and not parse_err
            else (sc.answer if parse_err and sc is not None else "N/A")
        )
        lines.append(
            f"| `{arm}` | `{tone}` | `{prefill}` | `{log.eval.model}` | {status} | {traj} | `{outcome}` |"
        )
    lines.append("")
    return lines


def _format_message_content(content: Any) -> tuple[str, str]:
    """Return (visible_text, reasoning_text) from Inspect string or content list."""
    if isinstance(content, str):
        return content, ""
    if isinstance(content, list):
        visible_parts: list[str] = []
        reasoning_parts: list[str] = []
        for item in content:
            ctype = getattr(item, "type", None)
            if ctype == "reasoning":
                rtxt = getattr(item, "reasoning", None) or getattr(item, "summary", "") or ""
                if rtxt:
                    reasoning_parts.append(str(rtxt))
            elif ctype == "text":
                ttxt = getattr(item, "text", "")
                if ttxt:
                    visible_parts.append(str(ttxt))
            else:
                visible_parts.append(str(item))
        return "\n".join(visible_parts), "\n".join(reasoning_parts)
    return str(content), ""


def format_sample_markdown(
    log: Any,
    sample: Any,
    log_name: str,
    include_system: bool = False,
) -> str:
    """Render a single evaluated sample trajectory into readable Markdown."""
    smeta = sample.metadata or {}
    task_args = log.eval.task_args or {}
    scores = sample.scores or {}
    main_score = scores.get("selective_updating_scorer")
    judge_score = scores.get("judge_audit_scorer")

    arm = smeta.get("arm") or task_args.get("arm", "")
    tone = smeta.get("tone") or task_args.get("tone", "")
    prefill = bool(smeta.get("prefill_wrong", task_args.get("prefill_wrong", False)))
    score_val = (
        main_score.as_float()
        if main_score is not None and smeta.get("applicable", True)
        else "N/A"
    )
    score_expl = main_score.explanation if main_score is not None else ""

    lines = [
        f"## `{sample.id}` — `{log.eval.model}` | `{arm}` / `{tone}` (prefill={prefill})",
        "",
        f"- **Log:** `{log_name}`",
        f"- **Domain:** `{smeta.get('domain', '')}` | **Gold Target:** `{sample.target}`",
        f"- **Applicable:** `{smeta.get('applicable', True)}` | **Skip Reason:** `{smeta.get('skip_reason')}`",
        f"- **Outcome:** `{score_val}` — {score_expl}",
    ]
    if judge_score is not None:
        lines.append(f"- **Judge Audit:** {judge_score.explanation}")
    lines.append("")

    turn_idx = 0
    for msg in sample.messages or []:
        role = getattr(msg, "role", "unknown")
        if role == "system" and not include_system:
            continue
        visible, reasoning = _format_message_content(getattr(msg, "content", ""))
        if role == "assistant":
            label = f"Assistant (Turn {turn_idx})"
            turn_idx += 1
        elif role == "user":
            label = f"User (Turn {turn_idx})"
        else:
            label = role.capitalize()

        lines.append(f"### {label}")
        if reasoning:
            lines.extend(
                [
                    "<details>",
                    "<summary>Model reasoning trace</summary>",
                    "",
                    "```text",
                    reasoning.strip(),
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            )
        lines.append(visible.strip() if visible.strip() else "_(empty visible completion)_")
        lines.append("")

    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def dump_transcripts(
    inputs: list[Path],
    out_md: Path | None = None,
    sample_random: int | None = None,
    seed: int = 42,
    include_system: bool = False,
    only_applicable: bool = False,
    sort_by: str = "item",
    split_by_item_dir: Path | None = None,
) -> int:
    eval_files = collect_eval_files(inputs)
    entries: list[tuple[Any, Any, str]] = []
    for path in eval_files:
        log = read_eval_log(str(path))
        for sample in log.samples or []:
            smeta = sample.metadata or {}
            if only_applicable and not smeta.get("applicable", True):
                continue
            entries.append((log, sample, path.name))

    if sample_random is not None and sample_random < len(entries):
        rng = random.Random(seed)
        entries = rng.sample(entries, sample_random)

    entries.sort(key=lambda item: entry_sort_key(item[0], item[1], sort_by=sort_by))

    if out_md is not None:
        header = [
            "# Evaluation Transcripts",
            "",
            f"Total transcripts rendered: **{len(entries)}** (sorted by `{sort_by}`)",
            "",
            "---",
            "",
        ]
        body = [
            format_sample_markdown(log, sample, log_name, include_system=include_system)
            for log, sample, log_name in entries
        ]
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(header + body), encoding="utf-8")

    if split_by_item_dir is not None:
        split_by_item_dir.mkdir(parents=True, exist_ok=True)
        grouped: dict[str, list[tuple[Any, Any, str]]] = defaultdict(list)
        for log, sample, log_name in entries:
            grouped[str(sample.id)].append((log, sample, log_name))
        for item_id, item_entries in grouped.items():
            item_entries.sort(key=lambda item: entry_sort_key(item[0], item[1], sort_by="item"))
            first_meta = item_entries[0][1].metadata or {}
            item_header = [
                f"# Item `{item_id}` Transcripts",
                "",
                f"- **Domain:** `{first_meta.get('domain', '')}` | **Gold Target:** `{item_entries[0][1].target}` | **Runs:** `{len(item_entries)}`",
                "",
                "## Cell Comparison Summary",
                "",
                *_item_summary_table(item_entries),
                "---",
                "",
            ]
            item_body = [
                format_sample_markdown(log, sample, log_name, include_system=include_system)
                for log, sample, log_name in item_entries
            ]
            (split_by_item_dir / f"{item_id}.md").write_text(
                "\n".join(item_header + item_body), encoding="utf-8"
            )

    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render .eval logs into human-readable Markdown transcripts for inspection and Role B labelling."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more .eval files or directories containing .eval logs.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output Markdown file path (defaults to outputs/transcripts.md unless --split-by-item-dir is set).",
    )
    parser.add_argument(
        "--split-by-item-dir",
        type=Path,
        default=None,
        help="Optional directory to write one sorted Markdown file per item with a comparison table.",
    )
    parser.add_argument(
        "--sort-by",
        default="item",
        choices=["item", "model"],
        help="Sort order for transcripts (default: item).",
    )
    parser.add_argument(
        "--sample-random",
        type=int,
        default=None,
        help="Optional deterministic random sample size (e.g. 100 for human labelling).",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--include-system",
        action="store_true",
        help="Include system prompt in every transcript.",
    )
    parser.add_argument(
        "--only-applicable",
        action="store_true",
        help="Skip non-applicable / skipped samples.",
    )
    args = parser.parse_args()

    out_md = args.out
    if out_md is None and args.split_by_item_dir is None:
        out_md = ROOT_DIR / "outputs" / "transcripts.md"

    count = dump_transcripts(
        inputs=args.inputs,
        out_md=out_md,
        sample_random=args.sample_random,
        seed=args.seed,
        include_system=args.include_system,
        only_applicable=args.only_applicable,
        sort_by=args.sort_by,
        split_by_item_dir=args.split_by_item_dir,
    )
    if out_md is not None:
        print(f"Wrote {count} transcript(s) to {out_md}")
    if args.split_by_item_dir is not None:
        print(f"Wrote sorted per-item transcript files to {args.split_by_item_dir}")


if __name__ == "__main__":
    main()
