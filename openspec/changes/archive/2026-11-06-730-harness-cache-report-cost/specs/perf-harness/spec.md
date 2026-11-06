# Spec Delta

## ADDED Requirements

### Requirement: Cache report off for B
The harness SHALL offer an option that runs B's benches without the
per-frontier cache report. With it, B has no cache counters, so the harness
SHALL treat the invocation as a declared cache-policy change and SHALL print
that B's hit rates are unavailable.

#### Scenario: A/A cost of the report
- **WHEN** the harness runs with the same tree as A and B and the option set
- **THEN** A's runs carry `--cache-stats`, B's do not, every pair is kept, and the summary gives the first-token gain of B over A with its interval
