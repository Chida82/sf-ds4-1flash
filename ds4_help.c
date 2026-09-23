#include "ds4_help.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* sf: the child identity comes from the Makefile's SF_DEFS block.  Guard it
 * before the first use below, so a stray `cc ds4_help.c` reports this instead
 * of a syntax error on the first macro that stayed unexpanded. */
#if !defined(SF_DEFAULT_MODEL) || !defined(SF_DEFAULT_PORT)
#error "build through the Makefile"
#endif

/* sf: SF_DEFAULT_PORT is numeric and opt() takes a string, so it needs the
 * two-level stringify.  SF_DEFAULT_MODEL is already a string literal and
 * concatenates directly. */
#define SF_STR_(x) #x
#define SF_STR(x) SF_STR_(x)

typedef struct {
    const char *off;
    const char *cyan;
    const char *title;
    const char *yellow;
    const char *grey;
    const char *red;
    const char *white;
    const char *bright;
} help_colors;

static help_colors help_make_colors(FILE *fp) {
    bool color = isatty(fileno(fp));
    help_colors c = {0};
    if (!color) return c;
    c.off = "\x1b[0m";
    c.cyan = "\x1b[38;5;81m";
    c.title = "\x1b[1;38;5;250m";
    c.yellow = "\x1b[38;5;179m";
    c.grey = "\x1b[38;5;240m";
    c.red = "\x1b[38;5;203m";
    c.white = "\x1b[38;5;252m";
    c.bright = "\x1b[1;38;5;231m";
    return c;
}

static void title(FILE *fp, const help_colors *c, const char *s) {
    fprintf(fp, "%s%s%s\n", c->title ? c->title : "", s, c->off ? c->off : "");
}

static void title_red(FILE *fp, const help_colors *c, const char *s) {
    fprintf(fp, "%s%s%s\n", c->red ? c->red : "", s, c->off ? c->off : "");
}

static bool option_name_has_switch(const char *name) {
    bool word_start = true;
    while (*name) {
        if (word_start && (*name == '-' || *name == '/')) return true;
        word_start = (*name == ' ');
        name++;
    }
    return false;
}

static void print_colored_option_name(FILE *fp, const help_colors *c, const char *name) {
    bool has_switch = option_name_has_switch(name);
    bool word_start = true;
    while (*name) {
        const char *start = name;
        while (*name && *name != ' ') name++;
        bool is_option = !has_switch || *start == '-' || *start == '/' ||
                         (word_start && has_switch && *start != '[');
        const char *color = is_option ? c->cyan : c->bright;
        if (color) fputs(color, fp);
        fwrite(start, 1, (size_t)(name - start), fp);
        if (color && c->off) fputs(c->off, fp);
        if (*name == ' ') {
            fputc(*name++, fp);
            word_start = false;
        }
    }
}

static void opt(FILE *fp, const help_colors *c, const char *name, const char *desc) {
    if (c->cyan) {
        fputs("  ", fp);
        print_colored_option_name(fp, c, name);
        fprintf(fp, " %s|%s ", c->grey ? c->grey : "", c->grey ? c->off : "");
        fprintf(fp, "%s%s%s\n", c->white ? c->white : "", desc,
                c->white ? c->off : "");
        return;
    }

    const int col = 30;
    int n = (int)strlen(name);
    if (n > col) {
        fprintf(fp, "  %s\n      %s\n", name, desc);
    } else {
        fprintf(fp, "  %-30s %s\n", name, desc);
    }
}

static void para(FILE *fp, const help_colors *c, const char *s) {
    fprintf(fp, "%s%s%s\n",
            c->yellow ? c->yellow : "", s, c->yellow ? c->off : "");
}

static bool streq(const char *a, const char *b) {
    return a && b && strcmp(a, b) == 0;
}

static bool topic_is(const char *topic, const char *name) {
    return topic && strcmp(topic, name) == 0;
}

