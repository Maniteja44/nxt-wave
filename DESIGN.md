# Design notes: why the system is built this way

## 1. Framing the problem

The deliverable is not one lesson. It is a system that decides **on its own** whether a lesson is good enough to put in front of a beginner. I planned the work around three questions:

1. **What does "good enough" mean for *this* learner?** The learner reads English as a second language, has no AI background, and has used ChatGPT but has never thought about how it works. "Good" means *correct*, *understandable on the first read*, and *taught through things they already know*.
2. **How can a machine check that reliably?** LLM judges are flexible but noisy, and they can be persuaded. Code checks are reliable but narrow. Neither is enough alone.
3. **What happens when the content isn't good enough?** Revise in a targeted way, re-check everything, stop after a bounded number of tries, and never ship something that hasn't passed.

## 2. Architecture

```
topic spec (ground truth) ──► plan ─► write ─► EVALUATE ─pass─► ship
                                          ▲        │fail
                                          └─revise─┘ (max 2)
                                                   │still failing
                                                   └─► block: best attempt + log → human
after every run: learn (memory) ─► next run's prompts + rubric
```

**Why LangGraph?** The workflow is a state machine with a cycle and a conditional exit, which is exactly what LangGraph models. Each node is a plain function over typed state. Routing lives in one pure function (`route_after_eval`), which makes the termination guarantee easy to read and easy to unit test. It also leaves room to add a human-approval interrupt or checkpointing later without restructuring.

**Why a separate plan step?** Writing in one shot tends to skip key points or pick a generic analogy. The planner first commits to an analogy, a concrete worked example (documents → question → retrieved chunks → answer), and a key-point-to-section map. The writer then has one job: write that plan in simple English.

