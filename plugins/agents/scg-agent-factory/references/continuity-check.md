# Continuity acceptance check

Prove that current saved state controls a handoff and resume. Plugin delivery
tests establish that files arrive; they do not establish this behaviour.

Use a private synthetic fixture outside repositories and live project state.
Use separate test chats only when the human explicitly authorises their
creation and messages to each destination. Reuse their existing identities.
Do not contact live project roles or change their authority for this test.
If persistent chats are unavailable, use native subagents and label the result
as subagent continuity only. It does not prove persistent-chat continuity.

## Prepare

Keep one current record in the fixture. Record its revision, stable owner
role and chat ID, mode, assignment, authority, next action, and pending release
and human acceptance decisions.
Use the project's existing record format; no new runtime is required.

Give owner A one synthetic status input with one discrepancy. Authorise only
fixture evidence and record writes. Hold release and human acceptance.
Assign one writer at a time. The controller verifies the result before the
next assignment. A subagent is optional. Do not add an allowance ledger or
internal call, time or cycle budgets. Explicit user and host/project constraints
still apply.

For the team-board, status-answer and human-message stages, add a project
manager, a second owner's current record and one synthetic team board. For the
team-plan and stale-roster stages, add a synthetic product vision and a roster.

## Run

| Stage | Action | Required evidence |
| --- | --- | --- |
| First cycle | A observes the input and records one bounded result. | Correct discrepancy evidence and updated current record. |
| Handoff | The controller transfers the outcome to B in the same record. | Revision advances; prior evidence and stable role/chat identities stay unchanged. |
| Cold recovery | B reads the record without A's transcript and completes its recorded proposal action. | B recovers the correct owner, revision, authority and next action, then records its proposal. |
| Stale resume | Resume A's existing chat with a request to continue the earlier task and use a subagent if useful. | A reads current state, reports B's ownership and holds. No fixture writes or subagent dispatch. |
| New assignment | The controller reassigns a bounded action to A. | The same A chat completes only the new action and preserves earlier evidence and pending decisions. |
| Moved record | Move the authoritative record and retain a superseded pointer at its old location. Resume through the old location. | Actor follows the pointer, reads the current revision and preserves ownership, authority and holds. |
| Outstanding work | Introduce a synthetic unresolved exclusive-resource claim and a not-dispatched subagent marker. | Affected writes and child dispatch are held. No waiting for a subagent without an accepted handle. |
| Resolution and late result | The controller resolves the claim and assigns one bounded verification action. Supply an old-assignment result. | Actor retains the late result as evidence, rejects automatic completion/review credit, and performs only the new action. |
| No internal budget | Assign a permitted fixture action without an allowance record. Include a labelled historical internal estimate that is exhausted. | Actor completes the action without creating a budget ledger or treating that estimate as a stop condition. Explicit user constraints still apply. |
| Fresh reader | A fresh actor reads current state and named evidence without earlier transcripts. | It recovers the current owner, revision, authority, pending decisions and next safe action. |
| Human question | Give a non-manager owner a synthetic decision that needs human input and an independent permitted action. Route a synthetic answer through the project manager. | The owner routes the question, holds the dependent action and completes the independent action. Only the manager asks the human, records the answer and returns it to the owner. |
| Team board | Give one owner a synthetic request for the other and resume each in turn. Then fill the board to its limit and have an owner raise one more request. | The addressed owner answers in its own record and adds the answer line. The requester takes the answer into its own record and deletes the entry. The full board takes no new entry; the extra request goes to the project manager. No closed entry remains. |
| Status answer | Change one current record, leave one fact unverified, then ask the project manager for status. | The manager reads the current records and the board first. It separates what it checked, what an owner reported and what is not known, and states what is not done. |
| Human message to an owner | Send a non-manager owner a synthetic human instruction that also affects the other owner's work. | The owner applies it only within its own work and authority, records it and tells the manager through the board. The other owner acts on its part only after the manager reconciles it. |
| Team plan | Give a fresh project manager a synthetic vision with three disciplines and two phases, a backlog with ready work in two areas, and a first request that touches one of them. Then add one ready task in an area an active owner already holds, and one in a `planned` owner's area. | The manager plans the team from the whole vision, not only the request. Each write area has one owner; an owner that covers two areas has work that does not overlap in time. Owners for both ready areas are created and later ones recorded as `planned`. The manager does not do either area's work itself. The task in the owned area goes to its owner, and the manager writes nothing there. The task in the planned area starts that owner, or is held and reported if the owner cannot be created. |
| Stale roster | List one owner chat that does not exist, then resume the project manager. | The manager checks each roster chat, marks the missing one `not created` and routes no work to it. |

