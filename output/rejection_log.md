# Rejection log - Introduction to RAG (Retrieval-Augmented Generation)

- **Run:** `20261115-133042_rag`
- **Writer model:** gemini/gemini-3.5-flash-lite  |  **Judge model:** gemini/gemini-3.8-flash
- **Topic spec:** `rag.yaml` (human-verified)
- **Outcome:** **BLOCKED** after 3 attempt(s) (max 3). Final lesson = attempt 1.
- **LLM usage:** 16 calls, 33,610 input / 8,481 output tokens, 2030s

## Scoreboard (every check, every attempt)

| Check | Kind | Dimension | Attempt 1 | Attempt 2 | Attempt 3 |
|---|---|---|---|---|---|
| `structure` | code | coherent teaching flow | ✅ | ✅ | ✅ |
| `length` | code | beginner-friendly language | ✅ | ✅ | ✅ |
| `readability` | code | beginner-friendly language | ✅ | ✅ | ✅ |
| `sentence_length` | code | beginner-friendly language | ✅ | ✅ | ✅ |
| `glossary_coverage` | code | clear, no unexplained jargon | ✅ | ✅ | ✅ |
| `misconception_tripwire` | code | accurate & grounded | ✅ | ✅ | ✅ |
| `quiz_format` | code | covers the key points | ✅ | ✅ | ✅ |
| `accuracy` | llm | accurate & grounded | ✅ | ✅ | ❌ |
| `key_points` | llm | covers the key points | ❌ | ❌ | ❌ |
| `jargon_explained` | llm | clear, no unexplained jargon | ✅ | ❌ | ✅ |
| `plain_language` | llm | beginner-friendly language | ✅ | ❌ | ❌ |
| `examples` | llm | teaches by example | ✅ | ✅ | ❌ |
| `flow` | llm | coherent teaching flow | ✅ | ✅ | ❌ |
| **Verdict** | | | REJECT | REJECT | REJECT |
| Words / FK grade | | | 988 / 6.52 | 979 / 6.68 | 1006 / 6.92 |

## Attempt 1 - REJECTED

**What failed and why:**

- ❌ **`key_points`** (llm · covers the key points) - Judge said PASS but could not quote where these are taught: kp6_why. All 8 key points from the topic specification are clearly taught and explained in the lesson.
  - fix requested: Teach these key points clearly and explicitly: kp6_why: Why it matters: the LLM can use private and up-to-date information without being retrained; answers are more grounded so hallucinations are reduced; the system can show which sources it used; updating knowledge is as simple as updating documents.

**Result of the retry:** fixed nothing; newly broke jargon_explained, plain_language.

## Attempt 2 - REJECTED

**What the reviser changed to get here (from the previous attempt's failures):**

- Fixed kp6_why check by explicitly adding sentences in the 'Why does this matter?' section to cover all required points: private and up-to-date info without retraining, reduced hallucinations due to grounded answers, source visibility, and easy updates via documents.

**What failed and why:**

- ❌ **`key_points`** (llm · covers the key points) - Judge said PASS but could not quote where these are taught: kp6_why. All key points from the topic spec are clearly taught with direct explanations and examples in the lesson.
  - fix requested: Teach these key points clearly and explicitly: kp6_why: Why it matters: the LLM can use private and up-to-date information without being retrained; answers are more grounded so hallucinations are reduced; the system can show which sources it used; updating knowledge is as simple as updating documents.
- ❌ **`jargon_explained`** (llm · clear, no unexplained jargon) - Judge error - cannot verify, so not shippable: [judge:jargon_explained] LLM call failed after retries: Connection error.
  - fix requested: (no content fix - judge failed)
- ❌ **`plain_language`** (llm · beginner-friendly language) - Judge error - cannot verify, so not shippable: [judge:plain_language] LLM call failed after retries: Connection error.
  - fix requested: (no content fix - judge failed)

**Result of the retry:** fixed jargon_explained; newly broke accuracy, examples, flow.

## Attempt 3 - REJECTED

**What the reviser changed to get here (from the previous attempt's failures):**

- fixed kp6_why: ensured all parts of why it matters (private and up-to-date info without retraining, reduced hallucinations, showing sources, and updating knowledge by updating documents) are clearly taught under 'Why does this matter?' and 'Key takeaways'

**What failed and why:**

- ❌ **`accuracy`** (llm · accurate & grounded) - Judge error - cannot verify, so not shippable: [judge:accuracy] LLM call failed after retries: Request timed out.
  - fix requested: (no content fix - judge failed)
- ❌ **`key_points`** (llm · covers the key points) - Judge error - cannot verify, so not shippable: [judge:key_points] LLM call failed after retries: Error code: 429
  - fix requested: (no content fix - judge failed)
- ❌ **`plain_language`** (llm · beginner-friendly language) - Judge error - cannot verify, so not shippable: [judge:plain_language] LLM call failed after retries: Error code: 429
  - fix requested: (no content fix - judge failed)
- ❌ **`examples`** (llm · teaches by example) - Judge error - cannot verify, so not shippable: [judge:examples] LLM call failed after retries: Error code: 429
  - fix requested: (no content fix - judge failed)
- ❌ **`flow`** (llm · coherent teaching flow) - Judge error - cannot verify, so not shippable: [judge:flow] LLM call failed after retries: Error code: 429
  - fix requested: (no content fix - judge failed)

## What the system learned from this run (memory updates)

- New rule g1 (for key_points): Every key point from the topic specification must be explicitly taught with its own dedicated heading, label, or clear paragraph.
