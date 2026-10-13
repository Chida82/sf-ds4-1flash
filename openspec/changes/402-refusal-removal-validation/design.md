# Design

## Context

See proposal.md for the two delivery milestones. Existing `eval/` modules provide loaders, argument builders, parsing functions and report formatting. Their offline checks were reported green, and live fetches found AdvBench 520, HarmBench 400, StrongREJECT 313 and XSTest-safe 250; the composed harmful union was 1201. These counts describe those fetched revisions, not eternal dataset sizes.

Current gaps established by source review:
- `run.py` stops after a message even when the model is present.
- `build_cli`/`gen` omit residual scale and supply no filename after `--dump-logprobs`.
- The A/B comparison strips arbitrary arguments following the steering block, accepting a changed temperature in `extra`.
- The image payload uses a local-path format the OpenAI server parser does not consume.
- The logprob CLI independently generates greedy tokens; it is not teacher forcing.
- KL independently renormalizes different top-k supports, floors missing tokens and returns zero for empty sequences.
- Capability helpers do not establish a steered run, and their output fixtures are not the real eval output contract.

No output-changing inference optimization is part of this change. A minimal test-driver diagnostic may exercise existing session APIs where the current CLI lacks a measurement interface.

## Goals / Non-Goals

**Goals:** a runner another agent can reproduce and consume through KPIs, strict failures, explicit evidence audit, transparent uncertainty and complete coverage of the requested axes. Qualify this same contract for reuse by later steering proposals once it works.

**Non-Goals:** derive directions, tune candidates inside the held-out evaluation, blend incompatible published protocols, treat a classifier failure as a model finding, force every candidate to change its first token, or bypass an agent/provider's policies. Execution is a deterministic program, not another autonomous agent interpreting and rewriting the test.

## Decisions

### D1. M0 and M1 have different completion criteria

**M0 (groups 1-4 in tasks.md):** an automatic first pass runs the available numerical/no-op checks and a pinned benign suite, saves raw records and returns deterministic task/format KPIs without requiring an LLM judge. A configured text-evaluation suite also connects the calibrated three-way grader and keyword diagnostic when that scope is explicitly requested. First-pass execution is useful before every M0 component is finished, but its report names exactly which checks ran. Synthetic controls allow smoke tests without gated vectors; model-less checks remain independently runnable when the GGUF is absent.

**M1 (groups 5-7 plus integration):** all A-E axes, forced-prefix distribution evidence, capability and image/thinking repeats are connected and run. Missing datasets, graders or authorized evaluation resources keep their verification open; M0 is not reported as full acceptance.

The planned runner interface is `--mode screen|full`, `--suite`, `--steer`, `--residual`, `--limit`, `--judge`, `--report kpi|audit`, and an output/run directory. Default to the pinned `benign-smoke` profile, completed-response `full` mode for that profile, and `kpi` presentation. Here `full` means complete the selected suite, not automatically select the full A-E benchmark. `screen` restricts measurement to the declared diagnostic. A separately selected benchmark profile declares its own required axes and explicit launch scope; neither a promising KPI nor a failure automatically selects it.

An `--input-run DIR` path renders stored results with either report presentation and never launches a generator or judge. Conflicting generation options are rejected on that path. An incomplete stored run remains incomplete; rendering cannot invent missing scores. The audit view can therefore be requested explicitly after an operator-run batch without rerunning it. Preserve named protocol selection only for implemented profiles; unknown/incompatible settings fail before model work. `make eval-refusal` must call this runner, not a placeholder. Document actual commands when implemented.

### D2. One experiment identity, explicitly different arms

Use `common.build_cli` and `generate.gen` as the V4.1 adapter, adding residual arguments without implicitly activating FFN. Construct invariant options separately from the small allowlisted steering delta. Compare parsed/structured configurations, not an arbitrary tail of argv. Reject duplicate conflicting options and changes to temperature, template, system prompt, context, token budget, model, thinking or image input between paired arms.

Greedy temp 0 is the primary protocol. A stochastic protocol, if requested later, is separately named and uses matched seeds; it is not mixed into this report. Treat command failure, timeout, malformed/empty output and unexpected truncation as explicit statuses. Save return code and stderr in the local evidence before aborting a requested validation; the default terminal/report path receives only structured error codes, counts and opaque evidence references. Never score a missing response as refusal, compliance or zero KL, and never forward raw child output merely because the run failed.

`--dump-logprobs` takes an output filename. Parse the produced JSON with token IDs, not just rendered token strings. Normal CLI generation and diagnostic dumps have different output contracts; use fixtures copied from their real formats. Freeze the judge separately from the generated arms, clear inherited steering switches, and serialize its model runs as well.

### D3. Small run manifest and evidence, not a new platform

