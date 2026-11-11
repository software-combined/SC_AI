# Planning advisor: review a plan before action

Use one independent, read-only child when the user requests plan review, or a
multi-step plan has material dependencies, costly rework or uncertain evidence
that an independent critique can resolve. Skip routine one-step actions unless
the user asks. This advisory role does not replace required pre-commit reviews,
domain-specific checks or user authorization.

## Model choice

Evidence refreshed 2026-11-11. These are provisional choices, not measured local
plan-review success rates. Choose capability and comparable cost independently
of subscriptions or account billing.

| Situation | Model and fixed effort | Reason |
| --- | --- | --- |
| Bounded general planning advisor | `meta/muse-ember` at `max` | Inexpensive reasoning and automation candidate; no direct plan-critique result |
| Concrete repository/tool plan, bounded and low consequence | `deepseek/deepseek-v4.1-flash-1017` at `max` | Cheap tool-workflow reasoning with objective verification |
| Intricate operational plan or unresolved material finding | `openai/gpt-6.1-sol` at `max` | Stronger current reasoning and terminal proxies |
| Remaining high-impact uncertainty after Sol | `openai/gpt-6-astra` at `max` | Focused escalation when the consequence justifies the premium |

Read [security selection](cybersecurity.md) for any security plan; its
qualification rules take precedence over this table. Finance, destructive
actions and production cutovers retain their owner and specialist gates.
No advisor can issue an authorization or integrity acceptance on their behalf.

For availability, use the applicable [workload fallback order](fallbacks.md),
preserving domain requirements and fixed effort. Resolve the actual callable
identifier from the active tools. Use a matching GPT subscription route first
when host instructions require it. Native `gpt-6-sol` is a different version
from GPT-6.1 Sol; never transfer scores or infer access from a picker row.
Do not automatically substitute Muse Contributor: its data-use terms and exact
tier qualification differ. Record requested and served identity; absent serving
identity is `unverified`. Stop cycling models on a shared transport failure.

## What to send and receive

Give the child the proposed plan, goal and first observable success proof,
constraints, known authorization, relevant canonical sources, and unresolved
questions. Use the [delegation tools](tool-guide.md); no recursive delegation.
Allow only the read-only sources needed for this review. The parent can continue
independent preparation, but should resolve material findings before the actions
whose assumptions they challenge.

Suggested brief; replace the brace fields with the actual request before sending:

> {Selected model} {Fixed effort} — Planning advisor review for {real task or plan context}.
>
> Independently review this plan before action. Work read-only: no edits,
> system mutations, messages to stakeholders or delegated execution. Check the
> goal and success proof, evidence and assumptions, sequence and dependencies,
> ownership and approval boundaries, simplest adequate approach, realistic
> failure paths, rollback where relevant, and verification. Report only material
> actionable concerns, with affected step, evidence, impact and smallest remedy.
> Separate pre-action blockers from later checks. Do not invent evidence, add
> speculative scope or block on optional polish. Return READY, READY WITH FIXES
> or BLOCKED, with unresolved uncertainty. Your advice grants no authorization.

The parent adjudicates each concern against source and scope, applies accepted
corrections and verifies the result. READY WITH FIXES means identified corrections
still need disposition; it does not approve the uncorrected plan. Ask one focused
follow-up only when material uncertainty remains; avoid repeated full reviews.

## Evidence and qualification

The refresh found no direct head-to-head qualification of these exact models
critiquing supplied plans. [Ember](https://artificialanalysis.ai/models/muse-ember)
scores 36.02 on Intelligence Index v5.0.1, with 68.08% on AutomationBench-AA.
[Sol 6.1](https://artificialanalysis.ai/models/gpt-6-1-sol) scores 54.61 and
56.06% on Terminal-Bench 4.0. These are broad proxies, not plan-review accuracy
or cost per accepted plan. The [catalogue](catalogue.md) records current prices,
workload evidence and exclusions. No paid comparative evaluation was run.

Before promoting a model on local evidence, compare the same small frozen set
of sanitized flawed and valid plans with hidden, human-checked ground truth.
Include dependency errors, missing verification/rollback, unsupported evidence,
missing authority, and valid minimal plans. Fix acceptance criteria beforehand:
no missed critical authority/safety flaws or invented evidence, useful material
flaw recall and precision, and few false blockers on valid controls. Record scope
expansion, requested/served identity, tokens, route cost, latency and retries.
A small qualification set improves the routing prior; it is not a population
success-rate claim and does not authorize paid evaluations by itself.
