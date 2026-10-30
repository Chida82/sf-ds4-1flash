# Coding Agent Clients

[README](../README.md) | [Server](SERVER.md)

Start the server first:

```sh
./sf-ds4-1flash-server --ctx 100000 --kv-disk-dir /tmp/ds4-kv --kv-disk-space-mb 8192
```

Set the client's context limit no higher than the server's. Output tokens also
consume that context; a client limit does not enlarge the server allocation.
The examples use Flash and localhost. Change the address for a trusted remote
server. The `dsv4-local` strings are placeholders, not server authentication.

## Text encoding

The server's JSON responses are always valid UTF-8. A model can emit a token
whose bytes do not form a complete UTF-8 character — likelier under steering, or
when `max_tokens` cuts an answer mid-character. The server replaces each such
ill-formed byte subpart with U+FFFD (the replacement character) in the response,
streaming and non-streaming alike, and logs one line naming the request, the
number of replaced subparts and the first byte offset. Valid text is passed
through byte for byte. A client that sends a replaced answer back as prompt
re-tokenizes U+FFFD differently from the original tokens, so the KV prefix match
ends at that character.

The CLI (`./sf-ds4-1flash`) is a byte-faithful view and writes the raw token
bytes to stdout; the terminal renders or replaces them. Use the server for a
client that needs valid UTF-8.

## Pi

Add this provider to `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "ds4": {
      "baseUrl": "http://127.0.0.1:8002/v1",
      "api": "openai-completions",
      "apiKey": "dsv4-local",
      "compat": {
        "supportsStore": false,
        "supportsDeveloperRole": false,
        "supportsReasoningEffort": true,
        "supportsUsageInStreaming": true,
        "maxTokensField": "max_tokens",
        "supportsStrictMode": false,
        "thinkingFormat": "deepseek",
        "requiresReasoningContentOnAssistantMessages": true
      },
      "models": [{
        "id": "deepseek-v4.1-flash",
        "name": "DwarfStar Flash",
        "reasoning": true,
        "thinkingLevelMap": {
          "minimal": "minimal", "low": "low", "medium": "medium",
          "high": "high", "xhigh": "xhigh", "max": "max"
        },
        "input": ["text"],
        "contextWindow": 100000,
        "maxTokens": 16384,
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
      }]
    }
  }
}
```

On a server started with `--steering-profile-on-request`, add a second entry
to `models` with `"id": "deepseek-v4.1-flash-steering"`, a name such as
`"DwarfStar Flash (steering)"`, and the same `thinkingLevelMap`; selecting it
in Pi turns the profile on for those requests (`docs/SERVER.md`, Steering per
request).

Pi's levels map one to one onto the server's effort names (`docs/SERVER.md`):
`minimal` turns thinking off, `low` to `max` think at 25, 50, 75, 90 and 100.
`off` is left out of the map on purpose. With `"thinkingFormat": "deepseek"`,
Pi 1.4.0 sends `"thinking":{"type":"disabled"}` for `off` unless the map sets
`"off": null`, which marks the level unsupported and sends nothing (read from
its `openai-completions.js`). The model id `deepseek-chat` turns thinking off
regardless of what a client sends.

Select `ds4/deepseek-v4.1-flash` in Pi. This is a text-only client configuration;
image use also requires the appropriate client input declaration and server
vision encoder.

## OpenCode

Merge the provider into `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "ds4": {
      "name": "DwarfStar",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:8002/v1",
        "apiKey": "dsv4-local"
      },
      "models": {
        "deepseek-v4.1-flash": {
          "name": "DwarfStar Flash",
          "limit": {"context": 100000, "output": 16384}
        }
      }
    }
  }
}
```

Select `ds4/deepseek-v4.1-flash` as the model.

## Codex CLI

Use the Responses API. Add a provider to the Codex configuration:

```toml
[model_providers.ds4]
name = "DwarfStar"
base_url = "http://127.0.0.1:8002/v1"
wire_api = "responses"
stream_idle_timeout_ms = 1000000
```

```sh
codex --model deepseek-v4.1-flash -c model_provider=ds4
```

## Claude Code

Use the Anthropic-compatible endpoint. A shell wrapper can select the local
model for the main agent and its secondary model roles:

```sh
#!/bin/sh
unset ANTHROPIC_API_KEY
export ANTHROPIC_BASE_URL="http://127.0.0.1:8002"
export ANTHROPIC_AUTH_TOKEN="dsv4-local"
export ANTHROPIC_MODEL="deepseek-v4.1-flash"
export ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek-v4.1-flash"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="deepseek-v4.1-flash"
export ANTHROPIC_DEFAULT_OPUS_MODEL="deepseek-v4.1-flash"
export CLAUDE_CODE_SUBAGENT_MODEL="deepseek-v4.1-flash"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
export CLAUDE_STREAM_IDLE_TIMEOUT_MS=600000
exec claude "$@"
```

Give the wrapper a different name from `claude`. Agent clients can send large
initial prompts, so the first prefill may take time. Disk caching helps reuse
compatible prefixes on later sessions.