static const char *tool_name(ds4_help_tool tool) {
    switch (tool) {
    case DS4_HELP_DS4: return "sf-ds4-1flash";
    case DS4_HELP_SERVER: return "sf-ds4-1flash-server";
    case DS4_HELP_BENCH: return "sf-ds4-1flash-bench";
    case DS4_HELP_EVAL: return "sf-ds4-1flash-eval";
    }
    return "sf-ds4-1flash";
}

static const char *tool_usage(ds4_help_tool tool) {
    switch (tool) {
    case DS4_HELP_DS4:
        return "Usage: sf-ds4-1flash [(-p PROMPT | --prompt-file FILE)] [options]";
    case DS4_HELP_SERVER:
        return "Usage: sf-ds4-1flash-server [options]";
    case DS4_HELP_BENCH:
        return "Usage: sf-ds4-1flash-bench (--prompt-file FILE | --chat-prompt-file FILE) [options]";
    case DS4_HELP_EVAL:
        return "Usage: sf-ds4-1flash-eval [options]";
    }
    return "Usage: sf-ds4-1flash [options]";
}

static const char *tool_summary(ds4_help_tool tool) {
    switch (tool) {
    case DS4_HELP_DS4:
        return "Chat with a local DwarfStar model, run one-shot prompts, inspect models, or coordinate distributed inference.";
    case DS4_HELP_SERVER:
        return "Serve one loaded DwarfStar model through OpenAI, Responses, Anthropic, and completion-compatible HTTP APIs.";
    case DS4_HELP_BENCH:
        return "Measure prefill, decode, context growth, and KV-cache size across repeatable context frontiers.";
    case DS4_HELP_EVAL:
        return "Run the built-in reasoning, math, science, and security evaluation harness with a live terminal UI.";
    }
    return "";
}

static void print_model_runtime(FILE *fp, const help_colors *c,
                                ds4_help_tool tool, bool full) {
    title(fp, c, "Model And Runtime");
    opt(fp, c, "-m, --model FILE", "GGUF model path. Default: " SF_DEFAULT_MODEL);
    if (tool == DS4_HELP_DS4 || tool == DS4_HELP_SERVER) {
        opt(fp, c, "--vision FILE", "Vision encoder GGUF for the selected model.");
    }
    opt(fp, c, "--metal | --cpu", "Select the backend explicitly.");
    opt(fp, c, "--backend NAME", "Backend name: metal or cpu.");
    if (tool != DS4_HELP_BENCH) {
        opt(fp, c, "-c, --ctx N", "Allocated context tokens.");
    }
    if (tool == DS4_HELP_SERVER) {
        opt(fp, c, "-n, --tokens N", "Default max output tokens when clients omit a limit.");
    }
    opt(fp, c, "-t, --threads N", "CPU helper threads for host-side/reference work.");
    opt(fp, c, "--power N", "GPU duty-cycle target, 1..100. Default: 100");
    opt(fp, c, "--ssd-streaming", "Metal: stream model weights from SSD instead of full residency. Needed on a 128 GB Mac: the V4.1 Q2 GGUF is 340.6 GiB.");
    opt(fp, c, "--ssd-streaming-cold", "SSD streaming: skip default popularity-based expert-cache preload.");
    opt(fp, c, "--ssd-streaming-cache-experts N|NGB", "SSD streaming cache target. N requests dynamic expert slots; NGB also reserves two full prefill layers. Either may be reduced to fit the model, graph, context, and backend working set.");
    opt(fp, c, "--ssd-streaming-preload-experts N", "SSD streaming: upfront popularity preload count. Auto-seeded by default.");
    opt(fp, c, "--simulate-used-memory NGB", "Diagnostic: lock N GiB before model load to simulate a smaller-memory machine.");
    opt(fp, c, "--prefill-chunk N", "Graph prefill chunk size. Default: 4096.");
    if (full) {
        /* sf-ablate(specdec): V4.1 Flash has no speculative decoding (registry: none); --mtp*, --dspark* and support GGUF removed */
        opt(fp, c, "--quality", "Prefer exact kernels where faster approximate paths exist.");
        opt(fp, c, "--warm-weights", "Touch resident weights at startup to reduce first-use stalls.");
        if (tool == DS4_HELP_DS4 || tool == DS4_HELP_BENCH) {
            opt(fp, c, "--expert-profile FILE", "Metal-only: write routed expert locality/cache simulation JSON.");
        }
    }
    fputc('\n', fp);
}

