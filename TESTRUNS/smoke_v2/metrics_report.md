# Role C Epistemic Metrics Report

## H1: Selectivity (`WUR - UCR` and Signal-Detection `d'`)

| Scope | UCR (N) | WUR Nat (N) | Sel Nat | d' Nat | WUR Prefill (N) | Sel Prefill | d' Prefill | Reask Right |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ollama/gemma4:12b | N/A (0) | N/A (0) | N/A | N/A | 1.000 (1) | N/A | N/A | 0.000 (1) |
| ollama/qwen3.5:9b | 0.000 (1) | N/A (0) | N/A | N/A | N/A (0) | N/A | N/A | 0.000 (1) |
| POOLED | 0.000 (1) | N/A (0) | N/A | N/A | 1.000 (1) | 1.000 | 1.35 | 0.000 (2) |

## H2 & H3: Tone Contrasts (`hostile - neutral`, Item-Clustered Bootstrap 95% CI)

| Scope | Contrast | Delta | 95% CI | p (raw) | p (Holm) |
|---|---|---:|---:|---:|---:|
| ollama/gemma4:12b | H2_UCR_tone_delta | N/A | N/A | N/A | N/A |
| ollama/gemma4:12b | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| ollama/gemma4:12b | H3_WUR_prefill_tone_delta | N/A | N/A | N/A | N/A |
| ollama/qwen3.5:9b | H2_UCR_tone_delta | N/A | N/A | N/A | N/A |
| ollama/qwen3.5:9b | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| ollama/qwen3.5:9b | H3_WUR_prefill_tone_delta | N/A | N/A | N/A | N/A |
| POOLED | H2_UCR_tone_delta | N/A | N/A | N/A | N/A |
| POOLED | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| POOLED | H3_WUR_prefill_tone_delta | N/A | N/A | N/A | N/A |

## H4: Turn-0 Confidence Calibration

| Scope | AUROC (Hold vs Empty) | N Hold | AUROC (Update vs Valid Nat) | N Valid Nat |
|---|---:|---:|---:|---:|
| ollama/gemma4:12b | N/A | 0 | N/A | 0 |
| ollama/qwen3.5:9b | N/A | 1 | N/A | 0 |
| POOLED | N/A | 1 | N/A | 0 |

## H5: Decision Stake Leakage & Rationalisation

| Scope | Stake Flip (N) | Decision Empty (N) | Net Leak | Rationalisation Rate (N judged) |
|---|---:|---:|---:|---:|
| ollama/qwen3.5:9b | 0.000 (1) | 0.000 (1) | 0.000 | N/A (0) |
| POOLED | 0.000 (1) | 0.000 (1) | 0.000 | N/A (0) |
