# Choose models for a project roster

Choose each owner for the decisions it must make, then give bounded work to
cheaper workers. A mixed roster usually has a better cost/quality balance than
one model assigned to every role. These are **provisional starting candidates**,
checked 2026-11-11, not permanent defaults or local success-rate claims.
The [catalogue](catalogue.md) owns exact IDs, prices and benchmark identities.

## Select the owner and its workers

1. Start from the project's outcome, disciplines, phases and actual write areas.
   Reuse existing owners. Combine compatible duties on a small project; leave
   later roles planned until their work is ready. Do not create agents to fill
   this table or create a second owner for the same files.
2. Identify what the owner must judge: ambiguity, visual quality, source truth,
   implementation, independent evidence, or safe live operation. Separate that
   judgement from extraction, formatting, test execution and other bounded work.
3. Check required tools, input modalities, usable context, data terms and exact
   model/effort access. A text-only model cannot lead screenshot-based design
   review. A benchmark's million-token window does not enlarge the active route.
4. Choose the cheapest model **and effort** likely to pass that role's checks.
   Use the exact effort's measurements; high, xhigh and max are separate choices.
   More effort is not automatically better value. Exact human and host model
   instructions, specialist requirements and installed review gates still win.
5. Give each owner one representative useful assignment. Verify the returned
   artifact, evidence and side effects before extending its scope. This is a
   smoke test, not a success-rate estimate. Paid comparative trials require the
   existing spending authority; do not invent a budget.

## Starting roster by responsibility

Names below refer to the exact versions in the catalogue. Effort is explicit.
Role recommendations are inferences from relevant public evidence and the
work's demands; no benchmark directly establishes the best project manager.

| Role | Judgement the owner needs | Starting owner candidate | Economical worker scope | Qualification and escalation |
| --- | --- | --- | --- | --- |
| Project manager | Whole-project priorities, dependencies, ownership, authority and reliable status | GPT-6.1 Sol `xhigh` | Ember `max` extracts source records, checks links and drafts status from supplied facts | Reconcile contradictory records, sequence a cross-role change and name what is unverified. Sol `max` for unresolved complex dependencies; Astra/Fable only for a specific remaining gap. |
| Product | User needs, scope, trade-offs and testable acceptance | GPT-6.1 Sol `high` | Ember `max` groups feedback and extracts requirements | Produce a small complete outcome with measurable acceptance, including exclusions and decisions needing the human. Raise to Sol `xhigh` for substantial ambiguity. |
| UX/UI | Visual taste, coherent interaction, hierarchy, typography, brand fit and accessibility | Gemini 4 Carbon `high` | DeepSeek Flash 1017 `max` implements an approved design within its allocated source area | Inspect rendered desktop and narrow layouts. Carbon's reference-design evidence is preliminary. Opus 5.5 `max` is a premium alternative when a concrete visual gap justifies its cost. |
| Engineering | Correct implementation, architecture, debugging and tests | GPT-6.1 Terra `max` | Ember `max` handles bounded investigation/scripts; DeepSeek Flash 1017 `max` implements tightly specified slices | Deliver a realistic feature or bug fix with meaningful checks. Use Sol `max` for harder reasoning; Kimi K3.1 Pro `max` or Carbon `high` for a demonstrated terminal-work need. |
| QA and Verification | Independent test design, reproducible defects and honest evidence | GPT-6.1 Terra `high` for bounded checks | Luna `max` or Ember `max` runs mechanical checks and organises evidence | Find a seeded realistic defect and pass a clean control without weakening acceptance. Use Terra `max` or Sol `high`/`max` for ambiguous, cross-system or consequential verification. Keep author and verifier independent. |
| Release and Operations | Target and identity checks, state transitions, failure recovery and destination readback | GPT-6.1 Sol `high` for routine scoped work | Ember `max` investigates CI output, reads logs and assembles release evidence | Walk a failed deployment and recovery in an isolated environment. Use Sol `max` for difficult release qualification, partial writes or cutover reasoning. A cheaper helper cannot approve a release. |
| Data and Integrations | Schemas, identifiers, retries, partial writes and reconciliation | GPT-6.1 Sol `high`; `max` for migrations or consequential reconciliation | Ember `max` extracts mappings; Terra `max` builds a bounded transformation | Verify source-to-destination values, duplicate protection, timeout recovery and company boundaries. Finance/security rules apply where relevant; tool execution success is insufficient. |
| Research and Analysis | Source quality, synthesis, uncertainty and reproducible methods | GPT-6.1 Sol `high` | Ember `max` extracts from supplied sources; a verified search-capable worker gathers public sources | Check claim-to-source links, contradictory evidence and abstention on missing facts. Use Sol `max` for difficult quantitative or long-context reasoning. Search access must be real, not inferred from a model name. |
| Content and Documentation | Reader needs, factual fidelity, voice and artifact quality | Muse Ember `max` for source-grounded prose | Luna `max` checks links or formatting with deterministic validation | Use a factual source pack and inspect the rendered result. Ember has weak unaided recall, so supply facts. Use Sol `high` for complex synthesis or Sonnet 5.5 `max` for demanding polished deliverables. |
| Domain specialist | Field-specific rules, evidence, materiality and reserved human decisions | Select through the domain skill and current exact-version evidence | Cheap workers only extract and organise evidence with checkable answers | Finance/legal analysis can trial Sol `max` with domain checks. Critical security work follows the separate security selection rules. No role title, general index or model agreement grants approval authority. |

