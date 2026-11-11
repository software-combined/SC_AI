# Catalogue analysis: 2026-11-11

Public evidence was refreshed from Artificial Analysis (AA) and the OpenRouter
models API. The Router registry and installed mixed catalogue were inspected.
This covers 27 current external models and five distinct native legacy models.
GPT-6 Astra/Luna native routes share selection entries with their matching
external versions; GPT-6 Sol and GPT-6.1 Sol stay separate. Fable 5.2 is the
replacement in this source revision; the inspected installed catalogue still
had 5.1. No paid comparative model evaluation was run. Fable 5.2 separately
passed the Router's real-client checks at low effort; that does not qualify
its max-effort ranked performance or prove installed delivery.

## Prescribed effort and reference prices

USD per million input/output tokens from the
[OpenRouter public API](https://openrouter.ai/api/v1/models), retrieved 11 November.
Native legacy entries use their exact AA reference route where available.
Prices are advertised starting rates, independent of subscription billing.
They are not guaranteed invoices. JSON records cache prices and tier/schedule
overrides; search, image, audio and tool fees require the actual route quote.
The AA benchmark bill below uses AA prices and representative caching, which
can differ substantially from the cheapest OpenRouter endpoint.

| Model identifier | Prescribed effort | Input / output USD | Role and limitations |
| --- | --- | ---: | --- |
| `anthropic/claude-fable-5.2` | `max` | 8 / 40 | Premium reasoning ceiling; AA default-fallback harness, high cost and latency. No zero data retention on the public route. |
| `anthropic/claude-haiku-5.5` | `max` | 0.1 / 0.5 | Cheap draft/extraction candidate; long-context pricing increases from 100k input tokens. |
| `anthropic/claude-opus-5.5` | `max` | 4 / 20 | Premium deliverables and UI; no blanket need to pay for every task. |
| `anthropic/claude-sonnet-5.5` | `max` | 2 / 10 | Strongest Briefcase result in this set; separate from the general aggregate ranking. |
| `deepseek/deepseek-v4-pro-0813` | `max` | 0.111 / 4.44 | Exact 0813 snapshot; historical security evidence does not establish current security suitability. |
| `deepseek/deepseek-v4.1-flash-1017` | `max` | 0.006 / 0.5 | Cheap text/tool worker; 1017 scores do not belong to earlier Flash snapshots. |
| `google/gemini-3.1-pro-preview` | `high` | 2 / 12 | Legacy specialist; AA effort unspecified, excluded from prescribed-effort frontiers. |
| `google/gemini-3.8-flash` | `high` | 0.825 / 4.125 | Multimodal candidate; current route prices exceed the old snapshot. |
| `google/gemini-4-argon` | `high` | 2 / 10 | Strong automation candidate; Carbon is stronger on the current aggregate. |
| `google/gemini-4-carbon` | `high` | 2 / 10 | High reasoning/automation and terminal capability; Arena UI result is preliminary. |
| `meta/muse-ember` | `max` | 0.1 / 0.5 | Low-cost reasoning/tool candidate with much lower AA task latency than GLM Flash. |
| `meta/muse-spark-1.3-contributor` | `xhigh` | 0.1 / 0.2 | Training-use terms; no independent tier-specific score. Never inherit standard Muse scores. |
| `meta/muse-spark-1.3` | `max` | 1.25 / 4.25 | Synthesis candidate, not the universal value default; xhigh/max measurements stay separate. |
| `meta/muse-wonder` | `max` | 4 / 20 | Strong document candidate; distinct from Wonder Full, with higher reference prices than Spark. |
| `minimax/minimax-m3.1-flash` | `max` | 0.15 / 0.6 | Inexpensive automation candidate; schedule-dependent price overrides. |
| `moonshotai/kimi-k3.1-pro` | `max` | 2 / 10 | Strongest terminal result in this maintained set; slow. K3 cyber evidence does not transfer. |
| `openai/gpt-6-astra` | `max` | 10 / 50 | Focused hard reasoning; higher API price than Sol/Terra. Prefer matching subscription access when available. |
| `openai/gpt-6-luna` | `max` | 0.1 / 0.5 | Native lightweight option; weak terminal result relative to other cheap workers. |
| `openai/gpt-6.1-sol` | `max` | 2 / 10 | Strong general reasoning and UI candidate; max here does not alter installed reviewer settings. |
| `openai/gpt-6.1-terra` | `max` | 1 / 5 | Value coding/reasoning candidate; verify the actual native identifier before selecting a subscription route. |
| `qwen/qwen3.8-max-0902` | `xhigh` | 2 / 6 | AA undated identity is a proxy; Arena exact snapshot has unspecified effort. Excluded from both frontiers. |
| `x-ai/grok-4.7` | `xhigh` | 2 / 6 | Document/automation alternative; no inferred search permission or cyber result. |
| `stepfun/step-5-preview` | `high` | 1 / 2.7 | Preview specialist; AA effort unspecified. No default-role promotion from its general score. |
| `xiaomi/mimo-v2.6-flash` | `xhigh` | 0.14 / 0.28 | Cheap multimodal candidate; AA effort unspecified, excluded from prescribed-effort frontiers. |
| `xiaomi/mimo-v2.6-pro` | `xhigh` | 0.435 / 0.87 | Text/tool candidate; AA effort unspecified, excluded from prescribed-effort frontiers. |
| `z-ai/glm-5.3-flash` | `max` | 0.0399 / 0.0784 | Cheapest fixed-token scenario here; AA suite is slow and uses different prices. |
| `z-ai/glm-5.3` | `max` | 0.0699 / 1.4 | Targeted terminal escalation; text-only registry row, despite other families supporting images. |
| `gpt-6-sol` | `max` | 2 / 10 | Native older Sol; not GPT-6.1. Keep exact version evidence separate. |
| `gpt-5.6-terra` | `max` | 2 / 12 | Native older Terra; not GPT-6.1 Terra. |
| `gpt-5.5` | `xhigh` | 5 / 30 | Legacy compatibility/reproduction; current composite and cost/task absent. |
| `gpt-5.4-mini` | `xhigh` | 0.75 / 4.5 | Legacy lightweight option; weak measured terminal capability. |
| `gpt-5.3-codex-spark` | `xhigh` | Unverified / Unverified | Latency/compatibility candidate; no exact current independent score or price. |

The table lists comparison defaults; role-specific choices may use the
separately measured Sol high/xhigh and Terra high rows below. Never borrow
another effort's score. The calculator admits only the declared eligible
efforts. Muse Spark xhigh remains supporting evidence. Follow Claude
host-specific model/effort instructions when they apply. Installed review
routing and owner preferences remain separate and unchanged. Read
[roster model selection](roster.md) to select persistent owners and workers.

## Comparable workload evidence

[AA methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking)
is now Intelligence Index **v5.0.1**. All composite scores below use that
version. The old v4.3 numbers were replaced, not combined with these rows.
TB is Terminal-Bench 4.0, Auto is AutomationBench-AA, PDF is GDP.pdf
all-pass, BC is Briefcase v1.1 Elo. Percentages are multiplied by 100.
Dashes mean missing. Proxy/unknown-effort rows are retained but excluded
from prescribed-effort frontiers. AA cost/task is its suite bill, not
cost per accepted task. Time is the AA suite average in minutes.

| Model / measured effort | II | AA USD/task | Minutes/task | TB % | Auto % | PDF % | BC Elo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [claude-fable-5.2 / max](https://artificialanalysis.ai/models/claude-fable-5-2) | 64.56 | 26.54 | 45.16 | 59.60 | 76.42 | 24.20 | 1785.32 |
| [claude-haiku-5.5 / max](https://artificialanalysis.ai/models/claude-haiku-5-5) | 36.48 | 0.41 | 14.78 | 32.83 | 35.41 | 20.80 | 1572.67 |
| [claude-opus-5.5 / max](https://artificialanalysis.ai/models/claude-opus-5-5) | 59.11 | 10.04 | 25.03 | 59.60 | 69.54 | 26.20 | 1800.58 |
| [claude-sonnet-5.5 / max](https://artificialanalysis.ai/models/claude-sonnet-5-5) | 54.54 | 10.02 | 32.72 | 63.64 | 71.77 | 25.80 | 1816.46 |
| [deepseek-v4-pro-0813 / max](https://artificialanalysis.ai/models/deepseek-v4-pro) | 23.06 | 1.77 | 23.33 | 14.14 | 56.71 | 11.40 | 1253.16 |
| [deepseek-v4.1-flash-1017 / max](https://artificialanalysis.ai/models/deepseek-v4-1-flash-1017) | 32.59 | 0.60 | 16.53 | 33.84 | 66.64 | 17.20 | 1570.42 |
| [gemini-3.1-pro-preview / unknown](https://artificialanalysis.ai/models/gemini-3-1-pro-preview) | — | — | — | 4.04 | 35.43 | 17.80 | 456.99 |
| [gemini-3.8-flash / high](https://artificialanalysis.ai/models/gemini-3-8-flash) | 30.85 | 7.77 | 14.38 | 19.70 | 59.93 | 21.00 | 1202.99 |
| [gemini-4-argon / high](https://artificialanalysis.ai/models/gemini-4-argon) | 50.41 | 9.95 | 29.02 | 57.07 | 77.51 | 21.80 | 1484.37 |
| [gemini-4-carbon / high](https://artificialanalysis.ai/models/gemini-4-carbon) | 60.03 | 7.76 | 25.55 | 65.15 | 77.82 | 28.40 | 1610.63 |
| [muse-ember / max](https://artificialanalysis.ai/models/muse-ember) | 36.02 | 0.14 | 3.10 | 40.91 | 68.08 | 22.80 | 1520.92 |
| muse-spark-1.3-contributor / xhigh | — | — | — | — | — | — | — |
| [muse-spark-1.3 / max](https://artificialanalysis.ai/models/muse-spark-1-3) | 36.62 | 2.39 | 11.98 | 33.33 | 57.85 | 26.60 | 1581.34 |
| [muse-spark-1.3 / xhigh](https://artificialanalysis.ai/models/muse-spark-1-3-xhigh) | — | — | — | 16.67 | 56.84 | 24.20 | 1481.26 |
| [muse-wonder / max](https://artificialanalysis.ai/models/muse-wonder) | 43.57 | 6.95 | 13.21 | 52.02 | 68.09 | 30.60 | 1658.65 |
| [minimax-m3.1-flash / max](https://artificialanalysis.ai/models/minimax-m3-1-flash) | 29.06 | 0.49 | 14.43 | 25.76 | 72.52 | 20.80 | 1474.33 |
| [kimi-k3.1-pro / max](https://artificialanalysis.ai/models/kimi-k3-1-pro) | 46.45 | 3.68 | 37.19 | 67.17 | 73.30 | 31.40 | 1674.14 |
| [gpt-6-astra / max](https://artificialanalysis.ai/models/gpt-6-astra) | 56.85 | 6.24 | 22.89 | 59.09 | 68.49 | 31.00 | 1568.92 |
| [gpt-6-luna / max](https://artificialanalysis.ai/models/gpt-6-luna) | 27.86 | 0.15 | 11.53 | 12.63 | 53.17 | 22.80 | 1337.11 |
| [gpt-6.1-sol / max](https://artificialanalysis.ai/models/gpt-6-1-sol) | 54.61 | 1.27 | 20.18 | 56.06 | 64.87 | 31.00 | 1554.66 |
| [gpt-6.1-terra / max](https://artificialanalysis.ai/models/gpt-6-1-terra) | 51.33 | 0.96 | 13.49 | 55.56 | 60.17 | 28.60 | 1402.61 |
| [PROXY qwen3.8-max-0902 / xhigh](https://artificialanalysis.ai/models/qwen3-8-max) | 33.65 | 10.02 | 54.84 | 38.89 | 56.19 | 22.80 | 1604.55 |
| [grok-4.7 / xhigh](https://artificialanalysis.ai/models/grok-4-7) | 35.49 | 7.77 | 27.44 | 25.76 | 65.56 | 20.00 | 1635.58 |
| [step-5-preview / unknown](https://artificialanalysis.ai/models/step-5) | 28.53 | 2.35 | 12.96 | 33.33 | 50.96 | 14.80 | 1423.01 |
| [mimo-v2.6-flash / unknown](https://artificialanalysis.ai/models/mimo-v2-6-flash) | 26.73 | 0.13 | 64.53 | 22.73 | 64.05 | 9.00 | 1486.83 |
| [mimo-v2.6-pro / unknown](https://artificialanalysis.ai/models/mimo-v2-6-pro) | 29.89 | 0.26 | 35.91 | 34.85 | 58.62 | 19.20 | 1511.68 |
| [glm-5.3-flash / max](https://artificialanalysis.ai/models/glm-5-3-flash) | 27.80 | 0.58 | 45.79 | 32.83 | 60.37 | 15.40 | 1449.84 |
| [glm-5.3 / max](https://artificialanalysis.ai/models/glm-5-3) | 31.65 | 5.01 | 28.55 | 41.92 | 62.20 | 11.20 | 1502.84 |
| [gpt-6-sol / max](https://artificialanalysis.ai/models/gpt-6-sol) | 44.16 | 2.47 | 7.42 | 43.94 | 61.63 | 25.20 | 1476.46 |
| [gpt-5.6-terra / max](https://artificialanalysis.ai/models/gpt-5-6-terra) | 32.34 | 3.73 | 10.91 | 35.35 | 59.65 | 24.00 | 1333.13 |
| [gpt-5.5 / xhigh](https://artificialanalysis.ai/models/gpt-5-5) | — | — | — | 14.65 | 47.30 | 21.20 | 1135.35 |
| [gpt-5.4-mini / xhigh](https://artificialanalysis.ai/models/gpt-5-4-mini) | — | — | — | 2.02 | 26.20 | 13.40 | 719.91 |
| gpt-5.3-codex-spark / xhigh | — | — | — | — | — | — | — |
| [gpt-6.1-sol / high](https://artificialanalysis.ai/models/gpt-6-1-sol-high) | 50.33 | 0.59 | 6.65 | 51.52 | 64.50 | 32.00 | 1468.52 |
| [gpt-6.1-sol / xhigh](https://artificialanalysis.ai/models/gpt-6-1-sol-xhigh) | 52.46 | 0.76 | 9.05 | 54.04 | 66.57 | 31.80 | 1503.18 |
| [gpt-6.1-terra / high](https://artificialanalysis.ai/models/gpt-6-1-terra-high) | 42.43 | 0.26 | 3.97 | 41.92 | 58.46 | 28.00 | 1263.74 |

JSON also retains Briefcase confidence intervals, FrontierCode-AA 2.0,
MMMU-Pro, GDPval-AA v2.1, SciCode and legacy AA-LCR v1.1. The last three
are supporting measures, not components of the current index. Anthropic
AA rows use the labelled default-fallback harness; do not treat them as
isolated-weight attestation. Kimi's embedded row identifies max even
where the rendered model title omits an effort suffix.

## What changes selection

The eligible AA aggregate cost frontier includes Ember max, Terra 6.1 high,
Sol 6.1 high/xhigh/max, Astra max, Carbon high and Fable 5.2 max.
Ember is 36.02 at USD 0.14/task;
Terra is 51.33 at USD 0.96 and Sol is 54.61 at USD 1.27. Fable is the
quality ceiling at 64.56, but USD 26.54/task and about 45 minutes.
These are public priors, not local success rates or a spending allowance.

For terminal work, Kimi K3.1 Pro reaches 67.17%, Carbon 65.15%,
Sonnet 5.5 63.64%, and Terra/Sol about 56%. For professional deliverables,
Sonnet leads this maintained set at 1816.46 Briefcase Elo. An aggregate
rank cannot replace these task-specific signals. Fixed-token frontiers
are price sensitivity calculations, not measured workload invoices.

[Arena WebDev](https://arena.ai/leaderboard/code/webdev), published
10 November and retrieved 11 November, supports Opus 5.5 max, Carbon
high, Sol/Terra max and DeepSeek Flash 1017 max as UI candidates. The
JSON retains selected exact rows, votes, confidence intervals and
preliminary flags. Fable 5.2 is measured at xhigh, so its 1836 score
does not qualify the prescribed max configuration. Qwen 0902 and GLM
Flash have unspecified Arena effort and stay outside that frontier.

Current security suitability was not refreshed by this general benchmark
pass. Read [security selection](cybersecurity.md); historical cyber results
do not transfer to successor versions. Contributor remains separately
qualified, with training-use terms. Wonder Full is not standard Wonder.
Automatic routers and hidden/system rows are excluded from fixed-model
selection. Verify actual tools, context, privacy terms, permitted effort
and callable identity before dispatch. See [refresh methodology](refresh.md).
