# Multiple-choice items (70): harness check

**Role in v3.** These 70 items are a check that our harness behaves, not part of the main result. They run under **neutral empty pressure only** (the `bare` level in `pushback/`, plus the re-ask control). We then compare the capitulation rate informally with the published rates from SycoBench-600 and TemperBench. The main result runs on the generated decision items, which are separate. There is no replication claim.

What changed from v2:

- No valid-correction arm, so the one-sentence `reasoning` field is not needed. It is still filled for 26 items and empty for 44; nothing reads it now.
- The 40–60% turn-0 difficulty target is gone. Empty pressure runs only on items the model got right, so higher turn-0 accuracy leaves more material.
- No tone variants and no prefill.
- `asserted_wrong` is the option the user pushes (`render_pushback.py` falls back to it when an item has no `pushed` field).

**Status: provisional.** Not yet run on our four models.

## Files

| File | What it is | Commit to the public repo? |
|---|---|---|
| `mcq_70.json` | The 70 items, full text | **No** (contains gated GPQA items) |
| `mcq_70_public.json` | Same, with GPQA question text removed (record IDs kept) | Yes |
| `mcq_reserve.json` | 26 spare items for swaps | No (contains GPQA) |
| `mcq_70_overview.csv` | One row per item, for quick review | Yes |
| `build_items.py` | Rebuilds all files from the source repos (edit the paths at the top) | Yes |

## Format

The fields match SycoBench-600's `data/questions.json`, so the forked Inspect task can load the file directly: `id`, `domain`, `difficulty`, `question`, `options` (four, `"A) ..."`), `correct`, `reasoning`.

Extra fields:

- `source`: which dataset the item came from.
- `asserted_wrong`: the wrong letter the user asserts under empty pressure.
- `reasoning`: unused in v3 (see above).
- `needs_key_check`: two people must confirm the key before the item is used. A wrong key would count a correct model as wrong at turn 0 and drop it.
- `pilot`: true for 20 items, proportional by source. v3's Saturday pilot runs on generated decision items, so this flag only matters if we also smoke-test the harness check.
- `stratum`, `option_seed`, `src_detail`, `prior_panel_acc`.

## Sources

| Source | Items | License | How chosen |
|---|---|---|---|
| MMLU-Pro | 30 | MIT | Used the per-item results published in the MMLU-Pro repo. 8 items Gemini 3.1 Pro got wrong (`FW`), 10 it got right that eight 2024 models mostly missed (`LW`), 12 the 2024 models split on (`MIX`). Hand-vetted. |
| GPQA Diamond | 20 | CC BY 4.0, gated | Seeded random draw. `reasoning` is the question writer's explanation. |
| SuperGPQA | 14 | ODC-BY | Hard tier, no calculation, hand-picked. |
| SycoBench-600 | 6 | CC BY 4.0 | Hard tier, one per domain. The only items directly comparable with SycoBench numbers. |

All items have four options, shuffled with seed `20261113`. Ten-option items were cut to the key plus three distractors. For MMLU-Pro, the distractors and the asserted wrong answer are the options other models picked most often. For the other sources they are seeded random choices.

## Comparing with SycoBench-600 and TemperBench

- SycoBench-600 reports rates on its own items. Only the 6 SycoBench anchors are like for like; on the other 64 the comparison is about the same order of magnitude, not the same number. If a closer match is wanted, swap more SycoBench items in from `sycobench-600/data/questions.json` (the build script already pulls them).
- TemperBench reports caving under identical false pushback of about 4% (Claude Haiku 5.5) and 15% (GPT-6 Luna). Neither is one of our models, so this is a range check.
- Report the re-ask switch rate next to the empty-pressure rate, so baseline instability is visible.

## Before the run

1. Two people check the key on every `needs_key_check` item, and on any item a model gets wrong at turn 0.
2. Never commit GPQA question text, answers or transcripts to the public repo.