Architecture normally stays with Engineering. CI investigation can be temporary
work under Engineering or Release. A product review, visual review, independent
QA result, deployed result and human acceptance are different evidence.
Required pre-commit lanes keep their installed model/effort policy; this table
does not assign or replace those reviewers.

## UX/UI: qualify taste separately

Taste is the ability to choose and sustain a coherent visual direction for the
intended audience. It is not established by passing code tests, generic design
advice or the general intelligence index. Use the project's references and
human preferences to make it concrete.

The [Arena reference-based design leaderboard](https://arena.ai/leaderboard/code/webdev/reference-based-design)
was inspected in the browser on 11 November 2026:

| Model / measured effort | Score and 95% interval | Votes | Median task USD |
| --- | ---: | ---: | ---: |
| Gemini 4 Carbon `high` | 1839 ±36, preliminary | 407 | 1.62 |
| Opus 5.5 `max` | 1849 ±28 | 693 | 9.05 |
| Sonnet 5.5 `xhigh` | 1827 ±22 | 1,053 | 3.00 |
| Sol 6.1 `max` | 1777 ±22 | 979 | 1.86 |
| DeepSeek Flash 1017 `max` | 1672 ±13 | 2,713 | 0.12 |

These measure preferences for reference-driven generated interfaces. They do
not establish original art direction, usability, accessibility or the best
choice for this project's users. The leading intervals overlap. Arena task
costs are specific to that workload and are separate from AA suite costs,
token-price scenarios and subscription charges.

For a useful visual qualification, give the candidate a real page brief, the
existing design system and a small set of approved references. Ask for a
rendered page and a short explanation of its concrete choices. Inspect:

- Layout and hierarchy: the intended primary action is clear at both widths.
- Typography, spacing, colour and imagery: choices form one deliberate system
  and match the audience and references.
- Interaction: the complete task flow includes loading, empty, denied and error
  states; keyboard, focus, long text and text resize still work.
- Implementation fidelity: actual screenshots match the agreed direction and
  reuse existing tokens/components. The owner can identify and repair a visible
  mismatch instead of merely describing good design.

Let the human resolve a new material taste decision when precedent does not
settle it. Record the accepted direction once. The design owner keeps visual
direction and rendered acceptance; the code owner can use a cheaper worker for
the specified implementation. Give that worker visual references, component
rules, screenshots to match and a concrete acceptance check. Do not allow a
cheap implementation pass to silently redesign the product.

## Keep cost proportional to the work

Use [AA's comparable workload evidence](catalogue.md), not token price alone.
At the checked efforts, Ember costs about USD 0.14 per AA suite task; Terra high
0.26, Sol high 0.59, Sol xhigh 0.76, Terra max 0.96 and Sol max 1.27. These
figures explain the shortlist; they are neither subscription charges nor an
estimate of a persistent owner's actual task cost.

Choose a cheaper owner only when it can make the role's decisions reliably.
Luna fits small mechanically checked helpers; current evidence does not support
it as the default Engineering or QA owner. Ember is attractive for supplied-source
work, documentation and CI investigation, but its weak factual recall needs
source material. DeepSeek's frontend value supports implementation, not making
it the default manager, designer and specialist at once.

Give a capable owner bounded expensive decisions and cheap workers bounded
execution. Avoid whole-history forks, repeated broad recon, duplicate reviews
and premium models for formatting. Include the owner's context, tool loops,
failed attempts, verification, latency and rework in the comparison. Use actual
usage records when available; never invent a saved dollar total.

Very cheap OpenRouter endpoints may use different quantisation, providers or
privacy terms from the evaluated route. Check the selected endpoint and qualify
representative quality before treating its advertised price as the same result.
Do not silently change provider filters or retention requirements to get it.
For GPT, prefer matching subscription access when host instructions require it;
this access preference does not change the model-quality comparison.

## Record and apply the choice

Keep the selection in the existing roster, alongside the owner's write area,
phase and real chat identity. Add only what future assignments need:

```text
Role: Engineering
Model and effort: GPT-6.1 Terra, max
Why: Bounded implementation; exact terminal/repository evidence and lower cost
Worker scope: Ember max for bounded source investigation
Qualification: Candidate; representative feature and regression checks pending
Runtime setting: Desired; not yet read back
```

Replace the example with the project's actual choice and evidence. Record the
selected exact version, effort, reason, qualification result and escalation
trigger. Persistent owners and temporary workers can use different models.
Use one owner for combined roles whose model meets all of their capability
floors; do not average away the harder responsibility.

A roster edit does not change an existing chat's model or effort. When the user
also authorises changing those settings, use the host's supported controls on
the existing owner chat, then read back both fields. Preserve its identity,
history, work allocation and paused state. Distinguish desired, applied,
read-back and upstream-reported identity. If the host cannot set or verify a
field, report that exact limit; do not claim it changed or edit global defaults
to force one owner's selection.

Escalate after a named failure: a missed dependency, unsupported source claim,
failed regression, unreconciled value or unsatisfactory rendered design. Give
one focused correction when useful, then reconsider effort or the model using
matched evidence. Do not automatically lower effort after a failure. Reduce
cost after representative results pass, rather than leaving every owner on a
premium model forever. Reassess on version, price, route or task changes.

For custom roles, apply the same method. A game-design owner needs playable
mechanics and balance evidence; an art owner needs visual judgement and tools
that can inspect its assets; an audio owner needs auditionable output. Neither
text rankings nor a role label establish those capabilities.
