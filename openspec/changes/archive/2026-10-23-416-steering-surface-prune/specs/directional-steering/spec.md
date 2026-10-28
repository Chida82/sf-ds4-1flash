# Spec Delta

## REMOVED Requirements

### Requirement: Bounded fold activation capture
**Reason**: The capture switch `DS4_V41_DUMP_STEER_INPUT` is removed. It existed to
extract a direction from the model's own activations; that extraction was done, the
resulting directions were measured and did not win, and no live path reads the switch.
**Migration**: None. The directions it produced are kept under `com-steering/`, and the
`.f32` plus sidecar format for a derived direction is unchanged.

### Requirement: Activation-contrast extraction records provenance
**Reason**: The extractor (`eval/extract_floor_direction.py`) is removed with the rest of
the one-off harness, so there is no code left to impose a provenance contract on.
**Migration**: None. Provenance of the vectors still in the tree is in their `.json`
sidecars, and a steering profile records the SHA-256 of each matrix it carries.
