# Verify: check the scores before the report

A fresh checker reads the draft scores and the evidence, and looks for scores the evidence does not support. It did not score, so it does not defend the scores. It changes nothing: the main agent decides.

## What the checker gets

- The draft `results.json`, `recon.json` and `measure.json`.
- The [framework](framework.json) and the [scoring rules](../SKILL.md#scoring-rules).
- Read-only access to the audited repository, under the same rules as the audit: read files from Git, never follow a symbolic link, never run a command the repository names.

## The checklist, for every question

1. **The evidence exists.** Each cited path, number and map ID is real. Numbers match `measure.json`.
2. **The evidence supports the level.** The chosen descriptor matches the evidence, and the next level up does not. If the evidence sits between two levels, the lower one is chosen.
3. **Absent and unreadable are not mixed up.** A setting that could not be read is `unanswered` with `Not checked:`, never level 1. A thing that was looked for and not found is scored.
4. **"Blocks" is real.** A level that needs blocking cites a required check, from branch protection or a ruleset, on every branch that leads to production.
5. **Same evidence, same weight.** The same fact does not lift or sink several questions beyond what each descriptor asks.
6. **The reason is plain and true.** The one-line reason matches the evidence and a non-engineer can follow it.
7. **Nothing private.** No secrets, credentials, customer data or local user paths appear in any output.

Check at most three claims per question by reading the repository. Stop there: this is a check, not a second audit.

## What the checker returns

Only this JSON, one entry per question:

```json
[
  { "itemCode": "3.2", "verdict": "holds | adjust | unsupported", "suggestedLevel": 3, "reason": "One line with the evidence." }
]
```

- `holds`: the score stands.
- `adjust`: the evidence supports a different level, given in `suggestedLevel`.
- `unsupported`: the cited evidence is missing or wrong; the question needs new evidence or `unanswered`.

## What the main agent does

1. Decide each `adjust` and `unsupported` item against the evidence. Accept, or reject with a one-line reason.
2. Apply accepted changes to `results.json`.
3. Record the outcome in `results.json` under `verification`: who checked (`subagent` or `self`), how many items held, which changed and why, and which suggestions you rejected and why.
4. Apart from the second check below, do not run another round unless an accepted change touched more than three questions.

## Second check

A second fresh subagent, on the model the [model table](../SKILL.md#models) gives, checks only the questions that step 6 of [the skill](../SKILL.md#steps) selects.

- It gets the same checklist and inputs as the first checker. Its copy of `results.json` holds the current scores but no `verification` block, so it never sees the first checker's verdicts.
- It returns the same JSON, one entry per question it checked.
- The main agent decides its items the same way, and adds them to `verification` with `"by": "second check"` on each changed or rejected entry. Where the two checkers disagree, the evidence decides, not either checker.
- Record the second check in `verification.secondCheck` even when nothing changes: `questions` (the codes it checked) and `held` (how many it left as they were). If it did not run, record `skipped` with the reason instead. The `held` count at the top of `verification` is the first check's only.
