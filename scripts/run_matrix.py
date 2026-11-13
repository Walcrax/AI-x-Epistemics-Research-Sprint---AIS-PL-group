import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log

from scripts.analyze_metrics import analyze_all, load_results_csv, render_markdown_report
from scripts.export_results import export_logs, format_markdown_summary
from src.data_loader import build_balanced_subset_ids, load_utf8_samples
from src.prompts import ConfidenceScale
from src.solvers import VALID_ARMS, VALID_TONES
from src.tasks import DATA_DIR, selective_updating_eval

DEFAULT_MODELS = ["ollama/qwen3.5:9b", "ollama/llama3.1:8b"]
CORE_ARMS = ["reask_control", "empty_pushback", "valid_correction"]
ORDERED_TONES = ["neutral", "hostile"]
TARGET_TOTAL_ITEMS = 100
TARGET_MCQ_ITEMS = 75
TARGET_DECISION_ITEMS = 25


@dataclass(frozen=True)
class MatrixCell:
    model: str
    arm: str
    tone: str
    prefill_wrong: bool
    dataset_name: str
    confidence_scale: ConfidenceScale

    def key(self) -> tuple[str, str, str, bool, str, str]:
        return (
            self.model,
            self.arm,
            self.tone,
            self.prefill_wrong,
            self.dataset_name,
            self.confidence_scale,
        )


def build_matrix_cells(
    models: list[str],
    arms: list[str],
    tones: list[str],
    dataset_name: str,
    include_prefill: bool,
    confidence_scale: ConfidenceScale,
) -> list[MatrixCell]:
    cells: list[MatrixCell] = []
    for model in models:
        for arm in arms:
            # reask_control uses identical wording across tones; run once under neutral.
            arm_tones = ["neutral"] if arm == "reask_control" else tones
            for tone in arm_tones:
                cells.append(
                    MatrixCell(
                        model=model,
                        arm=arm,
                        tone=tone,
                        prefill_wrong=False,
                        dataset_name=dataset_name,
                        confidence_scale=confidence_scale,
                    )
                )
            if arm == "valid_correction" and include_prefill:
                for tone in arm_tones:
                    cells.append(
                        MatrixCell(
                            model=model,
                            arm=arm,
                            tone=tone,
                            prefill_wrong=True,
                            dataset_name=dataset_name,
                            confidence_scale=confidence_scale,
                        )
                    )
    return cells


def completed_cell_keys(log_dir: Path) -> set[tuple[str, str, str, bool, str, str]]:
    done: set[tuple[str, str, str, bool, str, str]] = set()
    if not log_dir.exists():
        return done
    for eval_file in log_dir.rglob("*.eval"):
        try:
            log = read_eval_log(str(eval_file), header_only=True)
        except Exception:
            continue
        if log.status != "success":
            continue
        args = log.eval.task_args or {}
        done.add(
            (
                str(log.eval.model),
                str(args.get("arm", "")),
                str(args.get("tone", "")),
                bool(args.get("prefill_wrong", False)),
                str(args.get("dataset_name", "auto")),
                str(args.get("confidence_scale", "numeric")),
            )
        )
    return done


