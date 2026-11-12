# Proposal

## Why

The most expensive part of a decision is prefilling its state (6-7 s for a
few hundred tokens). In the commonest real use, **the state is a
conversation this server has just generated**: a guardrail on the answer, a
router choosing the next tool, an agent checking "is the task finished?". The
slot's session already holds that conversation in its KV. A decision that
takes the conversation as its state should cost only its question: about 1 s
instead of 7-20 s.

Small-model systems cannot do this: their decision model is a different model
from the one that wrote the conversation. Here it is the same one, with the
same session.

## What Changes

- `/v1/systemone` accepts the state as chat messages:
  `"state": [ {"role","content"}, ... ]` with `"sf":{"state":"messages"}`.
- The server renders the messages with the chat template, appends each
  question as an ordinary next user turn with thinking off and the answer
  prefill, syncs to the tokens all questions share, and branches per
  question as `800` does.
- When the slot's live session is a token prefix of that rendering, only the
  new tokens are evaluated. The chat's state is restored afterwards (`830`).

## Non-goals

- No decision *during* a generation (a tap between two decode tokens). It
  was examined and set aside: mid-reasoning the model's stop signal is a
  cliff, so free taps carry almost no information, and a repetition or length
  watchdog is better done by a counter on the CPU.
- No tools, no images in the messages: 422.
- No steered sessions: the decision is unsteered, as everywhere.

## Impact

- `ds4_server.c`: the request option, the rendering, the common-prefix
  branch.
- `sf_sysone.c`: a "next user turn" suffix builder.
- Live test and docs.