**Why a fixed lesson template?** For a beginner, the order matters. The template is *problem → idea → mechanism → worked example → limits → recap → glossary → self-check*. Showing the problem first (LLMs hallucinate and don't know your data) gives the learner a reason to care before introducing a new term. A fixed template also makes structure deterministically checkable.

## 3. The topic spec is the ground truth

`topics/rag.yaml` holds the 8 key points, the reference facts, the known misconceptions, and the jargon list. **The writer and the evaluator are both anchored to it.** This matters because without it, the accuracy judge would grade the lesson against the same model knowledge that wrote it, and a shared blind spot would pass silently. With a curated spec, accuracy means "consistent with facts a human checked".

For a topic with no curated spec, the system drafts one with the LLM, saves it under `topics/generated/`, marks it `verified: false`, and shows that warning in the rejection log. The system is honest about what it has not verified.

## 4. The evaluator

### 4.1 Binary checks, all must pass

The brief asks for hard pass/fail checkpoints. I made the ship gate **AND over all 13 checks**: no weighted score that lets strong prose hide one factual error. Each check states its pass condition in one sentence (`rubric.py`). This makes failures actionable: "glossary is missing *embedding*" can be fixed, while "score 7.2/10" cannot.

### 4.2 Hybrid: code where possible, LLM only where necessary

| Use **code** when "good" can be measured | Use an **LLM judge** when it needs understanding |
|---|---|
| Structure and section order, length, readability, sentence length, glossary completeness, quiz format, known-misconception tripwire | Accuracy, key-point coverage, jargon explained *in context*, plain language and idioms, quality of analogy and example, teaching flow |

Code checks are free, instant, reproducible, and **cannot be argued out of a verdict**. They also run with no API key (`evaluate --code-only`), which is how I calibrated thresholds on a hand-written fixture lesson.

**Threshold reasoning:**
- **Flesch-Kincaid grade ≤ 8 and average sentence ≤ 15 words.** These are standard plain-language targets for second-language readers. FK is implemented in-repo (no dictionary download), so it behaves the same on every machine.
- **No sentence over 30 words.** Average length can hide one monster sentence, and one monster sentence is where a learner gives up.
- **900–2,600 words.** That is enough room to cover 8 key points with an example, but not so much that it overwhelms. (The writer is told to aim for 2,200 or less, which leaves margin.)
- **Glossary coverage.** Every jargon term used must appear in the glossary. This is checked against a regex list from the spec plus terms learned from memory.

### 4.3 The misconception tripwire

This is a deterministic, negation-aware filter for the most harmful RAG misconceptions: "RAG retrains the model", "the model permanently learns your docs", "RAG removes all hallucinations", "always correct", "the vector DB writes the answer". A sentence trips only if it matches a pattern, mentions RAG or retrieval (where relevant), is not a question, and contains no negation or contrast word ("not", "unlike", "than", "instead"...). So "RAG does not retrain the model" and "RAG is cheaper than retraining" pass. The LLM accuracy judge remains the primary accuracy check; the tripwire is a second line of defence that cannot be talked out of a verdict.

**Trade-off:** a false positive costs one extra revision, while a false negative puts a misconception in front of a beginner. That asymmetry justifies a strict tripwire.

### 4.4 Making LLM judges trustworthy

- **One judge per check, at temperature 0.** Each judge has a narrow criterion, so verdicts don't bleed into each other and the same lesson gets the same verdict. The judges run in parallel threads.
- **The judge must prove its verdict.** Every FAIL must quote the lesson. Quotes are **verified in code** (exact or ≥ 85% fuzzy match). If none of a judge's quotes exist, it is asked once more to re-read the lesson.
- **Coverage cannot be faked.** The `key_points` judge must give a quote for each covered point. If a quote isn't in the lesson, that point is treated as *not covered* and the check fails, even if the judge said PASS. This blocks the most common judge failure: confidently asserting coverage.
- **Structured output is reconciled with the verdict.** If the jargon judge marks any term `explained_at_first_use: false` but says PASS, code overrides it to FAIL.
- **A judge error counts as FAIL.** If the system can't verify a lesson, it doesn't ship it.
- **A separate judge model is supported.** Setting `JUDGE_PROVIDER` / `JUDGE_MODEL` reduces self-preference bias.
- **The judge is told to fail only for concrete problems a real beginner would hit, not style preferences.** This keeps strictness from turning into endless rejection.

## 5. Regeneration strategy

- **Collect all failures in one pass, then revise once.** With only 2 retries, fixing one issue per retry would waste them.
- **Targeted revision, not a rewrite.** The reviser gets the previous lesson, each failed check's criterion, the reason, the exact problem text, and a fix instruction, plus **the list of checks that already pass** with an instruction not to break them. It also returns a change list, which goes into the rejection log, so you can see *what was changed on retry*.
- **Re-run every check on every attempt.** Passes are never cached, so a regression introduced by a revision is caught.
- **Bounded loop.** At most `1 + max_retries` (≤ 3) evaluations; `max_retries` is capped at 2 in code.
- **If it never passes, it blocks.** The system picks the best attempt (fewest accuracy failures first, then fewest failures overall, then the latest), labels it **NOT SHIPPED**, saves it as `lesson_NEEDS_REVIEW.md`, and exits with code 2. A plausible-but-failing lesson is never silently shipped.

## 6. Memory and self-evolution

Memory is a single JSON file (`memory/memory.json`): human-readable, diff-able in git, and written atomically. A vector store would be overkill at this scale; the interface in `memory.py` is small enough to swap later.

| Mechanism | Trigger | Effect on future runs |
|---|---|---|
| **Learned writing rules** (prompt evolution) | After each run with failures, a reflector LLM turns the failures into ≤ 3 general rules, or reinforces existing ones instead of duplicating them | The top 12 rules (human rules first, then the most reinforced) are injected into the planner and writer prompts |
| **Rule effectiveness tracking** | Each run records whether a rule's target check passed *on the first attempt* while the rule was applied | After 3 first-attempt failures and 0 passes, the rule is flagged *ineffective* and the reflector is asked to rewrite it. Rules that don't work don't just pile up. |
| **Learned jargon** (rubric evolution) | Judges flag hard words; they are counted across runs | After 2 runs, a word becomes an **enforced** jargon term, so the deterministic glossary check now requires it |
| **Judge calibration** | Human feedback such as "false positive on X" | A calibration note is injected into that judge's prompt |
| **Human feedback** | `feedback "free text"` (LLM-routed) or direct flags (`--rule`, `--jargon`, `--calibrate`) | Becomes rules, jargon, or calibration as appropriate |
| **Stats** | Every run | Per-check first-attempt failure rates show which part of the generator is weakest. The first-attempt pass rate is the headline metric for "is it improving?" |

Failures from a reflector call never stop learning: if that call fails, a fallback writes one rule per failed check.

## 7. Trade-offs and known limits

- **Cost vs reliability.** There are 6 separate judges instead of 1 combined judge. That means more calls (about 8 to 25 per run), but each verdict is independent and easier to debug. I chose reliability; the code checks keep the judge count low.
- **Strictness vs throughput.** All-must-pass with strict judges will sometimes BLOCK. That is the intended behaviour for learning content: a blocked lesson costs a human review, while a wrong lesson costs a confused learner.
- **Readability formulas are rough.** FK counts syllables, not meaning. That is why `plain_language` and `jargon_explained` exist as LLM checks on top of it.
- **The judges are still LLMs.** Quote verification and code reconciliation reduce, but do not remove, judge error. The next step would be an **evaluator test set**: a labelled set of good and bad lessons to measure each judge's precision and recall, and to re-run whenever a judge prompt changes. The `--inject-error` modes and `tests/fixtures` are the start of that set.
- **A spec is needed for real accuracy.** Auto-drafted specs for new topics are clearly marked unverified.

## 8. What I would add next

1. An evaluator benchmark (labelled lessons → judge precision and recall) run in CI on every prompt change.
2. Pairwise A/B checks so that a new learned rule is kept only if it improves first-attempt pass rate on a fixed topic set.
3. A LangGraph human-approval interrupt before publishing, plus feedback captured directly from real learners (for example, "which sentence confused you?") feeding the memory loop.
4. Translation or bilingual glossary support (for example, Hindi or Telugu glosses for key terms) for this learner group.