def _git_head_sha() -> str | None:
    try:
        res = subprocess.run(
            ["git", "-C", str(ROOT_DIR), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip() if res.returncode == 0 else None
    except OSError:
        return None


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    parser = argparse.ArgumentParser(
        description="Deterministic matrix runner for Selective Updating Under Pushback."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=DEFAULT_MODELS,
        help="Model identifiers (default: ollama/qwen3.5:9b ollama/llama3.1:8b).",
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        default=None,
        choices=sorted(VALID_ARMS),
        help="Experimental arms to run (defaults to H1-H4 core: reask_control, empty_pushback, valid_correction).",
    )
    parser.add_argument(
        "--include-stake",
        action="store_true",
        help="Include secondary H5 stake_pushback arm when using default core arms.",
    )
    parser.add_argument(
        "--tones",
        nargs="+",
        default=ORDERED_TONES,
        choices=sorted(VALID_TONES),
        help="Tone wrappers to run.",
    )
    parser.add_argument(
        "--preset",
        default="full",
        choices=["pilot", "full"],
        help="Run preset: 'pilot' caps --limit to 20 unless overridden; 'full' targets all 100 items.",
    )
    parser.add_argument(
        "--dataset",
        default="auto",
        choices=["auto", "mcqs", "decisions"],
        help="Dataset slice ('auto' routes stake_pushback to decisions only).",
    )
    parser.add_argument(
        "--include-prefill",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also run off-policy prefill_wrong=True cells for valid_correction.",
    )
    parser.add_argument(
        "--confidence-scale",
        default="numeric",
        choices=["numeric", "verbal5"],
        help="Confidence scale prompt/parser mode.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max samples per cell.")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for .eval logs and manifest.json (defaults to logs/<timestamp>).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip cells that already have a successful .eval log in --log-dir.",
    )
    parser.add_argument(
        "--export-csv",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export results.csv and summary.csv inside --log-dir after completion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned matrix cells without running models.",
    )
    args = parser.parse_args()

    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = args.log_dir or (ROOT_DIR / "logs" / run_stamp)

    arms = list(args.arms) if args.arms is not None else list(CORE_ARMS)
    if args.arms is None and args.include_stake and "stake_pushback" not in arms:
        arms.append("stake_pushback")

    effective_limit = args.limit if args.limit is not None else (20 if args.preset == "pilot" else None)

    mcq_count = len(load_utf8_samples([DATA_DIR / "hard_mcqs.jsonl"]))
    dec_count = len(load_utf8_samples([DATA_DIR / "decision_items.jsonl"]))
    total_items = mcq_count + dec_count
    print(
        f"Dataset inventory: {mcq_count} MCQs + {dec_count} decisions = {total_items} items "
        f"(preregistered target: {TARGET_TOTAL_ITEMS} = {TARGET_MCQ_ITEMS} + {TARGET_DECISION_ITEMS})"
    )

    cells = build_matrix_cells(
        models=args.models,
        arms=arms,
        tones=args.tones,
        dataset_name=args.dataset,
        include_prefill=args.include_prefill,
        confidence_scale=args.confidence_scale,
    )

    balanced_preview = build_balanced_subset_ids(
        DATA_DIR,
        dataset_name=args.dataset,
        arm="empty_pushback",
        limit=effective_limit,
        seed=args.seed,
    )
    print(f"Planned {len(cells)} cell(s) [preset={args.preset}, limit={effective_limit}] -> log_dir={log_dir}")
    if balanced_preview is not None:
        print(f"Balanced slice ({len(balanced_preview)} IDs): {balanced_preview}")
    for idx, cell in enumerate(cells, start=1):
        print(
            f"  [{idx}/{len(cells)}] model={cell.model} arm={cell.arm} "
            f"tone={cell.tone} prefill={cell.prefill_wrong} scale={cell.confidence_scale}"
        )

    if args.dry_run:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    done_keys = completed_cell_keys(log_dir) if args.skip_existing else set()

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_head_sha(),
        "dataset_counts": {"mcqs": mcq_count, "decisions": dec_count, "total": total_items},
        "config": {
            "models": args.models,
            "arms": arms,
            "tones": args.tones,
            "dataset": args.dataset,
            "preset": args.preset,
            "include_prefill": args.include_prefill,
            "include_stake": args.include_stake,
            "confidence_scale": args.confidence_scale,
            "limit": effective_limit,
            "balanced_sample_ids": balanced_preview,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "seed": args.seed,
        },
        "runs": [],
    }

    for idx, cell in enumerate(cells, start=1):
        if cell.key() in done_keys:
            print(f"[{idx}/{len(cells)}] SKIP existing: {cell}")
            continue

        print(
            f"\n[{idx}/{len(cells)}] Running model={cell.model} arm={cell.arm} "
            f"tone={cell.tone} prefill={cell.prefill_wrong}",
            flush=True,
        )
        sample_ids = build_balanced_subset_ids(
            DATA_DIR,
            dataset_name=cell.dataset_name,
            arm=cell.arm,
            limit=effective_limit,
            seed=args.seed,
        )
        task = selective_updating_eval(
            arm=cell.arm,
            tone=cell.tone,
            dataset_name=cell.dataset_name,
            prefill_wrong=cell.prefill_wrong,
            confidence_scale=cell.confidence_scale,
            use_judge=False,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            seed=args.seed,
        )
        logs = inspect_eval(
            tasks=task,
            model=cell.model,
            log_dir=str(log_dir),
            limit=None if sample_ids is not None else effective_limit,
            sample_id=sample_ids,
            ctl_server=False if sys.platform == "win32" else None,
            fail_on_error=True,
            score=True,
            tags=[cell.arm, cell.tone, f"prefill:{cell.prefill_wrong}"],
        )
        eval_log = logs[0]
        manifest["runs"].append(
            {
                "cell": asdict(cell),
                "status": eval_log.status,
                "location": eval_log.location,
            }
        )
        (log_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    if args.export_csv:
        rows, summary = export_logs(
            [log_dir],
            out_csv=log_dir / "results.csv",
            summary_csv=log_dir / "summary.csv",
        )
        print(f"\nExported {len(rows)} sample rows to {log_dir / 'results.csv'}")
        print(format_markdown_summary(summary))
        if rows:
            report = analyze_all(
                load_results_csv(log_dir / "results.csv"),
                n_boot=2000,
                seed=args.seed,
            )
            (log_dir / "metrics_report.md").write_text(
                render_markdown_report(report), encoding="utf-8"
            )
            (log_dir / "metrics_summary.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )


if __name__ == "__main__":
    main()
