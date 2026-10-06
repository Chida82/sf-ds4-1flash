# Spec Delta

## Purpose

Lets decode read the experts that the next layer is predicted to select before that selection is known, without changing output or the expert cache budget.

## ADDED Requirements

### Requirement: Prefetch never changes output
Decode with route-prediction prefetch SHALL produce bit-identical logits, tokens and session state compared with decode without it.

#### Scenario: Same prompt with and without prefetch
- **WHEN** the same prompt is decoded with prefetch on and off
- **THEN** logits, tokens and KV state match exactly

### Requirement: Bounded staging and promotion on selection
Prefetched experts SHALL be held in a bounded staging area outside the configured cache budget. A prefetched expert SHALL enter the expert cache only when the next layer actually selects it. An unselected one SHALL be discarded without evicting any cached expert.

#### Scenario: Wrong prediction
- **WHEN** a prefetched expert is not selected
- **THEN** it is discarded, and the cache contents equal those of a run without that prefetch

#### Scenario: Right prediction
- **WHEN** a prefetched expert is selected and its read has completed
- **THEN** it is used without a second disk read and enters the cache like a loaded miss

### Requirement: Safe settlement
No prefetched expert SHALL be used before its read completes. A failed prefetch read SHALL fall back to the ordinary miss path, and no reader SHALL still be writing to a staging slot when the slot is reused or freed.

#### Scenario: Prefetch read fails
- **WHEN** a prefetch read returns an error
- **THEN** the expert is read as an ordinary miss and the staging slot is released after its reader has settled
