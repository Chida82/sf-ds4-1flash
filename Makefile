ifneq ($(shell uname -s),Darwin)
$(error sf-ds4-1flash builds on macOS only)
endif

# sf: child identity (SPEC.md §E). Everything else below is upstream's.
BIN ?= sf-ds4-1flash
SF_DEFS := -DSF_DEFAULT_MODEL='"deepseek-v4.1-flash.gguf"' -DSF_DEFAULT_PORT=8002 \
           -DSF_HOME='".sf/ds4-1flash"' -DSF_LOCK_FILE='"/tmp/sf-ds4-1flash.lock"'

CC ?= cc
NATIVE_CPU_FLAG ?= -mcpu=native
SAMPLING_TEST := tests/test_sampling
GLM53_KDA_TEST := tests/test_glm53_kda
QWEN4_KERNEL_TEST := tests/test_qwen4_kernels

DEBUG_FLAGS ?= -g
CFLAGS ?= -O3 -ffast-math $(DEBUG_FLAGS) $(NATIVE_CPU_FLAG) -Wall -Wextra -std=c99
OBJCFLAGS ?= -O3 -ffast-math $(DEBUG_FLAGS) $(NATIVE_CPU_FLAG) -Wall -Wextra -fobjc-arc
QUALITY_CFLAGS ?= -O3 $(DEBUG_FLAGS) $(NATIVE_CPU_FLAG) -Wall -Wextra -std=c11
CFLAGS += $(SF_DEFS)
OBJCFLAGS += $(SF_DEFS)