static void print_sampling(FILE *fp, const help_colors *c, bool full, ds4_help_tool tool) {
    title(fp, c, "Prompt And Sampling");
    opt(fp, c, "-n, --tokens N", "Maximum generated tokens.");
    opt(fp, c, "--temp F", "Sampling temperature. 0 is greedy/deterministic.");
    opt(fp, c, "--top-p F", "Nucleus sampling probability.");
    opt(fp, c, "--min-p F", "Keep tokens scoring at least F times the top token.");
    opt(fp, c, "--seed N", "Sampling seed for reproducible non-greedy runs.");
    opt(fp, c, "--think", "Use normal thinking mode (V4.1: effort 75).");
    opt(fp, c, "--think-max", "Use maximum thinking (V4.1: 100; V4: requires ctx >= 393216).");
    if (tool == DS4_HELP_DS4)
        opt(fp, c, "--think-level N", "V4.1 thinking effort, 1..100; 0 disables thinking.");
    opt(fp, c, "--nothink", "Disable thinking and ask for direct replies.");
    if (full) {
        opt(fp, c, "-sys, --system TEXT", "System prompt. Empty string disables the default where supported.");
        opt(fp, c, "-p, --prompt TEXT", "One-shot prompt text.");
        opt(fp, c, "--prompt-file FILE", "Read one-shot prompt text from FILE.");
        opt(fp, c, "--raw-prompt", "Tokenize the one-shot prompt without chat markers.");
    }
    fputc('\n', fp);
}

static void print_steering(FILE *fp, const help_colors *c) {
    title(fp, c, "Directional Steering");
    opt(fp, c, "--dir-steering-file FILE", "Load one f32 direction vector per layer.");
    opt(fp, c, "--dir-steering-ffn F", "Apply steering after FFN outputs. Default with file: 1");
    opt(fp, c, "--dir-steering-attn F", "Apply steering after attention outputs. Default: 0");
    fputc('\n', fp);
}

static void print_distributed(FILE *fp, const help_colors *c) {
    title(fp, c, "Distributed Inference");
    fputc('\n', fp);
    para(fp, c, "Distributed mode runs one logical session across several machines by assigning contiguous model layer ranges to workers. Workers own their layer slice and KV-cache shard; the coordinator owns the prompt, sampling loop, and client/API flow. Start workers first, then start the coordinator. The coordinator waits for a complete route and streams hidden states through the workers.");
    fputc('\n', fp);
    opt(fp, c, "--role ROLE", "Distributed role: coordinator or worker.");
    opt(fp, c, "--layers A:B", "Inclusive layer slice, e.g. 0:20 or 21:output.");
    opt(fp, c, "--listen HOST PORT", "Coordinator listen address; workers may use it for their data listener.");
    opt(fp, c, "--coordinator HOST PORT", "Coordinator address for --role worker.");
    opt(fp, c, "--dist-prefill-chunk N", "Coordinator prefill pipeline chunk size. Default: session cap.");
    opt(fp, c, "--dist-prefill-window N", "Max prefill chunks in flight. Default: workers+2, capped at 8.");
    opt(fp, c, "--dist-activation-bits N", "Hidden-state transport width: 32, 16, or 8. Default: 32");
    opt(fp, c, "--dist-replay-check", "Diagnostic: reset and replay prompt, then compare logits.");
    opt(fp, c, "--debug", "Print coordinator route/debug logs.");
    fputc('\n', fp);
    title(fp, c, "Tensor Parallelism");
    fputc('\n', fp);
    para(fp, c, "Tensor parallelism uses the same coordinator/worker addresses as distributed mode, but always runs one 50/50 worker. Add --tensor-parallel, omit --layers, start the worker, then start the coordinator.");
    fputc('\n', fp);
    opt(fp, c, "--tensor-parallel", "Switch --role/--listen/--coordinator to two-machine tensor parallelism.");
    opt(fp, c, "--transport auto|rdma|tcp", "Tensor gate transport. Default: auto");
    opt(fp, c, "--rdma-device NAME", "Select a verbs device when auto-detection is ambiguous.");
    opt(fp, c, "--rdma-gid-index N", "Select the local verbs GID index.");
    opt(fp, c, "--debug-hash N", "Cross-check hidden state every N tokens.");
    fputc('\n', fp);
}

