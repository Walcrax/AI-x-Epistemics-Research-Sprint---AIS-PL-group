import argparse
import random
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai.log import read_eval_log

from scripts.export_results import collect_eval_files


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
    out_md: Path,
    sample_random: int | None = None,
    seed: int = 42,
    include_system: bool = False,
    only_applicable: bool = False,
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

    header = [
        "# Evaluation Transcripts",
        "",
        f"Total transcripts rendered: **{len(entries)}**",
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
        default=ROOT_DIR / "outputs" / "transcripts.md",
        help="Output Markdown file path (default: outputs/transcripts.md).",
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

    count = dump_transcripts(
        inputs=args.inputs,
        out_md=args.out,
        sample_random=args.sample_random,
        seed=args.seed,
        include_system=args.include_system,
        only_applicable=args.only_applicable,
    )
    print(f"Wrote {count} transcript(s) to {args.out}")


if __name__ == "__main__":
    main()