LDLIBS ?= -lm -pthread
METAL_SRCS := $(wildcard metal/*.metal)
DS4_TEST_MODEL ?= deepseek-v4.1-flash.gguf

METAL_LDLIBS := $(LDLIBS) -framework Foundation -framework Metal
CORE_OBJS = ds4.o ds4_image.o ds4_distributed.o ds4_tp.o ds4_ssd.o ds4_metal.o ds4_layer_pack.o ds4_engram.o
CPU_CORE_OBJS = ds4_cpu.o ds4_image.o ds4_distributed.o ds4_tp.o ds4_ssd.o ds4_layer_pack.o

.PHONY: all help clean cpu test test-metal-session-batch

.PHONY: metal-decode-schedule-bench metal-prefill-variant-bench session-concurrency-bench check-mxfp4-half-lut
.PHONY: test-metal-moe-prefill test-metal-dense-mpp

all: $(BIN) $(BIN)-server $(BIN)-bench $(BIN)-eval

help:
	@echo "sf-ds4-1flash build targets:"
	@echo "  make              Build the four Metal binaries ($(BIN), -server, -bench, -eval)"
	@echo "  make cpu          Build the four CPU-reference binaries ($(BIN)-cpu*)"
	@echo "  make test         Build and run the model-less tests"
	@echo "  make metal-decode-schedule-bench  Build the balanced Metal decode schedule benchmark"
	@echo "  make session-concurrency-bench    Build the concurrency x context serving benchmark"
	@echo "  make metal-prefill-variant-bench  Build the balanced Metal prefill variant benchmark"
	@echo "  make check-mxfp4-half-lut  Verify the checked-in MXFP4 half LUT matches the generator"
	@echo "  make test-mxfp4-metal  Check the MXFP4 half LUT, then run Metal MXFP4 exactness tests"
	@echo "  make test-deepseek41-metal  Run the DeepSeek V4.1 Metal kernel tests"
	@echo "  make test-engram         Run the Engram store tests"
	@echo "  make clean        Remove build outputs"

$(BIN): ds4_cli.o ds4_help.o ds4_prompt_prefix.o linenoise.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ ds4_cli.o ds4_help.o ds4_prompt_prefix.o linenoise.o $(CORE_OBJS) $(METAL_LDLIBS)

$(BIN)-server: ds4_server.o ds4_help.o ds4_kvstore.o rax.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ ds4_server.o ds4_help.o ds4_kvstore.o rax.o $(CORE_OBJS) $(METAL_LDLIBS)

$(BIN)-bench: ds4_bench.o ds4_help.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ ds4_bench.o ds4_help.o $(CORE_OBJS) $(METAL_LDLIBS)

$(BIN)-eval: ds4_eval.o ds4_eval_cases.o ds4_help.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ ds4_eval.o ds4_eval_cases.o ds4_help.o $(CORE_OBJS) $(METAL_LDLIBS)

gguf-tools/quality-testing/score_official: gguf-tools/quality-testing/score_official.c ds4.h ds4_distributed.h ds4_tp.h $(CORE_OBJS) rax.o
	$(CC) $(QUALITY_CFLAGS) -I. -o $@ gguf-tools/quality-testing/score_official.c $(CORE_OBJS) rax.o $(METAL_LDLIBS)

tests/test_metal_session_batch.o: tests/test_metal_session_batch.c ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ tests/test_metal_session_batch.c

tests/test_metal_session_batch: tests/test_metal_session_batch.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_metal_tp_spec.o: tests/test_metal_tp_spec.c ds4.h ds4_tp.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

tests/test_metal_tp_spec: tests/test_metal_tp_spec.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_metal_tp_cancel: tests/test_metal_tp_cancel.c ds4.h ds4_tp.h $(CORE_OBJS)
	$(CC) $(CFLAGS) -I. -o $@ $< $(CORE_OBJS) $(METAL_LDLIBS)

test-metal-session-batch: tests/test_metal_session_batch
	DS4_TEST_MODEL="$(DS4_TEST_MODEL)" ./tests/test_metal_session_batch

speed-bench/metal_decode_schedule_bench.o: speed-bench/metal_decode_schedule_bench.c ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

speed-bench/metal_decode_schedule_bench: speed-bench/metal_decode_schedule_bench.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

metal-decode-schedule-bench: speed-bench/metal_decode_schedule_bench

speed-bench/metal_prefill_variant_bench.o: speed-bench/metal_prefill_variant_bench.c ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

speed-bench/metal_prefill_variant_bench: speed-bench/metal_prefill_variant_bench.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

metal-prefill-variant-bench: speed-bench/metal_prefill_variant_bench

speed-bench/session_concurrency_bench.o: speed-bench/session_concurrency_bench.c ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

speed-bench/session_concurrency_bench: speed-bench/session_concurrency_bench.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

session-concurrency-bench: speed-bench/session_concurrency_bench

tests/test_mxfp4_metal.o: tests/test_mxfp4_metal.c ds4_gpu.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

tests/test_mxfp4_metal: tests/test_mxfp4_metal.o ds4_metal.o ds4_image.o
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

check-mxfp4-half-lut:
	python3 metal/generate_mxfp4_half_lut.py --check

test-mxfp4-metal: check-mxfp4-half-lut tests/test_mxfp4_metal
	./tests/test_mxfp4_metal

tests/test_metal_moe_prefill.o: tests/test_metal_moe_prefill.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_metal_moe_prefill: tests/test_metal_moe_prefill.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

test-metal-moe-prefill: tests/test_metal_moe_prefill
	./tests/test_metal_moe_prefill

tests/test_qwen4_moe_mm_specialize.o: tests/test_qwen4_moe_mm_specialize.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_qwen4_moe_mm_specialize: tests/test_qwen4_moe_mm_specialize.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-qwen4-moe-mm-specialize
test-qwen4-moe-mm-specialize: tests/test_qwen4_moe_mm_specialize
	./tests/test_qwen4_moe_mm_specialize

tests/test_qwen4_conv_parallel.o: tests/test_qwen4_conv_parallel.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_qwen4_conv_parallel: tests/test_qwen4_conv_parallel.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-qwen4-prefill-reuse
test-qwen4-prefill-reuse: tests/test_qwen4_conv_parallel tests/test_qwen4_moe_mm_specialize
	./tests/test_qwen4_conv_parallel
	./tests/test_qwen4_moe_mm_specialize

tests/test_q8_prefill_variants.o: tests/test_q8_prefill_variants.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_q8_prefill_variants: tests/test_q8_prefill_variants.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-q8-prefill-variants
test-q8-prefill-variants: tests/test_q8_prefill_variants
	./tests/test_q8_prefill_variants

tests/test_metal_ssd_experts.o: tests/test_metal_ssd_experts.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_metal_ssd_experts: tests/test_metal_ssd_experts.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-metal-ssd-experts
test-metal-ssd-experts: tests/test_metal_ssd_experts
	./tests/test_metal_ssd_experts
	./tests/test_metal_ssd_experts --q4
	./tests/test_metal_ssd_experts --mxfp4

tests/test_metal_command_memory: tests/test_metal_command_memory.c ds4_gpu.h $(CORE_OBJS)
	$(CC) $(CFLAGS) -I. -o $@ $< $(CORE_OBJS) $(METAL_LDLIBS)

.PHONY: test-metal-command-memory
test-metal-command-memory: tests/test_metal_command_memory
	MTL_DEBUG_LAYER=1 ./tests/test_metal_command_memory
	MTL_DEBUG_LAYER=1 ./tests/test_metal_command_memory row
	MTL_DEBUG_LAYER=1 ./tests/test_metal_command_memory session
	MTL_DEBUG_LAYER=1 ./tests/test_metal_command_memory batch
	MTL_DEBUG_LAYER=1 ./tests/test_metal_command_memory big

tests/test_deepseek41_metal.o: tests/test_deepseek41_metal.c ds4_gpu.h ds4_deepseek41_gpu.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -I. -c -o $@ $<

tests/test_deepseek41_metal: tests/test_deepseek41_metal.o $(CORE_OBJS)
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-deepseek41-metal
test-deepseek41-metal: tests/test_deepseek41_metal
	./tests/test_deepseek41_metal

tests/test_deepseek41_graph.o: tests/test_deepseek41_graph.c ds4.c ds4_gpu.h ds4_engram.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -Wno-unused-function -I. -c -o $@ $<

tests/test_deepseek41_graph: tests/test_deepseek41_graph.o $(filter-out ds4.o,$(CORE_OBJS))
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -o $@ $^ $(METAL_LDLIBS)

tests/test_deepseek41_prefill.o: tests/test_deepseek41_prefill.c ds4.c ds4_gpu.h ds4_engram.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -Wno-unused-function -I. -c -o $@ $<

tests/test_deepseek41_prefill: tests/test_deepseek41_prefill.o $(filter-out ds4.o,$(CORE_OBJS))
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -o $@ $^ $(METAL_LDLIBS)

tests/test_metal_tp_bulk: tests/test_metal_tp_bulk.c ds4_gpu.h ds4_tp.h $(CORE_OBJS)
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -I. -o $@ $< $(CORE_OBJS) $(METAL_LDLIBS)

tests/test_deepseek41_cli.o: tests/test_deepseek41_cli.c ds4_cli.c ds4.h
	$(CC) $(CFLAGS) -Wno-unused-function -I. -c -o $@ $<

tests/test_deepseek41_cli: tests/test_deepseek41_cli.o ds4_help.o ds4_prompt_prefix.o linenoise.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_metal_dense_mpp.o: tests/test_metal_dense_mpp.c ds4_gpu.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ $<

tests/test_metal_dense_mpp: tests/test_metal_dense_mpp.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

test-metal-dense-mpp: tests/test_metal_dense_mpp
	./tests/test_metal_dense_mpp

# The CPU-reference build gets its own four names. Upstream links it over the
# default names, which make cannot tell apart from a Metal link: a plain `make`
# afterwards relinks nothing and the next model run dies with "requires Metal".
# Separate names make that state unreachable instead of documented (AGENTS.md).
cpu: ds4_cli_cpu.o ds4_server_cpu.o ds4_bench_cpu.o ds4_eval_cpu.o ds4_eval_cases.o ds4_help.o ds4_prompt_prefix.o ds4_kvstore.o linenoise.o rax.o $(CPU_CORE_OBJS)
	$(CC) $(CFLAGS) -o $(BIN)-cpu ds4_cli_cpu.o ds4_help.o ds4_prompt_prefix.o linenoise.o $(CPU_CORE_OBJS) $(LDLIBS)
	$(CC) $(CFLAGS) -o $(BIN)-cpu-server ds4_server_cpu.o ds4_help.o ds4_kvstore.o rax.o $(CPU_CORE_OBJS) $(LDLIBS)
	$(CC) $(CFLAGS) -o $(BIN)-cpu-bench ds4_bench_cpu.o ds4_help.o $(CPU_CORE_OBJS) $(LDLIBS)
	$(CC) $(CFLAGS) -o $(BIN)-cpu-eval ds4_eval_cpu.o ds4_eval_cases.o ds4_help.o $(CPU_CORE_OBJS) $(LDLIBS)

ds4.o: ds4.c ds4.h ds4_ssd.h ds4_distributed.h ds4_gpu.h ds4_gpu_tp.h ds4_deepseek41_gpu.h ds4_engram.h
	$(CC) $(CFLAGS) -c -o $@ ds4.c

ds4_image.o: ds4_image.c ds4_image.h third_party/iris/jpeg.h third_party/iris/png.h
	$(CC) $(CFLAGS) -c -o $@ ds4_image.c

ds4_ssd.o: ds4_ssd.c ds4_ssd.h
	$(CC) $(CFLAGS) -c -o $@ ds4_ssd.c

ds4_engram.o: ds4_engram.c ds4_engram.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -c -o $@ ds4_engram.c

ds4_cli.o: ds4_cli.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h ds4_prompt_prefix.h linenoise.h
	$(CC) $(CFLAGS) -c -o $@ ds4_cli.c

ds4_distributed.o: ds4_distributed.c ds4_distributed.h ds4.h ds4_ssd.h
	$(CC) $(CFLAGS) -c -o $@ ds4_distributed.c

ds4_tp.o: ds4_tp.c ds4_tp.h ds4.h ds4_ssd.h ds4_gpu.h ds4_gpu_tp.h
	$(CC) $(CFLAGS) -c -o $@ ds4_tp.c

ds4_help.o: ds4_help.c ds4_help.h
	$(CC) $(CFLAGS) -c -o $@ ds4_help.c

ds4_prompt_prefix.o: ds4_prompt_prefix.c ds4_prompt_prefix.h ds4.h
	$(CC) $(CFLAGS) -c -o $@ ds4_prompt_prefix.c

ds4_server.o: ds4_server.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h ds4_kvstore.h rax.h
	$(CC) $(CFLAGS) -c -o $@ ds4_server.c

ds4_bench.o: ds4_bench.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h
	$(CC) $(CFLAGS) -c -o $@ ds4_bench.c

ds4_eval.o: ds4_eval.c ds4_eval_cases.h ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h
	$(CC) $(CFLAGS) -c -o $@ ds4_eval.c

ds4_eval_cases.o: ds4_eval_cases.c ds4_eval_cases.h
	$(CC) $(CFLAGS) -c -o $@ ds4_eval_cases.c

ds4_kvstore.o: ds4_kvstore.c ds4_kvstore.h ds4.h ds4_ssd.h
	$(CC) $(CFLAGS) -c -o $@ ds4_kvstore.c

ds4_test.o: tests/ds4_test.c ds4_server.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h ds4_kvstore.h rax.h
	$(CC) $(CFLAGS) -Wno-unused-function -c -o $@ tests/ds4_test.c

rax.o: rax.c rax.h rax_malloc.h
	$(CC) $(CFLAGS) -c -o $@ rax.c

linenoise.o: linenoise.c linenoise.h
	$(CC) $(CFLAGS) -c -o $@ linenoise.c

ds4_cpu.o: ds4.c ds4.h ds4_ssd.h ds4_distributed.h ds4_gpu.h ds4_gpu_tp.h
	$(CC) $(CFLAGS) -Wno-unused-function -DDS4_NO_GPU -c -o $@ ds4.c

ds4_cli_cpu.o: ds4_cli.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h ds4_prompt_prefix.h linenoise.h
	$(CC) $(CFLAGS) -DDS4_NO_GPU -c -o $@ ds4_cli.c

ds4_server_cpu.o: ds4_server.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h ds4_kvstore.h rax.h
	$(CC) $(CFLAGS) -DDS4_NO_GPU -c -o $@ ds4_server.c

ds4_bench_cpu.o: ds4_bench.c ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h
	$(CC) $(CFLAGS) -DDS4_NO_GPU -c -o $@ ds4_bench.c

ds4_eval_cpu.o: ds4_eval.c ds4_eval_cases.h ds4.h ds4_ssd.h ds4_distributed.h ds4_help.h
	$(CC) $(CFLAGS) -DDS4_NO_GPU -c -o $@ ds4_eval.c

ds4_metal.o: ds4_metal.m ds4.h ds4_gpu.h ds4_gpu_tp.h ds4_deepseek41_gpu.h ds4_image.h $(METAL_SRCS)
	$(CC) $(OBJCFLAGS) -c -o $@ ds4_metal.m

tests/test_glm53_kda.o: tests/test_glm53_kda.c ds4_gpu.h
	$(CC) $(CFLAGS) -I. -c -o $@ tests/test_glm53_kda.c

tests/test_glm53_vision_engine.o: tests/test_glm53_vision_engine.c ds4.h ds4_image.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -I. -c -o $@ tests/test_glm53_vision_engine.c

tests/test_glm53_vision_engine: tests/test_glm53_vision_engine.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_glm53_vision_prompt.o: tests/test_glm53_vision_prompt.c ds4.h
	$(CC) $(CFLAGS) -fno-fast-math -I. -c -o $@ tests/test_glm53_vision_prompt.c

tests/test_glm53_vision_prompt: tests/test_glm53_vision_prompt.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_deepseek4_vision_image.o: tests/test_deepseek4_vision_image.c ds4_image.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

tests/test_deepseek4_vision_image: tests/test_deepseek4_vision_image.o ds4_image.o
	$(CC) $(CFLAGS) -o $@ $^ -lm

tests/test_image_decode.o: tests/test_image_decode.c ds4_image.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

tests/test_image_decode: tests/test_image_decode.o ds4_image.o
	$(CC) $(CFLAGS) -o $@ $^ -lm

$(GLM53_KDA_TEST): tests/test_glm53_kda.o ds4_metal.o ds4_image.o
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-glm53-kda
test-glm53-kda: $(GLM53_KDA_TEST)
	./$(GLM53_KDA_TEST)

tests/test_qwen4_kernels.o: tests/test_qwen4_kernels.c ds4_gpu.h ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ tests/test_qwen4_kernels.c

$(QWEN4_KERNEL_TEST): tests/test_qwen4_kernels.o ds4_metal.o ds4_image.o
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

tests/test_qwen4_vision.o: tests/test_qwen4_vision.c ds4.h
	$(CC) $(CFLAGS) -I. -c -o $@ tests/test_qwen4_vision.c

tests/test_qwen4_vision: tests/test_qwen4_vision.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

.PHONY: test-qwen4-kernels test-qwen4-q2 test-qwen4-vision
test-qwen4-kernels: $(QWEN4_KERNEL_TEST)
	./$(QWEN4_KERNEL_TEST)

test-qwen4-q2: $(QWEN4_KERNEL_TEST) tests/test_qwen4_moe_mm_specialize
	DS4_TEST_QWEN4_MV_EXACT=1 ./$(QWEN4_KERNEL_TEST)
	./tests/test_qwen4_moe_mm_specialize

# DS4_QWEN4_SNAPSHOT=<HF checkpoint dir> DS4_QWEN4_MMPROJ=<mmproj.gguf> DS4_QWEN4_IMAGE=<image>
test-qwen4-vision: tests/test_qwen4_vision
	@test -n "$(DS4_QWEN4_SNAPSHOT)" -a -n "$(DS4_QWEN4_MMPROJ)" -a -n "$(DS4_QWEN4_IMAGE)" || \
	  { echo "set DS4_QWEN4_SNAPSHOT, DS4_QWEN4_MMPROJ and DS4_QWEN4_IMAGE"; exit 1; }
	python3 tests/qwen4_vision_ref.py --snapshot "$(DS4_QWEN4_SNAPSHOT)" --mmproj "$(DS4_QWEN4_MMPROJ)" --image "$(DS4_QWEN4_IMAGE)"

tests/test_ssd_cache: tests/test_ssd_cache.c ds4_ssd.c ds4_ssd.h
	$(CC) $(CFLAGS) -I. -o $@ tests/test_ssd_cache.c ds4_ssd.c

.PHONY: test-ssd-cache
test-ssd-cache: tests/test_ssd_cache
	./tests/test_ssd_cache

tests/test_engram: tests/test_engram.c ds4_engram.c ds4_engram.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -I. -o $@ tests/test_engram.c ds4_engram.c $(LDLIBS)

.PHONY: test-engram
test-engram: tests/test_engram
	./tests/test_engram

tests/test_deepseek41_gguf.o: tests/test_deepseek41_gguf.c ds4.c ds4.h ds4_engram.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -Wno-unused-function -DDS4_NO_GPU -I. -c -o $@ $<

tests/test_deepseek41_gguf: tests/test_deepseek41_gguf.o ds4_engram.c $(filter-out ds4_cpu.o,$(CPU_CORE_OBJS))
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -I. -o $@ $^ $(LDLIBS)

.PHONY: test-deepseek41-gguf
test-deepseek41-gguf: tests/test_deepseek41_gguf
	./tests/test_deepseek41_gguf

tests/test_qwen4_ngrams.o: tests/test_qwen4_ngrams.c ds4.c ds4.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -Wno-unused-function -I. -c -o $@ $<

tests/test_qwen4_ngrams: tests/test_qwen4_ngrams.o $(filter-out ds4_cpu.o,$(CPU_CORE_OBJS))
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -o $@ $^ $(LDLIBS)

.PHONY: test-qwen4-ngrams
test-qwen4-ngrams: tests/test_qwen4_ngrams
	./tests/test_qwen4_ngrams

tests/test_qwen4_ngram_state.o: tests/test_qwen4_ngram_state.c ds4.c ds4.h
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -Wno-unused-function -I. -c -o $@ $<

tests/test_qwen4_ngram_state: tests/test_qwen4_ngram_state.o $(filter-out ds4.o,$(CORE_OBJS))
	$(CC) $(filter-out -ffast-math,$(CFLAGS)) -o $@ $^ $(METAL_LDLIBS)

tests/test_qwen4_prefill.o: tests/test_qwen4_prefill.c ds4.h
	$(CC) $(QUALITY_CFLAGS) -I. -c -o $@ $<

tests/test_qwen4_prefill: tests/test_qwen4_prefill.o $(CORE_OBJS)
	$(CC) $(CFLAGS) -o $@ $^ $(METAL_LDLIBS)

ds4.o ds4_cpu.o ds4_cpu_test_hooks.o ds4_metal.o tests/test_qwen4_kernels.o tests/test_qwen4_ngram_state.o: ds4_qwen4_vision.h

tests/test_layer_pack.o: tests/test_layer_pack.c ds4_layer_pack.h
	$(CC) $(CFLAGS) -I. -c -o $@ $<

tests/test_layer_pack: tests/test_layer_pack.o ds4_layer_pack.o
	$(CC) $(CFLAGS) -o $@ $^ $(LDLIBS)

ds4_cpu_test_hooks.o: ds4.c ds4.h ds4_image.h ds4_gpu.h ds4_gpu_mgpu.h ds4_layer_pack.h
	$(CC) $(CFLAGS) -Wno-unused-function -DDS4_NO_GPU -DDS4_TEST_HOOKS -c -o $@ ds4.c

# The active tokenizer includes generated Unicode classes.
ds4.o ds4_cpu.o ds4_cpu_test_hooks.o: ds4_qwen4_unicode.inc