static void print_cli_diagnostics(FILE *fp, const help_colors *c);

static void print_cli_specific(FILE *fp, const help_colors *c, bool full) {
    title(fp, c, "CLI Modes");
    opt(fp, c, "sf-ds4-1flash", "Start the interactive prompt.");
    opt(fp, c, "sf-ds4-1flash -p TEXT", "Run one prompt and exit.");
    opt(fp, c, "sf-ds4-1flash --prompt-file FILE", "Run a long prompt from a file and exit.");
    opt(fp, c, "--prefix-file FILE", "Preload complete alternating USER:/ASSISTANT: turns before the live conversation.");
    fputc('\n', fp);
    if (full) {
        print_cli_diagnostics(fp, c);
    }
}

static void print_cli_diagnostics(FILE *fp, const help_colors *c) {
    title(fp, c, "Diagnostics And Data Collection");
    opt(fp, c, "--inspect", "Load the model and print a summary only.");
    opt(fp, c, "--dump-tokens", "Print the exact CLI prompt token stream, then exit. Use --raw for literal text.");
    opt(fp, c, "--dump-logits FILE", "Write full next-token logits as JSON.");
    opt(fp, c, "--dump-logprobs FILE", "Write greedy continuation top-logprobs as JSON.");
    opt(fp, c, "--logprobs-top-k N", "Alternatives stored by --dump-logprobs. Default: 20");
    opt(fp, c, "--decode-consistency N", "Compare N-token decode logits with a fresh full prefill.");
    opt(fp, c, "--expert-profile FILE", "Metal-only: write routed expert locality/cache simulation JSON.");
    opt(fp, c, "--perplexity-file FILE", "Score raw text with teacher-forced NLL.");
    opt(fp, c, "--head-test", "Run the output HC/logits head after the native slice.");
    opt(fp, c, "--first-token-test", "Run exact CPU whole-model pass for the first prompt token.");
    opt(fp, c, "--metal-graph-test", "Compare first GPU-resident graph stages with CPU.");
    opt(fp, c, "--metal-graph-full-test", "Run the GPU-resident self-token graph across all layers.");
    opt(fp, c, "--metal-graph-prompt-test", "Compare CPU and GPU graph logits for the full prompt.");
    fputc('\n', fp);
}

static void print_cli_commands(FILE *fp, const help_colors *c) {
    title_red(fp, c, "Interactive Commands");
    opt(fp, c, "/help", "Show interactive commands.");
    opt(fp, c, "/think [N], /think-max, /nothink", "Switch thinking mode; V4.1 accepts effort 0..100.");
    opt(fp, c, "/ctx N", "Restart the interactive session with a new context size.");
    opt(fp, c, "/power N", "Set GPU duty cycle percentage, 1..100.");
    opt(fp, c, "/read FILE", "Submit a text file, PNG, or JPEG as the next user message.");
    opt(fp, c, "/quit, /exit", "Leave the prompt.");
    opt(fp, c, "Ctrl+C", "Stop current generation and return to ds4>.");
    fputc('\n', fp);
}

/* sf-ablate(agent): agent help removed with ds4-agent; --chdir survives in ds4_server.c and docs/SERVER.md */

