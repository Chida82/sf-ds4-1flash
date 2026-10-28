# Tasks

## 1. Phase gate
- [x] 1.1 Track the reasoning phase per session from the prompt's last token and the `</think>` boundary
- [x] 1.2 Apply each slot's gate to its constant scale on prompt sync and on every decode step
- [x] 1.3 Read the two environment variables at engine open; an unrecognised value means both phases
- [x] 1.4 Refuse the native batched decode path for gated sessions

## 2. Profile format and loader
- [x] 2.1 Define the container: magic, header length, JSON header, one matrix per slot
- [x] 2.2 Parse the header's site, shape and slots; reject a mismatched site or shape
- [x] 2.3 Reject a slot with a zero scale, an unknown phase, or a file whose size contradicts the slot count
- [x] 2.4 Load each matrix through the existing direction-file validation
- [x] 2.5 Resolve a bare name under `com-steering/profiles`; list the available profiles when it does not match
- [x] 2.6 Treat the profile as the opt-in; refuse it combined with the `--dir-steering-*` options
- [x] 2.7 Print the profile name and each slot's scale and phase at engine open
- [x] 2.8 Thread `--steering-profile` through the CLI, the server and the eval binary

## 3. Tooling
- [x] 3.1 `com-steering/make_profile.py` builds a profile from vectors, scales and phases
- [x] 3.2 The same tool shows a profile's header and verifies each matrix against its recorded hash
- [x] 3.3 Build the first profile and keep it under `com-steering/profiles`

## 4. Verify
- [x] 4.1 Profile output byte-identical to the equivalent raw-flag run
- [x] 4.2 Profile output byte-identical to the pre-prune binary's raw-flag run
- [x] 4.3 Steered output differs from unsteered, so the edit is applied
- [x] 4.4 `make test` passes
- [ ] 4.5 Automated oracle for the parser and the gate — not done, see `416`