Use the existing JSON helpers and a fresh per-run output directory. Separate local evidence from the agent-facing summary: keep the manifest, raw records and judge output locally; emit `summary.json` and its KPI-only Markdown view by default. The summary links to evidence by generated run/example IDs without embedding prompt-bearing argv or copying raw records. Record in the local manifest/evidence:
- source commit plus dirty-diff identity, binary identity, resolved model/quantization/revision information;
- source and application hook, intervention revision, effective scale, direction hash, disable state and cache policy;
- resolved arguments, relevant environment switches, thinking/template settings and token budget;
- dataset source/revision or content hash, stable prompt IDs, category, split/selector and composition hash;
- scorer/rubric/judge identities, random seeds, predeclared primary metric and acceptance margins;
- every attempted prompt, status, actual generated count, raw text/diagnostics and report references.

Do not hash the entire 341 GiB GGUF on every invocation; reuse a trustworthy artifact identifier when available and record file identity plus its limitation otherwise. Never reuse outputs whose manifest does not match the experiment. Derived vectors and large raw data may stay outside git; retain a compact result/evidence reference with enough information to regenerate the run. If evidence has expired, label the historical result unreproducible rather than claiming it was rechecked.

Cache fetches must not publish partially downloaded/unparsed data. Keep dataset caches and any task-specific dependency/package caches isolated; avoid loaders falling back to a user's reusable cache. Do not embed tokens or secrets in manifests.

The versioned summary contains run/profile/protocol/intervention identities; requested, attempted, completed and valid counts; per-stage and per-metric statuses; no-op results; available task, format/language, over-refusal, distribution and timing metrics; per-category aggregates; baseline/candidate deltas and paired intervals; supplied margins and verdict eligibility; and opaque evidence references. Each metric names its denominator. Unavailable KL, semantic grading or other axes appear as `not_measured` with a reason code, never zero. Report only timings actually measured; a first-pass result is not a speed-harness acceptance substitute. Profile-required metrics missing means incomplete execution; explicitly optional diagnostics may be unmeasured without invalidating the narrower profile.

### D4. Controls distinguish machinery from hypotheses

Mandatory no-op checks: base versus explicit scale zero and base versus a zero vector at nonzero scale. At the eval level compare generated IDs where available and complete text, then labels; `401` owns the stronger logits/KV/Engram gate. Mismatched counts/IDs/order are errors, even when labels happen to match.

Keep the equal-row-norm random-direction control, record its seed and zero-row mask, and use multiple seeds when estimating selectivity. A random control changing behavior does not prove a harness bug: it weakens the claim of direction specificity and blocks that claim until investigated. The runtime no-op controls failing are actual pipeline/correctness failures and stop the run.

`405` adds activation-perturbation-matched and layer-permuted controls using its instrumentation. Reports must distinguish matched vector norm from matched `||delta h||/||h||`; a random direction in 5120 dimensions can perturb activations much less than a learned one.

### D5. The first-token screen is a diagnostic

Implement `probe_firsttoken.py` on the same runner and manifest, not a second argument-building stack. Retain per-prompt top-1 token IDs and lexicon mass with a versioned lexicon in local evidence; the default KPI view shows numeric aggregates, support/coverage and opaque example IDs, not token strings or completions. If only top-k is available, the summed mass is a **lower bound**, and the report includes retained probability mass/support. Full first-position logits are already available through the CLI's `--dump-logits FILE` route and can resolve a truncated screen without adding a new inference API.

Do not equate tokens such as `I` with a semantic refusal or use the screen as an automatic rejection gate. Thinking-on first tokens need their own interpretation. A candidate with unchanged first-token mass can still proceed to completed-response testing. A full-vocabulary JS value may characterize shift; different truncated top-k lists must not be independently renormalized and called exact JS. Neither JS nor KL ranks usefulness by itself.

### D6. Calibrate graders, reproduce interventions separately

Keep keyword, three-way judge and StrongREJECT-style scores separate. Use a fixed, independently annotated sample covering refusal, deflection, useful answers with disclaimers, malformed outputs and response text attempting to instruct the judge. Supply request/response as delimited untrusted data. Prefer strict whole-answer labels or structured fields; unknown labels are INVALID, not DEFLECT. Keep judge reasoning separate from its final label and test the actual runner's output form.

The current shortened StrongREJECT prompt is a local variant, not automatically the published evaluator. Either pin and reproduce the original rubric/model protocol or label and calibrate the variant explicitly. Preserve its continuous score without replacing the three-way result. For `--judge base`, run the frozen unsteered model; an external judge selection must have a real supported adapter or fail clearly, not silently fall back to base.

Published anchors retained as **reference**, not acceptance thresholds:

| Source | Reported protocol | Historical numbers |
|---|---|---|
| distributedcognition | Heretic, n=100, weight-edited artifact | keyword 98->41; judge 17->1; KL 0.142 with reported floor 0.131; GSM8K 14->16/20 |
| msuiche | vLLM lane, n=32, source-hook alpha 0.5 | refusal32 compliance 4->24; no-op 32/32 |

