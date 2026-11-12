# system-one-bench Specification

## Purpose
Measure System One decisions (accuracy, calibration, latency) with `sysone-bench/`, so later changes are accepted or dropped on numbers.

## Requirements

### Requirement: Decisions are measured for accuracy, calibration and latency
`sysone-bench/run.py` SHALL send a JSONL set of single-question decisions to
the server and report, per question type and overall: accuracy with a 95%
bootstrap interval, NLL, Brier score, ECE on 10 bins, mean and minimum legal
mass, tokens, and latency p50 and p95.

#### Scenario: Italian fixtures
- **WHEN** `run.py --mode sysone --items sysone-bench/fixtures-it.jsonl` runs against the server
- **THEN** it prints one row per type and one overall, and a line ready for `record.md`

### Requirement: The model's own generation is the reference
The bench SHALL run the same items through chat completions with thinking off
(`gen`) and with reasoning effort high (`think`), and SHALL report the
accuracy difference between `think` and `sysone` on the same items.

#### Scenario: The gap is stated
- **WHEN** the baseline finishes
- **THEN** `sysone-bench/record.md` states the System One gap in points on at least 100 items

### Requirement: Position bias is measured
`run.py --rotate K` SHALL rotate the option order and map answers back, and
the baseline SHALL report the share of items whose top option changes.

#### Scenario: Rotation
- **WHEN** the same items run with `--rotate 0` and `--rotate 1`
- **THEN** the record states the flip rate

### Requirement: Temperatures are fitted offline and bound to the model
`fit.py` SHALL fit one temperature per question type on half of the items and
report NLL and ECE on the other half. The server SHALL apply a calibration
file given with `--sysone-calibration` and SHALL refuse to start when the
file's model size, model mtime, template version or layout does not match.

#### Scenario: Calibration lowers ECE
- **WHEN** the fitted file is applied and the held-out half is run again
- **THEN** its ECE is not higher than raw, and both figures are in the record

#### Scenario: Wrong model
- **WHEN** the file's `model_bytes` differs from the opened GGUF
- **THEN** the server exits at startup with a message naming `model_bytes`

### Requirement: The bench adds nothing to the machine
The scripts SHALL use only the Python standard library, and downloaded sets
SHALL stay in the Hugging Face cache or the `--work` directory.

#### Scenario: Clean repository
- **WHEN** a full baseline has run
- **THEN** `git status` shows only files under `sysone-bench/` that this change lists

### Requirement: Intervals respect that decisions on one state are correlated
Bootstrap intervals SHALL resample states, with all decisions of a state
moving together.

#### Scenario: Five decisions per state
- **WHEN** a set has five decisions per state
- **THEN** the reported interval comes from resampling states

### Requirement: Abstention and schedule stability have recorded baselines
The bench SHALL report how well four signals available without engine work
detect a state that lacks the answer, and SHALL measure how much the top-two
option logit gap moves between two prefill schedules. Answers whose gap is
under that measured 95th percentile SHALL be marked unstable in the `sf`
object.

#### Scenario: Abstention baseline
- **WHEN** the twin states have run
- **THEN** the record holds four AUROC figures

#### Scenario: Unstable flag
- **WHEN** a decision's top-two option logits differ by less than the recorded `delta95`
- **THEN** its `sf` entry carries `"unstable": true`
