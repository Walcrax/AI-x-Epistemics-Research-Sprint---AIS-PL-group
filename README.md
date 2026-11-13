# AI x Epistemics Research Sprint - AIS PL group

**Track 1 — Model Epistemics & Decision-Making Evals (`inspect_ai`)**

Multi-turn evaluation pipeline measuring **Selective Updating Under Pushback**: whether LLMs accept valid corrections without caving to empty social pressure or irrelevant personal stakes across `neutral` and `hostile` user tones.

## How It Works

Each item runs a deterministic multi-turn conversation expecting `FINAL: <LETTER>` and `CONFIDENCE: <0-100 | VERY_LOW..VERY_HIGH>` at the end of every assistant turn (`src/solvers.py`):

1. **Turn 0 (Baseline / Prefill):** The model answers from scratch (or starts from an off-policy wrong assistant reply when `prefill_wrong=True`, leaving `turn0_conf=None` to guarantee sample size on items models normally solve).
2. **Gating & Pushback (Turns 1–2):**
   - `reask_control` (`neutral`): Baseline stability check asking the model to re-verify.
   - `empty_pushback` (`neutral`, `hostile`, gated on `turn0_correct=True`): Content-matched unsupported disagreement measuring **Unwarranted Capitulation Rate (`UCR`)**.
   - `valid_correction` (`neutral`, `hostile`, natural errors + `prefill_wrong=True`): Content-matched `valid_hint` measuring **Warranted Update Rate (`WUR`)**.
   - *(Opt-in H5 via `--include-stake`)* `stake_pushback` on decision items only: personal commitment pressure, optionally audited post-hoc by a cross-family judge (`RATIONALISED` vs. `EXPLICIT_DEFERENCE`).
3. **Deterministic Scoring & Analysis (`src/scorers.py`, `scripts/analyze_metrics.py`):** Turn-0 and Turn-1 `max_tokens` truncations fail fast as explicit parse errors instead of counting as holds. Exports flat CSVs, signal-detection selectivity (`WUR - UCR`, `d'`), item-clustered bootstrap CIs with Holm-Bonferroni adjustment, Turn-0 confidence `AUROC`, and readable Markdown transcripts (`scripts/dump_transcripts.py`).

## Repository Structure

- `data/hard_mcqs.jsonl` — **75 MCQs** (1 seed reflection item + 74 `hard` items imported from MIT-licensed [debu-sinha/sycobench-600](https://github.com/debu-sinha/sycobench-600) via `scripts/import_sycobench.py`).
- `data/decision_items.jsonl` — **8 computable decision items** so far (expected value, base rates, dominated options, cost-effectiveness; preregistered target: 25).
- `src/` — Dataset validation & balanced slicing (`data_loader.py`), prompts/tone wrappers (`prompts.py`), multi-turn pushback solver (`solvers.py`), deterministic + judge scorers (`scorers.py`), and `inspect_ai` task entrypoint (`tasks.py`).
- `scripts/` — `run_matrix.py`, `export_results.py`, `analyze_metrics.py`, `dump_transcripts.py`, `run_judge.py`, `import_sycobench.py`.
- `tests/test_pipeline.py` — Offline `unittest` suite using `inspect_ai`'s `mockllm/model`.
- `TESTRUNS/pilot_balanced/` — Sorted transcripts, CSVs, and Role C metrics from the 56-run balanced local pilot.
- `PREREGISTRATION.md` — Hypotheses (H1–H5), 100-item design, and statistical rules.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # optional: add frontier API keys
```

For local Ollama thinking models (e.g., `ollama/qwen3.5:9b`), keep `--max-tokens >= 4096` (or `8192` if pushback reasoning loops) so CoT traces do not exhaust the budget before `FINAL:`.

```powershell
# 1. Verify offline unit tests (13 tests)
python -m unittest discover -s tests -v

# 2. Preview the 7-cell H1-H4 matrix (14 cells across default local models)
python scripts/run_matrix.py --dry-run

# 3. Run a balanced pilot (splits MCQs + decisions when --limit is set)
python scripts/run_matrix.py --preset pilot --limit 4 --log-dir logs/pilot_balanced

# 4. Run full benchmark (add --include-stake for optional H5; --confidence-scale verbal5 if numeric conf clusters >=90)
python scripts/run_matrix.py --preset full --log-dir logs/full_run

# 5. View interactive logs or export readable transcripts
inspect view start --log-dir logs/pilot_balanced --port 7575
python scripts/dump_transcripts.py logs/pilot_balanced --out outputs/transcripts.md
```

## Provenance

- `data/hard_mcqs.jsonl` includes 74 items from [debu-sinha/sycobench-600](https://github.com/debu-sinha/sycobench-600) (`data/questions.json`, MIT License, Copyright (c) 2026 Debu Sinha).
- Tone-wrapper isolation (content-matched declarative framing without directive `"switch"` commands) follows TemperBench design recommendations.
