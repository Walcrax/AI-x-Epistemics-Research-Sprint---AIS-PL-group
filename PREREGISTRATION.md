# Pre-Registration: Selective Updating Under Pushback

**Sprint:** AI x Epistemics Research Sprint (2026-11-13 to 2026-11-15) — Track 1: Model Epistemics & Decision-Making Evals  
**Status:** Draft (commit this file with final item files and target models before running the full matrix)

## 1. Research Question
When a user pushes back across multiple turns, does an LLM update selectively (accept valid corrections, resist empty pressure), and is that selectivity moved by user tone (`neutral` vs. `hostile`) or predicted by the model's Turn-0 stated confidence?

## 2. Hypotheses
- **H1 (Replication — Selectivity):** Every model accepts valid corrections (`WUR`) more often than it yields to empty pressure (`UCR`), and selectivity (`WUR - UCR`, signal-detection `d'`) differs by model.
- **H2 (Replication/Extension — Tone on Empty Pushback):** Holding pushback content fixed, tone (`hostile` vs. `neutral`) does not substantially change unwarranted capitulation (`UCR`).
- **H3 (Primary Novelty — Tone × Valid Correction):** Tone (`hostile` vs. `neutral`) shifts acceptance of valid corrections (`WUR`), and therefore selectivity (`WUR - UCR`). Two-sided test; a tight null interval counts as a finding.
- **H4 (Confidence Calibration):** Stated Turn-0 confidence predicts selective updating: higher Turn-0 confidence predicts holding firm under empty pushback (`AUROC > 0.5`), without blocking acceptance of valid corrections.
- **H5 (Optional Secondary — Value Leakage & Rationalisation):** Only run if enabled via `--include-stake` after H1–H4 complete. On computable decision items, an irrelevant personal stake shifts recommendations (`Leak Rate` net of `empty_pushback` on decision items), and switches often cite merit grounds rather than the stake (`Rationalisation Rate`).

## 3. Experimental Design (100-Item Cut)
- **Dataset (100 items total):**
  - `data/hard_mcqs.jsonl`: **75 MCQs** (seed reflection item + 74 stratified `hard` items imported from MIT-licensed `debu-sinha/sycobench-600`).
  - `data/decision_items.jsonl`: **25 computable decision items** (expected value, base rates, dominated options, stated cost-effectiveness).
- **Core Matrix (7 deterministic cells per model for H1–H4):**
  - `reask_control` (`neutral`, 1 cell): neutral verification re-ask measuring baseline `temperature=0` instability, stratified by `turn0_correct`.
  - `empty_pushback` (`neutral`, `hostile`, 2 cells): content-matched unsupported disagreement, gated on `turn0_correct == True`.
  - `valid_correction` natural (`neutral`, `hostile`, 2 cells): content-matched `valid_hint`, gated on `turn0_correct == False`.
  - `valid_correction` off-policy prefill (`neutral`, `hostile`, 2 cells, `prefill_wrong=True`): synthetic wrong Turn-0 prefill (`turn0_conf=None`), **reported separately from natural Turn-0 errors**.
  - *(Optional H5)* `stake_pushback` (`neutral`, `hostile`, 2 cells, decision items only, `--include-stake`).
- **Turns & Decoding:** Turn 0 baseline + Turn 1 pushback + Turn 2 persistence escalation; `temperature=0.0`, `seed=42`, `max_tokens=4096`.

## 4. Statistical Power, Exclusions & Stopping Rules
- **Power (100-item scale):** 100 items per model detects ~15–20 percentage point per-model differences; smaller tone/selectivity interactions (5–10 pts) are tested pooled across models (~400 item-model observations per cell across 4 models) using item-clustered bootstrap (2,000 resamples) and Holm-Bonferroni correction across H2/H3 contrasts.
- **Failure handling:** Turn-0 and Turn-1 `max_tokens` truncations or format failures fail fast (`parse_error=True`), and Turn-2 failures are reported explicitly via `parse_error_rate`—never counted as holds or natural errors.
- **Confidence clustering check:** Check Turn-0 confidence distribution in the 20-item pilot (`--preset pilot`); if `>=80%` of observations fall in `[90, 100]`, switch the full run to `-T confidence_scale=verbal5` (or `--confidence-scale verbal5`).
- **Judge cut:** Descriptive `quiet_retreat` and `hollow_apology` labels are cut; if optional H5 (`--include-stake`) is run, cross-family `judge_audit_scorer` labels `RATIONALISED` vs. `EXPLICIT_DEFERENCE` post-hoc via `scripts/run_judge.py` with human validation on up to `min(50, N_flips)` transcripts.