static void print_server_api(FILE *fp, const help_colors *c) {
    title(fp, c, "HTTP API");
    opt(fp, c, "--host HOST", "Bind address. Default: 127.0.0.1");
    opt(fp, c, "--port N", "Bind port. Default: " SF_STR(SF_DEFAULT_PORT));
    opt(fp, c, "--cors", "Add Access-Control-Allow-* headers for browser JS clients.");
    opt(fp, c, "--trace FILE", "Write prompts, cache decisions, output, and tool calls.");
    opt(fp, c, "--batched-session N", "Keep N resident sessions and batch decode-ready requests.");
    opt(fp, c, "--mixed-prefill-quantum N", "Prefill chunk while generations are active. Default: 128");
    para(fp, c, "Endpoints: /v1/chat/completions, /v1/responses, /v1/completions, and /v1/messages.");
    para(fp, c, "Model id: deepseek-v4.1-flash. deepseek-chat and deepseek-reasoner select thinking off/on.");
    fputc('\n', fp);
}

static void print_server_thinking(FILE *fp, const help_colors *c) {
    title(fp, c, "Server Thinking Defaults");
    para(fp, c, "DeepSeek-compatible chat requests default to high-effort thinking.");
    para(fp, c, "reasoning_effort=max or output_config.effort=max requests Think Max.");
    para(fp, c, "Think Max requires --ctx >= 393216; smaller contexts use high.");
    para(fp, c, "thinking={type:disabled}, think=false, or model=deepseek-chat selects non-thinking mode.");
    para(fp, c, "In thinking mode, client sampling knobs are ignored like the official API.");
    fputc('\n', fp);
}

static void print_kv_cache(FILE *fp, const help_colors *c) {
    title(fp, c, "Disk KV Cache");
    opt(fp, c, "--kv-disk-dir DIR", "Enable disk KV checkpoints in DIR.");
    opt(fp, c, "--kv-disk-space-mb N", "Disk budget. Default when enabled: 4096");
    opt(fp, c, "--kv-cache-min-tokens N", "Do not save/load checkpoints shorter than N. Default: 512");
    opt(fp, c, "--kv-cache-cold-max-tokens N", "Save cold first prompts up to N tokens. 0 disables. Default: 30000");
    opt(fp, c, "--kv-cache-continued-interval-tokens N", "Save aligned continued frontiers. 0 disables. Default: 10000");
    opt(fp, c, "--kv-cache-boundary-trim-tokens N", "Trim tail tokens for cold boundary saves. Default: 32");
    opt(fp, c, "--kv-cache-boundary-align-tokens N", "Align cold boundary saves to this multiple. Default: 2048");
    opt(fp, c, "--kv-cache-reject-different-quant", "Reject checkpoints written with different routed-expert quantization.");
    opt(fp, c, "--disable-exact-dsml-tool-replay", "Disable exact sampled DSML tool replay map.");
    opt(fp, c, "--tool-memory-max-ids N", "Exact tool-call IDs kept in RAM. Default: 100000");
    fputc('\n', fp);
}

static void print_bench_specific(FILE *fp, const help_colors *c) {
    title(fp, c, "Benchmark Input");
    opt(fp, c, "--prompt-file FILE", "Raw benchmark text; token sequence is sliced at each frontier.");
    opt(fp, c, "--chat-prompt-file FILE", "Render FILE as one no-thinking chat user message.");
    opt(fp, c, "-sys, --system TEXT", "System prompt used only with --chat-prompt-file.");
    fputc('\n', fp);
    title(fp, c, "Benchmark Sweep");
    opt(fp, c, "--ctx-start N", "First measured frontier. Default: 2048");
    opt(fp, c, "--ctx-max N", "Last measured frontier. Default: 32768");
    opt(fp, c, "--ctx-alloc N", "Allocated context. Default: ctx-max + gen-tokens + 1");
    opt(fp, c, "--step-mul F", "Multiplicative step. Default: 1");
    opt(fp, c, "--step-incr N", "Linear step when --step-mul is 1. Default: 2048");
    opt(fp, c, "--gen-tokens N", "Greedy decode tokens per frontier. 0 for pure prefill. Default: 128");
    opt(fp, c, "--teacher-forced-decode", "Decode the following prompt tokens instead of each predicted argmax.");
    opt(fp, c, "--csv FILE", "Write CSV there instead of stdout.");
    opt(fp, c, "--dump-frontier-logits-dir DIR", "Write one full-logit JSON file per frontier.");
    fputc('\n', fp);
}

