# Compaction

Paths are relative to `router/`. See the [architecture map](../ARCHITECTURE.md) for the module overview and dependency direction.

## Experimental compaction

`jev-compaction` beside the router home's `channel` file controls the opt-in
Jev consumer. `ROUTER_HOME` overrides `~/.codex/mixed-model-router`; use the
home the service actually runs with. The router reads the file at every
external V1 or V2 compaction, without a restart. Trimmed lowercase `shadow`
and `on` are the only enabled values. Missing, empty, unreadable and all other
values, including `ON` and `1`, mean off.

Both enabled modes send selected history text to TypeSafe and bill the
external provider key. Confirm that this data sharing is permitted before
enabling either mode. Subscription threads and ordinary turns never call Jev.
`shadow` is the recommended first step: it logs proposed counts but leaves
the existing summary and input unchanged. `on` uses kept evidence as the
summary text inside the existing V1/V2 envelopes. There is no new capsule or
history store. Disabling the flag affects future compactions, not summaries
already produced.

Choose one mode command after selecting the home. macOS/Linux:

```sh
RH="${ROUTER_HOME:-$HOME/.codex/mixed-model-router}"
printf 'shadow\n' > "$RH/jev-compaction"  # Measure only, recommended first
printf 'on\n' > "$RH/jev-compaction"      # Replace the summary
rm -f "$RH/jev-compaction"                # Disable
```

PowerShell:

```powershell
$rh = if ($env:ROUTER_HOME) { $env:ROUTER_HOME } else { Join-Path $HOME '.codex/mixed-model-router' }
Set-Content "$rh/jev-compaction" shadow -Encoding ascii # Measure only
Set-Content "$rh/jev-compaction" on -Encoding ascii     # Replace the summary
Remove-Item "$rh/jev-compaction" -ErrorAction SilentlyContinue # Disable
```

One batch considers at most 16 complete pairs, largest outputs first. The
first item, latest user message and everything after it, newest six items,
prior compactions, discovery results, agent messages and system/developer
messages stay pinned. The rest stay verbatim. A pair is dropped only when the
judge says its facts are already covered (0.90 or above) *and* that knowing
the call happened no longer matters (below 0.90); covered evidence whose call
still matters keeps the call with a shortened output, and everything else
stays whole. This conservative experimental threshold needs
calibration from shadow data, not assumed safety: a previous trial scored a
plainly true fact at 0.69, so the scores are not a calibrated guarantee.

Wide windows keep their newest evidence and report how many older entries
were left out as `retained_omitted`; both questions tell the judge not to
infer coverage from that absence. When the facts
count as covered but the call still matters, the output keeps
its first 300 characters plus the number removed; the router never advises
re-running a tool, because it cannot know whether that tool is idempotent.
Ambiguous pairs, invalid or partial answers, decision failures,
a state that cannot fit the 32 KiB request budget, or retained text over 40%
of the selected model's compaction limit (its context window when the row sets
no limit) all use the existing summarizer.
The fast summarizer uses Xiaomi MiMo V2.6 Flash first, then DeepSeek V4.1 Flash
after an unsent timeout or incomplete output. History can therefore go to a
different vendor from the active model. A timeout after dispatch fails closed
to avoid duplicate side effects.
There are no decision retries, fallback models, per-turn calls or decision
cache. `compact_jev` logs only mode, counts, byte sizes, elapsed milliseconds
and a closed-set error code; never content, tool names or keys.

## Jev consumer: compaction evidence

`jev_compaction.py` owns `state(home)` and
`summary(model, key, items, defn, home=None, ask=None) -> str | None`.
The two summary assignments in `ExternalResponsesProvider.compact` and
`compact_trigger` use it before falling back to `self.summarize`. The
external-only `compaction_call` gate is unchanged: subscription threads and
ordinary turns never reach Jev. Dependencies flow providers -> consumer ->
decisions/compaction/tool_runs -> leaves. Upstream facts remain in `provider_defs`.

