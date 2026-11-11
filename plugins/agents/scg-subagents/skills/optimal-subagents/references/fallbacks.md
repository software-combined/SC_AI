# Model-unavailable fallback

A fallback preserves the task, acceptance checks and data constraints while
changing the model. It is not permission to silently lower the assigned reasoning
level, change accounts/credentials, broaden tool authority or relax a required
review gate. Choose by workload and comparable model cost, independently of
subscriptions and billing arrangements.

## Classify the failure first

- **Missing model or unsupported identifier:** verify the active catalogue and
  supported aliases. Resolve the selected model's callable id; if unavailable,
  move to a different eligible model below. A hidden picker row is not proof of
  availability, and a model name in a prompt is not served-identity evidence.
- **Unsupported selected effort:** choose another eligible model/effort pair.
  Do not silently downgrade the same model's effort.
- **Model-specific rate/capacity limit or transient provider error:** respect a
  supplied retry delay if waiting is practical; otherwise use the next eligible
  model. Do not repeat immediate retries or continue after a known budget limit.
- **Shared transport/router/tool failure:** a malformed or encrypted assignment
  rejected before inference may affect every candidate. Stop cycling models;
  report the common failure and continue in the parent where possible. Resume
  delegation only after evidence that the shared problem is resolved.
- **Authentication, billing, account or policy denial:** do not change credentials,
  accounts or data-use policy to bypass it. A different model is eligible only
  when already authorized and unaffected by the denial. Otherwise report the gap.
- **Model answered but failed acceptance:** this is a capability/quality problem,
  not unavailability. Give one focused correction when worthwhile, or escalate
  the difficult slice using the main selection guide. Preserve the failed check.

## Default fallback orders

For cybersecurity, use the workload choices and qualification rules in
[security model selection](cybersecurity.md) before these general ladders.
Preserve its quality floor. A policy refusal is not a capacity failure and
does not trigger automatic model cycling.

Start after the unavailable model in the applicable row; when it is absent from
that row, start at the first eligible choice. Skip known unavailable candidates
without probing them. Read the catalogue for exact ids, prices and evidence gaps.
These are availability ladders, not claims that every successor is more capable.

| Workload | Ordered candidates, each with its fixed effort |
| --- | --- |
| Extraction, simple edits, reconnaissance | Muse Ember `max` → GLM Flash `max` → DeepSeek Flash 1017 `max` → Luna `max` for mechanical work → Terra 6.1 `high` |
| Repository work, scripts, tool workflows | Terra 6.1 `max` → Sol 6.1 `max` → Kimi K3.1 Pro `max` or Carbon `high`; Ember or DeepSeek 1017 `max` only for bounded worker scope |
| Business analysis, synthesis, documents | Ember `max` → Sol 6.1 `high` → Sonnet 5.5 `max` → Opus 5.5 `max`; skip draft-only candidates for demanding polished deliverables |
| UI design direction | Carbon `high` → Opus 5.5 `max` → Sol 6.1 `max`; qualify visual judgement and preserve human taste decisions |
| UI implementation from an agreed design | DeepSeek Flash 1017 `max` → Terra 6.1 `max` → Sol 6.1 `max`; preserve design references and rendered acceptance |
| Images or other multimodal input | Gemini 3.8 Flash `high` → GPT-6.1 Terra `max` → Gemini 4 Carbon `high` → GPT-6 Astra `max`; each candidate must actually accept the required input through the current tools |
| Long-document extraction/reasoning | DeepSeek Flash 1017 `max` → GPT-6.1 Terra `max` → GPT-6.1 Sol `max` → Kimi K3.1 Pro `max`; retain source citations and context-capacity checks |

For a premium model that is unavailable, reconsider the workload's cheapest
eligible candidate rather than automatically moving to another premium model.
Escalate to Astra, Opus or Fable only for a specific unresolved capability need.
Contributor is never an automatic fallback for standard Muse: its own data-use
eligibility and representative-task qualification must already be established.
Legacy models and specialists follow the appropriate workload row as well.

Do not choose a text-only or shorter-context substitute for a task that requires
capabilities it lacks. Split or reduce context only when the task's evidence and
acceptance checks remain valid; otherwise report that no eligible fallback exists.

## Execute and report

Keep a tried-model set for the assignment. Default to at most two alternative
model attempts after the original failure; stop sooner for a shared failure,
known budget limit or no eligible candidate. Longer retries need a task-specific
reason and authorized cost envelope, not an endless walk through the catalogue.

Carry forward the bounded brief, relevant artifacts, failure evidence and
acceptance check instead of restarting research. Do not overlap writers: stop
the failed child's turn and inspect partial changes before transferring ownership.
Record requested and returned identity; absent served identity is `unverified`.

Tell the parent/user the material substitution, reason, fixed effort and remaining
capability or cost uncertainty. A useful report is: “GLM 5.3 Flash was unavailable;
used DeepSeek V4.1 Flash at max. The same acceptance checks passed.” Never say
that checks passed when the fallback only started or returned an answer.

**Exact requirements:** when the user or an applicable instruction explicitly
pins an exact model for a pre-commit lane, report unavailability and preserve the work. A fallback
requires explicit authorization for that exception; never silently replace it
or change permanent reviewer policy. Otherwise the installed review policy's
listed availability fallbacks are permitted. A past one-time exception is not
permission to bypass an exact requirement in future sessions.
