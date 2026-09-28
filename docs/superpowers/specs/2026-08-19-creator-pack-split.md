# Creator pack split (main / trial / growth) — Design

**Date:** 2026-08-19  
**Status:** Shipped.  
**Product name:** VaryForge

## Why

One model is not one Drive folder. The operator posts the same source through
Repurpose to **main**, **trial Reels**, and **growth** (2nd/3rd) accounts. Those
are different Instagram accounts. Instagram duplicate-detects if the same file
(or the whole 20-pack) lands in more than one Repurpose queue.

Caption folders stay by **niche** (Gym vs cooking). This feature is by
**account role**.

## What already exists (use this until we build)

| Piece | How to use it today |
|---|---|
| Drive destinations | One saved folder per Repurpose queue: `Maya / main`, `Maya / trial`, `Maya / growth` |
| One inbox | Raw clips for that model. Do not reuse the output folder as inbox. |
| Caption folder | One niche bank (e.g. Gym) for all three outputs |
| Gallery Send to Drive | Select a slice → Custom or folder → send to **one** destination |
| Workflow | One inbox → **one** output. Three workflows on the same inbox would re-render 3× — wrong |

Manual gym-test path: generate once → send v01–v07 to main, v08–v14 to trial,
v15–v20 to growth.

## Goal (when we build)

Generate **once**. Partition that pack across N destinations so each account
gets **different** files. Same caption folder may name all of them.

Default split for 20 variants × 3 destinations: contiguous slices, remainder
on the first buckets.

| Destination | Variants |
|---|---|
| main | 1–7 |
| trial | 8–14 |
| growth | 15–20 |

20 × 2 → 1–10 and 11–20. Empty destination list is a no-op.

## Non-goals

- Repurpose.io API or Instagram posting
- A creator CRM / model directory (destinations + names are enough)
- Three workflows that re-render the same inbox clip
- Sharing one Drive folder across main + trial + growth
- Phase 12 platform labeling / a detector

## Success

Operator picks destinations **main / trial / growth**, hits split-send (or a
workflow fan-out that copies already-rendered files). Each Repurpose watcher
sees only its slice. No file is uploaded twice.