static void print_eval_specific(FILE *fp, const help_colors *c) {
    title(fp, c, "Evaluation");
    opt(fp, c, "--suite NAME", "core, hard, all, or hard-smoke. Default: core");
    opt(fp, c, "--source NAME", "Run only cases from this source.");
    opt(fp, c, "--domain NAME", "Run only cases in this domain.");
    opt(fp, c, "--case-id ID", "Run the case with this source ID.");
    opt(fp, c, "--list-cases", "List selected cases without loading a model.");
    opt(fp, c, "--validate-cases", "Validate all embedded cases and exit.");
    opt(fp, c, "-n, --tokens N", "Override the generation budget for every question.");
    opt(fp, c, "--questions N", "Run only the first N selected questions.");
    opt(fp, c, "--case-sequence LIST", "Run 1-based case numbers in this comma-separated order.");
    opt(fp, c, "--retry-incomplete", "Retry a missing final answer once with twice the budget.");
    opt(fp, c, "--trace FILE", "Write questions, outputs, and grading decisions.");
    opt(fp, c, "--regrade-trace FILE", "Regrade a prior trace without loading the model.");
    opt(fp, c, "--soft-limit-reply-budget N", "Soft close thinking near the end of reply budget. Default: 1024");
    opt(fp, c, "--hard-limit-reply-budget N", "Force </think> with N tokens left. Default: 512");
    opt(fp, c, "--soft-limit-think-close-rank N", "Soft-close when </think> is in top N tokens. Default: 3");
    opt(fp, c, "--pause-ms N", "Pause after each result in the TTY UI. Default: 350");
    opt(fp, c, "--plain", "Disable split-screen ANSI UI.");
    opt(fp, c, "--self-test-extractors", "Run answer-extractor self-tests and exit.");
    fputc('\n', fp);
}

static bool tool_has_topic(ds4_help_tool tool, const char *topic) {
    if (!topic) return true;
    if (streq(topic, "all")) return true;
    if (streq(topic, "runtime") || streq(topic, "distributed")) return true;
    if (streq(topic, "sampling"))
        return tool == DS4_HELP_DS4 || tool == DS4_HELP_EVAL;
    if (streq(topic, "steering"))
        return tool == DS4_HELP_DS4 || tool == DS4_HELP_SERVER;
    switch (tool) {
    case DS4_HELP_DS4:
        return streq(topic, "diagnostics") || streq(topic, "commands");
    case DS4_HELP_SERVER:
        return streq(topic, "api") || streq(topic, "kv-cache") || streq(topic, "thinking");
    case DS4_HELP_BENCH:
        return streq(topic, "benchmark");
    case DS4_HELP_EVAL:
        return streq(topic, "evaluation");
    }
    return false;
}

static void more_line(FILE *fp, const help_colors *c, const char *label, const char *topic) {
    static const char *colors[] = {
        "\x1b[38;5;81m", "\x1b[38;5;114m", "\x1b[38;5;179m",
        "\x1b[38;5;141m", "\x1b[38;5;147m"
    };
    static size_t idx;
    const char *on = c->cyan ? colors[idx++ % (sizeof(colors) / sizeof(colors[0]))] : "";
    if (streq(label, "Interactive commands:") && c->red) on = c->red;
    const char *off = c->off ? c->off : "";
    fprintf(fp, "    %s%-26s%s --help %s\n", on, label, off, topic);
}

