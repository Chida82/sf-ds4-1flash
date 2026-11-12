# Spec Delta

## ADDED Requirements

### Requirement: Suffix variants are measured on the bench
The template probe SHALL compare the version-1 suffix with variants that
tokenize the suffix as one string and drop fixed text, reporting accuracy,
NLL, legal mass and mean suffix tokens on the `820` sets.

#### Scenario: Recorded table
- **WHEN** the runs finish
- **THEN** `sysone-bench/record.md` holds one row per candidate and the gate outcome

### Requirement: A shorter template is adopted only if it holds quality
Template version 2 SHALL be the candidate with the fewest suffix tokens among
those within 1 accuracy point and 0.02 nats of version 1 and with mean legal
mass at least 0.99; otherwise version 1 SHALL stay the only template.

#### Scenario: No acceptable candidate
- **WHEN** every candidate loses more than 1 accuracy point
- **THEN** no version 2 exists and the record says why

### Requirement: Template versions stay selectable
The server SHALL select the template with `--sysone-template N` and SHALL
refuse a calibration file bound to another version.

#### Scenario: Calibration mismatch
- **WHEN** the server starts with template 2 and a calibration bound to template 1
- **THEN** startup fails naming `template_version`
