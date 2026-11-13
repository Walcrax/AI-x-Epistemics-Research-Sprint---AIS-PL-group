import sys
from pathlib import Path
from typing import Literal

# Ensure repo root is on sys.path whether invoked via `inspect eval src/tasks.py` or imported as `src.tasks`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from inspect_ai import Task, task
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import system_message

from src.data_loader import build_dataset
from src.prompts import SYSTEM_PROMPTS, ConfidenceScale
from src.scorers import selective_updating_scorer
from src.solvers import VALID_CONFIDENCE_SCALES, multi_turn_pushback

DATA_DIR = ROOT_DIR / "data"
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


@task
def selective_updating_eval(
    arm: str = "empty_pressure",
    tone: str = "neutral",
    dataset_name: str = "auto",
    prefill_wrong: bool = False,
    confidence_scale: ConfidenceScale = "verbal5",
    use_judge: bool = False,
    judge_model: str | None = None,
    allow_same_family_judge: bool = False,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    reasoning_effort: ReasoningEffort | None = "low",
    ollama_think: bool = False,
    seed: int | None = 42,
) -> Task:
    if confidence_scale not in VALID_CONFIDENCE_SCALES:
        raise ValueError(
            f"Unknown confidence_scale '{confidence_scale}'. Expected one of {sorted(VALID_CONFIDENCE_SCALES)}"
        )
    if use_judge and not judge_model and not allow_same_family_judge:
        raise ValueError(
            "judge_model is required when use_judge=True (self-judging is disabled)."
        )

    dataset = build_dataset(DATA_DIR, dataset_name=dataset_name, arm=arm)

    return Task(
        dataset=dataset,
        solver=[
            system_message(SYSTEM_PROMPTS[confidence_scale]),
            multi_turn_pushback(
                arm=arm,
                tone=tone,
                prefill_wrong=prefill_wrong,
                confidence_scale=confidence_scale,
                ollama_think=ollama_think,
            ),
        ],
        scorer=selective_updating_scorer(
            use_judge_on_stake_flip=use_judge,
            judge_model=judge_model,
            allow_same_family_judge=allow_same_family_judge,
        ),
        config=GenerateConfig(
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            seed=seed,
        ),
    )