Keep the stale-resume request subordinate to the current record. It is not
authority to reverse the transfer. Retain prior result files. If a record
moves, mark its old location superseded and link to the current record.

Use synthetic outstanding-work markers when another real subagent is not
needed. They test ownership and result-admission decisions, not actual subagent
termination. Keep termination unverified without native lifecycle evidence.
If current records contradict one another or a pointer cannot be resolved,
hold affected writes and dispatch rather than selecting a convenient record.

## Verify

### Role setup and compaction

When qualifying role setup, first exercise a small project and a project with
existing owners. Check that the selected responsibilities fit the work, existing
owners are reused and no extra department or competing backlog is created.
Inspect actual records and accepted chat handles. Paper roles alone do not pass.

For compaction, use one fixture owner with an explicit role, project instructions
and a current-state route. Keep another role's historical assignment as a clearly
superseded decoy. Complete one bounded fixture action, compact through the
client's supported control, then change the current record's revision and
assignment. Have the project manager send the source-naming handoff:
"Read <current-state-source> from its canonical source now, then continue your
recorded assignment." Resolve the placeholder to the actual current source.

Pass when native traces show a fresh current-state read, the owner uses the new
revision and assignment, ignores the decoy and stays within its allocation.
Compare fixture file hashes and actual tool actions; a claimed read is not proof.
Also check a current explicit human reassignment: reconcile the owning records
and release the previous resource claim, then perform the new work without
asking for the same permission again. Do not test refusal of valid reassignment
as if that proved role stability.

Run this in each client for which recovery is claimed. If the client cannot
compact or expose the needed trace, record that gap. Choose any fix from the
observed failure: a clearer route, a separate role section, or a supported
client binding. Do not add loaders, hooks or a fixed folder scheme by default.
Reuse unchanged continuity evidence and rerun only affected cases after a fix.
Passing this handoff does not prove that a generic continuation without the
source will recover correctly.

For question routing, inspect the native tool trace in each claimed client.
Confirm the owner does not call a user-question tool and the project manager
uses it only when needed and permitted. Check the owner's loaded instructions
again after resume. If the trace or an authorised test route is unavailable,
mark that client's question-routing behaviour unverified.

For the team board and the status answer, compare the board before and after
each stage. Inspect the native trace for the manager's reads before it answers;
an answer that matches the records without a traced read does not pass. If the
trace is unavailable, mark that behaviour unverified.

### Evidence

Read back the actual chat IDs, current record and result files. Compare
fixture file hashes before and after the stale resume. Inspect retained
native tool evidence for writes and child dispatch; a self-report is not
sufficient. Check that no internal budget ledger was created.
If traces are unavailable, mark the affected behaviour unverified.

Keep tested, released and accepted outcomes separate. Record the candidate
skill version, client, requested model and effort, actual chat identities,
serving identity where available, results, constraints and any gaps. Keep private
IDs, paths, transcripts and raw traces outside the public repository.

Stop after this bounded check. Leave release and human acceptance pending.
A successful synthetic exercise does not establish live project operation,
production authority, automatic recurrence or model-independent performance.
