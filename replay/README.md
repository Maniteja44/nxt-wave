# Replay mode: you are the LLM

`LLM_PROVIDER=replay` swaps the model for pre-written response files. For the k-th call of a task it returns
`REPLAY_DIR/<task>__<k>.json|md`, for example `judge-accuracy__2.json`. It also saves every prompt it receives to
`REPLAY_DIR/_prompts/`. This lets the **whole real pipeline** run offline: the LangGraph loop, the code checks, quote
verification, revision, memory, and the rejection log.

- `run1/`: I acted as the writer and the six judges. The draft has three natural mistakes (an idiom, an unexplained
  term, and a 44-word sentence), plus the injected misconception. The judge verdicts are honest assessments of that draft, with
  exact quotes. The reviser fixes all of it. Result: REJECT, then SHIP, and 3 rules are learned.
- `run2/`: a fresh run. The 3 learned rules appear in the writer prompt, and the lesson ships on the first attempt.

Run it with `bash replay/demo.sh`.

If a response file is missing, the run stops and names the file it expected. The prompt is already saved in
`_prompts/`, so you can paste it into any chat model, save the reply under that name, and re-run. That is a manual "you are the LLM" loop.

**Important:** these responses were written by hand, not produced by a live API call. The rejection log labels the model as
`replay/...`. Use a real provider for the run you submit.
