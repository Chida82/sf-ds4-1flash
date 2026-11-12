# Spec Delta

## ADDED Requirements

### Requirement: Suffix variants are measured on the bench
The change SHALL compare the version-1 suffix with variants that tokenize the
suffix as one string and drop fixed text, reporting accuracy, NLL, legal mass
and suffix tokens saved on the Italian fixtures and on the 500-decision
typed-decisions subset.

#### Scenario: Recorded table
- **WHEN** the runs finish
- **THEN** `sysone-bench/record.md` holds one row per candidate and the gate outcome

### Requirement: A shorter template is adopted only if it holds quality
Template version 2 SHALL be the candidate that saves the most suffix tokens
among those that, against version 1 on the same items, lose at most 0.010 of
accuracy and 0.02 nats of NLL on the typed-decisions subset, miss at most one
more Italian fixture, keep mean legal mass at least 0.99, save at least 3
tokens per question, and whose answer flip rate under option rotation is at
most 5 points above version 1's; otherwise version 1 SHALL stay the only
template.

#### Scenario: No acceptable candidate
- **WHEN** no candidate passes every threshold
- **THEN** no version 2 exists, the code edits are reverted and the record says which threshold each candidate failed

#### Scenario: A winner
- **WHEN** a candidate passes
- **THEN** it is template version 2, the server default, and the other candidates are deleted from the code

### Requirement: Template versions stay selectable
When a version 2 exists, the server SHALL select the template with
`--sysone-template N` (default 2), SHALL report the one in use as
`sf.template_version`, and SHALL refuse a calibration file bound to another
version.

#### Scenario: Calibration mismatch
- **WHEN** the server starts with template 2 and a calibration bound to template 1
- **THEN** startup fails naming `template_version`

#### Scenario: Version 1 on request
- **WHEN** the server starts with `--sysone-template 1`
- **THEN** a decision's option logits are bitwise equal to those of the build before this change
