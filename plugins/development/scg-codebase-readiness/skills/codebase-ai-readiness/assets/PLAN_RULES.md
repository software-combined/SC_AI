# Plan rules

Every plan in this repository follows these rules, so anyone can see what is planned, under way or finished.

## Where plans live

- One plan per change, at `plans/<domain>/<subdomain>/<NNN>-<short-name>.md`. Use the same domain and subdomain names as the code.
- A plan that spans domains lives under the domain that owns most of the work and links to the others. A repository-wide change lives under `plans/repository/<topic>/`.
- `plans/README.md` lists every plan with its status, grouped by domain. Update it in the same pull request as the plan.
- Only plans live in `plans/`. Notes, evidence and task logs have their own folders.

## Template

```markdown
# <What changes, in plain words>

Status: Proposed
Owner: <person or team>
Updated: <YYYY-MM-DD>

## Why
One or two sentences: the problem and who it affects.

## What changes
- The parts that change, and what stays the same.

## Steps
- [ ] First step.
- [ ] Next step.

## Done when
- The checks that prove the plan is finished.

## Links
- Related plans, pull requests and evidence.
```

## Status

- **Proposed:** agreed to consider, not started.
- **In progress:** work has started. Tick each step as it lands.
- **Done:** every "Done when" check passed. Keep the file: it records the decision.
- **Dropped:** not going ahead. Add one line that says why.

Change the status, and the index, in the same pull request as the work.

## Size

A plan is 200 lines or fewer. Split a bigger change into several plans that link to each other.
