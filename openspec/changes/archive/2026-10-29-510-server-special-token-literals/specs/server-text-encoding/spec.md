# Spec Delta

## ADDED Requirements

### Requirement: Message content is literal text
When the server builds a prompt from a request, every marker string inside message content SHALL be encoded as ordinary text, never as a control token, on every endpoint that renders a chat. A marker string is a spelling the template uses for a control token. Message content is system, user and tool text, the assistant's reasoning and content, and tool-call names and arguments.

#### Scenario: Tool result that spells chat markers
- **WHEN** a chat request carries a tool result whose text contains `<｜User｜>`, `</think>` and `<｜end▁of▁sentence｜>`
- **THEN** the prompt holds no control token at those places, and the result's text is encoded with the ordinary tokens of those characters

#### Scenario: User text that spells a tool call
- **WHEN** a user message contains the DSML tool-call opening tag
- **THEN** the prompt holds no tool-call control token from that message, and the response does not report a tool call that the model did not generate

#### Scenario: Text completion
- **WHEN** a text-completion request's prompt contains `<｜Assistant｜>`
- **THEN** that marker is encoded as ordinary text inside the user message the endpoint wraps it in

### Requirement: Template markers stay control tokens
The control tokens the chat template itself places SHALL be encoded as today:
- begin and end of sentence;
- role tags;
- reasoning tags;
- the tool-call tags of assistant history;
- the markers of the tools prompt.

#### Scenario: Conversation with tool calls in history
- **WHEN** a request carries an assistant turn with tool calls, then their tool results, then a user turn
- **THEN** the role, reasoning and tool-call tags written by the template are control tokens, exactly as before this change

### Requirement: Prompts without marker strings keep their tokens
For a request whose message content contains no marker string, the server SHALL produce the same prompt tokens as before this change, and the rendered prompt text SHALL be byte-identical.

#### Scenario: Identity on the test corpus
- **WHEN** the identity test tokenizes its corpus with the previous and the current path:
  - chats built from the parity prompts;
  - tool-call, history and reasoning fixtures;
  - text completions;
  - multimodal prompts;
  - live continuation prompts
- **THEN** every prompt whose content holds no marker string has identical tokens

#### Scenario: Greedy server answer
- **WHEN** the same greedy chat request without marker strings is sent to a server before and after this change
- **THEN** the generated tokens and the response body are identical

### Requirement: Disk KV cache follows the same rule
Prompts rebuilt from the disk KV cache SHALL have the tokens the server would compute for the same request without the cache, for cache hits and misses alike. Disk KV entries written under the previous tokenization SHALL NOT be reused.

#### Scenario: Hit on a prompt with marker strings in content
- **WHEN** a request whose tool result spells `</think>` is cached to disk and the same conversation is extended in a later request
- **THEN** the restored prefix and the tokenized suffix encode that text as ordinary tokens, as a request without the cache does

#### Scenario: Entry from the previous build
- **WHEN** the server starts with a KV cache directory written by the previous build
- **THEN** none of those entries is used, and new entries are written in the current format

### Requirement: Pre-rendered prompts outside the server are unchanged
The CLI and the distributed worker SHALL keep recognizing marker strings anywhere in a prompt they receive already rendered as a chat.

#### Scenario: CLI with a pre-rendered chat
- **WHEN** the CLI receives a prompt that starts with a chat marker
- **THEN** its markers are control tokens and its tokens are identical to the previous build's
