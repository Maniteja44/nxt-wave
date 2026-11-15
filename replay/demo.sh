#!/usr/bin/env bash
# Offline end-to-end demo: the "LLM" is pre-written responses in replay/run1 and replay/run2.
# Uses its own memory/output folders so it never touches your real memory/ or output/.
set -e
cd "$(dirname "$0")/.."
rm -rf replay/_memory replay/_runs replay/_output
export LLM_PROVIDER=replay LESSONGEN_MEMORY_DIR=replay/_memory LESSONGEN_RUNS_DIR=replay/_runs LESSONGEN_OUTPUT_DIR=replay/_output

echo "=== RUN 1: deliberate error injected + natural writing mistakes -> caught -> revised -> shipped"
REPLAY_DIR=replay/run1 python -m lessongen run --topic "Introduction to RAG" --inject-error misconception || true

echo; echo "=== RUN 2: same topic; rules learned in run 1 are now in the writer prompt"
REPLAY_DIR=replay/run2 python -m lessongen run --topic "Introduction to RAG" || true
grep -A4 "LESSONS LEARNED" replay/run2/_prompts/write__1.txt

echo; python -m lessongen memory
echo; echo "Run-1 rejection log: $(ls -d replay/_runs/*_rag | head -1)/rejection_log.md"