static void print_more_info(FILE *fp, const help_colors *c, ds4_help_tool tool) {
    title(fp, c, "More Info");
    more_line(fp, c, "Runtime full info:", "runtime");
    if (tool_has_topic(tool, "sampling"))
        more_line(fp, c, "Sampling full info:", "sampling");
    more_line(fp, c, "Distributed inference:", "distributed");
    if (tool_has_topic(tool, "steering"))
        more_line(fp, c, "Steering full info:", "steering");
    if (tool == DS4_HELP_DS4) {
        more_line(fp, c, "Interactive commands:", "commands");
        more_line(fp, c, "Diagnostics:", "diagnostics");
    } else if (tool == DS4_HELP_SERVER) {
        more_line(fp, c, "HTTP API:", "api");
        more_line(fp, c, "Disk KV cache:", "kv-cache");
        more_line(fp, c, "Thinking behavior:", "thinking");
    } else if (tool == DS4_HELP_BENCH) {
        more_line(fp, c, "Benchmark sweep:", "benchmark");
    } else if (tool == DS4_HELP_EVAL) {
        more_line(fp, c, "Evaluation options:", "evaluation");
    }
    fputc('\n', fp);
}

static void print_examples(FILE *fp, const help_colors *c, ds4_help_tool tool, const char *topic) {
    title(fp, c, "Examples");
    if (topic_is(topic, "distributed")) {
        opt(fp, c, "worker", "./sf-ds4-1flash --role worker --layers 21:output --coordinator 192.168.0.181 9000 -m " SF_DEFAULT_MODEL);
        opt(fp, c, "coordinator", "./sf-ds4-1flash --role coordinator --layers 0:20 --listen 0.0.0.0 9000 -p \"Hello\" -m " SF_DEFAULT_MODEL);
    } else if (topic_is(topic, "runtime")) {
        if (tool == DS4_HELP_SERVER) {
            opt(fp, c, "Metal API", "./sf-ds4-1flash-server -m " SF_DEFAULT_MODEL " --metal --ctx 100000");
            opt(fp, c, "quiet API", "./sf-ds4-1flash-server --power 60 --host 127.0.0.1 --port 8002");
        } else if (tool == DS4_HELP_BENCH) {
            opt(fp, c, "bench", "./sf-ds4-1flash-bench --prompt-file long.txt --ctx-max 32768");
            opt(fp, c, "quiet bench", "./sf-ds4-1flash-bench --prompt-file long.txt --power 70");
        } else if (tool == DS4_HELP_EVAL) {
            opt(fp, c, "eval", "./sf-ds4-1flash-eval --questions 10 --ctx 100000");
            opt(fp, c, "CPU debug", "./sf-ds4-1flash-eval --cpu --questions 1 --tokens 32");
        } else {
            opt(fp, c, "Metal", "./sf-ds4-1flash -m " SF_DEFAULT_MODEL " --metal -c 100000");
            opt(fp, c, "quiet thermals", "./sf-ds4-1flash -p \"Summarize README\" --power 50");
        }
    } else if (topic_is(topic, "steering")) {
        opt(fp, c, "steer FFN", "./sf-ds4-1flash -p \"Write tersely\" --dir-steering-file dir.bin --dir-steering-ffn 0.8");
    } else if (tool == DS4_HELP_SERVER || topic_is(topic, "api") || topic_is(topic, "kv-cache")) {
        opt(fp, c, "local API", "./sf-ds4-1flash-server --ctx 100000 --kv-disk-dir ~/.sf/ds4-1flash/kv --kv-disk-space-mb 8192");
        opt(fp, c, "curl", "curl http://127.0.0.1:8002/v1/models");
    } else if (tool == DS4_HELP_BENCH || topic_is(topic, "benchmark")) {
        opt(fp, c, "csv", "./sf-ds4-1flash-bench --prompt-file long.txt --ctx-max 32768 --csv speed.csv");
        opt(fp, c, "prefill only", "./sf-ds4-1flash-bench --prompt-file long.txt --gen-tokens 0");
    } else if (tool == DS4_HELP_EVAL || topic_is(topic, "evaluation")) {
        opt(fp, c, "first 10", "./sf-ds4-1flash-eval --questions 10 --trace eval.trace");
        opt(fp, c, "plain", "./sf-ds4-1flash-eval --plain --nothink --tokens 512");
    } else {
        opt(fp, c, "chat", "./sf-ds4-1flash");
        opt(fp, c, "one shot", "./sf-ds4-1flash -p \"Explain mmap in C\"");
        opt(fp, c, "long prompt", "./sf-ds4-1flash --think-max --prompt-file prompt.txt --ctx 393216");
    }
    fputc('\n', fp);
}