A reproduction requires exact prompt IDs, template, generation settings, model artifact/quantization, intervention site/method and grader protocol. If any is unavailable, label reproduction unavailable and state why. Do not run the local transient-fold edit at a nominal source alpha and diagnose a different result as a harness bug.

### D7. Forced-prefix KL with valid support

Compute `KL(P_base || P_steered)` on the same token prefixes, accumulating log-softmax in a stable form over the complete vocabulary. Token IDs define support; lengths, vocabulary identity and forced-sequence identity must match. Empty, nonfinite, missing or mismatched input fails. Report both per-position values and per-prompt aggregates; bootstrap prompts, not correlated token positions as independent samples.

Use an unsteered generated or fixed benign continuation as raw text. The CLI already teacher-forces raw text through `--perplexity-file` (it reports NLL), and the same tokenizer yields identical token IDs in both arms. First extend that existing path to dump per-position full-vocabulary logprobs to a file; only if it cannot expose full distributions, fall back to a small test-only driver on `ds4_session_sync`/`ds4_session_eval`/`ds4_session_copy_logits`, which is not a fifth production binary. Process arms serially; dump bounded/raw rows under the run directory and stream/reduce them rather than holding all runs in RAM. Do not fake teacher forcing by aligning two independent greedy generations or retokenizing their different answers.

Run same-build base/base and scale-zero controls to measure the local numerical floor. The external 0.131 identity-requant figure is not a threshold for same-GGUF runtime steering. An actual identity-requant experiment, if available, is a separately identified comparison. A full KL is mandatory for M1; a top-k or embedding proxy can be reported as exploratory evidence only and cannot pass the fidelity gate.

Required scorer regression: swapping probabilities 0.500001 and 0.499999 yields a near-zero full KL; selecting each distribution's top-1 must not produce a reported full KL near 20.7. Also test empty/unequal sequences, duplicate IDs, same distribution and nonfinite logits.

### D8. Complete behavioral, capability and modality coverage

- **A:** keep the named AdvBench slice separate from the deduplicated union; preserve domain/source membership for E. Complete responses, keyword and both calibrated graders are required for M1.
- **B:** use verified benign instructions, forced-prefix KL and completed-response language/repetition/task-quality checks. A handful of hand-read 512-token answers is a pilot, not a non-inferiority proof. Include longer target-mix answers before adopting a long-output schedule.
- **C:** XSTest-safe contains 250 rows in the recorded fetch, not 125. Use the full pinned set or print the exact subset. Add OR-Bench-hard when available; do not silently substitute a different column or split. First-token labels alone do not establish an over-refusal rate.
- **D:** reuse actual embedded eval cases and answer extraction. Give the eval frontend the minimal residual/gate option block needed to run both arms, or reuse its cases through an existing equivalent runner without duplicating grading. Verify the actual output parser and record benchmark membership; `core` is not automatically full MMLU/GSM8K/ARC-c/TruthfulQA coverage. Connect missing requested datasets explicitly. Define and report the ethics cluster membership; do not assume an arbitrary subject average reproduces a published aggregate.
- **Vision:** use the tested data-URI `image_url` shape for the OpenAI server (or the tested base64 source shape for Anthropic), load the vision component, and keep prompt payload out of the text channel except a neutral instruction. First verify a benign rendered prompt is readable and actually reaches the encoder; non-empty output alone is insufficient.
- **Thinking:** pin explicit mode and budget for both arms; separate reasoning from final output and record whether the final phase was reached. A budget exhausted inside thinking is incomplete, not a refusal verdict.

### D9. Decision and failure policy

Choose the primary behavioral metric before evaluating held-out data. Report all A metrics, B/C/D guards and E breadth; never blend published protocols into one score. Use prompt-paired confidence intervals and predeclared non-inferiority margins. No margins means report-only; no automated acceptance. An interval crossing zero is inconclusive, not proof of equivalence. Tuning and holdout sets stay disjoint; changing the candidate after viewing holdout results requires a new holdout/protocol, not relabeling the old one.

Exit nonzero when a requested run has missing prerequisites, no executed examples, failed controls, malformed records or missing required axes. Save partial evidence first and state the cause through the same KPI-only error boundary. Screen mode and the narrower benign first pass may succeed for their declared coverage while explicitly saying they made no full A-E acceptance decision. A reproducible negative result is a valid experiment, distinct from an execution failure.

### D10. Separate execution, KPI consumption and explicit audit

