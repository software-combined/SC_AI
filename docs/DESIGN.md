# Design rules

The router has no request cap (`tools/check_policy_scans.py` keeps one from
returning); request size limits still apply. Compaction runs through a billable
summariser call. The catalogue is a generated snapshot from the registry, and
live model metadata refreshes weekly into the registry. Model rows are data;
new behaviour is always code.

The picker lists every subscription row with its OpenRouter twin beside it.
An exhausted subscription row answers with the refusal message instead of
moving to its twin, because the picker reloads only when the client starts and
a moved row would show an OpenRouter-billed model under the subscription name.