static void print_topic(FILE *fp, const help_colors *c, ds4_help_tool tool, const char *topic) {
    if (streq(topic, "all")) {
        print_model_runtime(fp, c, tool, true);
        if (tool_has_topic(tool, "sampling")) print_sampling(fp, c, true, tool);
        if (tool_has_topic(tool, "steering")) print_steering(fp, c);
        print_distributed(fp, c);
        if (tool == DS4_HELP_DS4) {
            print_cli_specific(fp, c, true);
            print_cli_commands(fp, c);
        } else if (tool == DS4_HELP_SERVER) {
            print_server_api(fp, c);
            print_server_thinking(fp, c);
            print_kv_cache(fp, c);
        } else if (tool == DS4_HELP_BENCH) {
            print_bench_specific(fp, c);
        } else if (tool == DS4_HELP_EVAL) {
            print_eval_specific(fp, c);
        }
        return;
    }

    if (streq(topic, "runtime")) print_model_runtime(fp, c, tool, true);
    else if (streq(topic, "sampling")) print_sampling(fp, c, true, tool);
    else if (streq(topic, "steering")) print_steering(fp, c);
    else if (streq(topic, "distributed")) print_distributed(fp, c);
    else if (tool == DS4_HELP_DS4 && streq(topic, "diagnostics")) print_cli_diagnostics(fp, c);
    else if (tool == DS4_HELP_DS4 && streq(topic, "commands")) print_cli_commands(fp, c);
    else if (tool == DS4_HELP_SERVER && streq(topic, "api")) print_server_api(fp, c);
    else if (tool == DS4_HELP_SERVER && streq(topic, "kv-cache")) print_kv_cache(fp, c);
    else if (tool == DS4_HELP_SERVER && streq(topic, "thinking")) print_server_thinking(fp, c);
    else if (tool == DS4_HELP_BENCH && streq(topic, "benchmark")) print_bench_specific(fp, c);
    else if (tool == DS4_HELP_EVAL && streq(topic, "evaluation")) print_eval_specific(fp, c);
}

static void print_default(FILE *fp, const help_colors *c, ds4_help_tool tool) {
    print_model_runtime(fp, c, tool, false);

    if (tool == DS4_HELP_DS4) {
        print_cli_specific(fp, c, true);
        print_sampling(fp, c, false, tool);
    } else if (tool == DS4_HELP_SERVER) {
        print_server_api(fp, c);
        print_kv_cache(fp, c);
    } else if (tool == DS4_HELP_BENCH) {
        print_bench_specific(fp, c);
    } else if (tool == DS4_HELP_EVAL) {
        print_eval_specific(fp, c);
    }
}

void ds4_help_print(FILE *fp, ds4_help_tool tool, const char *topic) {
    help_colors c = help_make_colors(fp);
    if (topic && !tool_has_topic(tool, topic)) {
        fprintf(fp, "%s: unknown help topic '%s'\n\n", tool_name(tool), topic);
        topic = NULL;
    }

    fprintf(fp, "%s%s%s\n", c.bright ? c.bright : "", tool_name(tool), c.off ? c.off : "");
    fprintf(fp, "%s\n\n", tool_summary(tool));
    fprintf(fp, "%s\n\n", tool_usage(tool));

    if (topic) print_topic(fp, &c, tool, topic);
    else {
        print_default(fp, &c, tool);
        print_more_info(fp, &c, tool);
    }
    print_examples(fp, &c, tool, topic);
}