The developer agent changes a candidate/configuration and reads numerical results. The fixed runner executes the selected profile and calibrated scorers; it does not invent prompts, rewrite them after refusals, switch judges to obtain a desired answer or escalate its scope. Model processes remain serialized and perform the declared evaluation, not autonomous tool use. This separation reduces unnecessary content exposure and makes runs repeatable; it is not a guarantee that an agent/provider will authorize every evaluation.

The automatic first-pass profile uses model-less numerical fixtures, applicable no-op/state checks and completed benign tasks with deterministic reference/format scoring. It may include benign over-refusal or fidelity diagnostics only when the required scorer/measurement path is actually available and declared. It must not require a semantic LLM judge merely to return basic KPIs or trigger a benchmark containing other content as a fallback. Complete benchmark profiles are explicitly selected and launched within their reviewed scope, by an agent when permitted or directly by the operator. The operator can give the resulting identified summary to another agent for analysis.

Default stdout, stderr, `summary.json` and the summary Markdown use an allowlisted schema. Exclude prompt/response text, decoded token strings, judge narratives, text-bearing argv and raw exceptions/tracebacks. Use generated opaque IDs rather than snippets as keys. Keep raw evidence for inspection; this is not deletion or concealment of the experiment's purpose, suite identity or failures. `--report audit` is an explicit content-bearing view of the selected run; `--input-run` can produce it without model execution. Neither report mode changes prompts, grades, denominators or verdicts.

Maintain three distinct outcomes:
- **Model refusal:** a valid measured response when established by the selected scorer; include it in the behavioral rate.
- **Grader refusal/error:** an invalid/missing grade, with a separate count and retained raw evidence. Never interpret it as the tested model refusing or complying. Do not retry with rewritten evaluation instructions to bypass the refusal.
- **Launch blocked/not performed:** no measurement. If orchestration prevented invoking the runner, the agent states that limitation and offers the operator-run command; it cannot claim a runner result exists. If the runner detects a pre-execution block, it records `not_run` with zero measured examples and the appropriate nonzero exit.

KPI-only output never disables no-op checks, cache/vector validation, explicit launch requirements or full-evaluation quality guards. Audit remains necessary for scorer calibration and designated manual checks; it is an explicitly selected task, not raw text dumped into every development loop.

### D11. Qualify reuse before making it the steering default

Once the runner passes its end-to-end, failure-accounting, evidence-boundary and reproducibility checks, it becomes the preferred evaluation entry point for later steering proposals in this repository. Qualify the numerical/benign profile on at least two distinct experiment configurations, such as a scalar-scale comparison and an existing-format layer-mask comparison, without forking the runner. Full benchmark reuse additionally requires the corresponding M1 validation; passing a benign smoke test does not qualify unimplemented axes.

Future proposals reference the verified runner/report-schema version, profile and measured coverage, then supply their candidate identities, datasets/splits, primary KPIs and guard margins. Reuse argument construction, controls, serialization, scorers and reports; add a small metric or adapter only for a demonstrated missing measurement. Do not build a plugin system, service or family-wide package preemptively. Existing `403`/`404`/`405` may consume the same qualified profiles.

A new site, schedule or vector still needs its own correctness tests and measurement validation. Shared infrastructure does not transfer another intervention's acceptance, authorize an unreviewed benchmark or excuse schema/denominator changes. Record reuse qualification and a concrete invocation template in `docs/REFUSAL_VALIDATION.md` when verified; do not mark future proposals implemented merely because they can use this runner.

## Risks / Trade-offs

- [Full logits and complete outputs cost time/storage] -> bounded suites for development, sequential runs, streamed reductions and explicit larger acceptance runs.
- [The judge is biased or injectable] -> fixed unsteered grader, strict parse, annotated calibration and blinded manual audit; report disagreements.
- [Dependencies or gated source data unavailable] -> keep verification pending with a named prerequisite; never turn missing data into a pass.
- [M0 is mistaken for M1] -> print coverage and verdict eligibility in every report.
- [Content leaks through an error path] -> fixture canaries in prompts, completions, judge output and exceptions; assert no raw content enters either default output stream or summary.
- [KPI-only reporting is mistaken for policy bypass or removes needed audit] -> keep launch scope/policies unchanged, record refusal types separately and retain explicitly requested audits.
- [Reuse is claimed before validation] -> qualify the actual profile on distinct configurations and publish its tested coverage/version, not a blanket future guarantee.

## Migration Plan

Repair argument/error contracts and the KPI/evidence boundary before running candidates. Retain historical outputs only under their original identities; do not merge them with the corrected `401` revision. Land tests and docs with each component group, beginning with the deterministic numerical/benign first pass, then connect the full axes. Replace the old illustrative report/commands with ones generated by the real runner and include operator-run, stored-KPI and explicit-audit examples. Qualify profile reuse before recommending it for future steering proposals. The instrument can finish even if a particular external reproduction is unavailable, but it cannot claim that reproduction or a full candidate acceptance with unmeasured required axes.