The case-sensitive `jev-compaction` home file is read per compaction, with
`ROUTER_HOME` respected. `shadow` evaluates but returns `None`; `on` returns
kept text. Other, absent, empty or unreadable values mean off. The original
items are never modified. `remember(items, summary)` and the V1 summary and
V2 `ocx1:` envelopes consume the returned string unchanged. There is no new
capsule, replay module or request-path dispatch branch. Commands and the
TypeSafe data-sharing and billing disclosure are in
[Experimental compaction](#experimental-compaction) above.

The consumer matches complete calls/results by `call_id`, rejects orphans or
ambiguous IDs, and selects at most 16 pairs by descending output size. It
never questions the first item, anything from the latest user message onward,
the newest six items, prior compactions, discovery outputs, agent messages
or developer/system messages. Pinning either member pins the whole pair;
unselected pairs stay verbatim.

One batch carries `{task, retained, candidates}`. Evidence uses
`compaction._item_text`, excluding opaque reasoning; candidate outputs carry
only `ok|error, N chars (omitted)`. Each item's text is capped at 2000, then
500, then 120 characters; if the body, including model and questions, still
exceeds 32 KiB, the newest 64 retained entries are kept at 500, then the
newest 32 at 120, then the newest 16 at 60, and the state records how many
older entries it left out. A real compaction carries hundreds of items, and
refusing those meant the feature never ran; thinning keeps the newest
evidence. It is not one-way safe: less evidence lowers the coverage score
(fewer pairs count as covered) and the "call still matters" score too, which
can turn a truncation into a drop. Both instructions therefore name
`retained_omitted` and forbid inferring coverage from absence. If even the
smallest step cannot fit, no partial state is sent.
Retained evidence never includes another candidate, so two candidates cannot
justify deleting each other. Candidate IDs are `p1..pn`; every instruction
names its backticked state path because Jev cannot see question IDs.

Two `noul` propositions ask whether the pair's task-relevant facts are
already covered by retained evidence, and whether knowing the call happened
still matters. These are probabilities of propositions, not importance scores.
The conservative experimental `THRESHOLD = 0.90` is applied directly to each
returned value, and both propositions are read positively: a pair drops only
when the facts count as covered *and* the call no longer matters; covered
evidence whose call still matters keeps the call with a shortened output; an
uncovered pair is kept verbatim. An earlier revision compared both values
below the threshold, which deleted exactly the pairs the judge had called
uncovered; the benchmark measured it and the polarity is now pinned by tests.
The first 300 output characters and the removed character count are kept, and
no re-run advice is added, since idempotency is not known here. Otherwise keep
both verbatim, in original order. The threshold needs
shadow calibration; the previous live trial's 0.69 on a plainly true fact
shows why the scores are not assumed production-quality calibration.

Any decision refusal, malformed/partial answer, invalid history, oversized
request or rendered text over 40% of the model row's context window returns
`None`. The byte ceiling uses `turn_budget.BYTES_PER_TOKEN`; an unknown window
also declines. The existing summarizer then runs unchanged. Logs contain only
mode, counts, byte sizes, elapsed time and a closed-set error code.

This is a one-shot T0 judgment with untrusted input, owned by the router
consumer; deterministic code validates the result before selecting text.
The paid-call budget is zero when off and at most one per eligible compaction,
using the decision client's five-second socket timeout. That timeout is not a
whole-run wall-clock guarantee. There are no retries, fallback models, decision
cache, model-selected tools or loops. Persistent writes, harmful-replay
coordination and broad-autonomy controls are not applicable to this consumer:
it returns text, without mutating history or executing tools. Reassess those
controls if it gains writes, retries, tools or per-turn authority.

`tests/test_jev_compaction.py` owns offline flag, selection, immutability,
failure, byte-budget and V1/V2 contracts. `tests/test_decisions.py` retains
wire validation, while packaging and import-graph tests enforce delivery and
dependency direction. Source implementation and offline acceptance do not
prove live calibration, deployment or release acceptance. No paid trial is
part of this change.
