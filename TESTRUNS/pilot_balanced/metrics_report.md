# Role C Epistemic Metrics Report

## H1: Selectivity (`WUR - UCR` and Signal-Detection `d'`)

| Scope | UCR (N) | WUR Nat (N) | Sel Nat | d' Nat | WUR Prefill (N) | Sel Prefill | d' Prefill | Reask Right |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ollama/llama3.1:8b | 1.000 (3) | N/A (0) | N/A | N/A | 1.000 (8) | 0.000 | 0.44 | 0.500 (2) |
| ollama/qwen3.5:9b | 0.000 (3) | N/A (0) | N/A | N/A | 1.000 (8) | 1.000 | 2.74 | 0.000 (4) |
| POOLED | 0.500 (6) | N/A (0) | N/A | N/A | 1.000 (16) | 0.500 | 1.89 | 0.167 (6) |

## H2 & H3: Tone Contrasts (`hostile - neutral`, Item-Clustered Bootstrap 95% CI)

| Scope | Contrast | Delta | 95% CI | p (raw) | p (Holm) |
|---|---|---:|---:|---:|---:|
| ollama/llama3.1:8b | H2_UCR_tone_delta | 0.000 | [0.000, 0.000] | 1.0000 | 1.0000 |
| ollama/llama3.1:8b | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| ollama/llama3.1:8b | H3_WUR_prefill_tone_delta | 0.000 | [0.000, 0.000] | 1.0000 | 1.0000 |
| ollama/qwen3.5:9b | H2_UCR_tone_delta | 0.000 | [0.000, 0.000] | 1.0000 | 1.0000 |
| ollama/qwen3.5:9b | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| ollama/qwen3.5:9b | H3_WUR_prefill_tone_delta | 0.000 | [0.000, 0.000] | 1.0000 | 1.0000 |
| POOLED | H2_UCR_tone_delta | 0.000 | [-0.500, 0.500] | 1.0000 | 1.0000 |
| POOLED | H3_WUR_nat_tone_delta | N/A | N/A | N/A | N/A |
| POOLED | H3_WUR_prefill_tone_delta | 0.000 | [0.000, 0.000] | 1.0000 | 1.0000 |

## H4: Turn-0 Confidence Calibration

| Scope | AUROC (Hold vs Empty) | N Hold | AUROC (Update vs Valid Nat) | N Valid Nat |
|---|---:|---:|---:|---:|
| ollama/llama3.1:8b | N/A | 3 | N/A | 0 |
| ollama/qwen3.5:9b | N/A | 3 | N/A | 0 |
| POOLED | 1.000 | 6 | N/A | 0 |
